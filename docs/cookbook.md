# 任务食谱

一条条可复制的做法。命令都在仓库根目录、用自带 venv 跑。

## 1. 收一盘棋

```bash
# 文件
.venv/bin/python tools/chessmem.py analyze --pgn pgn/x.pgn --id x --title "标题" --meta "副标题" --depth 16
# 或直接粘 PGN 文本（stdin）
printf '%s\n' '[Event "..."]' '' '1. e4 e5 2. Nf3 1-0' | .venv/bin/python tools/chessmem.py analyze --pgn - --id x
# 一次收完 pgn/ 里所有棋谱
.venv/bin/python tools/chessmem.py analyze-all
```

预期输出：着数、局面数、**引擎查询 N 次 / 缓存命中 M 次**、用时。第二次跑同一盘应该是"0 次查询"。
PGN 走不通会直接说哪里走不通，不会甩堆栈。

## 2. 给一盘棋写讲解

讲解写在 `notes/<id>.json`（按着法序号索引，带 SAN 校验），**不要改 `games/`**：

```json
{
  "start_note": "起始局面下的一句提示",
  "plies": [
    { "ply": 3, "san": "d3", "note": "讲解文字" },
    { "ply": 13, "san": "Bf7#", "note": "为什么是杀",
      "arrows": [{ "from": "c4", "to": "f7", "tone": "best" }],
      "highlights": [{ "square": "e8", "tone": "check", "style": "ring" }] }
  ]
}
```

改完重新跑一次 `analyze`（命中缓存，1 秒内）把讲解合并进记录，再渲染。
着法序号不存在、或 SAN 与棋谱对不上，会警告并跳过那一条。

## 3. 在对话里展示

1. 产物写到**当前线程的可视化目录**：`~/.codex/visualizations/<日期>/<线程id>/`；
2. 用渲染脚本生成**片段**（不是完整网页）；
3. 回复里按"可视化引用"的方式给出路径（不要用普通文件链接），一次回复只放一个。

```bash
V=~/.codex/visualizations/2026/09/13/<线程id>
.venv/bin/python tools/render_replay.py --id x --out $V/replay.html
```

## 4. 讲一盘棋的流程

1. `show_game` → 看整盘评估曲线，找**跳变**（不是找"谁下得好"）；
2. 挑 **2-3 个转折点**，每个都要有：引擎数字、当时的替代着法、以及它意味着什么；
3. 赢棋要归因：对手是几档、它的失误是设计使然还是真被打崩；
4. 界面上已经画出来的信息不要在正文里复述；
5. 有问题的地方（包括自己这边的漏着）要直说——这是这个工具存在的意义。

## 5. 开一局

**想让用户自己点着下**（推荐）：

```bash
.venv/bin/python tools/render_play.py --out $V/play.html --player black --level 2
```

用户点棋子、点落点；对手离线应手；右边是吃子和子力差；下完按"让 Codex 点评"把棋谱传回来，再走第 1、4 步。

**想逐手陪你下**（需要真引擎评估时）：

```bash
.venv/bin/python tools/pve.py new --id s --level 中等 --player white --record yes
.venv/bin/python tools/pve.py move --session s --move Nf3
.venv/bin/python tools/pve.py finish --session s      # 全强度复盘并入库
```

`--record no` 表示不留档（临时练手）。对局中显示的是受限引擎的自评，别当定论。

## 6. 换棋组 / 加棋组

```bash
.venv/bin/python tools/render_replay.py --id x --out $V/r.html --pieces spatial
```

可选 `chessnut`（默认，Apache 2.0）/ `spatial`（MIT）。

加新棋组：把 12 个 SVG（`wK wQ wR wB wN wP bK bQ bR bB bN bP`）放进 `assets/pieces/<名字>/`，
在 `assets/pieces/LICENSE.md` 里记下作者与许可，然后跑 `.venv/bin/python tools/import_pieces.py`。

许可要当回事：`staunty`/`fresca`/`maestro` 更好看但都是 CC BY-NC-SA（禁止商用），当初就是因为这条没收进来。

## 7. 只看一个局面

```bash
.venv/bin/python tools/render_board.py --id x --ply 12 --out $V/b.html
.venv/bin/python tools/render_board.py --fen "rnbq... w KQkq - 0 1" --out $V/b.html
```

可选参数：`--orientation black`、`--theme green|slate`、`--caption "图注"`。

## 8. 检索与家底

```bash
.venv/bin/python tools/chessmem.py list --player Morphy --result 1-0 --eco C41
.venv/bin/python tools/chessmem.py stats
```

## 9. 测某档难度的真实水平

```bash
.venv/bin/python tools/pve.py elotest --candidate 入门 --anchor 1320 --games 120
```

120 局大约半分钟。得分接近 0/1 时区间会很大，别过度解读；想要可信就加大局数。

## 10. 更新插件

改完 `mcp/server.py`、`skills/` 或清单后，先用官方校验器校验本仓库，再用 `update_plugin_cachebuster.py`
刷新缓存戳（两个脚本都在 `~/.codex/skills/.system/plugin-creator/scripts/`）。

## 11. 故障排查

| 现象 | 原因 / 处理 |
| --- | --- |
| `找不到引擎` | `brew install stockfish`，或用 `--engine` / `CHESSPLUGIN_ENGINE` 指定 |
| `PGN 里有走不通的地方` | 棋谱本身有非法着法；先核对着法列表 |
| 第二次跑还是"引擎查询 N 次" | 深度或引擎换了（缓存键含这两项），属正常 |
| 界面一片空白 / 没有棋子 | 多半是模板 JS 报错；跑 `dev/tests/smoke.py --browser` 看具体哪一行 |
| 产物里出现 `__XXX__` | 占位符没被替换，说明没用渲染脚本生成 |
| 无头 Chrome 卡住不返回 | 它打印完 DOM 不会自己退出；拿完输出就 kill |
| `git` 报 Operation not permitted | 沙箱对 `.git` 只读，需要提权执行 |
| 窄屏截图被裁 | 无头窗口最小宽度约 500px；用固定宽容器模拟窄屏 |
