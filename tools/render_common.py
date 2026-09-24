"""两个渲染脚本共用的部分：棋组筛选 + 模板占位符注入。"""
from __future__ import annotations

import json
import pathlib

RUNTIME_PLACEHOLDER = "__PIECES_RUNTIME__"
PIECES_PLACEHOLDER = "__PIECE_SETS__"


def load_piece_sets(pieces_file: pathlib.Path, name: str) -> str:
    """只把用到的这一套棋组注入产物——三套全塞进去会让每个文件白白大一倍多。"""
    raw = pieces_file.read_text(encoding="utf-8")
    try:
        data = json.loads(raw.split("=", 1)[1].strip().rstrip(";"))
    except (IndexError, json.JSONDecodeError):
        raise SystemExit(f"读不懂棋组文件 {pieces_file}，先跑 tools/import_pieces.py")
    if name not in data:
        raise SystemExit(f"棋组 {name} 不在 {pieces_file.name} 里，可选：{', '.join(data)}")
    payload = json.dumps({name: data[name]}, ensure_ascii=False, separators=(",", ":"))
    return "const PIECE_SETS = " + payload + ";"


def render_template(template: str, runtime_js: str, pieces_js: str, placeholders: dict) -> str:
    html = template.replace(RUNTIME_PLACEHOLDER, runtime_js.strip())
    html = html.replace(PIECES_PLACEHOLDER, pieces_js.strip())
    for key, value in placeholders.items():
        if key not in html:
            raise SystemExit(f"模板里找不到占位符 {key}")
        html = html.replace(key, value)
    return html
