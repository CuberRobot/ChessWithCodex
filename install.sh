#!/bin/sh
# mac / Linux 安装：建 venv、装依赖、找引擎、写插件配置、登记 marketplace。
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "==> 1/4 建虚拟环境"
if [ -x .venv/bin/python ]; then
  echo "    已存在，跳过"
else
  python3 -m venv .venv
fi
PY="$ROOT/.venv/bin/python"

echo "==> 2/4 装依赖（python-chess）"
"$PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo "==> 3/4 找 Stockfish"
if ENGINE=$("$PY" -c "from tools.engines import find_engine; print(find_engine(required=False) or '')"); then
  if [ -n "$ENGINE" ]; then echo "    找到：$ENGINE"; else
    echo "    没找到。分析/复盘需要它，装一下再把路径告诉我（或用 CHESSPLUGIN_ENGINE 指定）："
    "$PY" -c "from tools.engines import INSTALL_HINT; print('    ' + INSTALL_HINT.replace(chr(10), chr(10) + '    '))"
  fi
fi

echo "==> 4/4 写插件配置并登记 marketplace"
"$PY" - <<'PYEOF'
import json, os, pathlib, sys
root = pathlib.Path(os.getcwd())
cfg = root / ".mcp.json"
cfg.write_text(json.dumps({"mcpServers": {"chess": {
    "command": str(root / ".venv" / "bin" / "python"),
    "args": [str(root / "mcp" / "server.py")]}}}, indent=2) + "\n", encoding="utf-8")
print("    已写 .mcp.json（指向本机绝对路径）")

entry = {"name": "chess",
         "source": {"source": "local", "path": str(root)},
         "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
         "category": "Productivity"}
market = pathlib.Path.home() / ".agents" / "plugins" / "marketplace.json"
market.parent.mkdir(parents=True, exist_ok=True)
data = json.loads(market.read_text(encoding="utf-8")) if market.exists() else {
    "name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
data.setdefault("plugins", [])
data["plugins"] = [p for p in data["plugins"] if p.get("name") != "chess"] + [entry]
market.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"    已登记到 {market}")
PYEOF

echo
echo "完成。重启 Codex 后，在 Personal 里启用 chess 插件即可。"
