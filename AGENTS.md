# 在这个仓库里工作：操作契约

给任何接手这个项目的人／agent 看的。目标：**不用重新摸索就能正确操作**。
更细的实现见 [`docs/architecture.md`](docs/architecture.md)，任务食谱见 [`docs/cookbook.md`](docs/cookbook.md)。

## 这是什么

本地棋谱库 + Stockfish 分析 + 三种界面（单张棋盘 / 可回放 / 可对弈），
并以 Codex 插件的形式暴露成工具。**全部离线**，数据都在仓库里。

## 五条铁律

1. **`games/` 是生成物，不要手改**。它由 `tools/chessmem.py` 从 PGN 重算出来，改了会被覆盖。
   要加讲解就写 `notes/<id>.json`（人写的），重算时按「第几着 + SAN」合并回记录。
2. **数字必须来自引擎**。评估、最佳着法、失误判定一律用 Stockfish 的结果；
   不要凭手感给评估。对局中显示的是受限强度的引擎自评，**不能当定论**——定论用 `analyze` 全强度重算。
3. **评估以「局面 + 深度 + 引擎名」为缓存键**（`cache/evals.json`）。默认走缓存，
   只有加 `--fresh` 才强制重算。换深度会自然失效，这是设计而非 bug。
4. **渲染产物是 HTML 片段**（不含 doctype/html/head/body），写到**当前线程的可视化目录**
   `~/.codex/visualizations/<日期>/<线程id>/`，再用可视化引用的方式交给用户，而不是普通文件链接。
5. **改完必须跑 `dev/tests/smoke.py`**（加 `--browser` 会真开浏览器逐格校验）再提交。
   注意 `dev/` 是本地开发目录、**不入库**：测试与诊断脚本只在自己的机器上留存。

## 常用命令（都在仓库根目录，用自带的 venv）

```bash
# 棋谱
.venv/bin/python tools/chessmem.py analyze --pgn pgn/x.pgn --id x --depth 16   # 单盘入库
.venv/bin/python tools/chessmem.py analyze-all                                  # 批量入库 pgn/
.venv/bin/python tools/chessmem.py list [--player 名] [--result 1-0] [--eco C41]
.venv/bin/python tools/chessmem.py show x [--json]                              # 着法 + 评估 + 讲解
.venv/bin/python tools/chessmem.py stats

# 三种界面
.venv/bin/python tools/render_replay.py --id x --out 路径            # 回放台（可点/可自动播）
.venv/bin/python tools/render_replay.py --session s --out 路径       # 进行中的对局（默认不显示评估条）
.venv/bin/python tools/render_board.py  --id x --ply 10 --out 路径   # 单张棋盘
.venv/bin/python tools/render_board.py  --fen "FEN" --out 路径
.venv/bin/python tools/render_play.py   --out 路径 [--player black] [--level 1-4]

# 人机对战（Python 侧）
.venv/bin/python tools/pve.py new --id s --level 休闲 --player white --record yes
.venv/bin/python tools/pve.py move --session s --move e4
.venv/bin/python tools/pve.py finish --session s        # 记录在案的话会全强度复盘入库
.venv/bin/python tools/pve.py elotest --candidate 入门 --anchor 1320 --games 120

# 素材 / 测试
.venv/bin/python tools/import_pieces.py      # 打包 assets/pieces/ 成 templates/pieces.js
.venv/bin/python dev/tools/probe_engine.py hello # 引擎链路诊断（本地，不入库）
sh tools/build/build_engine.sh               # 自己编单文件浏览器引擎（需 emscripten）
.venv/bin/python dev/tests/smoke.py --browser
```

## 插件（工具层）

仓库本身就是插件：`.codex-plugin/plugin.json`、`.mcp.json`（**绝对路径**指向 `.venv/bin/python mcp/server.py`）、
`skills/chess/SKILL.md`。已注册在 `~/.agents/plugins/marketplace.json`；改了插件内容后刷新缓存戳再重装。

暴露 11 个工具，**以 `mcp/server.py` 里的 `TOOLS` 为准**：
`list_games`、`show_game`、`analyze_pgn`、`render_replay`、`render_board`、`render_play`、
`pve_new`、`pve_move`、`pve_finish`、`elo_test`、`cache_stats`。
每个都是薄封装——直接调用 `tools/` 里同一套函数（`call(module, argv)` 走各自 argparse），
所以命令行和插件不会出现两套行为。

## 讲棋的纪律（这是产品的一部分）

- 先 `show_game` 看整盘的评估曲线，挑 **2-3 个转折点**讲，不要逐手复述。
- 指出问题时要给出引擎数字和替代着法（例如"2.exf5 是 +1.90，实战 2.d3 只剩 +0.36"）。
- 赢棋要归因清楚：对手是几档、它的失误是设计使然还是真被打崩了。
- 界面上已经画出来的东西不要在正文里重复一遍。

## 环境与坑（都是踩过的）

- 沙箱里 `.git` 只读 → `git init/add/commit` 需要提权。
- 无头 Chrome 在这台机器上 `--dump-dom` 后**不会自己退出**：测试里是「读到输出就 kill」。
- 无头 Chrome 的窗口最小宽度约 500px，测窄屏要用容器模拟。
- 可视化沙箱的 CSP 只放行少数 CDN，且 **`connect-src` 只有 blob/data（不能 fetch）**：
  所以规则库与引擎都必须**内嵌成数据**再运行时解出来用。对弈界面里的真引擎就是自己编的
  单文件 Stockfish（`engines/stockfish-single.js`，wasm 内嵌，**不随仓库分发**，见 `THIRD-PARTY.md`），
  以 gzip+base64 注入，产物约 394KB。引擎不在时界面自动退回轻量搜索，功能不受影响。
- **引擎必须先"就绪"再发指令**：建好 worker 就发命令会得到 `null function` /
  `memory access out of bounds`（运行时还没初始化完）。正确姿势是发 `uci`、等 `uciok` 再开始用；
  对弈界面里 20 秒没就绪会自动退回轻量引擎。
- **引擎代码只走字节，不做文本往返**：base64 → `Uint8Array` → `Blob` → worker/`<script src>`。
  用 `TextDecoder` 转成字符串再执行会弄坏它。
- **别用无头 Chrome + `--virtual-time-budget` 判断异步 wasm 能不能跑**：虚拟时间会卡住异步初始化，
  看起来像"引擎没反应"。判断引擎是否正常，用 Node 在真实时间里跑（或直接用真实界面看状态行）。
- 棋子渲染靠首次使用时的离屏 `getBBox()` 量包围盒（元素必须在文档里），
  再按统一比例和同一条基线摆放——换棋组不用手调。
- python-chess 的引擎评分要 `.pov(chess.WHITE)`；曾经因为 negamax 用错视角（白方视角 vs 行棋方视角）导致"强力档"乱走。
- 记录里 `mate: 0` 表示「已经将杀」，具体谁赢要结合该局面 FEN 的走子方判断。

## 边界（别承诺做不到的事）

- 浏览器里的对手**默认是真 Stockfish**（自编译单文件版，难度 1–4 走 `Skill Level`）；
  引擎没就绪时自动退回自带的轻量搜索（深度 1–3）保证棋盘永远能下。
  这个构建**没有 `UCI_Elo`**（源码较老），所以数字上的 Elo 标定只在 Python 侧那条路有效。
- Elo 实测目前只把 600 档标定准了；更高档需要更弱的锚点做链式标定。
- PvE 对局只存在浏览器内存里，刷新即重开；要留档必须把棋谱传回来入库。
- 棋钟**已做**（1+0 / 2+1 / 3+2 / 5+3 / 10+0 / 15+10、走完加秒、最后 10 秒变红、超时判负）；
  对弈界面还有「对手引擎（真/轻量）」和「重新开始」两个开关。
- **还没做**：长棋（40+ 回合）的着法列表双列排版；每手前三候选（MultiPV）自动进记录并画成箭头（现在仍手写）；
  对局持久化（刷新即重开，PvE 历史没有落库，所以也做不了跨盘统计）。
