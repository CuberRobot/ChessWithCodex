#!/usr/bin/env python3
"""ChessPlugin 的 MCP 服务：把仓库里的能力暴露成工具，让 Codex 直接调用。

走 stdio + 逐行 JSON-RPC，不依赖任何第三方 MCP SDK——这样随仓库自带就能跑。
每个工具都是薄封装：直接调用 tools/ 里现成的函数，保证命令行和工具行为一致。
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import chessmem  # noqa: E402
import pve  # noqa: E402
import render_board  # noqa: E402
import render_play  # noqa: E402
import render_replay  # noqa: E402

SERVER_NAME = "chess"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2024-11-05"


def call(module, argv: list) -> tuple:
    """跑一个命令行模块：argv 交给它的解析器，再把输出收成工具结果。

    统一走「模块 + argv」这条路，工具行为和命令行完全一致，不会两套逻辑各自跑偏。
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            if hasattr(module, "build_parser"):
                ns = module.build_parser().parse_args(argv)
                ns.func(ns)
            else:
                module.main(argv)
        except SystemExit as exc:  # argparse 与各工具的报错都走这里
            if exc.code not in (0, None):
                text = buf.getvalue().strip()
                if text:
                    return text, True
                return (exc.code if isinstance(exc.code, str) else f"命令没跑成（退出码 {exc.code}）"), True
    return buf.getvalue().strip(), False


def tool(name: str, description: str, properties: dict, required: list = None) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }


S = lambda desc: {"type": "string", "description": desc}  # noqa: E731
N = lambda desc: {"type": "integer", "description": desc}  # noqa: E731

TOOLS = [
    tool("list_games", "列出本地棋谱库（可按棋手/结果/开局过滤）", {
        "player": S("棋手名，模糊匹配"),
        "result": S("结果，如 1-0 / 1/2-1/2"),
        "eco": S("开局代码，如 C41"),
    }),
    tool("show_game", "把一盘棋打印成着法+评估清单", {
        "id": S("棋谱 id"),
        "json_output": {"type": "boolean", "description": "输出原始 JSON"},
    }, ["id"]),
    tool("analyze_pgn", "分析一盘棋（PGN 路径或 PGN 文本）并写入棋谱库", {
        "pgn_path": S("PGN 文件路径"),
        "pgn_text": S("直接给 PGN 文本（和 pgn_path 二选一）"),
        "id": S("记录 id（默认取文件名）"),
        "title": S("标题"),
        "meta": S("副标题/说明"),
        "depth": N("分析深度，默认 16"),
    }, []),
    tool("render_replay", "渲染可点着走的回放界面，返回 HTML 片段路径", {
        "id": S("棋谱 id"),
        "session": S("进行中的人机对局 id（和 id 二选一）"),
        "out": S("输出路径（通常放线程的可视化目录）"),
        "pieces": S("棋组：chessnut（默认）/ spatial"),
        "show_eval": {"type": "boolean", "description": "是否显示评估条"},
    }, ["out"]),
    tool("render_board", "渲染单张棋盘（某盘棋的某一着，或直接给 FEN）", {
        "id": S("棋谱 id"),
        "ply": N("第几着之后（1 起）"),
        "fen": S("直接给 FEN（和 id+ply 二选一）"),
        "caption": S("图注"),
        "out": S("输出路径"),
        "pieces": S("棋组"),
    }, ["out"]),
    tool("render_play", "渲染一个可以点着下的人机对战界面（离线、自带轻量对手）", {
        "out": S("输出路径"),
        "player": S("你执白还是黑：white / black"),
        "level": N("对手强度 1-4（1 很弱、4 认真下），默认 2"),
        "fen": S("从指定局面开始"),
        "pieces": S("棋组"),
    }, ["out"]),
    tool("pve_new", "开一局人机对战（按 Elo 选难度）", {
        "id": S("对局 id"),
        "level": S("难度档位：入门/休闲/中等/进阶/强硬/全力"),
        "elo": N("直接指定 Elo（400–3190），优先于 level"),
        "player": S("你执白还是黑：white / black"),
        "record": S("yes/no：是否记入棋谱库，默认 yes"),
    }),
    tool("pve_move", "在人机对战中走一步（引擎会跟着应一手）", {
        "session": S("对局 id"),
        "move": S("UCI（e2e4）或 SAN（e4 / Nf3）"),
    }, ["session", "move"]),
    tool("pve_finish", "结束对局；记录在案的会被全强度复盘并入库", {
        "session": S("对局 id"),
        "result": S("结果：1-0 / 0-1 / 1/2-1/2（默认按局面自动判断）"),
        "depth": N("复盘深度，默认 16"),
    }, ["session"]),
    tool("elo_test", "实测某档难度的 Elo（和锚点对打若干局）", {
        "candidate": S("被测档位：名字或 Elo"),
        "anchor": S("锚点档位，默认 1320"),
        "games": N("局数，默认 20；想要可信就上百"),
    }),
    tool("cache_stats", "看看棋谱库和评估缓存的家底", {}),
]


def dispatch(name: str, args: dict) -> tuple:
    if name == "list_games":
        argv = ["list"]
        for key in ("player", "result", "eco"):
            if args.get(key):
                argv += [f"--{key}", str(args[key])]
        return call(chessmem, argv)

    if name == "show_game":
        argv = ["show", args["id"]] + (["--json"] if args.get("json_output") else [])
        return call(chessmem, argv)

    if name == "analyze_pgn":
        path = args.get("pgn_path")
        tmp = None
        if not path:
            text = args.get("pgn_text")
            if not text:
                return "要么给 pgn_path，要么给 pgn_text", True
            handle = tempfile.NamedTemporaryFile("w", suffix=".pgn", delete=False, encoding="utf-8")
            handle.write(text)
            handle.close()
            tmp = handle.name
            path = tmp
        argv = ["analyze", "--pgn", path, "--depth", str(args.get("depth") or 16)]
        if args.get("id"):
            argv += ["--id", args["id"]]
        if args.get("title"):
            argv += ["--title", args["title"]]
        if args.get("meta"):
            argv += ["--meta", args["meta"]]
        try:
            return call(chessmem, argv)
        finally:
            if tmp:
                pathlib.Path(tmp).unlink(missing_ok=True)

    if name == "render_replay":
        argv = ["--out", args["out"]]
        argv += ["--id", args["id"]] if args.get("id") else ["--session", args["session"]]
        if args.get("pieces"):
            argv += ["--pieces", args["pieces"]]
        if args.get("show_eval"):
            argv += ["--show-eval"]
        return call(render_replay, argv)

    if name == "render_board":
        argv = ["--out", args["out"]]
        if args.get("fen"):
            argv += ["--fen", args["fen"]]
        else:
            argv += ["--id", args["id"], "--ply", str(args.get("ply") or 1)]
        if args.get("caption"):
            argv += ["--caption", args["caption"]]
        if args.get("pieces"):
            argv += ["--pieces", args["pieces"]]
        return call(render_board, argv)

    if name == "render_play":
        argv = ["--out", args["out"]]
        for key in ("player", "fen", "pieces"):
            if args.get(key):
                argv += [f"--{key}", str(args[key])]
        if args.get("level"):
            argv += ["--level", str(args["level"])]
        return call(render_play, argv)

    if name == "pve_new":
        argv = []
        if args.get("id"):
            argv += ["--id", args["id"]]
        if args.get("elo"):
            argv += ["--elo", str(args["elo"])]
        elif args.get("level"):
            argv += ["--level", args["level"]]
        if args.get("player"):
            argv += ["--player", args["player"]]
        if args.get("record"):
            argv += ["--record", args["record"]]
        return call(pve, ["new"] + argv)

    if name == "pve_move":
        return call(pve, ["move", "--session", args["session"], "--move", args["move"]])

    if name == "pve_finish":
        argv = ["--session", args["session"]]
        if args.get("result"):
            argv += ["--result", args["result"]]
        if args.get("depth"):
            argv += ["--depth", str(args["depth"])]
        return call(pve, ["finish"] + argv)

    if name == "elo_test":
        argv = ["--games", str(args.get("games") or 20)]
        if args.get("candidate"):
            argv += ["--candidate", str(args["candidate"])]
        if args.get("anchor"):
            argv += ["--anchor", str(args["anchor"])]
        return call(pve, ["elotest"] + argv)

    if name == "cache_stats":
        return call(chessmem, ["stats"])

    return f"没有这个工具：{name}", True


def handle(request: dict):
    method = request.get("method")
    params = request.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        text, is_error = dispatch(params.get("name", ""), params.get("arguments") or {})
        return {"content": [{"type": "text", "text": text or "(没有输出)"}], "isError": is_error}
    if method == "ping":
        return {}
    if method in ("notifications/initialized", "notifications/cancelled", "notifications/progress"):
        return None
    raise KeyError(method)


def respond(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            respond({"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "JSON 解析失败"}})
            continue

        request_id = request.get("id")
        try:
            result = handle(request)
        except KeyError as exc:
            if request_id is not None:
                respond({"jsonrpc": "2.0", "id": request_id,
                         "error": {"code": -32601, "message": f"不支持的方法：{exc.args[0]}"}})
            continue
        except Exception as exc:  # 工具内部的意外错误也不该让服务挂掉
            if request_id is not None:
                respond({"jsonrpc": "2.0", "id": request_id,
                         "error": {"code": -32603, "message": f"内部错误：{exc}"}})
            continue

        if result is not None and request_id is not None:
            respond({"jsonrpc": "2.0", "id": request_id, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
