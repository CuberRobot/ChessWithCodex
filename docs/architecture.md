# 实现说明

面向要改代码的人。操作约定在 [`../AGENTS.md`](../AGENTS.md)，任务食谱在 [`cookbook.md`](cookbook.md)。

## 数据流

```
pgn/*.pgn ──analyze──► games/<id>.json ──render_*──► HTML 片段 ──► 对话里的界面
                │  ▲                        ▲
                │  └── notes/<id>.json ─────┘（讲解/标注，人写，重算时合并）
                └──► cache/evals.json（局面 → 评估，跨棋谱复用）
```

一份记录是唯一的真相；缓存是可丢弃的加速层；讲解是人的资产，永不覆盖。

## 目录职责

| 路径 | 谁写 | 说明 |
| --- | --- | --- |
| `pgn/` | 人 | 原始棋谱。`analyze` 也能读 stdin（`--pgn -`） |
| `games/` | `chessmem.py` | 完整记录，**生成物** |
| `notes/` | 人 | 讲解与标注，按着法序号索引 |
| `cache/evals.json` | `chessmem.py` | 评估记忆，键为 `<fen>|d<深度>|<引擎名>` |
| `sessions/` | `pve.py` | 进行中的人机对局（结构同记录，多几个字段） |
| `tools/` | 人 | 7 个命令行工具，同时也是插件工具的实现 |
| `templates/` | 人 | 三个界面模板 + 棋子渲染器 + 打包后的棋组数据 |
| `assets/pieces/` | 人（外部素材） | 开源棋组，许可见 `assets/pieces/LICENSE.md` |
| `assets/js/chess.js` | 人（外部素材） | 内嵌的规则库（MIT），供对弈界面离线使用 |
| `mcp/server.py` | 人 | stdio JSON-RPC 服务，把工具暴露给 Codex |
| `dev/tests/smoke.py` | 人（本地，不入库） | 端到端自检 |

## 记录格式（`games/<id>.json`）

```jsonc
{
  "id": "legal-trap-1750",
  "title": "Légal 的陷阱",
  "meta": "巴黎 1750 · 白 Légal / 黑 Saint Brie · 结果 1-0",
  "headers": { "White": "...", "Black": "...", "Result": "1-0", "ECO": "C41" },
  "start_fen": "rnbq.../... w KQkq - 0 1",
  "start_cp": 25, "start_mate": null,        // 起始局面评估（白方视角）
  "start_note": "…",
  "engine": { "name": "Stockfish 19", "path": "...", "depth": 16, "threads": 4 },
  "created": "…", "analyzed": "…", "source": "pgn/legal-trap-1750.pgn",
  "stats": { "positions": 14, "cache_hits": 14, "engine_queries": 0, "seconds": 0.15 },
  "plies": [
    {
      "ply": 1, "san": "e4", "uci": "e2e4", "fen": "<走后的 FEN>",
      "cp": 29, "mate": null,                 // 白方视角；mate 非空时 cp 为 null
      "note": "…",                            // 这四个字段是人写的，重算时保留
      "arrows": [], "highlights": [], "markers": []
    }
  ]
}
```

约定：

- 评估一律**白方视角**（`score.pov(chess.WHITE)`）。`mate: 0` 表示"已经将杀"。
- `AUTHORED_FIELDS = note / arrows / highlights / markers` 是"人写的"，重算时按
  `(ply, san)` 匹配保留；`notes/<id>.json` 里的内容优先，且会校验 SAN 对得上，对不上警告并跳过。
- 标注语义色：`focus`（关键格）、`plan/best/alt/threat/mistake/blunder`（箭头与角标）、
  `check`（将军）、`last`（上一着）。样式 `fill | ring | dot`，其中 `dot` 画在棋子之上。
  完整表在 `templates/board.html` 的 `TONES`。

## 缓存语义

- 键：`f"{fen}|d{depth}|{engine_name}"`，值：`{cp, mate}`。
- 命中就不问引擎；`--fresh` 绕过。换深度或换引擎会自然重算，换命令不会。
- 终局（将杀/和棋）由 python-chess 直接判定，不占缓存。
- 实测：两盘共享开局的棋，第二盘 33 着里省掉 5 次查询；重跑同一盘是 0 次查询、0.1 秒级。

## 渲染管线

三个界面共用一套东西：

1. `templates/pieces.js`——由 `tools/import_pieces.py` 从 `assets/pieces/<棋组>/*.svg` 打包，
   内含每套棋子的 `viewBox` 与 SVG 内容。
2. `templates/pieces-runtime.js`——`makePieceRenderer()`：首次使用时离屏量出整套棋子的**包围盒**
   （`getBBox()` 要求元素在文档里），之后所有棋子按同一比例、同一条基线摆放，换棋组不用手调。
3. `tools/render_common.py`——只注入**用到的那一套**棋组（三套全塞会让产物白白大一倍多：
   92KB → 56KB），并统一替换占位符。

模板占位符（渲染脚本负责填）：

| 模板 | 占位符 | 内容 |
| --- | --- | --- |
| `board.html` | `__BOARD_JSON__` | 单个局面的参数（fen/标注/评估/图注…） |
| `replay.html` | `__GAME_JSON__` | 一盘棋（标题/着法/讲解/是否显示评估条） |
| `play.html` | `__PLAY_JSON__`、`__CHESS_JS__` | 对弈参数 + 内嵌规则库 |
| 三者共用 | `__PIECE_SETS__`、`__PIECES_RUNTIME__` | 棋组数据与渲染器 |

产物是 **HTML 片段**（无 doctype/html/head/body），必须写到当前线程的可视化目录。

## 人机对战为什么有两条路

| | Python 侧 `tools/pve.py` | 浏览器侧 `templates/play.html` |
| --- | --- | --- |
| 对手 | **真 Stockfish** | 产物自带的轻量搜索（深度 1–3） |
| 难度 | Elo（600–3190，可实测） | 4 档（深度 + 温度 + 随机度） |
| 交互 | 逐手命令 | 点击落子、吃子与子力、悔棋 |
| 用途 | 认真对局、需要真引擎评估 | 随手玩、离线可跑 |

浏览器侧不用 Stockfish 的原因：可视化沙箱 `connect-src` 只有 blob/data（**不能 fetch**），
而单文件浏览器版 Stockfish 有 1.5MB，超过片段 1MB 上限。所以强分析一律回到 Python 侧。
对局中显示的评估来自受限档位，**不能当定论**；`pve.py finish` 会用全强度重算。
（`play.html` 踩过的坑：negamax 要求"行棋方视角"，评估函数若写成白方视角就会反号；
搜索必须带时间预算，否则深搜会卡住界面。）

## 难度曲线（`pve.py`）

- `≥1320`：用 Stockfish 自带的 `UCI_LimitStrength + UCI_Elo`（它家标定过的限强）。
- `<1320`：它够不到，用 `w = (1320 - elo)/(1320 - 400)` 插值出
  `depth(2–8) / pool(3–8) / temp(40–300) / random(0–5%) / skill(14–0)`——
  低档主要输在**看不见战术**，随机着只占很小比例（调大它会变成"送子机器"，实测 120 局全负）。

`elotest` 的数学：得分 `score = (胜 + 0.5·和)/局数` →
`ΔElo = -400·log10(1/score - 1)`，区间用 Wilson 换算，并**把 Stockfish 的 UCI_Elo 标定当锚点真值**。
得分接近 0 或 1 时区间会大到没意义，这是方法本身的限制。

## 插件层

- `.codex-plugin/plugin.json`（清单，通过官方 `validate_plugin.py`）、`.mcp.json`（绝对路径启动服务）、`skills/chess/SKILL.md`。
- `mcp/server.py`：不依赖第三方 MCP SDK 的 stdio JSON-RPC 实现，支持
  `initialize` / `tools/list` / `tools/call` / `ping`，通知类消息忽略。
  工具统一走 `call(module, argv)`：把 argv 交给该模块的 argparse 再调用 `func`，
  保证插件与命令行行为一致（曾因为直接把 argv 喂给接收 Namespace 的函数而全崩过）。

## 测试策略（`dev/tests/smoke.py`，本地开发用，不随仓库分发）

1. 分析一盘小棋（`--fresh` 强制真问引擎）→ 校验记录结构与着数；
2. 重跑一次 → 断言 0 次引擎查询（缓存生效）；
3. 渲染两个界面 → 断言没有残留占位符；
4. `--browser`：用无头 Chrome 打开 → 断言**没有 JS 报错**、且 **DOM 里的棋子集合与 FEN 逐格一致**；
5. MCP 层：管道发四个 JSON-RPC 请求，断言工具数量、正常返回与错误分支。

第 4 步是唯一能抓住模板 JS 问题的一环（变量顺序、未定义标识符都只有浏览器能发现）。

## 已知限制与技术债

- 长棋（40+ 回合）的着法列表会拉成一条长蛇，双列排版还没做。
- 每手的前三候选（MultiPV）没有自动进记录，箭头标注仍是手写。
- `elotest` 只把 600 档标定准了；更高档需要更弱的锚点做链式标定。
- 浏览器侧对弈只在内存里，刷新即重开；留档要靠"让 Codex 点评"把棋谱传回来。
- 升变、王车易位这些路径靠人工构造局面测过，还没有系统性的残局用例集。
