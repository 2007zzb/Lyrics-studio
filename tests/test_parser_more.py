"""解析能力补充测试：覆盖真实世界里的各种奇怪写法。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import parse_lyrics  # noqa: E402


def _p(text):
    return parse_lyrics(text).sheet


def test_indented_credits():
    """缩进过的作词作曲也要能认出来（很多文件会缩进）。"""
    s = _p("    作词：方文山\n    作曲：周杰伦\n    编曲：钟兴民\n歌词")
    assert s.lyricist == "方文山"
    assert s.composer == "周杰伦"
    assert s.arranger == "钟兴民"


def test_merged_key_词曲():
    """「词曲：周杰伦」表示作词作曲都是他。"""
    s = _p("词曲：周杰伦\n编曲：钟兴民\n歌词")
    assert s.lyricist == "周杰伦"
    assert s.composer == "周杰伦"
    assert s.arranger == "钟兴民"


def test_merged_key_词曲编():
    s = _p("词曲编：周杰伦\n歌词")
    assert s.lyricist == "周杰伦"
    assert s.composer == "周杰伦"
    assert s.arranger == "周杰伦"


def test_bracket_wrapped_key():
    s = _p("【作词】方文山\n【作曲】周杰伦\n【编曲】钟兴民\n歌词")
    assert s.lyricist == "方文山"
    assert s.composer == "周杰伦"
    assert s.arranger == "钟兴民"


def test_square_bracket_key():
    s = _p("[作词]方文山\n[作曲]周杰伦\n歌词")
    assert s.lyricist == "方文山"
    assert s.composer == "周杰伦"


def test_space_around_colon():
    s = _p("作词 : 方文山\n作曲 : 周杰伦\n编曲 : 钟兴民\n歌词")
    assert s.lyricist == "方文山"
    assert s.composer == "周杰伦"
    assert s.arranger == "钟兴民"


def test_english_credits():
    s = _p("Lyricist: Vincent Fang\nComposer: Jay Chou\nArranger: Baby C\nlyrics")
    assert s.lyricist == "Vincent Fang"
    assert s.composer == "Jay Chou"
    assert s.arranger == "Baby C"


def test_relaxed_scan_key_in_middle():
    """「歌名 作词：方文山」这种键不在行首的写法，宽松补扫要接住。"""
    s = _p("爱的飞行日记 作词：方文山\n下一行歌词")
    assert s.lyricist == "方文山"
    assert "下一行歌词" in s.body


def test_lyric_with_colon_not_mistaken():
    """歌词里的「我说：xxx」不能被当成信息。"""
    s = _p("作词：方文山\n我说：这一次我不走了\n歌词第二句")
    assert s.lyricist == "方文山"
    assert "我说：这一次我不走了" in s.body


def test_no_credits_keeps_body_and_reports():
    """文件里确实没有作词作曲时，正文照常显示，提示要说清楚。"""
    r = parse_lyrics("[ti:爱的飞行日记]\n[ar:周杰伦]\n[al:跨时代]\n"
                     "[00:10.00]歌词一\n[00:14.00]歌词二")
    assert r.sheet.lyricist == ""
    assert "歌词一" in r.sheet.body and "歌词二" in r.sheet.body
    assert "没有作词" in r.summary()
    assert "正文 2 行" in r.summary()


def test_relaxed_scan_does_not_steal_lyrics():
    """宽松补扫不能把普通歌词吃掉。"""
    r = parse_lyrics("天青色等烟雨\n而我在等你\n炊烟袅袅升起")
    assert r.body_lines == 3, "歌词被误当成信息抽走了"


# ------------------------------------------------------------------ 标题行推断

def test_infer_title_artist_from_korean_parentheses():
    """LOSER - BIGBANG (빅뱅) → 歌名 LOSER，演唱 BIGBANG。"""
    s = parse_lyrics("[00:00.000]LOSER - BIGBANG (빅뱅)\n"
                     "[00:03.96]词：邓天佑\n[00:15.00]歌词").sheet
    assert s.title == "LOSER"
    assert s.artist == "BIGBANG"
    assert s.extras.get("原名") == "빅뱅"


def test_infer_title_artist_chinese_with_english():
    s = parse_lyrics("[00:00.00]晴天 - 周杰伦 (Jay Chou)\n[00:10.00]歌词").sheet
    assert s.title == "晴天"
    assert s.artist == "周杰伦"


def test_lrc_tags_win_over_title_line():
    """有 [ti:]/[ar:] 标签时以标签为准，不被标题行覆盖。"""
    s = parse_lyrics("[ti:晴天]\n[ar:周杰伦]\n[00:00.00]别的 - 别人 (X)\n"
                     "[00:10.00]歌词").sheet
    assert s.title == "晴天"
    assert s.artist == "周杰伦"


def test_no_parentheses_still_guesses_from_head():
    """首行是"歌名 - 演唱"（没括号）时也要能认。

    放宽的原因：很多文件只在第一行写 "LOSER - BIGBANG"，
    没有括号原文名。风险可控 —— 只在开头几行里找，且必须有短横线。
    """
    s = parse_lyrics("[00:00.00]LOSER - BIGBANG\n[00:10.00]歌词").sheet
    assert s.title == "LOSER"
    assert s.artist == "BIGBANG"


def test_dash_lyric_in_middle_not_treated_as_title():
    """正文中间的破折号不会被当成标题行。"""
    s = parse_lyrics("作词：方文山\n第一段歌词\n第二段歌词\n"
                     "某句 - 带横线的词\n第四段").sheet
    assert s.title == ""


def test_title_line_does_not_steal_lyrics():
    s = parse_lyrics("[00:10.00]天青色等烟雨\n[00:14.00]而我在等你").sheet
    assert s.title == ""
    assert s.artist == ""


def test_value_parentheses_stripped():
    """"演唱（周杰伦）"取出来的值不该带着括号。"""
    s = parse_lyrics("演唱（周杰伦）\n歌词").sheet
    assert s.artist == "周杰伦"
    assert "（" not in s.artist


# ------------------------------------------------------------------ 文件名兜底

def test_filename_infers_title_and_artist():
    """文件里没信息时，从 "歌名 - 演唱.lrc" 里拆出来。"""
    s = parse_lyrics("[00:10.00]歌词一句\n[00:14.00]歌词二句",
                     filename="晴天 - 周杰伦.lrc").sheet
    assert s.title == "晴天"
    assert s.artist == "周杰伦"


def test_filename_supports_windows_path():
    s = parse_lyrics("歌词", filename=r"C:\音乐\黑色幽默 - 周杰伦.lrc").sheet
    assert s.title == "黑色幽默"


def test_filename_with_native_name():
    s = parse_lyrics("歌词", filename="LOSER - BIGBANG (빅뱅).lrc").sheet
    assert s.title == "LOSER"
    assert s.artist == "BIGBANG"
    assert s.extras.get("原名") == "빅뱅"


def test_filename_multiple_artists():
    s = parse_lyrics("歌词", filename="爱的飞行日记 - 周杰伦、杨瑞代.lrc").sheet
    assert s.title == "爱的飞行日记"
    assert s.artist == "周杰伦、杨瑞代"


def test_filename_strips_noise():
    """"歌词"这类标记要从文件名里去掉。"""
    s = parse_lyrics("歌词", filename="晴天 - 周杰伦【歌词】.lrc").sheet
    assert s.title == "晴天"


def test_filename_does_not_override_tags():
    """[ti:]/[ar:] 标签优先，文件名只是兜底。"""
    s = parse_lyrics("[ti:晴天]\n[ar:周杰伦]\n歌词",
                     filename="别的歌 - 别人.lrc").sheet
    assert s.title == "晴天"
    assert s.artist == "周杰伦"


def test_filename_without_dash_ignored():
    """文件名没有短横线就不猜。"""
    s = parse_lyrics("歌词", filename="未命名.lrc").sheet
    assert s.title == ""


def test_filename_ending_with_punctuation_ignored():
    s = parse_lyrics("歌词", filename="周杰伦. - 某人.lrc").sheet
    assert s.title == ""
