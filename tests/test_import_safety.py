"""导入安全性测试：任何格式下都不能把用户的歌词弄丢。

回归背景：用户导入一个 .lrc 后，作词/作曲/编曲都识别到了，歌词正文却是空的。
现在的策略是——导入即"打开文件"：扫描只负责把信息填到上面的输入框，
正文区保留文件的全部内容（只剥掉时间轴和 [ti:] 标签行），
删除与否交给用户在编辑区里自己决定。这样歌词不可能凭空消失。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import parse_lyrics  # noqa: E402

STANDARD = """[ti:兰亭序]
[ar:周杰伦]
[al:魔杰座]
[00:00.00]作词：方文山
[00:03.00]作曲：周杰伦
[00:06.00]编曲：钟兴民
[00:10.00]兰亭临帖 行书如行云流水
[00:14.00]月下门推 心细如你脚步碎"""


def test_standard_lrc_keeps_full_content():
    r = parse_lyrics(STANDARD)
    assert r.sheet.lyricist == "方文山"
    assert r.sheet.composer == "周杰伦"
    assert "兰亭临帖" in r.sheet.body
    assert "月下门推" in r.sheet.body
    # 全文保留：信息行也留在正文里，供用户自己删
    assert "作词：方文山" in r.sheet.body


def test_lrc_tags_not_in_body():
    """[ti:][ar:][al:] 这类标签不是歌词，不该出现在正文区。"""
    r = parse_lyrics(STANDARD)
    assert "[ti:兰亭序]" not in r.sheet.body
    assert "[ar:周杰伦]" not in r.sheet.body


def test_timestamps_stripped():
    r = parse_lyrics(STANDARD)
    assert "[00:10.00]" not in r.sheet.body


def test_only_meta_lines_still_visible():
    """只有信息栏没歌词的文件，内容照样要显示出来，不能变空白。"""
    text = """作词：周杰伦
作曲：周杰伦
编曲：钟兴民
歌名：兰亭序"""
    r = parse_lyrics(text)
    assert r.body_lines == 4
    assert "歌名：兰亭序" in r.sheet.body


def test_only_timestamps_gives_empty_body():
    """只有时间轴没有文字，正文为空属于正常，且要给出提示。"""
    r = parse_lyrics("[00:10.00]\n[00:14.00]")
    assert r.body_lines == 0
    assert "空的" in r.summary()


def test_empty_file_message():
    r = parse_lyrics("   \n\n  ")
    assert r.total_lines == 0
    assert r.body_lines == 0
    assert "空的" in r.summary()


def test_summary_reports_body_count():
    r = parse_lyrics(STANDARD)
    assert "正文" in r.summary()
    assert "5 行" in r.summary()


def test_export_dedupes_header():
    """导出时正文开头与信息行重复的那些行要被去掉，避免写两遍。"""
    r = parse_lyrics(STANDARD)
    out = r.sheet.to_text()
    assert out.count("作词：") == 1
    assert out.count("作曲：") == 1
    assert out.count("编曲：") == 1
    assert "兰亭临帖" in out


def test_export_drops_stale_meta_lines():
    """改了作词之后，正文里那行旧的「作词：方文山」也要去掉。"""
    r = parse_lyrics(STANDARD)
    r.sheet.lyricist = "张小博"          # 用户改了作词
    out = r.sheet.to_text()
    assert out.count("作词：") == 1
    assert "作词：张小博" in out
    assert "作词：方文山" not in out, "旧的信息行没去掉"


def test_export_can_keep_meta_lines():
    r = parse_lyrics(STANDARD)
    out = r.sheet.to_text(drop_meta_lines=False)
    assert out.count("作词：") == 2      # 信息行 + 正文里那行


def test_no_content_lost_for_various_formats():
    """多种常见 LRC 格式下，歌词正文都不应为空。"""
    variants = {
        "两位毫秒": "[00:10.00]兰亭临帖 行书如行云流水",
        "三位毫秒": "[00:10.000]兰亭临帖 行书如行云流水",
        "冒号分隔": "[00:10:00]兰亭临帖 行书如行云流水",
        "时间轴后带空格": "[00:10.00]  兰亭临帖 行书如行云流水",
        "一行多时间轴": "[00:10.00][01:20.00]兰亭临帖 行书如行云流水",
        "尖括号时间轴": "<00:10.00>兰亭临帖 行书如行云流水",
        "无时间轴纯文本": "兰亭临帖 行书如行云流水",
    }
    for name, line in variants.items():
        r = parse_lyrics(f"[ti:兰亭序]\n{line}")
        assert "兰亭临帖" in r.sheet.body, f"{name} 格式丢了歌词"
