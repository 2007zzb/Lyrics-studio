"""全局常量与主题配置。"""

from __future__ import annotations

# ------------------------------------------------------------------ 应用信息
APP_NAME = "歌词修改工作台"
APP_NAME_EN = "Lyric Editor"
APP_VERSION = "1.0.0"
APP_BUILD = "1"
APP_DESC = "模板化歌词编辑工具：导入歌词自动识别作词 / 作曲 / 编曲"

AUTHOR = "张小博"
AUTHOR_QQ = "2771165282"
COPYRIGHT = f"Copyright © 2026 {AUTHOR}"
LICENSE_NAME = "MIT License"

GITHUB_OWNER = "zhangxiaobo"          # TODO: 换成你的 GitHub 用户名
GITHUB_REPO = "lyrics-studio"         # TODO: 换成你的仓库名
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
RELEASES_URL = f"{GITHUB_URL}/releases"
ISSUES_URL = f"{GITHUB_URL}/issues"

TECH_STACK = "Python 3 + Flet（一套代码，桌面 / 安卓 / iOS / 网页通用）"

CHANGELOG = [
    ("1.0.0", "2026-08-31", [
        "首个版本发布",
        "作词 / 作曲 / 编曲 三行模板编辑器",
        "导入 txt、lrc 自动扫描并填写作者信息",
        "导入即全文：文件全部内容直接进编辑区，不会吞掉歌词",
        "右侧抽屉：版本号、关于作者、QQ 一键复制",
    ]),
]

# ------------------------------------------------------------------ 配色
PRIMARY = "#4F46E5"        # 主色（靛蓝）
PRIMARY_SOFT = "#EEF0FF"
ACCENT = "#EC4899"         # 强调色（品红）
SUCCESS = "#16A34A"
WARNING = "#F59E0B"
TEXT_MAIN = "#1F2233"
TEXT_SUB = "#6B7280"
BORDER = "#E5E7EB"
CARD_BG = "#FFFFFF"
PAGE_BG = "#F6F7FB"
DRAWER_BG = "#FBFAFF"

RADIUS = 14
CARD_PADDING = 14

# ------------------------------------------------------------------ 文本
TIP_IMPORT = "支持 .txt / .lrc / .md，导入后会自动扫描作词、作曲、编曲并填写"
TIP_TEMPLATE = "前三行固定为 作词 / 作曲 / 编曲，第四行开始写歌词正文"
TIP_EMPTY = "还没有内容，点「导入歌词」自动识别，或直接开写 ↓"

QQ_TIP = f"作者 QQ：{AUTHOR_QQ}（点击复制）"
