#!/usr/bin/env python3
"""人机对战（PvE）：你执一方，Stockfish 执另一方，可选难度、可选是否记录在案。

用法：
    .venv/bin/python tools/pve.py new   --id mygame --level 休闲 --player white --record yes
    .venv/bin/python tools/pve.py move  --session mygame --move e4
    .venv/bin/python tools/pve.py state --session mygame
    .venv/bin/python tools/pve.py finish --session mygame [--result 1-0]

难度不是简单粗暴的"全力搜索"，每档是 Skill Level + 搜索深度 + 候选着法加权随机
的组合，低档会挑看起来合理但不最好的着法，而不是乱下。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import random
import sys

import chess
import chess.engine
import chess.pgn

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chessmem  # noqa: E402  （复用分析入库那一套）

ROOT = pathlib.Path(__file__).resolve().parents[1]
SESSIONS_DIR = ROOT / "sessions"
PGN_DIR = ROOT / "pgn"
DEFAULT_ENGINE = chessmem.DEFAULT_ENGINE

# 难度以 Elo 为准，名字只是常用档位的别名
PRESETS = {
    "入门": 600, "beginner": 600,
    "休闲": 900, "casual": 900,
    "中等": 1200, "club": 1200, "medium": 1200,
    "进阶": 1600, "advanced": 1600,
    "强硬": 2200, "hard": 2200,
    "全力": 3190, "max": 3190, "full": 3190,
}
SF_ELO_MIN = 1320   # Stockfish 自带 UCI_Elo 的下限
WEAKEST = 400       # 我们自己能模拟到的最弱


def resolve_elo(spec) -> int:
    """把 '休闲' / 'casual' / '900' 统一成 Elo 数字。"""
    text = str(spec).strip()
    if text in PRESETS:
        return PRESETS[text]
    if text.lower() in PRESETS:
        return PRESETS[text.lower()]
    try:
        elo = int(text)
    except ValueError:
        raise SystemExit(f"难度要么给 Elo 数字，要么给 {sorted(set(PRESETS))}")
    return max(WEAKEST, min(3190, elo))


def config_for_elo(elo: int) -> dict:
    """Elo → 引擎设置。

    ≥1320 用 Stockfish 自带的 UCI_LimitStrength/UCI_Elo（它自己标定过的限强）；
    更低的部分它够不到，用"浅深度 + 候选池 + 温度采样 + 随机着"来模拟——
    深度决定它看不看得见战术，温度和随机决定它会不会送子。
    """
    if elo >= SF_ELO_MIN:
        return {
            "elo": elo,
            "mode": "native",
            "skill": 20,
            "depth": 18 if elo >= 3190 else max(6, round((elo - 1200) / 90)),
            "pool": 1,
            "temp": None,
            "random": 0.0,
            "limit_strength": elo < 3190,
        }
    w = (SF_ELO_MIN - elo) / (SF_ELO_MIN - WEAKEST)   # 0 = 接近 1320，1 = 最弱
    return {
        "elo": elo,
        "mode": "emulated",
        "skill": round((1 - w) * 14),
        "depth": max(2, round(8 - w * 6)),      # w=0 → 8 层，w=1 → 2 层（越弱看得越浅）
        "pool": max(3, round(8 - w * 5)),       # w=0 → 8 个候选，w=1 → 3 个
        "temp": 40 + w * 260,                   # 越弱越容忍次好棋
        "random": w * 0.05,                     # 最弱档 5% 直接乱走
        "limit_strength": False,
    }
def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def session_path(session_id: str) -> pathlib.Path:
    return SESSIONS_DIR / f"{session_id}.json"


def load_session(session_id: str) -> dict:
    path = session_path(session_id)
    if not path.exists():
        raise SystemExit(f"没有这个对局：{session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(session: dict) -> None:
    session["updated"] = now()
    chessmem.save_json(session_path(session["id"]), session)


def configure(engine, conf: dict) -> None:
    # 注意：MultiPV 由 python-chess 在 analyse(multipv=...) 时自己管，不能手动 configure
    options = engine.options
    settings = {"Skill Level": conf.get("skill", 20)}
    if conf.get("limit_strength") and "UCI_LimitStrength" in options:
        settings["UCI_LimitStrength"] = True
        settings["UCI_Elo"] = conf["elo"]
    elif "UCI_LimitStrength" in options:
        settings["UCI_LimitStrength"] = False
    engine.configure({k: v for k, v in settings.items() if k in options})


def score_of(info) -> tuple:
    score = info.get("score")
    if score is None or "pv" not in info:
        return (None, None)
    white = score.pov(chess.WHITE)
    if white.is_mate():
        return (None, white.mate())
    return (white.score(), None)


def pick_engine_move(board: chess.Board, engine, conf: dict, rng: random.Random):
    """按难度配置挑一手：候选池内按"分差 + 温度"软采样，低档再掺一点完全随机。"""
    limit = chess.engine.Limit(depth=conf["depth"])
    pool = conf.get("pool", 1)
    if pool > 1:
        infos = engine.analyse(board, limit, multipv=pool)
    else:
        infos = [engine.analyse(board, limit)]
    infos = [i for i in infos if i.get("pv")]
    if not infos:
        return None, (None, None)

    def mover_score(info):
        score = info["score"].pov(board.turn)
        if score.is_mate():
            return 1500 if score.mate() > 0 else -1500
        return max(-1500, min(1500, score.score()))

    if conf["random"] and rng.random() < conf["random"]:
        move = rng.choice(list(board.legal_moves))
        info = next((i for i in infos if i["pv"][0] == move), infos[0])
        return move, score_of(info)

    temp = conf.get("temp")
    if temp is None or len(infos) == 1:
        return infos[0]["pv"][0], score_of(infos[0])

    import math

    scores = [mover_score(i) for i in infos]
    best = max(scores)
    weights = [math.exp((s - best) / temp) for s in scores]
    total = sum(weights)
    point = rng.random() * total
    acc = 0.0
    for info, weight in zip(infos, weights):
        acc += weight
        if point <= acc:
            return info["pv"][0], score_of(info)
    return infos[0]["pv"][0], score_of(infos[0])


def push_ply(session: dict, board: chess.Board, move: chess.Move, by: str, score) -> None:
    san = board.san(move)
    board.push(move)
    cp, mate = score
    session["plies"].append(
        {
            "ply": len(session["plies"]) + 1,
            "san": san,
            "uci": move.uci(),
            "fen": board.fen(),
            "cp": cp,
            "mate": mate,
            "by": by,
        }
    )


def board_now(session: dict) -> chess.Board:
    board = chess.Board(session["start_fen"])
    for ply in session["plies"]:
        board.push(chess.Move.from_uci(ply["uci"]))
    return board


def engine_reply(session: dict, engine, rng) -> str:
    """让引擎走一手，返回它的 SAN。"""
    board = board_now(session)
    if board.is_game_over():
        return ""
    conf = config_for_elo(session.get("elo") or 900)
    configure(engine, conf)
    move, score = pick_engine_move(board, engine, conf, rng)
    if move is None:
        return ""
    push_ply(session, board, move, "engine", score)
    return session["plies"][-1]["san"]


def level_label(elo: int) -> str:
    for name, value in PRESETS.items():
        if value == elo and not name.isascii():
            return name
    return f"{elo} Elo"


def cmd_new(args) -> int:
    elo = resolve_elo(args.elo or args.level)
    level = level_label(elo)
    session_id = args.id or f"pve-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if session_path(session_id).exists() and not args.force:
        raise SystemExit(f"{session_id} 已经存在（要覆盖加 --force）")

    start_fen = args.fen or chess.STARTING_FEN
    player_color = "w" if args.player.lower() in ("white", "w", "白", "白方") else "b"
    record = str(args.record).lower() in ("yes", "y", "true", "1", "是", "记录")
    engine_path = args.engine or DEFAULT_ENGINE
    rng = random.Random(args.seed if args.seed is not None else None)

    session = {
        "id": session_id,
        "kind": "pve",
        "title": f"人机对战 · {level}",
        "meta": f"难度 {level}（约 {elo} Elo）· 我执{'白' if player_color == 'w' else '黑'} · "
                + ("记录在案" if record else "临时对局，不入库"),
        "level": level,
        "elo": elo,
        "player_color": player_color,
        "record": record,
        "start_fen": start_fen,
        "start_cp": None,
        "engine": {"name": "", "path": str(engine_path), "depth": config_for_elo(elo)["depth"]},
        "created": now(),
        "updated": now(),
        "status": "playing",
        "result": "*",
        "plies": [],
    }

    with chessmem.open_engine(str(engine_path), args.threads) as engine:
        session["engine"]["name"] = f"{engine.id.get('name', 'engine')}（{level}档）"
        if player_color == "b":
            engine_reply(session, engine, rng)

    save_session(session)
    report(session)
    print(f"\n对局已建立：{session_id}（难度 {level}，你执{'白' if player_color == 'w' else '黑'}）")
    return 0


def cmd_move(args) -> int:
    session = load_session(args.session)
    if session.get("status") != "playing":
        raise SystemExit("这盘已经结束了")

    board = board_now(session)
    expected_turn = chess.WHITE if session["player_color"] == "w" else chess.BLACK
    if board.turn != expected_turn:
        raise SystemExit("现在不该你走（是不是还没轮到？）")

    raw = args.move.strip()
    move = None
    try:
        candidate = chess.Move.from_uci(raw.lower())
        if candidate in board.legal_moves:
            move = candidate
    except ValueError:
        move = None
    if move is None:
        try:
            move = board.parse_san(raw)
        except ValueError:
            raise SystemExit(f"这步走不了：{raw}")

    rng = random.Random(args.seed if args.seed is not None else None)
    push_ply(session, board, move, "player", (None, None))
    player_san = session["plies"][-1]["san"]
    save_session(session)  # 先把你的这步落盘：万一引擎那步出问题，局面不会停在半路

    with chessmem.open_engine(session["engine"]["path"] or DEFAULT_ENGINE, args.threads) as engine:
        reply = engine_reply(session, engine, rng)

    finish_if_over(session)
    save_session(session)
    report(session)
    print(f"\n你：{player_san}" + (f"　引擎：{reply}" if reply else "　引擎：无着可走"))
    return 0


def finish_if_over(session: dict) -> None:
    board = board_now(session)
    if board.is_game_over():
        session["status"] = "finished"
        session["result"] = result_of(board)


def cmd_reply(args) -> int:
    """轮空补一手：万一引擎那步没跑成，用它续上。"""
    session = load_session(args.session)
    if session.get("status") != "playing":
        raise SystemExit("这盘已经结束了")
    player_is_white = session["player_color"] == "w"
    if board_now(session).turn == (chess.WHITE if player_is_white else chess.BLACK):
        raise SystemExit("现在轮到你走，不用引擎补")
    with chessmem.open_engine(session["engine"]["path"] or DEFAULT_ENGINE, args.threads) as engine:
        reply = engine_reply(session, engine, random.Random(args.seed))
    finish_if_over(session)
    save_session(session)
    report(session)
    print(f"\n引擎：{reply or '无着可走'}")
    return 0


def result_of(board: chess.Board) -> str:
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return "*"
    return outcome.result()


def cmd_state(args) -> int:
    session = load_session(args.session)
    report(session)
    return 0


def cmd_finish(args) -> int:
    session = load_session(args.session)
    board = board_now(session)
    session["result"] = args.result or (result_of(board) if board.is_game_over() else "*")
    session["status"] = "finished"
    save_session(session)

    if not session.get("record"):
        print(f"{session['id']} 是临时对局（未记录在案），已结束，不写入棋谱库。")
        report(session)
        return 0

    PGN_DIR.mkdir(parents=True, exist_ok=True)
    game = chess.pgn.Game()
    game.headers["Event"] = "Codex PvE"
    game.headers["Date"] = session["created"][:10].replace("-", ".")
    game.headers["White"] = "你" if session["player_color"] == "w" else session["engine"]["name"]
    game.headers["Black"] = session["engine"]["name"] if session["player_color"] == "w" else "你"
    game.headers["Result"] = session["result"]
    node = game
    for ply in session["plies"]:
        node = node.add_variation(chess.Move.from_uci(ply["uci"]))
    pgn_path = PGN_DIR / f"{session['id']}.pgn"
    pgn_path.write_text(str(game) + "\n", encoding="utf-8")
    print(f"棋谱已存：{pgn_path.relative_to(ROOT)}")

    ns = argparse.Namespace(
        pgn=str(pgn_path),
        id=session["id"],
        title=session["title"],
        meta=session["meta"] + f" · 结果 {session['result']}",
        depth=args.depth,
        threads=args.threads,
        engine=None,
        fresh=False,
    )
    print("\n用引擎全强度复盘（这一遍才是权威评估）：")
    chessmem.cmd_analyze(ns)
    return 0


def report(session: dict) -> None:
    board = board_now(session)
    white = "我" if session["player_color"] == "w" else session["engine"]["name"]
    black = session["engine"]["name"] if session["player_color"] == "w" else "我"
    print(f"{session['title']}　[{session['id']}]　{session['meta']}")
    print(f"白：{white}　黑：{black}　状态：{session['status']}　结果：{session['result']}")
    line = []
    for i, ply in enumerate(session["plies"]):
        if i % 2 == 0:
            line.append(f"{i // 2 + 1}.")
        line.append(ply["san"])
    print("着法：" + (" ".join(line) if line else "（还没开始）"))
    print("局面：" + board.fen())
    turn = "白方" if board.turn else "黑方"
    you = (session["player_color"] == "w") == board.turn
    print(f"轮到{turn}　→　{'该你走' if you and session['status'] == 'playing' else '等引擎'}")


# ---------------------------------------------------------------- Elo 实测

def play_game(engine, candidate: dict, anchor: dict, candidate_is_white: bool,
              max_plies: int, rng: random.Random) -> tuple:
    """让候选和锚点下一局，返回（候选视角得分, 着数）。"""
    board = chess.Board()
    plies = 0
    for _ in range(max_plies):
        if board.is_game_over(claim_draw=True):
            break
        cand_turn = (board.turn == chess.WHITE) == candidate_is_white
        conf = candidate if cand_turn else anchor
        configure(engine, conf)
        move, _ = pick_engine_move(board, engine, conf, rng)
        if move is None:
            break
        board.push(move)
        plies += 1
    if board.is_checkmate():
        winner_is_white = board.turn == chess.BLACK
        return (1.0 if winner_is_white == candidate_is_white else 0.0), plies
    return 0.5, plies


def elo_from_score(score: float):
    import math

    if score <= 0 or score >= 1:
        return None
    return -400 * math.log10(1 / score - 1)


def elo_ci(score: float, games: int):
    """Wilson 区间换算到 Elo 尺度：比赛接近全胜/全负时比朴素标准误稳得多。"""
    import math

    if games < 2:
        return None
    z = 1.96
    centre = (score + z * z / (2 * games)) / (1 + z * z / games)
    half = z * math.sqrt(score * (1 - score) / games + z * z / (4 * games * games)) / (1 + z * z / games)
    low, high = max(0.0, centre - half), min(1.0, centre + half)
    if low <= 0.0 or high >= 1.0:
        return None
    to_elo = lambda s: -400 * math.log10(1 / s - 1)  # noqa: E731
    return (to_elo(high) - to_elo(low)) / 2


def cmd_elotest(args) -> int:
    cand_elo = resolve_elo(args.candidate)
    anchor_elo = resolve_elo(args.anchor)
    candidate = config_for_elo(cand_elo)
    anchor = config_for_elo(anchor_elo)
    rng = random.Random(args.seed)
    engine_path = args.engine or DEFAULT_ENGINE

    print(f"候选：{level_label(cand_elo)}（目标 {cand_elo} Elo，{candidate['mode']} 模式）")
    print(f"锚点：{level_label(anchor_elo)}（{anchor_elo} Elo，{anchor['mode']} 模式）")
    print(f"共 {args.games} 局，每局最多 {args.max_plies} 着\n")

    results = []
    with chessmem.open_engine(str(engine_path), args.threads) as engine:
        for i in range(args.games):
            cand_white = i % 2 == 0
            score, plies = play_game(engine, candidate, anchor, cand_white, args.max_plies, rng)
            results.append(score)
            tag = "胜" if score == 1 else ("和" if score == 0.5 else "负")
            print(f"  第 {i + 1:>2} 局　候选执{'白' if cand_white else '黑'}　{tag}　{plies} 着")
            sys.stdout.flush()

    wins = sum(1 for r in results if r == 1)
    draws = sum(1 for r in results if r == 0.5)
    losses = len(results) - wins - draws
    score = sum(results) / len(results)
    print(f"\n战绩：{wins} 胜 {draws} 和 {losses} 负　得分 {score:.3f}（{sum(results):g}/{len(results)}）")

    diff = elo_from_score(score)
    if diff is None:
        print("全胜或全败：这个局数给不出估计——换更接近的锚点，或把 --games 加大一个量级。")
    else:
        ci = elo_ci(score, len(results)) or 0
        print(f"相对锚点：{diff:+.0f} Elo　→　估计约 {anchor_elo + diff:.0f} Elo"
              + (f"　（95% 区间 ±{ci:.0f}）" if ci else ""))
        if ci and ci > 150:
            print("（区间还太宽：得分接近 0 或 1 时需要非常多的局数才收得窄）")
    print("\n注意：这里把「Stockfish 的 UCI_Elo 标定」当作锚点的真实实力；局数少时误差很大，"
          "几十局只能看个大概，上百局才谈得上精度。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="人机对战")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="开一局")
    p_new.add_argument("--id")
    p_new.add_argument("--level", default="休闲", help="难度别名：入门/休闲/中等/进阶/强硬/全力")
    p_new.add_argument("--elo", help="直接指定 Elo（400–3190），优先于 --level")
    p_new.add_argument("--player", default="white")
    p_new.add_argument("--record", default="yes", help="yes/no：是否把这盘记入棋谱库")
    p_new.add_argument("--fen", help="从别的局面开始")
    p_new.add_argument("--engine")
    p_new.add_argument("--threads", type=int, default=4)
    p_new.add_argument("--seed", type=int, help="固定随机种子，便于复现")
    p_new.add_argument("--force", action="store_true")
    p_new.set_defaults(func=cmd_new)

    p_move = sub.add_parser("move", help="你走一步（引擎跟着应一手）")
    p_move.add_argument("--session", required=True)
    p_move.add_argument("--move", required=True, help="UCI（e2e4）或 SAN（e4 / Nf3）")
    p_move.add_argument("--threads", type=int, default=4)
    p_move.add_argument("--seed", type=int)
    p_move.set_defaults(func=cmd_move)

    p_state = sub.add_parser("state", help="看当前局面")
    p_state.add_argument("--session", required=True)
    p_state.set_defaults(func=cmd_state)

    p_reply = sub.add_parser("reply", help="让引擎补一手（续上一盘中没跑完的引擎着法）")
    p_reply.add_argument("--session", required=True)
    p_reply.add_argument("--threads", type=int, default=4)
    p_reply.add_argument("--seed", type=int)
    p_reply.set_defaults(func=cmd_reply)

    p_elo = sub.add_parser("elotest", help="实测某档难度的 Elo（和锚点对打若干局）")
    p_elo.add_argument("--candidate", default="休闲", help="被测档位：名字或 Elo 数字")
    p_elo.add_argument("--anchor", default="1320", help="锚点档位，默认 Stockfish 自带限强的 1320")
    p_elo.add_argument("--games", type=int, default=20)
    p_elo.add_argument("--max-plies", type=int, default=200)
    p_elo.add_argument("--threads", type=int, default=4)
    p_elo.add_argument("--engine")
    p_elo.add_argument("--seed", type=int)
    p_elo.set_defaults(func=cmd_elotest)

    p_finish = sub.add_parser("finish", help="结束并（可选）复盘入库")
    p_finish.add_argument("--session", required=True)
    p_finish.add_argument("--result", help="1-0 / 0-1 / 1/2-1/2")
    p_finish.add_argument("--depth", type=int, default=16)
    p_finish.add_argument("--threads", type=int, default=4)
    p_finish.set_defaults(func=cmd_finish)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
