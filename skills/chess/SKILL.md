---
name: "chess"
description: "Local chess workspace: store PGNs, analyse positions and whole games with Stockfish, render an interactive replay board, and play PvE games at a chosen Elo. Use when the user wants to save or review a chess game, ask about a position or a move, play chess against the engine, or see a board rendered in the conversation."
---

# Chess

本地棋谱库 + Stockfish 分析 + 人机对战。所有数据都在这个仓库里，不联网。

## 什么时候用

- 用户发来一盘棋（PGN / 着法列表）想存下来、想让你讲讲 → `analyze_pgn` 入库，再 `render_replay` 出可交互的回放台。
- 用户问某个局面、某一步好不好 → 有记录就 `render_board`（`id` + `ply`），或直接拿 FEN 渲染；评估一律以引擎为准，不要凭手感下结论。
- 用户想下棋 → `pve_new` 开局（按 Elo 选难度，**默认不要用全力**），之后每轮 `pve_move` 走一步。
- 用户想知道某档难度到底多强 → `elo_test`。

## 怎么用

1. **先看家底**：`list_games`、`cache_stats`。同一盘棋重复分析会自动命中缓存，不必担心重复开销。
2. **渲染产物**：`out` 要写到当前线程的可视化目录，然后把片段路径按可视化引用的方式交给用户。
3. **对局节奏**：`pve_new` 之后，用户报一步、你调 `pve_move`（它会顺带让引擎应一手），然后重新 `render_replay --session` 刷新那张图。
4. **复盘**：`pve_finish` 会先按对局结果存 PGN，再用全强度引擎重算每一着——那才是可以拿来讲的权威评估；对局中显示的评估来自受限档位，别当定论。
5. **讲解**：引擎数据归引擎，人话归你。建议先 `show_game` 看清每步的评估变化，再挑 2-3 个关键转折点讲，而不是逐步复述。

## 底线

- 评估、最佳着法这类事实全部来自引擎，别编。
- 难度默认选 休闲/中等 这一档；除非用户明确要求，不要用 `全力`。
- 用户说"这盘别记录"就用 `record=no`，不要在库里留下痕迹。
