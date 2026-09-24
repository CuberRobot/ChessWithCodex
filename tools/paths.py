"""数据目录解析：代码在插件里，数据写到能写的地方。

为什么需要它：从 marketplace 装下来的插件目录是**只读快照**，而棋谱（games/）、
讲解（notes/）、缓存（cache/）、对局（sessions/）、引擎（engines/）都要写。

解析顺序：
  1. 环境变量 CHESSPLUGIN_HOME（用户显式指定）
  2. 插件目录本身 —— **可写时用它**（本地克隆、跑过安装脚本的情形，行为与以前完全一致）
  3. 各系统的用户数据目录（插件目录只读时）：
     mac    ~/Library/Application Support/ChessWithCodex
     Win    %LOCALAPPDATA%\\ChessWithCodex
     Linux  $XDG_DATA_HOME/ChessWithCodex 或 ~/.local/share/ChessWithCodex
"""
from __future__ import annotations

import os
import pathlib
import sys

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_NAME = "ChessWithCodex"


def _writable(path: pathlib.Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def user_data_dir() -> pathlib.Path:
    if sys.platform == "darwin":
        return pathlib.Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = pathlib.Path(base) if base else pathlib.Path.home()
        return root / APP_NAME
    base = os.environ.get("XDG_DATA_HOME")
    root = pathlib.Path(base) if base else pathlib.Path.home() / ".local" / "share"
    return root / APP_NAME


def data_root() -> pathlib.Path:
    env = os.environ.get("CHESSPLUGIN_HOME")
    if env:
        return pathlib.Path(env.strip().strip('"').strip("'")).expanduser()
    if _writable(PLUGIN_ROOT):
        return PLUGIN_ROOT
    return user_data_dir()


DATA_ROOT = data_root()
GAMES_DIR = DATA_ROOT / "games"
NOTES_DIR = DATA_ROOT / "notes"
PGN_DIR = DATA_ROOT / "pgn"
SESSIONS_DIR = DATA_ROOT / "sessions"
CACHE_FILE = DATA_ROOT / "cache" / "evals.json"
ENGINES_DIR = DATA_ROOT / "engines"
PLUGIN_ENGINES_DIR = PLUGIN_ROOT / "engines"      # 本地克隆时大家习惯放这里


def engine_files() -> list:
    """浏览器版单文件引擎可能的落点：先是数据目录，再是插件目录。"""
    return [ENGINES_DIR / "stockfish-single.js", PLUGIN_ENGINES_DIR / "stockfish-single.js"]


def describe() -> str:
    where = "插件目录" if DATA_ROOT == PLUGIN_ROOT else f"用户数据目录（插件目录只读）"
    return f"数据位置：{DATA_ROOT}（{where}）"
