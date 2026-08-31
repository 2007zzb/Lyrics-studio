"""文件读写与本地配置存储。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

# 常见中文编码，按概率排序逐个尝试
ENCODINGS: List[str] = [
    "utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "utf-16", "latin-1",
]


def read_text_file(path: str) -> str:
    """读入文本文件，自动判断编码，失败也不会抛异常。"""
    raw = Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="ignore")


def write_text_file(path: str, text: str) -> None:
    """统一以带 BOM 的 UTF-8 写出，Windows 记事本打开不乱码。"""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(text, encoding="utf-8-sig")


def app_dir() -> Path:
    """跨平台的应用配置目录。"""
    home = Path.home()
    if os.name == "nt":
        base = home / "AppData" / "Roaming"
    elif os.sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = home / ".config"
    target = base / "lyrics-studio"
    target.mkdir(parents=True, exist_ok=True)
    return target


SETTINGS_FILE = "settings.json"
MAX_RECENT = 8


def load_settings() -> dict:
    path = app_dir() / SETTINGS_FILE
    if not path.exists():
        return {"recent": [], "include_optional": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"recent": [], "include_optional": False}


def save_settings(settings: dict) -> None:
    try:
        (app_dir() / SETTINGS_FILE).write_text(
            json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def push_recent(path: str) -> List[str]:
    """记录最近打开的文件（去重、限长）。"""
    settings = load_settings()
    recent: List[str] = [p for p in settings.get("recent", []) if p != path]
    recent.insert(0, path)
    settings["recent"] = recent[:MAX_RECENT]
    save_settings(settings)
    return settings["recent"]
