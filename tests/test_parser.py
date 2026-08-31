"""解析引擎测试：pytest -q tests"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model import LyricSheet  # noqa: E402
from src.parser import parse_lyrics  # noqa: E402


def test_basic_three_lines():
    text = """作词：张小博
作曲：张小博
编曲：张小博
这一句写给你听
这一句写给我自己"""
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "张小博"
    assert r.sheet.composer == "张小博"
    assert r.sheet.arranger == "张小博"
    assert "这一句写给你听" in r.sheet.body
    assert "这一句写给我自己" in r.sheet.body
    assert r.matched_count == 3


def test_halfwidth_colon_and_spaces():
    text = "作词: 周杰伦\n作曲: 周杰伦\n编曲: 钟兴民\n夜里的雨还没停"
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "周杰伦"
    assert r.sheet.composer == "周杰伦"
    assert r.sheet.arranger == "钟兴民"
    assert "夜里的雨还没停" in r.sheet.body


def test_space_as_separator():
    text = "作词 方文山\n作曲 周杰伦\n编曲 钟兴民\n天青色等烟雨"
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "方文山"
    assert r.sheet.composer == "周杰伦"
    assert r.sheet.arranger == "钟兴民"


def test_one_line_multi_fields():
    text = "作词：张小博  作曲：李小明  编曲：王大锤\n副歌第一句"
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "张小博"
    assert r.sheet.composer == "李小明"
    assert r.sheet.arranger == "王大锤"
    assert "副歌第一句" in r.sheet.body


def test_merged_key():
    text = "作词/作曲：周杰伦\n编曲：钟兴民\n青花瓷的第一句"
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "周杰伦"
    assert r.sheet.composer == "周杰伦"
    assert r.sheet.arranger == "钟兴民"


def test_short_alias_词曲():
    text = "词：林夕\n曲：陈辉阳\n编曲：陈辉阳\n下一句歌词"
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "林夕"
    assert r.sheet.composer == "陈辉阳"


def test_english_aliases():
    text = "Lyricist: Adele\nComposer: Adele\nArranger: Paul\nHello from the other side"
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "Adele"
    assert r.sheet.composer == "Adele"
    assert r.sheet.arranger == "Paul"


def test_bracket_decoration():
    text = "【作词】张小博\n【作曲】李小明\n【编曲】王大锤\n歌词正文开始"
    r = parse_lyrics(text)
    # 【】 被剥掉装饰字符后应能识别；识别不了时至少不能污染正文
    assert r.sheet.body.endswith("歌词正文开始")


def test_lrc_tags_and_timestamps():
    text = (
        "[ti:晴天]\n[ar:周杰伦]\n[al:叶惠美]\n[offset:0]\n"
        "[00:12.34]故事的小黄花\n[00:16.50]从出生那年就飘着\n"
        "作词：周杰伦\n作曲：周杰伦\n编曲：周杰伦"
    )
    r = parse_lyrics(text)
    assert r.sheet.title == "晴天"
    assert r.sheet.artist == "周杰伦"
    assert r.sheet.album == "叶惠美"
    assert r.sheet.lyricist == "周杰伦"
    assert "[00:12.34]" not in r.sheet.body
    assert "故事的小黄花" in r.sheet.body


def test_keep_timestamps_option():
    text = "[00:01.00]第一句\n作词：A"
    r = parse_lyrics(text, strip_timestamps=False)
    assert "[00:01.00]" in r.sheet.body


def test_body_not_mistaken_as_meta():
    """歌词正文里出现的 'xxx：yyy' 不应被当成元数据。"""
    text = """作词：张小博
作曲：张小博
编曲：张小博
我说：这一次我不走了
你说：那就留下来吧"""
    r = parse_lyrics(text)
    assert r.sheet.lyricist == "张小博"
    assert "我说：这一次我不走了" in r.sheet.body
    assert "你说：那就留下来吧" in r.sheet.body


def test_long_value_is_lyric_not_name():
    text = "作词：我把这一整句非常非常长的歌词写在冒号的后面只是为了看看它会不会被误判成一个人的名字呢\n作曲：张小博"
    r = parse_lyrics(text)
    assert r.sheet.lyricist == ""        # 太长，拒绝填写
    assert r.sheet.composer == "张小博"
    assert "作词：" in r.sheet.body      # 回落为歌词正文


def test_extra_credits():
    text = "制作人：张小博\n混音：李雷\n作词：A\n作曲：B\n编曲：C\n歌词"
    r = parse_lyrics(text)
    assert r.sheet.extras.get("制作人") == "张小博"
    assert r.sheet.extras.get("混音") == "李雷"
    assert r.sheet.lyricist == "A"


def test_round_trip_export():
    text = """作词：张小博
作曲：李小明
编曲：王大锤

第一段歌词
第二段歌词"""
    r = parse_lyrics(text)
    rendered = r.sheet.to_text()
    assert rendered.splitlines()[0] == "作词：张小博"
    assert rendered.splitlines()[1] == "作曲：李小明"
    assert rendered.splitlines()[2] == "编曲：王大锤"
    assert "第一段歌词" in rendered
    r2 = parse_lyrics(rendered)
    assert (r2.sheet.lyricist, r2.sheet.composer, r2.sheet.arranger) == (
        r.sheet.lyricist, r.sheet.composer, r.sheet.arranger)


def test_empty_keeps_placeholder():
    sheet = LyricSheet(body="只有歌词")
    out = sheet.to_text()
    assert out.splitlines()[:3] == ["作词：", "作曲：", "编曲："]


def test_no_metadata_at_all():
    r = parse_lyrics("这一整段就是歌词\n没有任何作者信息\n第三行")
    assert r.sheet.lyricist == ""
    assert r.sheet.body.count("\n") == 2
    assert r.matched_count == 0


def test_crlf_and_blank_lines():
    r = parse_lyrics("作词：A\r\n作曲：B\r\n编曲：C\r\n\r\n\r\n第一段\r\n\r\n第二段\r\n")
    assert r.sheet.lyricist == "A"
    assert "第一段\n\n第二段" in r.sheet.body   # 段落间的空行要保留


def test_overwrite_flag():
    base = LyricSheet(lyricist="旧词", composer="旧曲", arranger="旧编")
    r = parse_lyrics("作词：新词\n作曲：新曲", base=base, overwrite=True)
    assert r.sheet.lyricist == "新词"
    assert r.sheet.arranger == "旧编"   # 没出现的字段保持原样
    r2 = parse_lyrics("作词：更新的词", base=LyricSheet(lyricist="旧词"), overwrite=False)
    assert r2.sheet.lyricist == "旧词"


def test_stats_and_filename():
    sheet = LyricSheet(title="晴天/夜曲", body="第一行\n\n第二行\n第三行")
    st = sheet.stats()
    assert st["lines"] == 3
    assert st["paragraphs"] == 2
    assert "/" not in sheet.suggested_filename()
