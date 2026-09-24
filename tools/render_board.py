#!/usr/bin/env python3
"""把棋盘渲染成单张图（HTML 片段）。

两种来源：
    .venv/bin/python tools/render_board.py --id legal-trap-1750 --ply 10 --out dist/ply10.html
    .venv/bin/python tools/render_board.py --fen "rnbq... w KQkq - 0 1" --out dist/pos.html
"""
from __future__ import annotations

import argparse
import json
import pathlib

from render_common import load_piece_sets, render_template

ROOT = pathlib.Path(__file__).resolve().parents[1]
GAMES_DIR = ROOT / "games"
DEFAULT_TEMPLATE = ROOT / "templates" / "board.html"
DEFAULT_PIECES = ROOT / "templates" / "pieces.js"
DEFAULT_PIECES_RUNTIME = ROOT / "templates" / "pieces-runtime.js"
BOARD_PLACEHOLDER = "__BOARD_JSON__"
PIECES_PLACEHOLDER = "__PIECE_SETS__"
RUNTIME_PLACEHOLDER = "__PIECES_RUNTIME__"


def eval_text(cp, mate, fen: str) -> str:
    side = fen.split()[1] if len(fen.split()) > 1 else "w"
    if mate is not None:
        if mate == 0:
            return "1-0 将杀" if side == "b" else "0-1 将杀"
        return ("#" + str(mate)) if mate > 0 else ("-#" + str(-mate))
    if cp is None:
        return ""
    value = cp / 100
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    return f"{sign}{abs(value):.2f}"


def eval_pawns(cp, mate, fen: str) -> float:
    if mate is not None:
        if mate == 0:
            return 5.0 if fen.split()[1] == "b" else -5.0
        return 5.0 if mate > 0 else -5.0
    return (cp or 0) / 100


def from_record(game_id: str, ply_no: int) -> dict:
    record_path = GAMES_DIR / f"{game_id}.json"
    if not record_path.exists():
        raise SystemExit(f"没有这盘棋：{record_path}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    ply = next((p for p in record.get("plies", []) if p.get("ply") == ply_no), None)
    if ply is None:
        raise SystemExit(f"{game_id} 里没有第 {ply_no} 着")

    fen = ply["fen"]
    uci = ply.get("uci", "")
    label = eval_text(ply.get("cp"), ply.get("mate"), fen)
    meta = record.get("meta", "")
    move_no = (ply_no + 1) // 2
    move_tag = f"{move_no}. {ply['san']}" if ply_no % 2 else f"{move_no}... {ply['san']}"
    heading = f"{record.get('title', game_id)} · {move_tag}"
    return {
        "fen": fen,
        "lastMove": [uci[:2], uci[2:4]] if len(uci) >= 4 else None,
        "highlights": ply.get("highlights", []),
        "arrows": ply.get("arrows", []),
        "markers": ply.get("markers", []),
        "eval": {"white": eval_pawns(ply.get("cp"), ply.get("mate"), fen), "label": label},
        "caption": ply.get("note", ""),
        "title": heading + (f"（{meta}）" if meta else ""),
        "pieces": None,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="渲染单张棋盘")
    parser.add_argument("--id", help="棋谱 id；配合 --ply 使用")
    parser.add_argument("--ply", type=int, default=None, help="第几着之后的局面（1 起）")
    parser.add_argument("--fen", help="直接给一个 FEN")
    parser.add_argument("--orientation", default="white", choices=["white", "black"])
    parser.add_argument("--theme", default="wood", choices=["wood", "green", "slate"])
    parser.add_argument("--caption", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--pieces-file", default=str(DEFAULT_PIECES))
    parser.add_argument("--pieces-runtime", default=str(DEFAULT_PIECES_RUNTIME))
    parser.add_argument("--pieces", default="chessnut")
    args = parser.parse_args(argv)

    if args.id and args.ply is not None:
        config = from_record(args.id, args.ply)
    elif args.fen:
        config = {
            "fen": args.fen,
            "lastMove": None,
            "highlights": [],
            "arrows": [],
            "markers": [],
            "eval": None,
            "caption": args.caption,
            "title": args.caption,
        }
    else:
        raise SystemExit("要么给 --id 加 --ply，要么给 --fen")

    config["orientation"] = args.orientation
    config["theme"] = args.theme
    config["pieces"] = args.pieces

    template = pathlib.Path(args.template).read_text(encoding="utf-8")
    pieces_js = load_piece_sets(pathlib.Path(args.pieces_file), args.pieces)
    runtime_js = pathlib.Path(args.pieces_runtime).read_text(encoding="utf-8")

    payload = json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = render_template(template, runtime_js, pieces_js, {BOARD_PLACEHOLDER: payload})
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"棋盘 -> {out}（{out.stat().st_size / 1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
