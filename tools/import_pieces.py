#!/usr/bin/env python3
"""把 assets/pieces/<set>/*.svg 打包成 templates/pieces.js，供两个渲染器注入。

想加新棋组：把 12 个 SVG（wK wQ wR wB wN wP bK bQ bR bB bN bP）放进
assets/pieces/<set>/，然后在 assets/pieces/LICENSE.md 里记下来源和许可，再跑一次本脚本。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "pieces"
DEFAULT_OUT = ROOT / "templates" / "pieces.js"
TYPES = ["K", "Q", "R", "B", "N", "P"]
FALLBACK_VIEWBOX = "0 0 45 45"


def strip_wrapper(text: str) -> str:
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.I)
    return text.strip()


def split_svg(text: str) -> tuple[str, str]:
    match = re.search(r"<svg\b([^>]*)>(.*)</svg>", text, re.S)
    if not match:
        raise ValueError("找不到 <svg> 元素")
    attrs, inner = match.group(1), match.group(2)
    viewbox = re.search(r'viewBox="([^"]+)"', attrs, re.I)
    return (viewbox.group(1).strip() if viewbox else FALLBACK_VIEWBOX), inner.strip()


def load_set(directory: pathlib.Path) -> dict:
    pieces = {}
    viewboxes = set()
    for color in ("w", "b"):
        for kind in TYPES:
            path = directory / f"{color}{kind}.svg"
            if not path.exists():
                raise SystemExit(f"{directory.name} 缺少 {path.name}")
            viewbox, inner = split_svg(strip_wrapper(path.read_text(encoding="utf-8")))
            pieces[color + kind] = inner
            viewboxes.add(viewbox)
    if len(viewboxes) != 1:
        raise SystemExit(f"{directory.name} 里 12 个 SVG 的 viewBox 不一致：{viewboxes}")
    return {"viewBox": viewboxes.pop(), "pieces": pieces}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打包棋子 SVG")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    sets = {}
    for directory in sorted(ASSETS.iterdir()):
        if directory.is_dir():
            sets[directory.name] = load_set(directory)
    if not sets:
        raise SystemExit(f"{ASSETS} 里没有棋组")

    payload = json.dumps(sets, ensure_ascii=False, separators=(",", ":"))
    code = (
        "/* 由 tools/import_pieces.py 生成，不要手改。 */\n"
        f"const PIECE_SETS = {payload};\n"
    )
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code, encoding="utf-8")
    print(f"{len(sets)} 套棋组 -> {out.relative_to(ROOT)}（{out.stat().st_size / 1024:.0f} KB）")
    print("  " + "、".join(f"{name}({data['viewBox']})" for name, data in sets.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
