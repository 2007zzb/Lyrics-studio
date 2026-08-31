"""名字同步测试：改了上面的作词/作曲/编曲，正文里对应的行要跟着改。

回归背景：用户导入《黑色幽默》，识别出作词是周杰伦，正文里有一行
"词：周杰伦"。他把作词改成"张志博"之后，正文里那行还是"词：周杰伦"。
本模块就是要保证这种情况下正文会同步更新。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model import LyricSheet  # noqa: E402
from src.parser import parse_lyrics, sync_credits_into_body  # noqa: E402


def _sync(body, **values):
    sheet = LyricSheet()
    for k, v in values.items():
        sheet.set(k, v)
    return sync_credits_into_body(body, sheet)


def test_basic_sync_lyricist():
    new, n = _sync("词：周杰伦\n曲：周杰伦\n难过是因为闷了很久",
                   lyricist="张志博", composer="周杰伦")
    assert n == 1
    assert "词：张志博" in new
    assert "曲：周杰伦" in new          # 没改的字段保持原样
    assert "难过是因为闷了很久" in new   # 歌词不受影响


def test_keeps_original_key_name():
    """原文写"词："就还是"词："，不能擅自改成"作词："。"""
    new, _ = _sync("词：周杰伦", lyricist="张志博")
    assert new == "词：张志博"


def test_sync_all_three():
    new, n = _sync("词：周杰伦\n曲：周杰伦\n编曲：钟兴民",
                   lyricist="张志博", composer="李小明", arranger="王大锤")
    assert n == 3
    assert "词：张志博" in new
    assert "曲：李小明" in new
    assert "编曲：王大锤" in new


def test_sync_with_full_label():
    """正文里写的是完整"作词："也要能改。"""
    new, _ = _sync("作词：周杰伦\n作曲：周杰伦", lyricist="张志博")
    assert "作词：张志博" in new
    assert "作曲：周杰伦" in new


def test_sync_with_timestamp():
    """带时间轴的 LRC 行，时间戳要原样保留。"""
    new, n = _sync("[00:03.960]词：周杰伦\n[00:07.000]曲：周杰伦",
                   lyricist="张志博", composer="周杰伦")
    assert n == 1
    assert "[00:03.960]词：张志博" in new
    assert "[00:07.000]曲：周杰伦" in new


def test_merged_key_same_person():
    """词曲是同一个人时，继续合并成一行。"""
    new, n = _sync("词曲：周杰伦\n歌词", lyricist="张志博", composer="张志博")
    assert n == 1
    assert "词曲：张志博" in new


def test_merged_key_split_when_different():
    """词曲改成不同的人时，拆成两行写清楚。"""
    new, n = _sync("词曲：周杰伦\n歌词", lyricist="张志博", composer="李小明")
    assert n == 1
    assert "作词：张志博" in new
    assert "作曲：李小明" in new
    assert "词曲：" not in new


def test_does_not_touch_other_fields():
    """制作人、混音这类字段不动。"""
    new, n = _sync("词：周杰伦\n制作人：张三\n混音：李四",
                   lyricist="张志博")
    assert n == 1
    assert "制作人：张三" in new
    assert "混音：李四" in new


def test_does_not_steal_lyrics():
    """歌词里的"我说：xxx"不能被当成信息行改掉。"""
    new, n = _sync("词：周杰伦\n我说：这一次我不走了\n难过是因为闷了很久",
                   lyricist="张志博")
    assert n == 1
    assert "我说：这一次我不走了" in new
    assert "难过是因为闷了很久" in new


def test_empty_value_does_not_wipe():
    """新值为空时不改动原文，避免把内容清掉。"""
    new, n = _sync("词：周杰伦\n歌词", lyricist="")
    assert n == 0
    assert "词：周杰伦" in new


def test_no_change_returns_zero():
    new, n = _sync("词：张志博\n歌词", lyricist="张志博")
    assert n == 0
    assert new == "词：张志博\n歌词"


def test_indented_line():
    new, n = _sync("  词：周杰伦\n歌词", lyricist="张志博")
    assert n == 1
    assert "词：张志博" in new


# ------------------------------------------------------------------ 端到端

def test_full_workflow_black_humor():
    """完整还原用户的场景：导入《黑色幽默》→ 改名字 → 正文跟着改。"""
    lrc = (
        "[ti:黑色幽默]\n[ar:周杰伦]\n[al:Jay]\n"
        "[00:00.000]黑色幽默 - 周杰伦 (Jay Chou)\n"
        "[00:03.960]词：周杰伦\n"
        "[00:07.000]曲：周杰伦\n"
        "[00:10.000]编曲：钟兴民\n"
        "[00:15.000]难过是因为闷了很久\n"
        "[00:19.000]是因为想了太多"
    )
    result = parse_lyrics(lrc)
    sheet = result.sheet

    # 导入后自动认出了三项
    assert sheet.lyricist == "周杰伦"
    assert sheet.composer == "周杰伦"
    assert sheet.arranger == "钟兴民"

    # 用户把作词改成自己
    sheet.lyricist = "张志博"
    new_body, changed = sync_credits_into_body(sheet.body, sheet)
    assert changed == 1
    assert "词：张志博" in new_body
    assert "词：周杰伦" not in new_body
    assert "难过是因为闷了很久" in new_body      # 歌词没被误伤

    # 导出：正文里那句旧信息行要被清掉，不能写两遍
    sheet.body = new_body
    out = sheet.to_text()

    def info_lines(text):
        return [ln for ln in text.split("\n")
                if ln.strip().startswith(("词：", "曲：", "编曲：", "作词：", "作曲："))]

    assert len(info_lines(out)) == 3, f"信息行重复或丢失：\n{out}"
    assert out.startswith("作词：张志博\n作曲：周杰伦\n编曲：钟兴民\n")
    assert "难过是因为闷了很久" in out
    # 标题行不是信息行，要保留
    assert "黑色幽默 - 周杰伦 (Jay Chou)" in out


def test_export_drops_meta_lines_anywhere():
    """信息行不在正文开头时，导出也要清掉。"""
    sheet = LyricSheet()
    sheet.lyricist = "张志博"
    sheet.composer = "张志博"
    sheet.arranger = "张志博"
    sheet.body = ("黑色幽默 - 周杰伦 (Jay Chou)\n"
                  "词：张志博\n"
                  "曲：张志博\n"
                  "编曲：张志博\n"
                  "难过是因为闷了很久")
    out = sheet.to_text()
    assert out.count("张志博") == 3, f"信息行重复了：\n{out}"
    assert "黑色幽默 - 周杰伦 (Jay Chou)" in out   # 标题行不是信息行，保留
    assert "难过是因为闷了很久" in out


def test_export_drops_timestamped_meta_lines():
    """带时间轴的信息行 "[00:03.96]词：X" 导出时也要清掉。

    回归：键名前面有 [00:03.96] 时，"词" 会被时间轴挤到
    8 个字符之外，导致识别失败，导出后作词写了两遍。
    """
    sheet = LyricSheet()
    sheet.lyricist = "邓天佑"
    sheet.composer = "TEDDY"
    sheet.arranger = "TEDDY"
    sheet.body = ("[00:00.000]LOSER - BIGBANG\n"
                  "[00:03.960]词：邓天佑\n"
                  "[00:07.000]曲：TEDDY\n"
                  "[00:10.000]编曲：TEDDY\n"
                  "[00:15.000]I'm a loser")
    out = sheet.to_text()
    assert out.count("邓天佑") == 1, f"信息行重复：\n{out}"
    assert out.count("TEDDY") == 2, f"作曲编曲各一次：\n{out}"
    assert "[00:15.000]I'm a loser" in out


def test_lyrics_kept_when_exporting():
    """歌词行不能因为含冒号就被误删。"""
    sheet = LyricSheet()
    sheet.lyricist = "方文山"
    sheet.body = "我说：这一次我不走了\n天青色等烟雨"
    out = sheet.to_text()
    assert "我说：这一次我不走了" in out
    assert "天青色等烟雨" in out
