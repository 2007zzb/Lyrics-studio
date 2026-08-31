"""歌词文本解析引擎。

核心能力：丢进来一段 txt / lrc 歌词，自动扫描并识别
"作词 / 作曲 / 编曲" 是谁，然后按模板重新排版：

    作词：xxx
    作曲：xxx
    编曲：xxx
    <歌词正文>

设计要点
--------
1. 别名覆盖中文常见写法（作词、作詞、填词、词、Lyricist…）。
2. 支持"一行多字段"： 作词：A  作曲：B  编曲：C
3. 支持"合并键"：     作词/作曲：周杰伦、作词、作曲 编曲：周杰伦
4. 支持 LRC 标签：    [ti:xxx] [ar:xxx] [al:xxx]
5. 只认"行首附近"的字段，避免把歌词正文里出现的句子误判成元数据。
6. 值过长（>40 字）时判定为歌词而非人名，宁可漏也不错填。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .model import (
    LyricSheet, LABELS, CORE_FIELDS,
    ALIASES, SHORT_ALIASES, EXTRA_ALIASES, MERGED_ALIASES,
    KEY_TO_FIELD, MERGED_KEY_MAP,
)

# ---------------------------------------------------------------- 别名表

MAX_VALUE_LEN = 40          # 超过这个长度的值不当作人名
MAX_LEADING_WS = 8          # 键前面最多允许多少个缩进空格
MAX_LEADING_DECO = 3        # 键前面最多允许多少个装饰字符（【、*、- 等）
STRIP_CHARS = " \t*#-·。．-—【】[]《》「」『』()（）"


# 长别名优先，避免 "作词" 被 "词" 抢先匹配
_ALL_KEYS: List[str] = sorted(KEY_TO_FIELD.keys(), key=len, reverse=True)
# 合并键（词曲 等）也要参与匹配，且要排在最前面
_MERGED_KEYS: List[str] = sorted(MERGED_KEY_MAP.keys(), key=len, reverse=True)
_KEY_RE = "|".join(re.escape(k) for k in _MERGED_KEYS + _ALL_KEYS)
# 分隔符：冒号（中英文全半角）、空格、或括号
# 右括号组支持【作词】方文山、[作词]方文山；
# 左括号组支持 演唱（周杰伦）这种写法
_SEP_RE = r"[:：=＝]|[ \t]+|[（(\[【]|[】〕》〉」』\]】]"
_JOIN_RE = r"(?:\s*(?:/|、|，|,|&|和|与|\+|及)\s*)"

# 一个"键组"：可以是一个别名，也可以是若干个用 /、& 连起来的别名
GROUP_RE = re.compile(
    rf"(?P<key>(?:{_KEY_RE})(?:{_JOIN_RE}(?:{_KEY_RE}))*)\s*(?:{_SEP_RE})\s*",
    re.IGNORECASE,
)

LRC_META_RE = re.compile(r"^\s*\[(?P<tag>[A-Za-z]+)\s*[:：]\s*(?P<value>.*?)\]\s*$")
LRC_TIME_RE = re.compile(r"[\[<]\s*\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\s*[\]>]")

LRC_TAG_MAP: Dict[str, str] = {
    "ti": "title", "ar": "artist", "al": "album",
    "by": "LRC制作", "re": "__skip__", "ve": "__skip__",
    "offset": "__skip__", "kana": "__skip__",
}

# LRC 首行常见的"标题行"，例如：
#   LOSER - BIGBANG (빅뱅)          → 歌名=LOSER，演唱=BIGBANG
#   晴天 - 周杰伦 (Jay Chou)        → 歌名=晴天，演唱=周杰伦
# 只在文件里没有 [ti:]/[ar:] 标签时启用，作为兜底。
# 判断依据：破折号后面那段**带括号原文名**（韩文/日文/英文），
# 括号原文名几乎只出现在演唱者身上，歌名很少这么写。
TITLE_LINE_RE = re.compile(
    r"^(?P<title>[^\-–—]+?)\s*[-–—]\s*"
    r"(?P<artist>[^（(]+?)\s*[（(]\s*(?P<native>[^）)]+?)\s*[）)]\s*$"
)

# 没有括号原文名的写法：晴天 - 周杰伦
TITLE_LINE_PLAIN_RE = re.compile(
    r"^(?P<title>[^\-–—]+?)\s*[-–—]\s*(?P<artist>[^\-–—]+?)\s*$"
)

MAX_TITLE_LEN = 40

# 文件名/标题行里要去掉的杂音
_NOISE_RE = re.compile(
    r"^\s*(?:\[(?:\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?)\]\s*)+"   # 行首时间轴
)


def _split_title_artist(text: str) -> Tuple[str, str, str]:
    """从"歌名 - 演唱（原名）"里拆出三段，拆不出来返回空串。

    返回 (歌名, 演唱, 原名)，原名可能为空。
    """
    line = LRC_TIME_RE.sub("", text or "").strip()
    if not line or LRC_META_RE.match(line):
        return "", "", ""

    m = TITLE_LINE_RE.match(line)          # 带括号原文名，最可靠
    if m:
        return (m.group("title").strip(),
                m.group("artist").strip(),
                m.group("native").strip())

    m = TITLE_LINE_PLAIN_RE.match(line)    # 没有括号，退一步
    if m:
        return m.group("title").strip(), m.group("artist").strip(), ""
    return "", "", ""


def _valid_title_parts(title: str, artist: str) -> bool:
    """判断拆出来的歌名/演唱是否可信。"""
    if not title or not artist:
        return False
    if len(title) > MAX_TITLE_LEN or len(artist) > MAX_TITLE_LEN:
        return False
    # 标题里不该有冒号（那是"作词：xxx"这类信息行）
    if "：" in title or ":" in title:
        return False
    # 结尾是句号/逗号之类的，多半是歌词不是标题
    if title.rstrip()[-1:] in "。，、！？!?,.":
        return False
    return True


def _fill_title_artist(sheet: LyricSheet, matched: List[Tuple[str, str]],
                       title: str, artist: str, native: str = "") -> bool:
    """把歌名/演唱填进**空着**的字段，返回是否填了。"""
    filled = False
    if not (sheet.title or "").strip() and title:
        sheet.title = title
        matched.append(("歌名", title))
        filled = True
    if not (sheet.artist or "").strip() and artist:
        sheet.artist = artist
        matched.append(("演唱", artist))
        filled = True
    if filled and native and "原名" not in sheet.extras:
        sheet.extras["原名"] = native
    return filled


def _infer_from_title_line(lines: List[str], sheet: LyricSheet,
                           matched: List[Tuple[str, str]]) -> None:
    """从 LRC 首行的"歌名 - 演唱（原名）"里补出歌名和演唱。

    只填**空着**的字段，不覆盖已有的（[ti:] 标签优先）。
    认不出来就什么都不做 —— 宁可空着也不错填。
    """
    if (sheet.title or "").strip() and (sheet.artist or "").strip():
        return

    # 只看前 3 行，标题行一般在最前面
    for raw in lines[:3]:
        title, artist, native = _split_title_artist(raw)
        if not _valid_title_parts(title, artist):
            continue
        if _fill_title_artist(sheet, matched, title, artist, native):
            return


def _infer_from_filename(filename: str, sheet: LyricSheet,
                         matched: List[Tuple[str, str]]) -> None:
    """最后的兜底：从文件名里拆歌名和演唱。

    用户的文件基本都叫 "晴天 - 周杰伦.lrc" 这种格式，
    文件里找不到信息时，文件名是最可靠的线索。
    """
    if (sheet.title or "").strip() and (sheet.artist or "").strip():
        return

    name = (filename or "").strip()
    if not name:
        return

    # 去掉路径和扩展名
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"\.(lrc|txt|md|csv)$", "", name, flags=re.IGNORECASE)
    # 去掉常见的杂音标记
    name = re.sub(r"[\[【（(]?(?:歌词|完整版|修正|精校)[】\]）)]?", "", name)
    name = _NOISE_RE.sub("", name).strip()
    if not name:
        return

    title, artist, native = _split_title_artist(name)
    if not _valid_title_parts(title, artist):
        return
    _fill_title_artist(sheet, matched, title, artist, native)


# ---------------------------------------------------------------- 结果

@dataclass
class ParseResult:
    sheet: LyricSheet
    matched: List[Tuple[str, str]] = field(default_factory=list)  # [(显示名, 值)]
    meta_lines: int = 0       # 被识别为元数据的行数
    lrc_lines: int = 0        # LRC 标签行数
    time_tags: int = 0        # 被剥离的时间轴个数
    source: str = ""
    total_lines: int = 0      # 原文里的非空行总数

    @property
    def matched_count(self) -> int:
        return len(self.matched)

    @property
    def body_lines(self) -> int:
        return len([ln for ln in self.sheet.body.splitlines() if ln.strip()])

    def summary(self) -> str:
        """给用户的导入结果摘要。"""
        parts = []

        if self.matched:
            items = "、".join(f"{k}={v}" for k, v in self.matched[:6])
            more = " 等" if self.matched_count > 6 else ""
            parts.append(f"识别到 {self.matched_count} 项：{items}{more}")
        else:
            parts.append("没有识别到任何信息，请在下面手动填写")

        # 三项核心信息一个都没有时，明确告诉用户原因
        if not any(getattr(self.sheet, f, "").strip() for f in CORE_FIELDS):
            parts.append("这个文件里没有作词/作曲/编曲，请手动填写前三行")

        extras = []
        if self.lrc_lines:
            extras.append(f"LRC 标签 {self.lrc_lines} 行")
        if self.time_tags:
            extras.append(f"去掉时间轴 {self.time_tags} 处")
        if extras:
            parts.append("，".join(extras))

        if self.body_lines == 0:
            parts.append("注意：文件是空的，没有读到任何内容")
        else:
            parts.append(f"正文 {self.body_lines} 行")

        return "；".join(parts)


# ---------------------------------------------------------------- 解析

def _split_key_group(key_text: str) -> List[str]:
    """把一个"键"拆成它可能对应的若干字段名。

    "作词/作曲" -> ["lyricist", "composer"]
    "词曲"      -> ["lyricist", "composer"]   （合并键）
    "作词"      -> ["lyricist"]
    """
    whole = key_text.strip().lower()
    if whole in MERGED_KEY_MAP:
        return list(MERGED_KEY_MAP[whole])

    fields: List[str] = []
    for part in re.split(_JOIN_RE, key_text):
        token = part.strip().lower()
        if token in MERGED_KEY_MAP:
            for fld in MERGED_KEY_MAP[token]:
                if fld not in fields:
                    fields.append(fld)
            continue
        fld = KEY_TO_FIELD.get(token)
        if fld and fld not in fields:
            fields.append(fld)
    return fields


_WRAPPED_RE = re.compile(r"^[（(]\s*(.*?)\s*[）)]$", re.DOTALL)


def _clean_value(value: str) -> str:
    value = value.strip()
    value = value.strip("，,、;；|/")
    # 整体被一对括号包住时去掉外层括号：
    # "演唱（周杰伦）" 里的值取出来是 "（周杰伦）"，留下括号反而不好看
    m = _WRAPPED_RE.match(value)
    if m and m.group(1).strip():
        value = m.group(1).strip()
    # 左括号被当分隔符吃掉时，末尾会剩一个右括号（"周杰伦）"）。
    # 只在值里没有配对的左括号时才剥，避免把 "BIGBANG (빅뱅)" 削坏。
    elif value.endswith(("）", ")")) and "（" not in value and "(" not in value:
        value = value[:-1].strip()
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip()


def _apply_match(
    stripped: str,
    sheet: LyricSheet,
    overwrite: bool,
    matched: List[Tuple[str, str]],
    core_only: bool = False,
) -> bool:
    """尝试从一行里抽信息，抽到了就写进 sheet，返回是否成功。

    core_only=True 时只补 作词/作曲/编曲 三项（宽松模式用）。
    """
    matches = list(GROUP_RE.finditer(stripped))
    if not matches:
        return False

    applied = False
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(stripped)
        value = _clean_value(stripped[match.end():end])
        if not value or len(value) > MAX_VALUE_LEN:
            continue
        for fld in _split_key_group(match.group("key")):
            if core_only and fld not in CORE_FIELDS:
                continue
            if fld in LABELS:
                if overwrite or not sheet.get(fld).strip():
                    sheet.set(fld, value)
                    matched.append((LABELS[fld], value))
                    applied = True
            else:
                if overwrite or not sheet.extras.get(fld, "").strip():
                    sheet.extras[fld] = value
                    matched.append((fld, value))
                    applied = True
    return applied


def _relaxed_scan(lines: List[str], sheet: LyricSheet,
                  matched: List[Tuple[str, str]], overwrite: bool) -> List[str]:
    """宽松补扫：键可以出现在行中间（前面有别的内容）。

    只在三项核心信息一个都没认出来时才调用，且只补
    作词 / 作曲 / 编曲。例如：

        爱的飞行日记 作词：方文山      →  作词=方文山

    命中成功的行会从正文里移除，避免信息重复。
    """
    if any(sheet.get(f).strip() for f in CORE_FIELDS):
        return lines

    safe_keys = [
        k for k in _ALL_KEYS
        if len(k) >= 2 and KEY_TO_FIELD.get(k) in CORE_FIELDS
    ]
    if not safe_keys:
        return lines
    pattern = re.compile(
        r"(?:^|[\s，,、;；|/（(])(?P<key>" + "|".join(re.escape(k) for k in safe_keys) +
        r")\s*[:：]\s*(?P<value>[^\s，,、;；|]{1," + str(MAX_VALUE_LEN) + r"})\s*$"
    )

    rest: List[str] = []
    for line in lines:
        m = pattern.search(line or "")
        if not m:
            rest.append(line)
            continue
        value = _clean_value(m.group("value"))
        if not value:
            rest.append(line)
            continue
        fld = KEY_TO_FIELD[m.group("key").lower()]
        if overwrite or not sheet.get(fld).strip():
            sheet.set(fld, value)
            matched.append((LABELS[fld], value))
            continue          # 抽走了就不再留在正文里
        rest.append(line)
    return rest


def parse_lyrics(
    text: str,
    strip_timestamps: bool = True,
    overwrite: bool = False,
    base: LyricSheet | None = None,
    filename: str = "",
) -> ParseResult:
    """解析一段歌词文本，返回填充好的 LyricSheet 与识别报告。

    filename 是可选的兜底线索：文件里实在找不到歌名 / 演唱时，
    会尝试从文件名里拆（"晴天 - 周杰伦.lrc" → 歌名=晴天，演唱=周杰伦）。
    """
    sheet = base or LyricSheet()
    matched: List[Tuple[str, str]] = []
    meta_lines = 0
    lrc_lines = 0
    time_tags = 0

    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw_nonempty: List[str] = [ln.rstrip() for ln in normalized.split("\n") if ln.strip()]

    body_lines: List[str] = []
    blank_streak = 0

    for raw_line in normalized.split("\n"):
        # ---- 1. 空行：压缩连续空行，最多保留 1 行
        if not raw_line.strip():
            blank_streak += 1
            if blank_streak == 1 and body_lines:
                body_lines.append("")
            continue
        blank_streak = 0

        # ---- 2. LRC 元数据标签
        lrc_match = LRC_META_RE.match(raw_line)
        if lrc_match:
            lrc_lines += 1
            tag = lrc_match.group("tag").lower()
            value = _clean_value(lrc_match.group("value"))
            target = LRC_TAG_MAP.get(tag)
            if target and target != "__skip__" and value:
                if target in LABELS:
                    if overwrite or not sheet.get(target).strip():
                        sheet.set(target, value)
                        matched.append((LABELS[target], value))
                else:
                    sheet.extras.setdefault(target, value)
                    matched.append((target, value))
            continue

        # ---- 3. 去掉时间轴
        line = raw_line
        if strip_timestamps:
            line, hits = LRC_TIME_RE.subn("", line)
            time_tags += hits
        line = line.rstrip()
        if not line.strip():
            continue

        # ---- 4. 看这一行是不是信息行
        #      先量缩进空格，再量装饰字符（【、*、- 之类）。
        #      缩进多少都行，装饰符最多 3 个，避免误伤歌词。
        core = line.strip()
        leading_ws = len(line) - len(line.lstrip(" \t"))
        stripped = core.lstrip(STRIP_CHARS)
        deco = len(core) - len(stripped)

        if leading_ws <= MAX_LEADING_WS and deco <= MAX_LEADING_DECO and stripped:
            if _apply_match(stripped, sheet, overwrite, matched):
                meta_lines += 1
                continue

        body_lines.append(line)

    # ---- 5. 收尾：去掉正文首尾空行
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    # ---- 6. 宽松补扫：一行都没认出来时再试一次
    body_lines = _relaxed_scan(body_lines, sheet, matched, overwrite)

    # ---- 6.5 兜底：补出歌名和演唱
    #      很多 LRC 既没有 [ti:]/[ar:] 标签，第一行也不是规范标题，
    #      这时先看首行的「歌名 - 演唱」，再看文件名。
    _infer_from_title_line(raw_nonempty, sheet, matched)
    _infer_from_filename(filename, sheet, matched)

    # ---- 7. 正文 = 去掉时间轴后的全文 ----
    # 导入就是"打开文件"：扫描只负责把作词/作曲/编曲填到上面的输入框，
    # 不负责删东西。所以正文区保留文件的全部内容（只剥掉 [00:12.34]
    # 时间轴和 [ti:] 这类标签行），用户想删什么自己在编辑区里删。
    # 这样无论遇到多奇怪的格式，歌词都不可能凭空消失。
    full_body: List[str] = []
    blank = 0
    for ln in normalized.split("\n"):
        if not ln.strip():
            blank += 1
            if blank == 1 and full_body:      # 段落之间最多保留一个空行
                full_body.append("")
            continue
        blank = 0
        if LRC_META_RE.match(ln):             # [ti:][ar:][al:] 不是歌词，跳过
            continue
        cleaned = LRC_TIME_RE.sub("", ln).strip() if strip_timestamps else ln.strip()
        if cleaned:
            full_body.append(cleaned)

    while full_body and not full_body[0].strip():
        full_body.pop(0)
    while full_body and not full_body[-1].strip():
        full_body.pop()

    sheet.body = "\n".join(full_body)
    return ParseResult(
        sheet=sheet,
        matched=matched,
        meta_lines=meta_lines,
        lrc_lines=lrc_lines,
        time_tags=time_tags,
        total_lines=len(raw_nonempty),
    )


# ---------------------------------------------------------------- 名字同步

# 核心字段（作词 / 作曲 / 编曲）的 别名 -> 字段名
_CORE_ALIAS_TO_FIELD: Dict[str, str] = {}
for _fld in CORE_FIELDS:
    for _alias in ALIASES.get(_fld, []):
        _CORE_ALIAS_TO_FIELD[_alias.lower()] = _fld
    for _alias in SHORT_ALIASES.get(_fld, []):
        _CORE_ALIAS_TO_FIELD.setdefault(_alias.lower(), _fld)

# 一行"信息行"：键名 + 分隔符 + 值
_META_LINE_RE = re.compile(r"^([^:：\s]{1,8})\s*[:：]\s*(.*)$")


def sync_credits_into_body(
    body: str,
    sheet: LyricSheet,
    strip_timestamps: bool = True,
) -> Tuple[str, int]:
    """把正文里"词 / 曲 / 编曲"这些行的名字，同步成 sheet 里的最新值。

    场景：导入《黑色幽默》后认出作词是周杰伦，正文里有一行
    "词：周杰伦"。用户在上面把作词改成了"张志博"，这行也要跟着
    变成"词：张志博"。

    设计要点：
    - **键名保持原样**：原文写"词："就还是"词："，只改冒号后面的名字，
      不擅自把"词"改成"作词"。
    - **只动核心三项**：制作人、混音这类不动。
    - **认不出就跳过**：歌词里的"我说：xxx"键名不在表里，不受影响。
    - **合并键会拆分**："词曲：周杰伦"在作词作曲改成不同的人之后，
      会拆成"作词：A""作曲：B"两行。

    返回 (新正文, 改了几行)。
    """
    if not body:
        return body, 0

    out: List[str] = []
    changed = 0

    for line in body.split("\n"):
        # 先分离行首的时间轴，处理完再原样拼回去
        ts = ""
        core = line
        if strip_timestamps:
            m_ts = LRC_TIME_RE.match(line)
            if m_ts:
                ts = m_ts.group(0)
                core = line[m_ts.end():]

        inner = core.strip()
        m = _META_LINE_RE.match(inner)
        if not m:
            out.append(line)
            continue

        key = m.group(1).strip()
        old_value = m.group(2).strip()
        k = key.lower()

        # ---- 合并键：词曲 / 词曲编 ----
        if k in MERGED_KEY_MAP:
            flds = MERGED_KEY_MAP[k]
            filled = [(sheet.get(f) or "").strip() for f in flds]
            filled = [v for v in filled if v]
            if not filled:
                out.append(line)
                continue
            if len(set(filled)) == 1:
                # 三项都改成了同一个人，继续合并成一行
                new_inner = f"{key}：{filled[0]}"
                if new_inner != inner:
                    changed += 1
                out.append(ts + new_inner)
            else:
                # 改成不同的人了，拆成几行写清楚
                changed += 1
                for f in flds:
                    v = (sheet.get(f) or "").strip()
                    if v:
                        out.append(ts + f"{LABELS.get(f, f)}：{v}")
            continue

        # ---- 单字段：词 / 曲 / 编曲 / 作词 / 作曲 ----
        fld = _CORE_ALIAS_TO_FIELD.get(k)
        if not fld:
            out.append(line)
            continue

        new_value = (sheet.get(fld) or "").strip()
        # 新值为空时不动，避免把用户的原文清掉
        if not new_value or new_value == old_value:
            out.append(line)
            continue

        out.append(ts + f"{key}：{new_value}")
        changed += 1

    return "\n".join(out), changed


def parse_file(path: str, **kwargs) -> ParseResult:
    """从文件读入并解析（自动处理编码）。

    会自动把文件名作为兜底线索传进去，
    这样 "晴天 - 周杰伦.lrc" 这类文件即使正文里没信息也能认出歌名。
    """
    from .storage import read_text_file

    kwargs.setdefault("filename", os.path.basename(path or ""))
    result = parse_lyrics(read_text_file(path), **kwargs)
    result.source = path
    return result
