"""引擎路径解析：让同一个仓库在 mac / Windows / Linux 上都能找到 Stockfish。

查找顺序（先命中先用）：
  1. 环境变量 CHESSPLUGIN_ENGINE（用户显式指定，最高优先级）
  2. 仓库内 engines/ 目录（放系统版 Stockfish 或自己编的）
  3. PATH 里的 stockfish / stockfish.exe
  4. 各系统常见的安装位置
找不到时返回 None（required=False）或抛出带安装指引的 SystemExit（required=True）。
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

INSTALL_HINT = (
    "装一个 Stockfish 就行：\n"
    "  mac      brew install stockfish\n"
    "  Windows  winget install stockfish   （或从 stockfishchess.org 下 zip 解压）\n"
    "  Linux    sudo apt install stockfish\n"
    "也可以把可执行文件放进 engines/，或用环境变量 CHESSPLUGIN_ENGINE 指路径。"
)


def _candidates() -> list:
    names = ["stockfish.exe", "stockfish"] if sys.platform.startswith("win") else ["stockfish"]
    out = []
    env = os.environ.get("CHESSPLUGIN_ENGINE")
    if env:
        out.append(pathlib.Path(env))
    for name in names:
        out.append(ROOT / "engines" / name)
    for name in names:
        found = shutil.which(name)
        if found:
            out.append(pathlib.Path(found))
    if sys.platform.startswith("win"):
        for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("ProgramFiles"), "C:/Program Files"):
            if not base:
                continue
            out += [
                pathlib.Path(base) / "Microsoft/WinGet/Links/stockfish.exe",
                pathlib.Path(base) / "stockfish/stockfish.exe",
            ]
    elif sys.platform == "darwin":
        out += [pathlib.Path("/opt/homebrew/bin/stockfish"), pathlib.Path("/usr/local/bin/stockfish")]
    else:
        out += [pathlib.Path("/usr/bin/stockfish"), pathlib.Path("/usr/local/bin/stockfish")]
    return out


def find_engine(required: bool = True):
    for path in _candidates():
        try:
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        except OSError:
            continue
    if required:
        raise SystemExit("找不到 Stockfish 引擎。\n" + INSTALL_HINT)
    return None
