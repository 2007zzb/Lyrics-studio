"""编辑器主界面：歌曲信息（可折叠）+ 歌词正文 + 分级保存。

自上而下的布局：

    1. 导入结果提示条
    2. 歌曲信息（作词 / 作曲 / 编曲 / 歌名…）     右边：保存信息
    3. 歌词正文                                  右边：保存歌词
    4. 底部：导入 / 新建 / 关于  ＋  【保存到原文件并覆盖】

保存分两级 —— 上面的「保存信息」「保存歌词」只是把这一段的修改
记进当前文档，不会动硬盘上的文件；只有最下面的
「保存到原文件并覆盖」才真正写回原文件。

原来顶部那张「歌词模板」卡片已经删掉，作词 / 作曲 / 编曲
并入第 2 区的「歌曲信息」，导入后会自动展开。
"""

from __future__ import annotations

import os
from typing import Dict, List

import flet as ft

from .. import theme
from ..model import LyricSheet, LABELS, CORE_FIELDS, OPTIONAL_FIELDS, EXTRA_FIELD_HINTS
from ..parser import LRC_TIME_RE, parse_lyrics, sync_credits_into_body
from ..storage import push_recent, read_text_file, write_text_file


class EditorView(ft.Column):
    """歌词编辑主视图。"""

    def __init__(
        self,
        page: ft.Page,
        pick_dialog: ft.FilePicker,
        save_dialog: ft.FilePicker,
        notify,
        open_about,
    ):
        # scroll 很关键：页面内容一旦变高（展开"歌曲信息"、窗口比较小），
        # 正文区如果还用 expand 去抢高度，就会被挤成 0 高度而彻底看不见。
        # 改成可滚动后，正文区保持自己的固有高度，永远不会被压缩消失。
        super().__init__(expand=True, spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
        self.page = page
        self.pick_dialog = pick_dialog
        self.save_dialog = save_dialog
        self.notify = notify
        self.open_about = open_about

        self.sheet = LyricSheet()
        self.current_path: str | None = None
        self.include_optional = False
        # 导入时始终保留原文（含 [00:12.34] 时间轴）。
        # 时间轴去不去掉交给正文区那个开关，所见即所得。
        self.strip_timestamps = False
        self.hide_timestamps = False

        # 两段各自记录"改过但还没点保存"
        self.dirty_info = False
        self.dirty_body = False

        self.fields: Dict[str, ft.TextField] = {}
        self.extra_fields: Dict[str, ft.TextField] = {}
        self._swipe_dx = 0.0
        self.info_expanded = False

        self._build_controls()
        self._compose()

    # -------------------------------------------------------------- 构建
    def _build_controls(self):
        for name in CORE_FIELDS + OPTIONAL_FIELDS:
            self.fields[name] = ft.TextField(
                label=LABELS[name],
                value="",
                dense=True,
                text_size=14,
                border_radius=10,
                border_color=theme.BORDER,
                focused_border_color=theme.PRIMARY,
                content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
                on_change=lambda e, n=name: self._on_field_change(n, e.control.value),
            )

        self.hint_text = ft.Text(theme.TIP_EMPTY, size=12, color=theme.TEXT_SUB,
                                 selectable=True, expand=True)
        self.hint_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=theme.SUCCESS),
                    self.hint_text,
                ],
                spacing=8,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, theme.SUCCESS),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            visible=False,
        )

        self.stats_text = ft.Text("", size=12, color=theme.TEXT_SUB)
        # 显式指定白底 + 描边。
        # Flet 的 TextField 默认不填色，空白时会透出页面底色（浅灰），
        # 看起来就像"一大片灰色区域"，很容易被误认为没内容或没渲染。
        # 卡片标题已经写了"歌词正文"，这里不再重复加 label。
        # 高度：最少 18 行（空着时不会是个小框），
        # 内容多时自动长高，最多 60 行 —— 绝大多数歌词文件都能整首看全，
        # 不用在框里滚来滚去。再长才开始内部滚动，避免超长文件拖慢界面。
        self.body_field = ft.TextField(
            hint_text=theme.TIP_TEMPLATE,
            multiline=True,
            min_lines=18,
            max_lines=60,
            filled=True,
            fill_color=ft.Colors.WHITE,
            bgcolor=ft.Colors.WHITE,
            border=ft.InputBorder.OUTLINE,
            text_size=14,
            border_radius=10,
            border_color=theme.BORDER,
            focused_border_color=theme.PRIMARY,
            content_padding=12,
            on_change=self._on_body_change,
        )
        self.path_text = ft.Text("没有打开文件", size=11, color=theme.TEXT_SUB)

    def _compose(self):
        self.controls = [
            self._toolbar_row(),      # 导入 / 新建 / 关于 放最上面
            self.hint_bar,
            self._info_card(),        # 歌曲信息（导入后自动展开）
            self._body_card(),        # 歌词正文
            self._commit_row(),       # 最下面：整行的「保存到原文件并覆盖」
        ]

    # -------------------------------------------------------------- 区块 0：顶部工具条
    def _toolbar_row(self):
        self.btn_import = ft.ElevatedButton(
            "导入歌词", icon=ft.Icons.FILE_OPEN_ROUNDED, on_click=self._import_clicked)
        self.btn_new = ft.OutlinedButton(
            "新建", icon=ft.Icons.NOTE_ADD_ROUNDED, on_click=self._new_clicked)
        self.btn_about = ft.OutlinedButton(
            "关于", icon=ft.Icons.INFO_OUTLINE_ROUNDED,
            on_click=lambda e: self.open_about())

        # 不用 wrap + expand 混用：那种组合在窄窗口下会把右边的
        # 控件挤到看不见。这里用固定顺序的一行，窗口再窄也只是横向排开。
        return ft.Row(
            controls=[
                self.btn_import, self.btn_new, self.btn_about,
                ft.Container(expand=True),
                self.path_text,
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # -------------------------------------------------------------- 区块 1：歌曲信息
    def _info_card(self):
        """可折叠的歌曲信息区，导入后自动展开。"""
        self.info_toggle_icon = ft.Icon(
            ft.Icons.EXPAND_MORE_ROUNDED, size=20, color=theme.TEXT_SUB)
        self.info_summary = ft.Text(
            "未填写", size=11, color=theme.TEXT_SUB, expand=True, selectable=True)

        self.btn_save_info = ft.ElevatedButton(
            "保存信息", icon=ft.Icons.CHECK_ROUNDED,
            on_click=self._save_info_clicked, height=34)

        # 标题区：点击折叠/展开，右滑打开「关于」。
        # 外面套一层 Container(expand=True) 是必须的 ——
        # GestureDetector 直接放进 Row 里可能被算成 0 尺寸而不显示。
        title_area = ft.GestureDetector(
            content=ft.Container(
                content=ft.Row(controls=[
                    self.info_toggle_icon,
                    ft.Column(controls=[
                        ft.Text("歌曲信息（作词 / 作曲 / 编曲…）", size=13,
                                weight=ft.FontWeight.W_500, color=theme.TEXT_MAIN),
                        self.info_summary,
                    ], spacing=0, expand=True),
                ], spacing=8),
                expand=True,
                padding=ft.padding.symmetric(vertical=4),
            ),
            on_tap=self._toggle_info,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
        )

        header = ft.Row(controls=[
            title_area,
            self.btn_save_info,
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.info_body = ft.Column(controls=self._info_body_controls(),
                                   spacing=8, visible=False)

        return ft.Container(
            content=ft.Column(controls=[header, self.info_body], spacing=0),
            bgcolor=theme.CARD_BG,
            border_radius=theme.RADIUS,
            border=ft.border.all(1, theme.BORDER),
            padding=theme.CARD_PADDING,
        )

    def _info_body_controls(self) -> list:
        def grid(names):
            return ft.ResponsiveRow(
                controls=[
                    ft.Container(content=self.fields[n],
                                 col={"xs": 12, "sm": 12, "md": 4},
                                 padding=ft.padding.only(bottom=2))
                    for n in names
                ],
                spacing=10, run_spacing=8,
            )

        self.new_extra_name = ft.TextField(
            hint_text="再加一项，如：制作人 / 混音 / 吉他",
            dense=True, text_size=12, border_radius=8,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            expand=True,
        )
        self.extra_rows = ft.Column(spacing=6)

        add_row = ft.Row(controls=[
            ft.Container(content=self.new_extra_name, expand=True),
            ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                          icon_color=theme.PRIMARY,
                          tooltip="添加自定义字段",
                          on_click=self._add_extra_field),
            ft.IconButton(icon=ft.Icons.ARROW_DROP_DOWN_CIRCLE_OUTLINED,
                          icon_color=theme.TEXT_SUB,
                          tooltip="快速选择常见字段",
                          on_click=self._quick_extra_menu),
        ], spacing=4)

        # 名字同步开关：改了上面的作词/作曲/编曲，正文里
        # "词：周杰伦" 这类行要不要跟着改。默认开着，这是最常用的需求。
        self.switch_sync = ft.Switch(
            label="改信息时，同步更新歌词里的名字",
            value=True,
            active_color=theme.PRIMARY,
            label_style=ft.TextStyle(size=12, color=theme.TEXT_MAIN),
            on_change=self._on_sync_switch_change,
        )

        return [
            grid(CORE_FIELDS),                 # 作词 / 作曲 / 编曲
            grid(OPTIONAL_FIELDS),             # 歌名 / 演唱 / 专辑
            ft.Divider(height=1, color=theme.BORDER),
            self.extra_rows,
            add_row,
            self.switch_sync,
        ]

    def _toggle_info(self, e=None):
        self._set_info_expanded(not self.info_expanded)

    def _set_info_expanded(self, expanded: bool):
        self.info_expanded = expanded
        self.info_body.visible = expanded
        self.info_toggle_icon.name = (
            ft.Icons.EXPAND_LESS_ROUNDED if expanded
            else ft.Icons.EXPAND_MORE_ROUNDED)
        self._safe_update()

    # -------------------------------------------------------------- 区块 2：歌词正文
    def _body_card(self):
        # 不用 expand：让正文区保持固有高度，页面整体可滚动。
        # 高度定在 10 行——再高就是一个占满屏幕的大空框，没什么用。
        self.btn_save_body = ft.ElevatedButton(
            "保存歌词", icon=ft.Icons.CHECK_ROUNDED,
            on_click=self._save_body_clicked, height=34)

        # 打开后只显示纯歌词，[00:12.34] 这些时间轴在界面上隐去。
        # 注意只是**显示**上隐藏，文档里仍保留完整原文，
        # 关掉开关时间轴就回来了。
        self.switch_hide_ts = ft.Switch(
            label="隐藏 [00:00.000] 时间轴",
            value=False,
            active_color=theme.PRIMARY,
            label_style=ft.TextStyle(size=12, color=theme.TEXT_MAIN),
            on_change=self._on_hide_ts_change,
        )

        # 注意：这里绝不能用 wrap=True。
        # Flutter 的 Wrap 里不能放 Expanded（撑满剩余宽度的控件），
        # 两者同时出现会让整行渲染失败，开关和按钮会凭空消失。
        # 所以标题行保持普通 Row，时间轴开关单独放一行。
        return ft.Container(
            content=ft.Column(controls=[
                ft.Row(controls=[
                    ft.Text("歌词正文", size=14, weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_MAIN),
                    ft.Container(expand=True),
                    self.stats_text,
                    self.btn_save_body,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(controls=[self.switch_hide_ts], spacing=0),
                self.body_field,
            ], spacing=8),
            bgcolor=theme.CARD_BG,
            border_radius=theme.RADIUS,
            border=ft.border.all(1, theme.BORDER),
            padding=theme.CARD_PADDING,
        )

    # -------------------------------------------------------------- 时间轴显示
    def _display_body(self) -> str:
        """按开关状态，算出编辑框里应该显示什么。"""
        raw = self.sheet.body or ""
        if not self.hide_timestamps:
            return raw
        return "\n".join(
            LRC_TIME_RE.sub("", ln).rstrip() for ln in raw.split("\n")
        )

    def _merge_edited_body(self, edited: str) -> str:
        """把隐藏模式下的编辑结果，按行把时间轴拼回原文。

        去掉时间轴是逐行进行的、行数不变，所以可以一一对应地还原：
        第 i 行的时间轴 + 用户改完的第 i 行内容。
        这样用户在"只看歌词"的状态下改词，切回显示时间轴时它们还在。

        幂等：如果某一行本来就带时间轴（比如刚切换开关、界面还没刷新），
        就原样保留，不会重复叠加。
        """
        if not self.hide_timestamps:
            return edited
        origin = (self.sheet.body or "").split("\n")
        result: List[str] = []
        for i, line in enumerate(edited.split("\n")):
            if LRC_TIME_RE.match(line):        # 已经有时间轴了，别再加
                result.append(line)
                continue
            timestamp = ""
            if i < len(origin):
                m = LRC_TIME_RE.match(origin[i])
                if m:
                    timestamp = m.group(0)
            result.append(timestamp + line)
        return "\n".join(result)

    def _on_hide_ts_change(self, e=None):
        """切换开关：先用旧状态收进编辑内容，再按新状态重新渲染。"""
        new_value = bool(e.control.value) if e is not None \
            else bool(self.switch_hide_ts.value)
        # 注意顺序：先按**旧**状态把框里的内容合并回原文
        self.sheet.body = self._merge_edited_body(self.body_field.value or "")
        self.hide_timestamps = new_value
        self.body_field.value = self._display_body()
        self._safe_update()

    # -------------------------------------------------------------- 区块 3：写回原文件
    def _commit_row(self):
        """整行的大按钮，独占一行，保证一定看得见、点得到。"""
        self.btn_overwrite = ft.ElevatedButton(
            "保存到原文件并覆盖",
            icon=ft.Icons.SAVE_ALT_ROUNDED,
            on_click=self._commit_clicked,
            height=46,
            expand=True,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.RED_600,
            ),
        )
        return ft.Container(
            content=ft.Row(controls=[self.btn_overwrite], spacing=0),
            padding=ft.padding.only(top=2, bottom=8),
        )

    # -------------------------------------------------------------- 数据同步
    def _on_field_change(self, name: str, value: str):
        self.sheet.set(name, value)
        self.dirty_info = True
        self._update_info_summary()
        self._update_status()

    def _on_body_change(self, e):
        self.sheet.body = self._merge_edited_body(e.control.value)
        self.dirty_body = True
        self._update_stats()
        self._update_status()

    def _on_extra_change(self, key: str, e):
        self.sheet.extras[key] = e.control.value
        self.dirty_info = True
        self._update_status()

    def _safe_update(self, control=None):
        """刷新界面，但绝不因为一次刷新失败就让整个程序崩掉。"""
        # 整体刷新时优先用 page.update()：这是 Flet 里最可靠的刷新方式，
        # 能保证输入框的新值一定同步到界面；局部刷新偶尔会漏掉子控件。
        try:
            if control is None and self.page:
                self.page.update()
            else:
                (control or self).update()
        except Exception:
            try:
                if self.page:
                    self.page.update()
            except Exception:
                pass

    def _update_stats(self):
        st = self.sheet.stats()
        self.stats_text.value = f"{st['paragraphs']} 段 · {st['lines']} 行 · {st['chars']} 字"
        self._safe_update(self.stats_text)

    def _update_info_summary(self):
        """折叠状态下也能一眼看到作词 / 作曲 / 编曲。"""
        parts = []
        for name in CORE_FIELDS:
            value = (self.sheet.get(name) or "").strip()
            parts.append(f"{LABELS[name]}：{value}" if value else f"{LABELS[name]}：未填")
        self.info_summary.value = "  ·  ".join(parts)
        self._safe_update(self.info_summary)

    def _update_status(self):
        """底部状态：显示当前文件，以及有没有改了没保存的部分。"""
        if not self.current_path:
            self.path_text.value = "没有打开文件"
            self.path_text.color = theme.TEXT_SUB
        else:
            name = os.path.basename(self.current_path)
            pending = []
            if self.dirty_info:
                pending.append("信息未保存")
            if self.dirty_body:
                pending.append("歌词未保存")
            if pending:
                self.path_text.value = f"{name}（{'、'.join(pending)}）"
                self.path_text.color = theme.WARNING
            else:
                self.path_text.value = f"{name}（已保存）"
                self.path_text.color = theme.SUCCESS
        self._safe_update(self.path_text)

    def refresh(self):
        """把 sheet 的数据刷回界面。"""
        for name, control in self.fields.items():
            control.value = self.sheet.get(name)
        # 按开关状态渲染：隐藏模式下正文框里显示的是纯歌词
        self.body_field.value = self._display_body()
        self._render_extras()
        self._update_stats()
        self._update_info_summary()
        self._safe_update()

    def _render_extras(self):
        self.extra_rows.controls = []
        for key, value in list(self.sheet.extras.items()):
            field = ft.TextField(
                value=value, dense=True, text_size=13, border_radius=8,
                content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
                on_change=lambda e, k=key: self._on_extra_change(k, e),
            )
            self.extra_fields[key] = field
            self.extra_rows.controls.append(
                ft.Row(controls=[
                    ft.Text(key, size=12, color=theme.TEXT_SUB, width=72),
                    ft.Container(content=field, expand=True),
                    ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                  icon_color=ft.Colors.RED_400, icon_size=18,
                                  tooltip="删除该字段",
                                  on_click=lambda e, k=key: self._remove_extra(k)),
                ], spacing=6)
            )

    def _add_extra_field(self, e=None, name: str = ""):
        name = (name or self.new_extra_name.value or "").strip()
        if not name:
            self.notify("先填一个字段名，例如：制作人")
            return
        if len(name) > 12:
            name = name[:12]
        self.sheet.extras.setdefault(name, "")
        self.new_extra_name.value = ""
        self.dirty_info = True
        self._render_extras()
        self._safe_update()
        self.notify(f"已添加字段：{name}")

    def _remove_extra(self, key: str):
        self.sheet.extras.pop(key, None)
        self.dirty_info = True
        self._render_extras()
        self._safe_update()

    def _quick_extra_menu(self, e):
        def close(_=None):
            dlg.open = False
            self.page.update()

        options = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=260)
        for hint in EXTRA_FIELD_HINTS:
            if hint in self.sheet.extras:
                continue
            options.controls.append(
                ft.ListTile(
                    title=ft.Text(hint, size=13),
                    dense=True,
                    on_click=lambda _, h=hint: (close(), self._add_extra_field(name=h)),
                )
            )
        dlg = ft.AlertDialog(
            title=ft.Text("选择字段", size=15),
            content=options,
            actions=[ft.TextButton("关闭", on_click=close)],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    # -------------------------------------------------------------- 手势
    def _on_pan_update(self, e):
        self._swipe_dx += e.dx or 0

    def _on_pan_end(self, e):
        dx, self._swipe_dx = self._swipe_dx, 0.0
        if dx > 55:          # 右滑 → 关于
            self.open_about()
        elif dx < -55:       # 左滑 → 写回原文件
            self._commit_clicked(None)

    # -------------------------------------------------------------- 导入
    def _import_clicked(self, e=None):
        self.pick_dialog.pick_files(
            allow_multiple=False,
            allowed_extensions=["txt", "lrc", "md", "csv"],
            dialog_title="选择歌词文件",
        )

    def on_pick_result(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return
        path = e.files[0].path
        if not path:
            self.notify("这个文件拿不到路径，请换个方式导入")
            return
        old_body = (self.sheet.body or "").strip()
        try:
            text = read_text_file(path)
            result = parse_lyrics(
                text,
                strip_timestamps=self.strip_timestamps,
                # 关键：必须用一张**全新的空表**来装新文件。
                # 之前传的是 self.sheet（复用上一首歌的表），
                # 结果上一首的制作人、混音、母带这些自定义字段会残留下来，
                # 而且新文件里没写到的字段也会留着旧值 —— 信息全乱了。
                base=LyricSheet(),
                # 文件名是重要的兜底线索：
                # "晴天 - 周杰伦.lrc" 能拆出歌名和演唱
                filename=os.path.basename(path),
            )
        except Exception as err:                       # pragma: no cover
            self.notify(f"导入失败：{err}")
            return

        # 保护：新文件是空的，但编辑器里本来有内容时不能冲掉它
        kept_old_body = False
        if result.body_lines == 0 and old_body:
            result.sheet.body = old_body
            kept_old_body = True

        self.sheet = result.sheet
        self.current_path = path
        self.dirty_info = False
        self.dirty_body = False
        self.refresh()
        # 上一首歌是空的、这一首有内容时清掉"还没内容"的提示，
        # 避免提示条和正文对不上
        if self.sheet.body.strip():
            self.hint_text.value = f"《{os.path.basename(path)}》 {result.summary()}"

        # 导入后自动展开「歌曲信息」，让作词/作曲/编曲一眼可见
        self._set_info_expanded(True)

        push_recent(path)
        file_name = os.path.basename(path)
        self.hint_text.value = f"《{file_name}》 {result.summary()}"

        # 空文件时把提示条换成警告色，避免用户以为导入成功了
        empty_body = result.body_lines == 0
        self.hint_bar.bgcolor = ft.Colors.with_opacity(
            0.10, theme.WARNING if empty_body else theme.SUCCESS)
        self.hint_bar.content.controls[0].color = (
            theme.WARNING if empty_body else theme.SUCCESS)
        self.hint_bar.visible = True
        self._update_status()
        self._safe_update()

        message = result.summary()
        if kept_old_body:
            message = "这个文件是空的，已保留你原来的内容。" + message
        self.notify(message, color=theme.WARNING if empty_body else theme.PRIMARY)

    def load_path(self, path: str):
        """供"最近文件"等外部调用。"""
        class _FakeFile:
            def __init__(self, p):
                self.path = p
                self.name = os.path.basename(p)

        class _FakeEvent:
            def __init__(self, p):
                self.files = [_FakeFile(p)]

        self.on_pick_result(_FakeEvent(path))

    # -------------------------------------------------------------- 分级保存
    def _collect_info(self):
        """把信息区输入框里的值收进文档。"""
        for name, control in self.fields.items():
            self.sheet.set(name, control.value or "")
        for key, control in self.extra_fields.items():
            if key in self.sheet.extras:
                self.sheet.extras[key] = control.value or ""

    def _collect_body(self):
        """把正文框里的内容收进文档。

        隐藏模式下框里是没有时间轴的，收录时按行把时间轴合并回去，
        保证文档里始终是完整原文。
        """
        self.sheet.body = self._merge_edited_body(self.body_field.value or "")

    def _on_sync_switch_change(self, e=None):
        """打开开关时立刻同步一次，把之前落下的改动补上。"""
        if self.switch_sync.value:
            changed = self._sync_credits_to_body()
            if changed:
                self.notify(f"已同步更新歌词里的 {changed} 处名字")
        else:
            self._safe_update()

    def _sync_credits_to_body(self) -> int:
        """把信息区的名字写进正文里对应的行，返回改了几行。

        例如上面把作词从"周杰伦"改成"张志博"，
        正文里那句"词：周杰伦"会变成"词：张志博"。
        """
        if not self.switch_sync.value:
            return 0
        new_body, changed = sync_credits_into_body(self.sheet.body, self.sheet)
        if not changed:
            return 0
        self.sheet.body = new_body
        self.body_field.value = self._display_body()
        return changed

    def _save_info_clicked(self, e=None):
        """只记录这一段，不写文件。"""
        self._collect_info()
        changed = self._sync_credits_to_body()
        self.dirty_info = False
        self._update_info_summary()
        self._update_stats()
        self._update_status()
        self._safe_update()
        if changed:
            self.notify(f"信息已保存，并同步更新了歌词里的 {changed} 处名字。"
                        f"要写回原文件，请点最下方「保存到原文件并覆盖」")
        else:
            self.notify("信息已保存。要写回原文件，请点最下方「保存到原文件并覆盖」")

    def _save_body_clicked(self, e=None):
        """只记录这一段，不写文件。"""
        self._collect_body()
        self.dirty_body = False
        self._update_stats()
        self._update_status()
        self._safe_update()
        self.notify("歌词已保存。要写回原文件，请点最下方「保存到原文件并覆盖」")

    def _commit_clicked(self, e=None):
        """真正的写盘：把整个文档写回原文件并覆盖。"""
        # 先把两段的最新内容都收进来，避免漏掉没点保存的部分
        self._collect_info()
        self._collect_body()
        # 顺序很重要：先收用户的手动编辑，再同步名字，
        # 否则同步结果会被 body_field 里的旧内容覆盖回去。
        self._sync_credits_to_body()

        if not self.current_path or not os.path.exists(self.current_path):
            self.notify("还没有打开文件，请选择保存位置")
            self._save_as_clicked()
            return

        self._confirm_overwrite()

    def _confirm_overwrite(self):
        """覆盖原文件前先确认一次，这个操作没法撤销。"""
        name = os.path.basename(self.current_path)

        def do_it(_=None):
            dlg.open = False
            self.page.update()
            self._do_save(self.current_path)

        def cancel(_=None):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Row(controls=[
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=theme.WARNING, size=20),
                ft.Text("覆盖原文件？", size=15, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Text(
                f"即将把当前内容写入并覆盖：\n{name}\n\n"
                f"原文件会被替换，这一步没法撤销。确定继续吗？",
                size=13, selectable=True),
            actions=[
                ft.TextButton("取消", on_click=cancel),
                ft.ElevatedButton("确定覆盖", on_click=do_it,
                                  style=ft.ButtonStyle(
                                      color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_600)),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _save_as_clicked(self, e=None):
        self.save_dialog.save_file(
            file_name=self.sheet.suggested_filename(),
            allowed_extensions=["txt"],
            dialog_title="另存为",
        )

    def on_save_result(self, e: ft.FilePickerResultEvent):
        if not e.path:
            return
        self._do_save(e.path)

    def _output_text(self) -> str:
        """要写进文件的文本。

        所见即所得：界面上把时间轴隐藏了，写出去的就是纯歌词。
        """
        text = self.sheet.to_text(self.include_optional)
        if self.hide_timestamps:
            text = "\n".join(
                LRC_TIME_RE.sub("", ln).rstrip() for ln in text.split("\n")
            )
        return text

    def _do_save(self, path: str):
        try:
            write_text_file(path, self._output_text())
        except Exception as err:                       # pragma: no cover
            self.notify(f"保存失败：{err}", color=ft.Colors.RED_600)
            return
        self.current_path = path
        self.dirty_info = False
        self.dirty_body = False
        push_recent(path)
        self._update_status()
        self._safe_update()
        self.notify(f"已覆盖写入 {path}", color=theme.SUCCESS)

    # -------------------------------------------------------------- 新建
    def _new_clicked(self, e=None):
        if self.sheet.is_empty():
            self._reset_sheet()
            return

        def do_new(_=None):
            dlg.open = False
            self.page.update()
            self._reset_sheet()

        def cancel(_=None):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("新建一张空白歌词？", size=15),
            content=ft.Text("当前内容会被清空，还没写回文件的话请先保存。", size=13),
            actions=[
                ft.TextButton("取消", on_click=cancel),
                ft.ElevatedButton("确认新建", on_click=do_new,
                                  style=ft.ButtonStyle(color=ft.Colors.RED_600)),
            ],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _reset_sheet(self):
        # 用全新实例，确保上一首歌的自定义字段（制作人/混音…）不会残留
        self.sheet = LyricSheet()
        self.current_path = None
        self.dirty_info = False
        self.dirty_body = False
        self.hint_bar.visible = False
        self._set_info_expanded(True)     # 新建后展开，方便填作词作曲
        self.refresh()
        self._update_status()
        self.notify("已新建空白歌词")

    # -------------------------------------------------------------- 外部接口
    def get_recent_menu(self) -> List[str]:
        from ..storage import load_settings
        return [p for p in load_settings().get("recent", []) if os.path.exists(p)]
