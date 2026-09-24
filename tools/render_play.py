#!/usr/bin/env python3
"""把人机对战渲染成可以点着下的界面（HTML 片段）。

规则库 chess.js 直接内嵌进产物，所以这个界面**完全离线**、不依赖 CDN；
对手是产物里自带的小搜索引擎（按强度档位调深度和随机度）。
注意：它只是个"能陪你下"的对手，真正严肃的复盘仍然交给 Stockfish（tools/chessmem.py）。

用法：
    .venv/bin/python tools/render_play.py --out dist/play.html --player white --level 2
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from render_common import load_piece_sets, render_template

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "play.html"
DEFAULT_PIECES = ROOT / "templates" / "pieces.js"
DEFAULT_PIECES_RUNTIME = ROOT / "templates" / "pieces-runtime.js"
DEFAULT_CHESS_JS = ROOT / "assets" / "js" / "chess.js"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402

DEFAULT_ENGINE = next((p for p in paths.engine_files() if p.exists()), paths.engine_files()[0])
PLAY_PLACEHOLDER = "__PLAY_JSON__"
CHESS_JS_PLACEHOLDER = "__CHESS_JS__"
ENGINE_PLACEHOLDER = "__ENGINE_B64_GZ__"


def engine_payload(path: pathlib.Path) -> str:
    """把引擎压成 gzip+base64 塞进产物：wasm 已内嵌在这个单文件里，运行时不需要任何网络。"""
    import base64
    import gzip
    return base64.b64encode(gzip.compress(path.read_bytes(), 9)).decode()


def inline_module(path: pathlib.Path) -> str:
    """把 ESM 模块内嵌成普通脚本：去掉 export 前缀，顶层声明就成了脚本作用域。"""
    text = path.read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        if line.startswith("export "):
            line = line[len("export "):]
        if line.startswith("//# sourceMappingURL="):
            continue
        out.append(line)
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="渲染人机对战界面")
    parser.add_argument("--out", required=True)
    parser.add_argument("--player", default="white", choices=["white", "black"])
    parser.add_argument("--level", type=int, default=2, choices=[1, 2, 3, 4])
    parser.add_argument("--fen", help="从别的局面开始")
    parser.add_argument("--pieces", default="chessnut")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--pieces-file", default=str(DEFAULT_PIECES))
    parser.add_argument("--pieces-runtime", default=str(DEFAULT_PIECES_RUNTIME))
    parser.add_argument("--chess-js", default=str(DEFAULT_CHESS_JS))
    parser.add_argument("--engine", default=str(DEFAULT_ENGINE),
                        help="内嵌的真引擎（默认 engines/stockfish-single.js）；文件不存在会自动退回轻量引擎")
    args = parser.parse_args(argv)

    config = {
        "playerColor": "w" if args.player == "white" else "b",
        "level": args.level,
        "fen": args.fen or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "pieces": args.pieces,
        "realEngine": args.engine not in ("none", ""),
    }
    template = pathlib.Path(args.template).read_text(encoding="utf-8")
    pieces_js = load_piece_sets(pathlib.Path(args.pieces_file), args.pieces)
    runtime_js = pathlib.Path(args.pieces_runtime).read_text(encoding="utf-8")
    chess_js = inline_module(pathlib.Path(args.chess_js))
    engine_b64 = ""
    if config["realEngine"]:
        engine_path = pathlib.Path(args.engine)
        if not engine_path.exists():
            # 引擎是可选的第三方产物（GPLv3，不随仓库分发）：没有就退回轻量引擎，功能不受影响
            print(f"提示：没找到 {engine_path}，本次只用轻量引擎（编引擎见 tools/build/build_engine.sh）")
            config["realEngine"] = False
        else:
            engine_b64 = engine_payload(engine_path)
    payload = json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

    html = render_template(template, runtime_js, pieces_js,
                           {PLAY_PLACEHOLDER: payload, CHESS_JS_PLACEHOLDER: chess_js,
                            ENGINE_PLACEHOLDER: engine_b64})
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"对战界面 -> {out}（{out.stat().st_size / 1024:.0f} KB，离线可用）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
