"""关于页面（右侧抽屉内容）。

从屏幕右边缘滑出，展示版本号、作者、QQ、开源信息与更新日志。
"""

from __future__ import annotations

import flet as ft

from .. import theme


def _info_row(label: str, value: str, on_more=None) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Text(label, size=12, color=theme.TEXT_SUB, width=68),
                ft.Text(value, size=13, color=theme.TEXT_MAIN, weight=ft.FontWeight.W_500,
                        expand=True, selectable=True),
                ft.IconButton(
                    icon=ft.Icons.COPY_ALL_ROUNDED,
                    icon_size=16,
                    tooltip=f"复制{label}",
                    visible=on_more is not None,
                    on_click=on_more,
                ) if on_more else ft.Container(width=0),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=16, vertical=6),
    )


def _section_title(text: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=12, weight=ft.FontWeight.BOLD, color=theme.PRIMARY),
        padding=ft.padding.only(left=16, right=16, top=14, bottom=4),
    )


def build_about_drawer(page: ft.Page) -> ft.NavigationDrawer:
    """构造右侧抽屉。返回后赋给 page.end_drawer 即可支持右滑唤出。"""

    def copy_qq(_=None):
        page.set_clipboard(theme.AUTHOR_QQ)
        _toast(page, f"已复制 QQ：{theme.AUTHOR_QQ}")

    def open_github(_=None):
        page.launch_url(theme.GITHUB_URL)

    def open_releases(_=None):
        page.launch_url(theme.RELEASES_URL)

    def open_issues(_=None):
        page.launch_url(theme.ISSUES_URL)

    changelog = ft.Column(spacing=8)
    for version, date, items in theme.CHANGELOG:
        changelog.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(f"v{version}", size=13, weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_MAIN),
                                ft.Text(date, size=11, color=theme.TEXT_SUB),
                            ],
                            spacing=10,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text("· " + item, size=12, color=theme.TEXT_SUB)
                                for item in items
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=4,
                ),
                padding=ft.padding.only(left=16, right=16, bottom=6),
            )
        )

    content = ft.Column(
        controls=[
            # 头部：图标 + 名称 + 版本
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.MUSIC_NOTE_ROUNDED, size=34, color="white"),
                            width=68, height=68,
                            border_radius=34,
                            bgcolor=theme.PRIMARY,
                            alignment=ft.alignment.center,
                        ),
                        ft.Text(theme.APP_NAME, size=19, weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_MAIN),
                        ft.Text(theme.APP_NAME_EN, size=12, color=theme.TEXT_SUB),
                        ft.Container(
                            content=ft.Text(
                                f"v{theme.APP_VERSION}  (Build {theme.APP_BUILD})",
                                size=12, color="white", weight=ft.FontWeight.W_500),
                            bgcolor=theme.PRIMARY,
                            border_radius=10,
                            padding=ft.padding.symmetric(horizontal=10, vertical=3),
                            margin=ft.margin.only(top=4),
                        ),
                        ft.Text(theme.APP_DESC, size=12, color=theme.TEXT_SUB,
                                text_align=ft.TextAlign.CENTER),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),
                padding=ft.padding.symmetric(vertical=18, horizontal=14),
                width=float("inf"),
            ),
            ft.Divider(height=1, color=theme.BORDER),
            # 作者信息
            _section_title("关于作者"),
            _info_row("作者", theme.AUTHOR),
            _info_row("QQ", theme.AUTHOR_QQ, on_more=copy_qq),
            _info_row("技术栈", theme.TECH_STACK),
            _info_row("开源协议", theme.LICENSE_NAME),
            # 链接
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.TextButton("GitHub 仓库", icon=ft.Icons.CODE_ROUNDED, on_click=open_github),
                        ft.TextButton("检查更新", icon=ft.Icons.SYSTEM_UPDATE_ROUNDED, on_click=open_releases),
                        ft.TextButton("反馈问题", icon=ft.Icons.BUG_REPORT_ROUNDED, on_click=open_issues),
                    ],
                    wrap=True,
                    spacing=2,
                ),
                padding=ft.padding.only(left=6),
            ),
            ft.Divider(height=1, color=theme.BORDER),
            _section_title("更新日志"),
            changelog,
            ft.Container(
                content=ft.Text(
                    f"{theme.COPYRIGHT}\n用 Python 手写的小工具，欢迎 Star ⭐",
                    size=11, color=theme.TEXT_SUB, text_align=ft.TextAlign.CENTER),
                padding=ft.padding.symmetric(vertical=18, horizontal=16),
            ),
        ],
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    return ft.NavigationDrawer(
        controls=[
            ft.Container(content=content, width=310, expand=True, bgcolor=theme.DRAWER_BG)
        ],
        bgcolor=theme.DRAWER_BG,
        elevation=8,
    )


def _toast(page: ft.Page, message: str) -> None:
    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color="white"),
        bgcolor=theme.PRIMARY,
        behavior=ft.SnackBarBehavior.FLOATING,
        duration=1800,
    )
    page.snack_bar.open = True
    page.update()
