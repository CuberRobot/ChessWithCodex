#!/usr/bin/env python3
"""跨平台启动器：`.mcp.json` 指向它，它负责找到"带依赖的那个 Python"再启动服务。

为什么要它：插件的启动命令必须是某个解释器，但系统 Python 里通常没有 python-chess；
而解释器路径在 mac/Linux 是 `.venv/bin/python`、在 Windows 是 `.venv\\Scripts\\python.exe`。
这个脚本用系统解释器先起来，再自己换成 venv 里的解释器跑真正的服务，于是三种系统共用一份配置。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp" / "server.py"


def venv_python() -> pathlib.Path | None:
    for rel in ("bin/python", "bin/python3", "Scripts/python.exe"):
        candidate = ROOT / ".venv" / rel
        if candidate.is_file():
            return candidate
    return None


def has_deps(python: str) -> bool:
    try:
        return subprocess.run([python, "-c", "import chess, chess.engine"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


def main() -> int:
    if not SERVER.is_file():
        print(f"找不到 {SERVER}", file=sys.stderr)
        return 1
    python = venv_python()
    if python is None or not has_deps(str(python)):
        fallback = sys.executable
        if python is None and has_deps(fallback):
            python = pathlib.Path(fallback)          # 系统解释器里恰好装过依赖也能用
        else:
            print("还没准备好运行环境。先执行一次安装：\n"
                  "  mac/Linux   ./install.sh\n"
                  "  Windows     powershell -ExecutionPolicy Bypass -File install.ps1",
                  file=sys.stderr)
            return 1
    os.execv(str(python), [str(python), str(SERVER)])   # 换成 venv 解释器跑服务
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
