#!/usr/bin/env python3
"""往棋谱库里添棋谱：从 Lichess 拉某个棋手的对局，或直接从任意 PGN 链接下载。

为什么要有它：省得每个会话都自己去网上找棋谱。预置的经典短局随仓库走（`pgn/`），
自己拉下来的放数据目录（`CHESSPLUGIN_HOME`/pgn 或仓库内 pgn/，见 tools/paths.py）。

用法：
    .venv/bin/python tools/fetch_games.py --user DrNykterstein --max 5 --analyze
    .venv/bin/python tools/fetch_games.py --url https://example.com/game.pgn
    .venv/bin/python tools/fetch_games.py --list                      # 看库里有什么
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402

LICHESS_EXPORT = "https://lichess.org/api/games/user/{user}"


def fetch(url: str, accept: str = "application/x-chess-pgn") -> str:
    request = urllib.request.Request(url, headers={
        "Accept": accept,
        "User-Agent": "ChessPlugin/1.0 (local study tool)",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"下载失败：HTTP {exc.code}（{url}）")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"下载失败：{exc.reason}\n"
            "  这台机器可能没有联网权限；拉棋谱需要联网，装依赖不需要。"
        )


def split_games(text: str) -> list:
    """把一整段 PGN 拆成单局（按 [Event 前切）。"""
    parts = re.split(r"\n(?=\[Event )", text.strip())
    return [p.strip() for p in parts if "[Event" in p]


def slug(text: str, fallback: str) -> str:
    keep = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return keep[:48] or fallback


def save(text: str, stem: str, out_dir: pathlib.Path) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stem}.pgn"
    n = 2
    while path.exists():
        path = out_dir / f"{stem}-{n}.pgn"
        n += 1
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def list_library() -> None:
    print("预置棋谱（随仓库，插件目录）：")
    for path in sorted((paths.PLUGIN_ROOT / "pgn").glob("*.pgn")):
        print(f"  · {path.stem}")
    if paths.PGN_DIR != paths.PLUGIN_ROOT / "pgn":
        print(f"自己的棋谱（{paths.PGN_DIR}）：")
        for path in sorted(paths.PGN_DIR.glob("*.pgn")):
            print(f"  · {path.stem}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="往棋谱库里添棋谱")
    parser.add_argument("--user", help="Lichess 用户名，拉 ta 最近的对局")
    parser.add_argument("--max", type=int, default=5, help="最多拉几局（默认 5）")
    parser.add_argument("--url", help="任意 PGN 链接")
    parser.add_argument("--out-dir", help="存到哪（默认数据目录里的 pgn/）")
    parser.add_argument("--analyze", action="store_true", help="拉完立刻入库分析")
    parser.add_argument("--list", action="store_true", help="只看库里有什么")
    args = parser.parse_args(argv)

    if args.list:
        list_library()
        return 0
    if not args.user and not args.url:
        parser.error("要么 --user，要么 --url（或者 --list 看看库里有什么）")

    out_dir = pathlib.Path(args.out_dir) if args.out_dir else paths.PGN_DIR
    saved = []
    if args.user:
        url = LICHESS_EXPORT.format(user=urllib.parse.quote(args.user))
        url += f"?max={max(1, args.max)}&opening=true"
        print(f"从 Lichess 拉取 {args.user} 的最近 {args.max} 局…")
        for chunk in split_games(fetch(url)):
            white = re.search(r'\[White "([^"]*)"', chunk)
            black = re.search(r'\[Black "([^"]*)"', chunk)
            date = re.search(r'\[Date "([^"]*)"', chunk)
            stem = slug(f"{white.group(1) if white else 'white'}-{black.group(1) if black else 'black'}-{date.group(1) if date else ''}", "game")
            saved.append(save(chunk, stem, out_dir))
    else:
        print(f"下载 {args.url} …")
        text = fetch(args.url)
        for i, chunk in enumerate(split_games(text), 1):
            saved.append(save(chunk, slug(f"downloaded-{i}", f"downloaded-{i}"), out_dir))

    for path in saved:
        print(f"  ✓ {path}")
    print(f"共 {len(saved)} 局，存到 {out_dir}")

    if args.analyze and saved:
        import chessmem
        for path in saved:
            ns = argparse.Namespace(pgn=str(path), id=path.stem, title=None, meta=None,
                                    depth=16, threads=4, engine=None, fresh=False)
            chessmem.cmd_analyze(ns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
