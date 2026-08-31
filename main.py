"""歌词修改工作台 —— 主入口。

运行：
    pip install -r requirements.txt
    python main.py            # 桌面窗口
    flet run main.py          # 热重载开发
    python main.py --web      # 浏览器里跑（方便手机同局域网访问）
"""

from __future__ import annotations

import sys

import flet as ft

from src import theme
from src.storage import load_settings, save_settings
from src.ui.about import build_about_drawer
from src.ui.editor import EditorView


def main(page: ft.Page):
    page.title = f"{theme.APP_NAME} v{theme.APP_VERSION}"
    page.bgcolor = theme.PAGE_BG
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = ft.padding.symmetric(horizontal=14, vertical=10)
    # 不指定自定义字体：远程字体地址一旦失效会导致文字渲染异常，
    # 直接用系统默认字体最稳，中文显示完全没问题。
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(primary=theme.PRIMARY, secondary=theme.ACCENT),
    )

    settings = load_settings()

    # ---------------------------------------------------------- 通知
    def notify(message: str, color: str = theme.PRIMARY):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color="white", selectable=True),
            bgcolor=color,
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=2600,
        )
        page.snack_bar.open = True
        page.update()

    # ---------------------------------------------------------- 文件选择器
    pick_dialog = ft.FilePicker()
    save_dialog = ft.FilePicker()
    page.overlay.extend([pick_dialog, save_dialog])

    # ---------------------------------------------------------- 关于抽屉（右滑）
    about_drawer = build_about_drawer(page)
    page.end_drawer = about_drawer

    def open_about(_=None):
        about_drawer.open = True
        about_drawer.update()

    # ---------------------------------------------------------- 主视图
    editor = EditorView(
        page=page,
        pick_dialog=pick_dialog,
        save_dialog=save_dialog,
        notify=notify,
        open_about=open_about,
    )
    pick_dialog.on_result = editor.on_pick_result
    save_dialog.on_result = editor.on_save_result
    editor.include_optional = bool(settings.get("include_optional", False))

    # ---------------------------------------------------------- 顶栏
    def open_recent(e):
        recent = editor.get_recent_menu()
        if not recent:
            notify("还没有打开过文件")
            return

        def close(_=None):
            dlg.open = False
            page.update()

        def pick(path):
            return lambda _: (close(), editor.load_path(path))

        dlg = ft.AlertDialog(
            title=ft.Text("最近打开", size=15),
            content=ft.Column(
                controls=[
                    ft.ListTile(title=ft.Text(p.split("/")[-1].split("\\")[-1], size=13),
                                subtitle=ft.Text(p, size=10, color=theme.TEXT_SUB),
                                dense=True, on_click=pick(p))
                    for p in recent
                ],
                spacing=2, tight=True, scroll=ft.ScrollMode.AUTO, height=280,
            ),
            actions=[ft.TextButton("关闭", on_click=close)],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def toggle_export_header(e):
        editor.include_optional = e.control.value
        settings["include_optional"] = e.control.value
        save_settings(settings)
        notify("导出时" + ("附带歌名/制作人等更多信息" if e.control.value
                        else "只保留 作词/作曲/编曲 三行"))

    def show_settings(e):
        switch_header = ft.Switch(
            label="导出时附带歌名 / 制作人等更多信息",
            value=editor.include_optional, on_change=toggle_export_header)

        def close(_=None):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("设置", size=15),
            content=ft.Container(
                content=ft.Column(controls=[
                    switch_header,
                ], spacing=6, tight=True),
                width=360,
            ),
            actions=[ft.TextButton("关闭", on_click=close)],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.MUSIC_NOTE_ROUNDED, color=theme.PRIMARY),
        leading_width=40,
        title=ft.Column(controls=[
            ft.Text(theme.APP_NAME, size=16, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
            ft.Text(f"v{theme.APP_VERSION} · {theme.APP_DESC}", size=10, color=theme.TEXT_SUB),
        ], spacing=0, tight=True),
        center_title=False,
        bgcolor=ft.Colors.with_opacity(0.96, ft.Colors.WHITE),
        elevation=0.5,
        actions=[
            ft.IconButton(icon=ft.Icons.HISTORY_ROUNDED, tooltip="最近打开", on_click=open_recent),
            ft.IconButton(icon=ft.Icons.SETTINGS_ROUNDED, tooltip="设置", on_click=show_settings),
            ft.IconButton(icon=ft.Icons.INFO_OUTLINE_ROUNDED, tooltip="关于（右滑也可）",
                          on_click=open_about),
        ],
    )

    page.add(editor)
    page.update()

    # 桌面端快捷键
    def on_keyboard(e: ft.KeyboardEvent):
        if e.ctrl and e.key.lower() == "s":
            editor._commit_clicked()          # Ctrl+S = 写回原文件
        elif e.ctrl and e.key.lower() == "o":
            editor._import_clicked()
        elif e.key == "F1":
            open_about()

    page.on_keyboard_event = on_keyboard
    notify("欢迎！导入歌词后会自动展开「歌曲信息」，改完点最下方写入文件 ✨")


def run():
    """入口：支持 --web 参数在浏览器 / 手机里访问。"""
    args = [a for a in sys.argv[1:]]
    if "--web" in args:
        args.remove("--web")
        ft.app(target=main, view=ft.WEB_BROWSER, port=8550)
    else:
        ft.app(target=main)


if __name__ == "__main__":
    run()
