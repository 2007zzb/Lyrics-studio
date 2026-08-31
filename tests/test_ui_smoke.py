"""界面冒烟测试：确保 Flet 控件都能正常构造（不需要图形界面）。

pytest -q tests
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft  # noqa: E402

from src import theme  # noqa: E402
from src.ui.about import build_about_drawer  # noqa: E402
from src.ui.editor import EditorView  # noqa: E402


def make_page():
    page = MagicMock()
    page.overlay = []
    page.dialog = None
    return page


def test_editor_view_builds():
    page = make_page()
    view = EditorView(
        page=page,
        pick_dialog=ft.FilePicker(),
        save_dialog=ft.FilePicker(),
        notify=lambda *a, **k: None,
        open_about=lambda *a: None,
    )
    assert view.controls, "编辑器没有生成任何控件"
    assert set(view.fields) >= {"lyricist", "composer", "arranger"}
    assert "作词" == view.fields["lyricist"].label


def test_editor_import_flow():
    """模拟导入解析后的数据回写。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    view.sheet.lyricist = "张小博"
    view.sheet.composer = "张小博"
    view.sheet.arranger = "张小博"
    view.sheet.body = "第一行歌词\n第二行歌词"
    view.refresh()
    assert view.fields["lyricist"].value == "张小博"
    assert view.body_field.value.startswith("第一行歌词")
    assert "2 行" in view.stats_text.value


def test_extras_add_and_remove():
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    view._add_extra_field(name="制作人")
    assert "制作人" in view.sheet.extras
    view._remove_extra("制作人")
    assert "制作人" not in view.sheet.extras


def collect_texts(control, bucket=None, depth=0):
    """递归收集控件树里所有可见文本。"""
    if bucket is None:
        bucket = []
    if control is None or depth > 15:
        return bucket
    if isinstance(control, (list, tuple)):
        for item in control:
            collect_texts(item, bucket, depth + 1)
        return bucket
    for attr in ("value", "text", "label", "hint_text", "tooltip"):
        value = getattr(control, attr, None)
        if isinstance(value, str) and value:
            bucket.append(value)
    for attr in ("content", "controls", "actions", "title", "subtitle",
                 "leading", "trailing", "drawer", "end_drawer"):
        child = getattr(control, attr, None)
        if child is not None:
            collect_texts(child, bucket, depth + 1)
    return bucket


def test_about_drawer_builds():
    drawer = build_about_drawer(make_page())
    assert isinstance(drawer, ft.NavigationDrawer)
    texts = "\n".join(collect_texts(drawer))
    assert theme.AUTHOR in texts
    assert theme.AUTHOR_QQ in texts
    assert theme.APP_VERSION in texts


def test_about_content_mentions_author_and_qq():
    """抽屉里必须能看到作者、QQ、版本、开源协议与更新日志。"""
    drawer = build_about_drawer(make_page())
    texts = "\n".join(collect_texts(drawer))
    assert theme.AUTHOR in texts
    assert theme.AUTHOR_QQ in texts
    assert f"v{theme.APP_VERSION}" in texts
    assert theme.LICENSE_NAME in texts
    assert "更新日志" in texts
    assert theme.COPYRIGHT in texts


def test_body_area_never_collapses():
    """正文区必须有固有高度，不能靠 expand 抢高度。

    回归背景：窗口较矮或展开"更多信息"时，expand=True 的正文区会被
    挤成 0 高度，用户看到的是页面背景（一片灰），以为歌词没导入进来。
    """
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    # 正文框靠 min_lines 撑出高度，而不是 expand
    assert view.body_field.multiline is True
    assert view.body_field.min_lines >= 10
    assert not view.body_field.expand, "正文框不能用 expand，否则会被挤没"
    # 页面可滚动，内容变高时不会挤掉正文
    assert view.scroll == ft.ScrollMode.ADAPTIVE


def test_import_fills_body_field():
    """导入后正文编辑框必须真的拿到歌词内容。"""
    import tempfile

    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    lrc = ("[ti:兰亭序]\n[ar:周杰伦]\n[al:魔杰座]\n"
           "[00:00.00]作词：方文山\n[00:03.00]作曲：周杰伦\n"
           "[00:06.00]编曲：钟兴民\n"
           "[00:10.00]兰亭临帖 行书如行云流水\n"
           "[00:14.00]月下门推 心细如你脚步碎")
    with tempfile.NamedTemporaryFile("w", suffix=".lrc", delete=False,
                                     encoding="utf-8") as f:
        f.write(lrc)
        path = f.name

    view.load_path(path)

    assert view.fields["lyricist"].value == "方文山"
    assert view.fields["composer"].value == "周杰伦"
    assert "兰亭临帖 行书如行云流水" in view.body_field.value, "正文框没拿到歌词"
    assert "月下门推" in view.body_field.value


# ------------------------------------------------------------------ 新版布局

LRC_SAMPLE = (
    "[ti:爱在西元前]\n[ar:周杰伦]\n[al:范特西]\n"
    "[00:00.00]作词：方文山\n[00:03.00]作曲：周杰伦\n"
    "[00:06.00]编曲：钟兴民\n"
    "[00:10.00]古巴比伦王颁布了汉谟拉比法典\n"
    "[00:14.00]刻在黑色的玄武岩\n"
    "[00:18.00]距今已经三千七百多年"
)


def _make_view_with_lrc(tmp_name="sample.lrc"):
    import tempfile
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    with tempfile.NamedTemporaryFile("w", suffix=".lrc", delete=False,
                                     encoding="utf-8") as f:
        f.write(LRC_SAMPLE)
        path = f.name
    view.load_path(path)
    return view, path


def test_top_template_card_removed():
    """原来的「歌词模板」卡片已经删掉，界面里不该再有它。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    texts = "\n".join(collect_texts(view))
    assert "歌词模板" not in texts, "歌词模板卡片还在"


def test_core_fields_moved_into_info_section():
    """作词/作曲/编曲并入「歌曲信息」区，不再单独一张卡片。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    assert set(view.fields) >= {"lyricist", "composer", "arranger"}
    texts = "\n".join(collect_texts(view))
    assert "歌曲信息" in texts


def test_import_auto_expands_info():
    """导入后「歌曲信息」必须自动展开。"""
    view, _ = _make_view_with_lrc()
    assert view.info_expanded is True
    assert view.info_body.visible is True


def test_import_fills_everything():
    view, _ = _make_view_with_lrc()
    assert view.fields["lyricist"].value == "方文山"
    assert view.fields["composer"].value == "周杰伦"
    assert view.fields["arranger"].value == "钟兴民"
    assert "汉谟拉比法典" in view.body_field.value


def test_info_summary_shows_credits_when_collapsed():
    view, _ = _make_view_with_lrc()
    assert "方文山" in view.info_summary.value
    assert "周杰伦" in view.info_summary.value


def test_toggle_info_collapse():
    view, _ = _make_view_with_lrc()
    view._toggle_info()
    assert view.info_expanded is False
    assert view.info_body.visible is False
    view._toggle_info()
    assert view.info_expanded is True
    assert view.info_body.visible is True


def test_section_saves_do_not_touch_file():
    """「保存信息」「保存歌词」只记录到文档，不能写文件。"""
    import pathlib
    view, path = _make_view_with_lrc()
    original = pathlib.Path(path).read_text(encoding="utf-8")

    view.fields["lyricist"].value = "张三"
    view._save_info_clicked()
    view.body_field.value = view.body_field.value + "\n新写的一句"
    view._save_body_clicked()

    assert pathlib.Path(path).read_text(encoding="utf-8") == original, "不该写文件"
    # 但文档里要生效
    assert view.sheet.lyricist == "张三"
    assert "新写的一句" in view.sheet.body
    assert view.dirty_info is False
    assert view.dirty_body is False


def test_commit_writes_and_overwrites_file():
    """最下面的按钮才真正覆盖原文件。"""
    import pathlib
    view, path = _make_view_with_lrc()

    view.fields["lyricist"].value = "李四"
    view._commit_clicked()          # 会弹确认框
    # 模拟用户点「确定覆盖」
    dlg = view.page.dialog
    assert dlg is not None and dlg.open is True, "覆盖前必须弹确认框"
    dlg.actions[1].on_click(None)   # 确定覆盖

    written = pathlib.Path(path).read_text(encoding="utf-8")
    assert "作词：李四" in written, "没有写回原文件"
    assert "汉谟拉比法典" in written
    assert view.dirty_info is False and view.dirty_body is False


def test_status_shows_pending_changes():
    view, path = _make_view_with_lrc()
    assert "已保存" in view.path_text.value
    view.fields["composer"].value = "王五"
    view._on_field_change("composer", "王五")
    assert "未保存" in view.path_text.value


def test_toolbar_is_on_top():
    """导入/新建/关于 在最上面，内容紧跟在下面。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    assert len(view.controls) == 5, "顶层应该是 工具条/提示/信息/正文/覆盖 五块"
    toolbar = view.controls[0]
    texts = "\n".join(collect_texts(toolbar))
    assert "导入歌词" in texts and "新建" in texts and "关于" in texts


def test_overwrite_button_visible_and_bound():
    """覆盖按钮必须独占一行、撑满宽度、且真的绑了点击事件。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    btn = view.btn_overwrite
    assert "保存到原文件并覆盖" in (btn.text or "")
    assert btn.expand is True, "不撑满宽度的话窄窗口下会被挤没"
    assert callable(btn.on_click), "按钮没绑事件，点了不会触发"
    # 独占最后一行
    assert view.controls[-1] is not None
    texts = "\n".join(collect_texts(view.controls[-1]))
    assert "保存到原文件并覆盖" in texts


def test_body_field_shows_plenty_of_lines():
    """正文框要够高，能一眼看到大半首歌词。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    # 至少 15 行，否则空着时是个小框、有内容时得一直滚
    assert view.body_field.min_lines >= 15
    # 有上限，超长文件不至于把界面撑到卡顿
    assert view.body_field.max_lines is not None
    assert view.body_field.max_lines >= 40


def test_app_renamed():
    from src import theme
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    assert theme.APP_NAME == "歌词修改工作台"
    assert "歌词模板" not in "\n".join(collect_texts(view))


# ------------------------------------------------------------------ 名字同步

def test_sync_switch_exists_and_default_on():
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    assert view.switch_sync is not None
    assert view.switch_sync.value is True, "默认应该开着"


def test_sync_credits_on_save_info():
    """点「保存信息」时，正文里对应的名字要跟着改。"""
    import tempfile
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    lrc = ("[ti:黑色幽默]\n[ar:周杰伦]\n"
           "[00:03.96]词：周杰伦\n[00:07.00]曲：周杰伦\n"
           "[00:10.00]编曲：钟兴民\n[00:15.00]难过是因为闷了很久")
    with tempfile.NamedTemporaryFile("w", suffix=".lrc", delete=False,
                                     encoding="utf-8") as f:
        f.write(lrc)
        path = f.name
    view.load_path(path)
    assert "词：周杰伦" in view.body_field.value

    # 改作词
    view.fields["lyricist"].value = "张志博"
    view._on_field_change("lyricist", "张志博")
    view._save_info_clicked()

    assert "词：张志博" in view.body_field.value, "正文里的名字没同步"
    assert "词：周杰伦" not in view.body_field.value
    assert "难过是因为闷了很久" in view.body_field.value   # 歌词没被误伤
    assert "曲：周杰伦" in view.body_field.value          # 没改的保持原样


def test_sync_switch_off_keeps_body():
    """关掉开关就不该动正文。"""
    import tempfile
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    lrc = "[00:03.96]词：周杰伦\n[00:15.00]难过是因为闷了很久"
    with tempfile.NamedTemporaryFile("w", suffix=".lrc", delete=False,
                                     encoding="utf-8") as f:
        f.write(lrc)
        path = f.name
    view.load_path(path)

    view.switch_sync.value = False
    view.fields["lyricist"].value = "张志博"
    view._on_field_change("lyricist", "张志博")
    view._save_info_clicked()

    assert "词：周杰伦" in view.body_field.value, "关了开关还改了正文"
    assert view.sheet.lyricist == "张志博"      # 但信息本身照常更新


def test_commit_also_syncs():
    """直接点最下面的覆盖按钮，也要先同步名字。"""
    import pathlib
    import tempfile
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    lrc = ("[00:03.96]词：周杰伦\n[00:07.00]曲：周杰伦\n"
           "[00:15.00]难过是因为闷了很久")
    with tempfile.NamedTemporaryFile("w", suffix=".lrc", delete=False,
                                     encoding="utf-8") as f:
        f.write(lrc)
        path = f.name
    view.load_path(path)

    view.fields["lyricist"].value = "张志博"
    view._on_field_change("lyricist", "张志博")
    view._commit_clicked()
    page.dialog.actions[1].on_click(None)      # 确定覆盖

    written = pathlib.Path(path).read_text(encoding="utf-8")
    assert "作词：张志博" in written
    assert "词：周杰伦" not in written, "旧的信息行没清掉"
    assert "难过是因为闷了很久" in written


# ------------------------------------------------------------------ 时间轴开关

def test_hide_timestamp_switch_default_off():
    """默认显示原文（含时间轴），不擅自改用户的文件。"""
    view, _ = _make_view_with_lrc()
    assert view.switch_hide_ts.value is False
    assert "[00:10.00]" in view.body_field.value


def test_hide_timestamp_switch_hides_in_ui():
    """打开开关后，界面上只剩歌词。"""
    view, _ = _make_view_with_lrc()
    view.switch_hide_ts.value = True
    view._on_hide_ts_change()
    shown = view.body_field.value
    assert "[00:10.00]" not in shown
    assert "古巴比伦王颁布了汉谟拉比法典" in shown


def test_hide_timestamp_keeps_raw_body():
    """隐藏只是显示层的事，文档里仍保留完整原文。"""
    view, _ = _make_view_with_lrc()
    view.switch_hide_ts.value = True
    view._on_hide_ts_change()
    assert "[00:10.00]" in view.sheet.body, "原文被破坏了"
    # 关掉开关，时间轴又回来了
    view.switch_hide_ts.value = False
    view._on_hide_ts_change()
    assert "[00:10.00]" in view.body_field.value


def test_edit_while_hidden_merges_timestamp_back():
    """隐藏状态下改歌词，时间轴要按行合并回去，不能丢。"""
    view, _ = _make_view_with_lrc()
    view.switch_hide_ts.value = True
    view._on_hide_ts_change()

    lines = view.body_field.value.split("\n")
    idx = next(i for i, ln in enumerate(lines) if "汉谟拉比法典" in ln)
    lines[idx] = "我改过的这一句"
    view.body_field.value = "\n".join(lines)
    view._on_body_change(type("E", (), {"control": view.body_field})())

    assert "我改过的这一句" in view.sheet.body
    assert "[00:10.00]我改过的这一句" in view.sheet.body, "时间轴丢了"


def test_export_follows_hide_switch():
    """所见即所得：界面隐藏了时间轴，导出就是纯歌词。"""
    import pathlib
    view, path = _make_view_with_lrc()

    # 默认带时间轴
    view._commit_clicked()
    view.page.dialog.actions[1].on_click(None)
    assert "[00:10.00]" in pathlib.Path(path).read_text(encoding="utf-8")

    # 打开隐藏开关后导出纯歌词
    view.switch_hide_ts.value = True
    view._on_hide_ts_change()
    view._commit_clicked()
    view.page.dialog.actions[1].on_click(None)
    written = pathlib.Path(path).read_text(encoding="utf-8")
    assert "[00:10.00]" not in written
    assert "古巴比伦王颁布了汉谟拉比法典" in written


# ------------------------------------------------------------------ 提示文案清理

def test_no_hint_texts_in_info_section():
    """信息区里不该再有"提示：..."这类说明文字。"""
    view, _ = _make_view_with_lrc()
    texts = collect_texts(view.controls[2])
    assert not [t for t in texts if t.startswith("提示")], texts


def test_no_hint_texts_anywhere():
    view, _ = _make_view_with_lrc()
    all_texts = collect_texts(view)
    assert not [t for t in all_texts if t.startswith("提示")], all_texts


# ------------------------------------------------------------------ 布局防回归

def _walk(control, out=None):
    out = [] if out is None else out
    if control is None:
        return out
    if isinstance(control, (list, tuple)):
        for c in control:
            _walk(c, out)
        return out
    out.append(control)
    for attr in ("content", "controls", "actions", "title", "subtitle", "leading"):
        child = getattr(control, attr, None)
        if child is not None and not isinstance(child, str):
            _walk(child, out)
    return out


def _row_has_expand_inside(row) -> bool:
    for c in _walk(getattr(row, "controls", [])):
        if getattr(c, "expand", None):
            return True
    return False


def test_no_row_combines_wrap_and_expand():
    """Row 不能同时用 wrap=True 和 expand=True 的子控件。

    回归背景：Flutter 的 Wrap 里不能放 Expanded，两者同时出现会让
    **整行渲染失败** —— 表现是这一行的开关和按钮凭空消失。
    """
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    offenders = []
    for c in _walk(view):
        if isinstance(c, ft.Row) and getattr(c, "wrap", False):
            if _row_has_expand_inside(c):
                offenders.append(c)
    assert not offenders, f"有 {len(offenders)} 个 Row 同时用了 wrap 和 expand"


def test_hide_ts_switch_and_save_button_both_present():
    """歌词正文那一行必须同时能看到开关和「保存歌词」按钮。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    texts = collect_texts(view.controls[3])
    assert "歌词正文" in texts
    assert any("隐藏" in t and "时间轴" in t for t in texts), "时间轴开关没显示"
    assert "保存歌词" in texts, "保存歌词按钮没显示"


def test_body_field_is_white_not_page_gray():
    """正文框要显式填白底，不能透出页面底色（会被看成一大片灰）。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)
    field = view.body_field
    assert field.filled is True
    assert field.fill_color in (ft.Colors.WHITE, "#FFFFFF")


# ------------------------------------------------------------------ 导入不残留

FULL_SONG = (
    "[ti:忘情牛肉面]\n[ar:马健涛]\n[al:忘情牛肉面]\n"
    "[00:00.00]作词：马健涛\n[00:03.00]作曲：马健涛\n[00:06.00]编曲：马健涛\n"
    "[00:09.00]制作人：蔡徐坤 KUN/Jacob Ray\n"
    "[00:12.00]混音：马健涛\n[00:15.00]母带：马健涛\n"
    "[00:18.00]出品：羡然文化\n[00:21.00]歌词第一句"
)

SPARSE_SONG = (
    "[ti:晴天]\n[ar:周杰伦]\n[al:叶惠美]\n"
    "[00:00.00]作词：方文山\n[00:03.00]作曲：周杰伦\n[00:06.00]编曲：蔡科俊\n"
    "[00:10.00]故事的小黄花"
)


def _write_tmp(content, name):
    import tempfile
    d = tempfile.mkdtemp()
    path = __import__("pathlib").Path(d) / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_switching_songs_clears_extra_fields():
    """换歌后，上一首的制作人/混音/母带/出品不能留下来。

    回归背景：导入时复用了上一首歌的 sheet 对象，自定义字段只增不减，
    导致第二首歌的信息栏里混着第一首歌的制作团队，全乱了。
    """
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    view.load_path(_write_tmp(FULL_SONG, "忘情牛肉面.lrc"))
    assert "制作人" in view.sheet.extras, "第一首歌该有制作人"
    assert "出品" in view.sheet.extras

    view.load_path(_write_tmp(SPARSE_SONG, "晴天.lrc"))

    leaks = [k for k in ("制作人", "混音", "母带", "出品") if k in view.sheet.extras]
    assert not leaks, f"上一首歌的信息残留了：{leaks}"
    assert view.sheet.title == "晴天"
    assert view.sheet.lyricist == "方文山"


def test_switching_songs_clears_missing_core_fields():
    """新歌里没写到的字段，不能沿用上一首的值。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    view.load_path(_write_tmp(FULL_SONG, "忘情牛肉面.lrc"))
    assert view.sheet.composer == "马健涛"

    # 第二首没有作曲信息
    view.load_path(_write_tmp("[ti:晴天]\n[00:10.00]歌词", "晴天.lrc"))
    assert view.sheet.composer == "", "上一首的作曲残留了"
    assert view.sheet.title == "晴天"


def test_switching_songs_replaces_body():
    """正文也要整体替换，不能拼接。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    view.load_path(_write_tmp(FULL_SONG, "a.lrc"))
    view.load_path(_write_tmp(SPARSE_SONG, "b.lrc"))
    assert "歌词第一句" not in view.sheet.body, "上一首的歌词残留了"
    assert "故事的小黄花" in view.sheet.body


def test_new_song_clears_extra_fields():
    """点「新建」也要清空，不能留着上一首的信息。"""
    page = make_page()
    view = EditorView(page, ft.FilePicker(), ft.FilePicker(),
                      notify=lambda *a, **k: None, open_about=lambda *a: None)

    view.load_path(_write_tmp(FULL_SONG, "a.lrc"))
    assert view.sheet.extras

    view._reset_sheet()
    assert view.sheet.extras == {}, "新建后还有残留字段"
    assert view.sheet.lyricist == ""
    assert view.sheet.body == ""


# ------------------------------------------------------------------ 打包脚本

def test_build_scripts_do_not_use_invalid_artifact_flag():
    """flet build 没有 --artifact 参数，用了会直接报错退出（码 2）。"""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for rel in ("build_android.sh", ".github/workflows/build.yml"):
        text = (root / rel).read_text(encoding="utf-8")
        code = "\n".join(ln for ln in text.splitlines()
                         if not ln.strip().startswith("#"))
        assert "--artifact" not in code, f"{rel} 里还有无用的 --artifact 参数"


def test_build_bat_avoids_raw_flet_command():
    """bat 脚本不能直接敲 flet 命令。

    pip 把 flet 脚本装到 Scripts 目录，那个目录常常不在 PATH 里，
    直接敲会报「'flet' 不是内部或外部命令」。
    必须用 python -c 调用 flet.cli.main 绕开 PATH。
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    text = (root / "打包成exe.bat").read_bytes().decode("gbk")
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    code = [ln for ln in lines if ln and not ln.startswith(("REM", "@", "echo"))]
    offenders = [ln for ln in code
                 if ln.startswith("flet ") or ln.startswith("flet\t")]
    assert not offenders, f"还在直接调用 flet 命令：{offenders}"
    assert "flet.cli" in text, "应该改用 python -c 调 flet.cli.main"


# ------------------------------------------------------------------ 打包脚本

def test_build_script_has_flutter_detection():
    """打包脚本必须能检测 Flutter，没有时自动换路线。

    回归背景：默认走 `flet build windows`，而它**要求本机装了 Flutter SDK**。
    用户机器上没装，直接报
    "flutter command is not available in PATH. Install Flutter SDK."
    脚本应该检测到这一点，自动改用不依赖 Flutter 的 PyInstaller 路线。
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    text = (root / "打包成exe.bat").read_bytes().decode("gbk")

    assert "where flutter" in text, "没有检测 Flutter"
    assert "pack main.py" in text, "没有不需要 Flutter 的备选路线"
    assert "build windows" in text, "原生路线丢了"


def test_build_script_labels_are_complete():
    """bat 里 goto 的目标标签必须都存在，否则会跳到不存在的位置。"""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    text = (root / "打包成exe.bat").read_bytes().decode("gbk").replace("\r\n", "\n")

    labels = set(re.findall(r"^:(\w+)$", text, re.M))
    gotos = set(re.findall(r"\bgoto\s+(\w+)", text))
    assert labels, "没解析到任何标签"
    assert not (gotos - labels), f"跳到了不存在的标签：{gotos - labels}"


def test_build_script_uses_ico_icon():
    """Windows 上 PyInstaller 只认 .ico，传 .png 可能失败。"""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    text = (root / "打包成exe.bat").read_bytes().decode("gbk")
    assert "icon.ico" in text, "应该优先使用 .ico 图标"
    assert (root / "assets" / "icon.ico").exists(), "icon.ico 文件不存在"
