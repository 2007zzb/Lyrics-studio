"""歌词数据模型。

负责描述一张"歌词表"在内存中的结构，并提供
模板渲染、纯文本导出与序列化能力。

模板约定（严格遵循需求）：
    第 1 行：作词：xxx
    第 2 行：作曲：xxx
    第 3 行：编曲：xxx
    第 4 行起：歌词正文
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# 前三行的固定顺序，不可调整
CORE_FIELDS: List[str] = ["lyricist", "composer", "arranger"]

# 用户要求里没有强制出现的"扩展信息"，默认不写进正文模板
OPTIONAL_FIELDS: List[str] = ["title", "artist", "album"]

LABELS: Dict[str, str] = {
    "title": "歌名",
    "artist": "演唱",
    "album": "专辑",
    "lyricist": "作词",
    "composer": "作曲",
    "arranger": "编曲",
}

ALL_FIELDS: List[str] = OPTIONAL_FIELDS + CORE_FIELDS

# 合并写法：一个键同时对应多个字段
# 例："词曲：周杰伦" 表示作词和作曲都是周杰伦
MERGED_ALIASES: Dict[str, List[str]] = {
    "词曲": ["lyricist", "composer"],
    "詞曲": ["lyricist", "composer"],
    "词曲编": ["lyricist", "composer", "arranger"],
    "詞曲編": ["lyricist", "composer", "arranger"],
    "作词作曲": ["lyricist", "composer"],
    "作詞作曲": ["lyricist", "composer"],
    "作曲作词": ["composer", "lyricist"],
    "词编": ["lyricist", "arranger"],
    "曲编": ["composer", "arranger"],
    "作曲编曲": ["composer", "arranger"],
    "编曲作曲": ["arranger", "composer"],
}

# 小写后的合并键集合，供"这行是不是信息行"的判断使用
MERGED_KEYS = {k.lower() for k in MERGED_ALIASES}

# 常见写法的别名 —— 放在 model 里是为了让"这行是不是信息行"的判断
# 和解析器共用同一份数据，避免两边各写一套导致漏判。
ALIASES: Dict[str, List[str]] = {
    "lyricist": [
        "作词", "作詞", "填词", "填詞", "词作者", "作词人", "作词者", "作词者名",
        "歌词作者", "文字", "Lyrics by", "Lyricist", "Lyrics", "Lyric",
        "Written by", "Words by", "Words",
    ],
    "composer": [
        "作曲", "譜曲", "谱曲", "曲作者", "作曲人", "作词人曲", "歌曲作曲",
        "Composed by", "Music by", "Composer", "Music",
    ],
    "arranger": [
        "编曲", "編曲", "编曲人", "编曲者", "编曲制作", "Arranged by",
        "Arranger", "Arrangement",
    ],
    "title": ["歌曲名", "歌名", "曲名", "标题", "歌曲名称", "歌曲", "Title", "Song", "Name"],
    "artist": ["演唱", "歌手", "主唱", "演唱者", "Artist", "Singer", "Vocal", "Vocalist", "Performed by"],
    "album": ["专辑", "唱片", "专集", "Album"],
}

# 单字简称，歧义大，必须配合长度限制使用
SHORT_ALIASES: Dict[str, List[str]] = {
    "lyricist": ["词", "詞"],
    "composer": ["曲"],
    "arranger": ["编", "編"],
}

EXTRA_ALIASES: Dict[str, List[str]] = {
    "制作人": ["制作人", "制作", "Producer", "Produced by"],
    "监制": ["监制", "Executive Producer"],
    "出品": ["出品", "出品人", "Presented by"],
    "策划": ["策划", "Planner"],
    "统筹": ["统筹"],
    "混音": ["混音", "混音师", "Mixing", "Mixed by"],
    "母带": ["母带", "Mastering", "Mastered by"],
    "录音": ["录音", "录音师", "Recording", "Recorded by"],
    "和声": ["和声", "和音", "Backing Vocal", "Chorus"],
    "吉他": ["吉他", "Guitar"],
    "贝斯": ["贝斯", "低音吉他", "Bass"],
    "鼓": ["鼓", "Drums", "Drum"],
    "键盘": ["键盘", "Keyboard"],
    "弦乐": ["弦乐", "Strings"],
    "后期": ["后期", "Post Production"],
    "发行": ["发行", "Released by"],
    "OP": ["OP", "op"],
    "SP": ["SP", "sp"],
}


def _build_key_to_field() -> Dict[str, str]:
    """别名（小写） -> 字段名。附加信息的值是它的显示名。"""
    mapping: Dict[str, str] = {}
    for field_name, alias_list in ALIASES.items():
        for alias in alias_list:
            mapping[alias.lower()] = field_name
    for field_name, alias_list in SHORT_ALIASES.items():
        for alias in alias_list:
            mapping.setdefault(alias.lower(), field_name)
    for label, alias_list in EXTRA_ALIASES.items():
        for alias in alias_list:
            mapping.setdefault(alias.lower(), label)
    return mapping


# 别名 -> 字段名（或附加信息的显示名）
KEY_TO_FIELD: Dict[str, str] = _build_key_to_field()

# 合并键（小写） -> 它覆盖的字段列表
MERGED_KEY_MAP: Dict[str, List[str]] = {k.lower(): v for k, v in MERGED_ALIASES.items()}


# 常见的附加制作信息，识别出以后放在"更多信息"里，不占用前三行
EXTRA_FIELD_HINTS: List[str] = [
    "制作人", "监制", "出品", "策划", "统筹", "混音", "母带", "录音",
    "和声", "吉他", "贝斯", "鼓", "键盘", "弦乐", "编曲助理", "后期",
    "OP", "SP", "发行", "录音棚", "封面",
]


_META_KEY_RE = None      # 延迟构造，避免在模块导入时多做一次正则编译
_LEADING_TS_RE = None


MAX_META_VALUE_LEN = 40


def _meta_key_of(line: str, written: set) -> str:
    """判断一行是不是"已经写到头部的信息行"，是则返回键名，否则返回空串。

    written 是已经输出到头部的字段集合（"lyricist" 这样的字段名，
    以及附加信息的显示名如"制作人"）。

    认别名，所以 "词：" "作词：" "Lyricist:" "词曲：" 都算，
    而歌词里的 "我说：xxx" 因为键名不认识，返回空串。

    行首的 LRC 时间轴会先剥掉再判断，所以
    "[00:03.96]词：周杰伦" 同样能认出来。
    """
    global _META_KEY_RE, _LEADING_TS_RE
    if _META_KEY_RE is None:
        import re
        _META_KEY_RE = re.compile(r"^\s*([^:：\s]{1,8})\s*[:：]\s*(.*)$")
        _LEADING_TS_RE = re.compile(
            r"^\s*[\[<]\s*\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\s*[\]>]")

    text = _LEADING_TS_RE.sub("", line or "")
    match = _META_KEY_RE.match(text)
    if not match:
        return ""
    key, value = match.group(1).strip(), match.group(2).strip()
    if len(value) > MAX_META_VALUE_LEN:
        return ""
    token = key.lower()

    field = KEY_TO_FIELD.get(token)
    if field and field in written:
        return key

    # 合并键：它覆盖的字段全都写过，才算重复
    subs = MERGED_KEY_MAP.get(token)
    if subs and all(f in written for f in subs):
        return key

    return ""


@dataclass
class LyricSheet:
    """一张歌词表。"""

    lyricist: str = ""
    composer: str = ""
    arranger: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    extras: Dict[str, str] = field(default_factory=dict)
    body: str = ""

    # ---------- 读写字段 ----------
    def get(self, name: str) -> str:
        return getattr(self, name, "")

    def set(self, name: str, value: str) -> None:
        if name in ALL_FIELDS:
            setattr(self, name, value)

    def set_if_empty(self, name: str, value: str) -> bool:
        """仅在原值为空时写入，返回是否真的写入了。"""
        value = (value or "").strip()
        if not value:
            return False
        if name in ALL_FIELDS:
            if getattr(self, name).strip():
                return False
            setattr(self, name, value)
            return True
        if not self.extras.get(name, "").strip():
            self.extras[name] = value
            return True
        return False

    # ---------- 模板渲染 ----------
    def to_text(self, include_optional: bool = False, drop_meta_lines: bool = True) -> str:
        """渲染成纯文本。

        include_optional=False 时输出严格的三行头部模板：
        作词 / 作曲 / 编曲，第四行起为歌词正文。

        drop_meta_lines=True 时（默认），会把正文里所有"信息行"删掉。
        导入时正文保留的是文件全文，里面往往还留着「词：周杰伦」这类行；
        它们的内容已经填到头部三行了，再原样写一遍就重复了。

        只删**头部已经写过**的那些字段 —— 核心三项永远删，
        歌名/演唱/专辑/自定义字段在 include_optional 打开时才删，
        避免把用户还没导出过的信息弄丢。

        判断依据是**行的键名**（作词 / 作曲 / 词曲 / 歌名…），
        不是整行内容完全相同 —— 所以即使把作词从"周杰伦"改成了别人，
        正文里那行旧的「词：周杰伦」也会被正确去掉。
        """
        lines: List[str] = []

        if include_optional:
            for name in OPTIONAL_FIELDS:
                value = (self.get(name) or "").strip()
                if value:
                    lines.append(f"{LABELS[name]}：{value}")

        for name in CORE_FIELDS:
            lines.append(f"{LABELS[name]}：{(self.get(name) or '').strip()}")

        if include_optional:
            for key, value in self.extras.items():
                value = (value or "").strip()
                if value:
                    lines.append(f"{key}：{value}")

        body_lines = (self.body or "").strip("\n").split("\n")

        if drop_meta_lines:
            written = set(CORE_FIELDS)
            if include_optional:
                written |= set(OPTIONAL_FIELDS)
                written |= set(self.extras.keys())
            # 全文扫描，而不只是看开头几行：
            # 很多 LRC 的第一行是标题，信息行排在它后面。
            body_lines = [ln for ln in body_lines if not _meta_key_of(ln, written)]

        body = "\n".join(body_lines).strip("\n")
        if body:
            lines.append(body)

        return "\n".join(lines) + "\n"

    def suggested_filename(self) -> str:
        """给用户一个默认保存名。"""
        base = (self.title or "").strip()
        if not base:
            first_line = ""
            for line in (self.body or "").splitlines():
                if line.strip():
                    first_line = line.strip()
                    break
            base = first_line[:12] or "未命名歌词"
        safe = "".join(ch for ch in base if ch not in r'\/:*?"<>|').strip()
        return (safe or "未命名歌词") + ".txt"

    # ---------- 统计 ----------
    def stats(self) -> Dict[str, int]:
        body_lines = [ln for ln in (self.body or "").splitlines() if ln.strip()]
        content = "".join(body_lines)
        paragraphs = 0
        blank = True
        for line in (self.body or "").splitlines():
            if line.strip():
                if blank:
                    paragraphs += 1
                blank = False
            else:
                blank = True
        return {
            "lines": len(body_lines),
            "paragraphs": paragraphs,
            "chars": len(content.replace(" ", "")),
            "total_chars": len(content),
        }

    def filled_core_fields(self) -> List[Tuple[str, str]]:
        return [(LABELS[n], self.get(n).strip()) for n in CORE_FIELDS if self.get(n).strip()]

    def is_empty(self) -> bool:
        return not any(
            [
                self.title.strip(), self.artist.strip(), self.album.strip(),
                self.lyricist.strip(), self.composer.strip(), self.arranger.strip(),
                self.body.strip(),
            ]
        ) and not self.extras

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "lyricist": self.lyricist,
            "composer": self.composer,
            "arranger": self.arranger,
            "extras": dict(self.extras),
            "body": self.body,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LyricSheet":
        return cls(
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            lyricist=data.get("lyricist", ""),
            composer=data.get("composer", ""),
            arranger=data.get("arranger", ""),
            extras=dict(data.get("extras") or {}),
            body=data.get("body", ""),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# 让 dataclass 在 python<3.10 的类型注解下也能正常工作
if "Tuple" not in globals():  # pragma: no cover
    from typing import Tuple  # noqa: F401
