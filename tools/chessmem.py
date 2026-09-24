#!/usr/bin/env python3
"""ChessPlugin 记忆层：棋谱落地 + 引擎评估记忆化。

用法：
    .venv/bin/python tools/chessmem.py analyze --pgn pgn/xxx.pgn --id xxx [--depth 16]
    .venv/bin/python tools/chessmem.py list
    .venv/bin/python tools/chessmem.py show xxx
    .venv/bin/python tools/chessmem.py stats

设计要点：
  * cache/evals.json 按「局面 + 深度 + 引擎」缓存评估，重复的局面永不重算。
  * games/<id>.json 是唯一真相：引擎数据每次刷新，人写的讲解/标注原位保留。
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import pathlib
import shutil
import sys
import time

import chess
import chess.engine
import chess.pgn

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import paths  # noqa: E402

ROOT = paths.DATA_ROOT          # 棋谱、讲解、缓存都写这里（插件目录只读时自动落到用户目录）
GAMES_DIR = paths.GAMES_DIR
NOTES_DIR = paths.NOTES_DIR
CACHE_FILE = paths.CACHE_FILE
PGN_DIR = paths.PGN_DIR
try:
    from engines import find_engine  # 同目录；跨平台解析引擎路径

    DEFAULT_ENGINE = find_engine(required=False) or os.environ.get("CHESSPLUGIN_ENGINE", "stockfish")
except Exception:  # 单独拷走本文件时也不至于崩
    DEFAULT_ENGINE = os.environ.get("CHESSPLUGIN_ENGINE", "stockfish")

# 这些字段是人写的，重新分析时要原样保留
AUTHORED_FIELDS = ("note", "arrows", "highlights", "markers")


def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def load_json(path: pathlib.Path, default):
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def open_engine(path: str, threads: int = 4):
    """打开引擎；出错时说人话，不甩堆栈。"""
    if not pathlib.Path(path).exists():
        found = shutil.which(path)          # 也可能给的是 PATH 里的名字（stockfish / stockfish.exe）
        if found:
            path = found
        else:
            raise SystemExit(
                f"找不到引擎：{path}\n"
                "  mac: brew install stockfish ｜ Windows: winget install stockfish ｜ Linux: apt install stockfish\n"
                "  也可以把可执行文件放进 engines/，或用 --engine / CHESSPLUGIN_ENGINE 指定路径"
            )
    try:
        engine = chess.engine.SimpleEngine.popen_uci(path)
    except Exception as exc:  # 引擎启动失败的原因五花八门，统一兜住
        raise SystemExit(f"引擎起不来（{path}）：{exc}")
    engine.configure({"Threads": threads})
    return engine


def save_json(path: pathlib.Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


def cache_key(fen: str, depth: int, engine_name: str) -> str:
    return f"{fen}|d{depth}|{engine_name}"


def fmt_eval(cp, mate) -> str:
    if mate is not None:
        if mate == 0:
            return "将杀"
        return ("#" if mate > 0 else "-#") + str(abs(mate))
    if cp is None:
        return "?"
    return f"{cp / 100:+.2f}"


def score_for(board: chess.Board, engine, depth: int):
    """白方视角的评估；终局直接判定，不问引擎。"""
    if board.is_checkmate():
        return {"cp": None, "mate": 0}
    if board.is_game_over():
        return {"cp": 0, "mate": None}
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].pov(chess.WHITE)
    if score.is_mate():
        return {"cp": None, "mate": score.mate()}
    return {"cp": score.score(), "mate": None}


def read_game(text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(text))
    if game is None:
        raise SystemExit("PGN 解析失败")
    return game


def collect_plies(game: chess.pgn.Game):
    board = game.board()
    start_fen = board.fen()
    plies = []
    for node in game.mainline():
        move = node.move
        san = board.san(move)
        board.push(move)
        plies.append({"san": san, "uci": move.uci(), "fen": board.fen()})
    return start_fen, plies


def cmd_analyze(args) -> int:
    if args.pgn == "-":
        text = sys.stdin.read()
        source = "stdin"
    else:
        path = pathlib.Path(args.pgn)
        if not path.exists():
            raise SystemExit(f"找不到 PGN：{path}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise SystemExit(f"{path} 不是 UTF-8 文本，读不了")
        source = str(path)

    try:
        game = read_game(text)
        start_fen, plies = collect_plies(game)
    except ValueError as exc:
        raise SystemExit(f"PGN 里有走不通的地方：{exc}")
    headers = {key: str(value) for key, value in game.headers.items()}
    if not plies:
        raise SystemExit("这盘棋一着都没有")

    game_id = args.id or pathlib.Path(args.pgn).stem
    game_file = GAMES_DIR / f"{game_id}.json"
    previous = load_json(game_file, {})

    # 人写的部分有两个来源：上次记录里存着的，以及 notes/<id>.json 里的（后者优先）
    authored = {}
    for old in previous.get("plies", []):
        extra = {k: old[k] for k in AUTHORED_FIELDS if old.get(k)}
        if extra:
            authored[int(old.get("ply"))] = extra

    start_note = previous.get("start_note", "")
    notes = load_json(NOTES_DIR / f"{game_id}.json", {})
    if notes.get("start_note"):
        start_note = notes["start_note"]
    san_by_ply = {i: ply["san"] for i, ply in enumerate(plies, start=1)}
    for entry in notes.get("plies", []):
        ply = int(entry.get("ply", 0))
        if ply not in san_by_ply:
            print(f"  ! notes 里的第 {ply} 着不存在，跳过", file=sys.stderr)
            continue
        if entry.get("san") and entry["san"] != san_by_ply[ply]:
            print(f"  ! notes 第 {ply} 着写的是 {entry['san']}，棋谱里是 {san_by_ply[ply]}，跳过", file=sys.stderr)
            continue
        extra = {k: entry[k] for k in AUTHORED_FIELDS if entry.get(k)}
        if extra:
            authored[ply] = extra

    cache = load_json(CACHE_FILE, {})
    hits = queries = 0
    engine_path = args.engine or DEFAULT_ENGINE
    started = time.time()

    with open_engine(engine_path, args.threads) as engine:
        engine_name = engine.id.get("name", "unknown")

        def evaluate(fen: str):
            nonlocal hits, queries
            key = cache_key(fen, args.depth, engine_name)
            if not args.fresh and key in cache:
                hits += 1
                return cache[key]
            data = score_for(chess.Board(fen), engine, args.depth)
            cache[key] = data
            queries += 1
            return data

        start_eval = evaluate(start_fen)
        enriched = []
        for i, ply in enumerate(plies, start=1):
            data = evaluate(ply["fen"])
            entry = {
                "ply": i,
                "san": ply["san"],
                "uci": ply["uci"],
                "fen": ply["fen"],
                "cp": data["cp"],
                "mate": data["mate"],
            }
            entry.update(authored.get(i, {}))
            enriched.append(entry)

    save_json(CACHE_FILE, cache)

    record = dict(previous)
    record.update(
        {
            "id": game_id,
            "title": args.title or previous.get("title") or f"{headers.get('White', '?')} – {headers.get('Black', '?')}",
            "meta": args.meta or previous.get("meta") or "",
            "headers": headers,
            "start_fen": start_fen,
            "start_cp": start_eval["cp"],
            "start_mate": start_eval["mate"],
            "start_note": start_note,
            "engine": {
                "name": engine_name,
                "path": str(engine_path),
                "depth": args.depth,
                "threads": args.threads,
            },
            "source": source,
            "created": previous.get("created") or now(),
            "analyzed": now(),
            "plies": enriched,
            "stats": {
                "positions": len(plies) + 1,
                "cache_hits": hits,
                "engine_queries": queries,
                "seconds": round(time.time() - started, 2),
                "cache_size": len(cache),
            },
        }
    )
    save_json(game_file, record)

    elapsed = time.time() - started
    print(f"{game_id}: {len(plies)} 着 / {len(plies) + 1} 个局面")
    print(f"  引擎查询 {queries} 次，缓存命中 {hits} 次，用时 {elapsed:.2f}s")
    print(f"  记录 -> {game_file.relative_to(ROOT)}")
    print(f"  缓存 -> cache/evals.json（共 {len(cache)} 个局面）")
    return 0


def load_records():
    return [load_json(path, {}) for path in sorted(GAMES_DIR.glob("*.json"))]


def cmd_list(args) -> int:
    records = load_records()
    if not records:
        print("（还没有棋谱记录）")
        return 0
    shown = 0
    for record in records:
        headers = record.get("headers", {})
        if args.player:
            names = (headers.get("White", "") + " " + headers.get("Black", "")).lower()
            if args.player.lower() not in names:
                continue
        if args.result and headers.get("Result") != args.result:
            continue
        if args.eco and headers.get("ECO") != args.eco:
            continue
        shown += 1
        plies = record.get("plies", [])
        result = record.get("headers", {}).get("Result", "")
        print(f"{record.get('id'):<24} {len(plies):>3} 着  {result:<5} {record.get('title', '')}")
        print(f"{'':<24} 分析于 {record.get('analyzed', '?')} · {record.get('engine', {}).get('name', '?')} "
              f"深度 {record.get('engine', {}).get('depth', '?')}")
    if shown == 0:
        print("（没有符合条件的棋谱）")
    return 0


def cmd_analyze_all(args) -> int:
    """把 pgn/ 里所有棋谱都分析入库（已有的走缓存，很快）。"""
    paths_ = sorted(PGN_DIR.glob("*.pgn"))
    if not paths_:
        raise SystemExit(f"{PGN_DIR} 里没有 .pgn 文件")
    for path in paths_:
        print(f"\n=== {path.name} ===")
        ns = argparse.Namespace(
            pgn=str(path),
            id=path.stem,
            title=None,
            meta=None,
            depth=args.depth,
            threads=args.threads,
            engine=args.engine,
            fresh=args.fresh,
        )
        cmd_analyze(ns)
    return 0


def cmd_show(args) -> int:
    record = load_json(GAMES_DIR / f"{args.id}.json", None)
    if record is None:
        raise SystemExit(f"没有这盘棋：{args.id}")
    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    headers = record.get("headers", {})
    print(f"{record.get('title', record['id'])}  ({headers.get('Result', '?')})")
    if record.get("meta"):
        print(record["meta"])
    print(f"引擎 {record.get('engine', {}).get('name')} · 深度 {record.get('engine', {}).get('depth')} "
          f"· 分析于 {record.get('analyzed')}")
    print(f"起始局面 {fmt_eval(record.get('start_cp'), record.get('start_mate'))}")
    print()
    for ply in record.get("plies", []):
        no = (ply["ply"] + 1) // 2
        tag = f"{no}." if ply["ply"] % 2 else f"{no}..."
        line = f"{tag:>6} {ply['san']:<8} {fmt_eval(ply.get('cp'), ply.get('mate')):>7}"
        if ply.get("note"):
            line += f"   {ply['note']}"
        print(line)
    return 0


def cmd_stats(args) -> int:
    cache = load_json(CACHE_FILE, {})
    records = load_records()
    path = CACHE_FILE
    size = path.stat().st_size if path.exists() else 0
    engines = {}
    for key in cache:
        parts = key.split("|")
        engines[parts[-1]] = engines.get(parts[-1], 0) + 1
    print(f"棋谱记录 {len(records)} 盘：{[r.get('id') for r in records]}")
    print(f"评估缓存 {len(cache)} 个局面（{size / 1024:.1f} KB）")
    for name, count in sorted(engines.items()):
        print(f"  · {name}: {count} 个局面")
    total = sum(len(r.get("plies", [])) for r in records)
    fresh = sum(r.get("stats", {}).get("engine_queries", 0) for r in records)
    print(f"累计着法 {total}，最近一次分析实际问引擎 {fresh} 次")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChessPlugin 记忆层")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="分析一盘棋并写入本地记录")
    p_analyze.add_argument("--pgn", required=True, help="PGN 文件路径，或 - 从 stdin 读")
    p_analyze.add_argument("--id", help="记录 id（默认取文件名）")
    p_analyze.add_argument("--title")
    p_analyze.add_argument("--meta")
    p_analyze.add_argument("--depth", type=int, default=16)
    p_analyze.add_argument("--threads", type=int, default=4)
    p_analyze.add_argument("--engine", default=None)
    p_analyze.add_argument("--fresh", action="store_true", help="忽略缓存，全部重算")
    p_analyze.set_defaults(func=cmd_analyze)

    p_list = sub.add_parser("list", help="列出本地棋谱")
    p_list.add_argument("--player", help="按棋手名过滤")
    p_list.add_argument("--result", help="按结果过滤，如 1-0")
    p_list.add_argument("--eco", help="按开局代码过滤，如 C41")
    p_list.set_defaults(func=cmd_list)

    p_all = sub.add_parser("analyze-all", help="把 pgn/ 里所有棋谱都分析入库")
    p_all.add_argument("--depth", type=int, default=16)
    p_all.add_argument("--threads", type=int, default=4)
    p_all.add_argument("--engine", default=None)
    p_all.add_argument("--fresh", action="store_true")
    p_all.set_defaults(func=cmd_analyze_all)

    p_show = sub.add_parser("show", help="打印一盘棋的记录")
    p_show.add_argument("id")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_stats = sub.add_parser("stats", help="看看缓存和记录的家底")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
