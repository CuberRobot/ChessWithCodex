#!/usr/bin/env python3
"""把本地棋谱记录渲染成可以点着走的界面（HTML 片段）。

用法：
    .venv/bin/python tools/render_replay.py --id legal-trap-1750 --out dist/legal-trap-1750.html
"""
from __future__ import annotations

import argparse
import json
import pathlib

from render_common import load_piece_sets, render_template

ROOT = pathlib.Path(__file__).resolve().parents[1]
GAMES_DIR = ROOT / "games"
SESSIONS_DIR = ROOT / "sessions"
DEFAULT_TEMPLATE = ROOT / "templates" / "replay.html"
DEFAULT_PIECES = ROOT / "templates" / "pieces.js"
DEFAULT_PIECES_RUNTIME = ROOT / "templates" / "pieces-runtime.js"
PLACEHOLDER = "__GAME_JSON__"
PIECES_PLACEHOLDER = "__PIECE_SETS__"
PIECES_RUNTIME_PLACEHOLDER = "__PIECES_RUNTIME__"


def build_game(record: dict, show_eval: bool = True) -> dict:
    engine = record.get("engine", {})
    label = [engine.get("name", "?")]
    if engine.get("depth"):
        label.append(f"深度 {engine['depth']}")

    is_pve = record.get("kind") == "pve"
    plies = []
    for ply in record.get("plies", []):
        note = ply.get("note", "")
        if not note and is_pve:
            note = ("你：" if ply.get("by") == "player" else "引擎：") + ply.get("san", "")
        plies.append(
            {
                "san": ply.get("san", ""),
                "uci": ply.get("uci", ""),
                "fen": ply.get("fen", ""),
                "cp": ply.get("cp"),
                "mate": ply.get("mate"),
                "note": note,
                "arrows": ply.get("arrows", []),
                "highlights": ply.get("highlights", []),
                "markers": ply.get("markers", []),
            }
        )

    start_note = record.get("start_note", "")
    if not start_note and is_pve:
        start_note = "该你走：直接告诉我着法（例如「e4」「Nf3」「马到 f3」），我会让引擎应一手并把这张图更新。"

    return {
        "title": record.get("title") or record.get("id", "棋谱"),
        "meta": record.get("meta", ""),
        "engineLabel": " · ".join(label),
        "startFen": record["start_fen"],
        "startCp": record.get("start_cp"),
        "startNote": start_note,
        "showEval": show_eval,
        "plies": plies,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="渲染棋谱回放界面")
    parser.add_argument("--id", help="games/<id>.json 里的 id")
    parser.add_argument("--session", help="sessions/<id>.json：进行中的人机对局")
    parser.add_argument("--out", required=True, help="输出 HTML 片段路径")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--pieces-file", default=str(DEFAULT_PIECES))
    parser.add_argument("--pieces-runtime", default=str(DEFAULT_PIECES_RUNTIME))
    parser.add_argument("--pieces", default="chessnut", help="棋组：chessnut（默认）/ spatial")
    parser.add_argument("--show-eval", dest="show_eval", action="store_true", default=None,
                        help="显示评估条（对局默认隐藏）")
    args = parser.parse_args(argv)

    if bool(args.id) == bool(args.session):
        raise SystemExit("--id（棋谱）和 --session（进行中的对局）二选一")
    if args.session:
        record_path = SESSIONS_DIR / f"{args.session}.json"
        show_eval = bool(args.show_eval)
    else:
        record_path = GAMES_DIR / f"{args.id}.json"
        show_eval = True if args.show_eval is None else args.show_eval
    if not record_path.exists():
        raise SystemExit(f"没有这个记录：{record_path}")

    record = json.loads(record_path.read_text(encoding="utf-8"))
    template = pathlib.Path(args.template).read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise SystemExit(f"模板里找不到占位符 {PLACEHOLDER}")

    pieces_js = load_piece_sets(pathlib.Path(args.pieces_file), args.pieces)
    runtime_js = pathlib.Path(args.pieces_runtime).read_text(encoding="utf-8")

    game = build_game(record, show_eval=show_eval)
    game["pieces"] = args.pieces
    payload = json.dumps(game, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = render_template(template, runtime_js, pieces_js, {PLACEHOLDER: payload})
    out.write_text(html, encoding="utf-8")
    label = record.get("id") or args.id or args.session
    print(f"{label} -> {out}（{len(record.get('plies', []))} 着，{out.stat().st_size / 1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
