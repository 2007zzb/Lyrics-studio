"""契约测试：确认代码里用到的 Flet API 在当前版本中真实存在。

目的：Flet 版本迭代很快，这个测试能在升级依赖时第一时间发现 API 失效。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft  # noqa: E402


PAGE_MEMBERS = [
    "title", "bgcolor", "theme_mode", "padding", "fonts", "theme",
    "overlay", "end_drawer", "drawer", "appbar", "dialog", "snack_bar",
    "add", "update", "set_clipboard", "launch_url", "run_thread",
    "on_keyboard_event", "width", "height",
]

CONTROLS = [
    "Column", "Row", "ResponsiveRow", "Container", "Text", "TextField",
    "Icon", "IconButton", "ElevatedButton", "OutlinedButton",
    "FilledTonalButton", "TextButton", "Divider", "Card",
    "NavigationDrawer", "AppBar", "AlertDialog", "SnackBar",
    "GestureDetector", "ExpansionTile", "ListTile", "Dropdown",
    "Switch", "FilePicker", "PopupMenuButton",
]

ENUMS = [
    "Colors", "Icons", "FontWeight", "TextAlign", "ScrollMode",
    "CrossAxisAlignment", "MainAxisAlignment", "SnackBarBehavior",
    "ThemeMode", "border", "padding", "margin", "alignment", "ButtonStyle",
]


def test_page_members_exist():
    members = dir(ft.Page)
    missing = [m for m in PAGE_MEMBERS if m not in members]
    assert not missing, f"ft.Page 缺少成员：{missing}"


def test_controls_exist():
    missing = [c for c in CONTROLS if not hasattr(ft, c)]
    assert not missing, f"flet 缺少控件：{missing}"


def test_enums_exist():
    missing = [e for e in ENUMS if not hasattr(ft, e)]
    assert not missing, f"flet 缺少：{missing}"


def test_colors_helpers():
    assert hasattr(ft.Colors, "with_opacity")
    assert ft.Colors.with_opacity(0.5, "#4F46E5")


def test_main_module_importable():
    """main.py 必须能被导入，且暴露 run()。"""
    import main

    assert callable(main.run)
