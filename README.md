# ChessPlugin

本地棋谱库 + Stockfish 分析 + 三种界面，并且作为 Codex 插件直接可调用。
**一切离线**，数据都在这个仓库里。

## 能做什么

| 你想干嘛 | 怎么办 |
| --- | --- |
| 存一盘棋、让它记住 | 把 PGN 丢进 `pgn/`，跑 `analyze-all`；或直接跟 Codex 说"把这盘收了" |
| 看一整盘棋 | 回放台：**整盘评估曲线（点哪跳哪）**、跳到下一个转折点、点着法列表跳转、自动播放、逐手讲解 |
| 只看一个局面 | 单张棋盘：给「哪盘棋的第几手」或直接给 FEN，可加箭头/圈选/评估条 |
| 自己下一盘 | 对弈盘：点着下、对手离线应手、显示吃子和子力差、可悔棋、下完交给 Codex 复盘 |
| 问"这步好不好" | 用真 Stockfish 全强度重算，给数字和替代着法 |
| 想知道某档多强 | `pve.py elotest` 让它和锚点对打若干局，换算成 Elo |

同一盘棋只算一次：评估按「局面 + 深度 + 引擎」缓存，重复的局面（哪怕是别的棋里的）直接命中。

## 前置要求

| 需要什么 | 说明 |
| --- | --- |
| **Codex 桌面版**（支持插件） | 装好插件后要**重启一次**才会出现 |
| **Python 3.9+** | mac/Linux 用 `python3`（系统自带或 brew 装的都行）；Windows 用 [python.org](https://www.python.org/downloads/) 版或 Microsoft Store 版，**安装时勾选 "Add to PATH"**。<br>这是插件能不能加载的前提：仓库里的 `.mcp.json` 默认写的是 `python3`（mac/Linux 写法），**Windows 上必须先跑 `install.ps1`** 把它换成你的解释器路径 |
| **网络**（仅安装时需要） | 装依赖（python-chess）与可选的引擎 |
| **Stockfish**（可选，强烈建议） | 分析、复盘、Elo 实测需要它；**缺了不会坏**——对弈界面自动退回内置轻量对手 |
| **磁盘** | venv + 依赖约 100MB，原生引擎约 100MB，内嵌引擎 0.7MB |
| **目录权限** | 插件目录**只读也能用**：数据会自动落到用户数据目录（见下） |

### 数据写在哪里

代码在插件目录，**数据按这个顺序落地**：

1. 环境变量 `CHESSPLUGIN_HOME` 指定的目录（显式指定时）
2. **插件目录本身（可写时）**——本地克隆就是这样，行为与以前完全一致
3. 插件目录只读时 → 用户数据目录：
   mac `~/Library/Application Support/ChessWithCodex`、
   Windows `%LOCALAPPDATA%\ChessWithCodex`、
   Linux `~/.local/share/ChessWithCodex`

所以从 marketplace 装下来的只读快照也能正常用（棋谱、讲解、缓存、对局、引擎都写到第 3 项里）。

## 安装

**一条命令**（会建好 Python 环境、装依赖、找引擎、写插件配置、登记到 Codex 的 marketplace）：

```bash
# mac / Linux
./install.sh

# Windows（PowerShell）
powershell -ExecutionPolicy Bypass -File install.ps1
```

装完**重启 Codex**，在 Personal 里启用 `chess` 插件就能用了——不用敲命令，直接跟它说话。

> **Windows 用户务必先跑安装脚本。** 仓库里的 `.mcp.json` 默认写的是 `python3 mcp/launch.py`
> （mac/Linux 的写法）；Windows 上没有 `python3` 这个命令，插件在 Codex 里会**静默不出现**。
> `install.ps1` 会把配置改成你本机的解释器路径，跑过它插件才会正常加载。

**还需要一个 Stockfish 引擎**（分析和复盘要用；界面对弈里的那个引擎是可选的，见 `THIRD-PARTY.md`）：

| 系统 | 装法 |
| --- | --- |
| mac | `brew install stockfish` |
| Windows | `winget install stockfish`（或从 stockfishchess.org 下 zip 解压） |
| Linux | `sudo apt install stockfish` |

装完不用配置——程序会自己按「环境变量 `CHESSPLUGIN_ENGINE` → 仓库内 `engines/` → `PATH` → 各系统常见目录」
的顺序去找。找不到时对弈界面会自动退回内置的轻量对手，**功能不会坏，只是对手弱一些**。

### 手动指定引擎（可选，三种系统各一份写法）

一般用不上（自动能找到）。真要指定，按系统这么写：

```bash
# mac / Linux（临时；写进 ~/.zshrc 或 ~/.bashrc 就长期生效）
export CHESSPLUGIN_ENGINE=/opt/homebrew/bin/stockfish
```
```powershell
# Windows PowerShell（临时；setx 是永久）
$env:CHESSPLUGIN_ENGINE = "C:\Program Files\stockfish\stockfish.exe"
setx CHESSPLUGIN_ENGINE "C:\Program Files\stockfish\stockfish.exe"
```

另外两种等价做法：把可执行文件放进 `engines/`（mac/Linux 叫 `stockfish`，Windows 必须是 `stockfish.exe`），
或者单次命令加 `--engine 路径`。注意：**对弈界面里那个引擎不需要这些配置**——
它是 wasm，一份文件三平台通用，见下。

### 两个引擎，别搞混

| | 原生引擎（Python 侧） | 内嵌引擎（浏览器侧） |
| --- | --- | --- |
| 用在哪 | 分析、复盘、`pve.py`、Elo 实测 | 对弈界面里的对手 |
| 形态 | 各平台的**原生可执行文件**（mac Mach-O / Windows .exe / Linux ELF） | **一份 wasm**，与平台无关 |
| 哪来的 | 系统包管理器装（brew / winget / apt） | 用 `tools/build/build_engine.sh` 编一次，产物放 `engines/stockfish-single.js` |
| 要不要按平台配置 | 要（上面那节） | **不要**，三平台同一个文件 |
| 缺少时 | 分析类命令会提示安装；对弈自动退回轻量对手 | 同样自动退回轻量对手 |

### Windows 上实测发现的两个坑

1. **别用 PowerShell 管道给引擎喂指令。** `"uci" | stockfish.exe` 这类写法会因编码问题让引擎读错命令
   （实测出现 `bestmove a2a3` 这种鬼结果）。用我们的 Python 命令（内部走 python-chess 的 stdin/stdout），
   或在 Python 里显式收发，不要靠 shell 管道。
2. **插件目录可能是只读的**（从 marketplace 装下来的快照就是这样）。分析结果、棋谱、缓存默认写在插件目录里，
   只读时会失败。现在的做法是：**把仓库克隆到你自己的可写目录，再跑安装脚本**。
   （把数据目录挪到用户目录、与插件本体解耦，已经记进 `docs/roadmap.md` 待做。）

## 文档地图

| 文件 | 给谁看 | 内容 |
| --- | --- | --- |
| [docs/from-zero.md](docs/from-zero.md) | 想从零复刻的人 | **按步骤引导 Codex**（空目录 → 现在）＋ mac/Windows 差异 ＋ 全部踩过的坑 |
| [AGENTS.md](AGENTS.md) | 接手项目的 agent | **操作契约**：铁律、常用命令、讲棋纪律、环境坑、边界 |
| [docs/architecture.md](docs/architecture.md) | 想改代码的人 | 目录职责、记录格式、缓存语义、渲染管线、插件层 |
| [docs/cookbook.md](docs/cookbook.md) | 想干活的人 | 一条条任务食谱：收棋、讲棋、开局、换棋组、发布更新 |

## 目录速查

```
pgn/        原始棋谱（示例两盘，也是文档里的例子）
games/      分析后的完整记录（生成物，别手改）
notes/      人写的讲解和标注（重算时合并回记录）
tools/      7 个命令行工具
templates/  界面模板 + 共享棋子渲染器
assets/     开源棋子（2 套）与内嵌的规则库 chess.js
mcp/        插件用的 MCP 服务
skills/     插件的使用说明
docs/       文档（实现说明 / 任务食谱 / 从零复刻 / 规划）
LICENSE     本项目代码的许可（MIT）
THIRD-PARTY.md  第三方组件与许可（引擎是 GPLv3，按需获取，不随仓库分发）

# 以下不入库（.gitignore），首次运行时自动生成或按需获取：
cache/      评估缓存        sessions/  进行中的人机对局
engines/    浏览器版引擎     dev/       本地测试与诊断脚本
dist/       渲染产物
```

---

以下为各工具的详细用法，见 `AGENTS.md` 的命令清单与 `docs/` 两份文档。

## 装完先验一下

```bash
.venv/bin/python tools/chessmem.py stats      # 看看棋谱库与缓存的家底
.venv/bin/python tools/chessmem.py analyze-all # 把 pgn/ 里的示例棋谱入库
.venv/bin/python dev/tests/smoke.py           # 自检（--browser 会真的开无头浏览器逐格校验）
```

## 三个目录各管一件事

| 目录 | 内容 | 谁写 |
| --- | --- | --- |
| `pgn/` | 原始棋谱 | 人（或以后从网上下） |
| `cache/evals.json` | 局面 → 评估的记忆 | `chessmem.py` 自动维护 |
| `games/<id>.json` | 一盘棋的完整记录 | `chessmem.py` 生成，讲解部分由人补 |
| `notes/<id>.json` | 人写的讲解和标注 | 人 |
| `assets/pieces/` | 棋子素材（开源 SVG） | 人（见 `assets/pieces/LICENSE.md`） |
| `templates/` | 渲染模板和共享渲染器 | 人 |
| `dist/` | 渲染出来的成品 | 渲染脚本 |

`games/*.json` 是唯一的真相：里面有每一着的 SAN、UCI、走后的 FEN、引擎评估，
以及人写的讲解和标注。重新分析时，引擎数据会被刷新，人写的部分原位保留。

## 用法

分析一盘棋（第一次会问引擎，第二次全部命中缓存）：

```bash
.venv/bin/python tools/chessmem.py analyze --pgn pgn/legal-trap-1750.pgn --id legal-trap-1750 --depth 16
```

看看本地有什么：

```bash
.venv/bin/python tools/chessmem.py list
.venv/bin/python tools/chessmem.py show legal-trap-1750
.venv/bin/python tools/chessmem.py stats
```

把记录渲染成可以点着走、自动播放的界面（输出 HTML 片段）：

```bash
.venv/bin/python tools/render_replay.py --id legal-trap-1750 --out dist/legal-trap-1750.html
```

只要一张静态棋盘（某个局面，或者某盘棋里的第几着）：

```bash
.venv/bin/python tools/render_board.py --id legal-trap-1750 --ply 10 --out dist/ply10.html
.venv/bin/python tools/render_board.py --fen "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" --out dist/start.html
```

## 棋子

棋子素材放在 `assets/pieces/<棋组>/`，来源和许可见
[assets/pieces/LICENSE.md](assets/pieces/LICENSE.md)。默认 `chessnut`，另有 `spatial`；
两个渲染脚本都用 `--pieces` 切换：

```bash
.venv/bin/python tools/render_replay.py --id legal-trap-1750 --out dist/x.html --pieces spatial
```

加新棋组：把 12 个 SVG（`wK wQ wR wB wN wP bK bQ bR bB bN bP`）放进
`assets/pieces/<名字>/`，在 LICENSE.md 里记下来源和许可，然后跑：

```bash
.venv/bin/python tools/import_pieces.py     # 打包成 templates/pieces.js
```

棋子摆放不用手调：渲染器首次使用时量出整套棋子的包围盒，所有棋子按同一比例、
同一条基线摆进格子，所以换棋组、换尺寸都自动合适。

引擎路径默认 `/opt/homebrew/bin/stockfish`，也可以用参数或环境变量
`CHESSPLUGIN_ENGINE` 指定。`--fresh` 可以绕过缓存强制重算。

一次分析 `pgn/` 下的全部棋谱：

```bash
.venv/bin/python tools/chessmem.py analyze-all
```

## 人机对战

```bash
.venv/bin/python tools/pve.py new  --id pve-1 --level 休闲 --player white --record yes
.venv/bin/python tools/pve.py move --session pve-1 --move e4     # UCI 或 SAN 都行
.venv/bin/python tools/pve.py state --session pve-1
.venv/bin/python tools/pve.py finish --session pve-1             # 记录在案的话会用全强度复盘并入库
```

难度以 Elo 为准：`--elo 850` 或档位别名（入门 600 / 休闲 900 / 中等 1200 /
进阶 1600 / 强硬 2200 / 全力）。`≥1320` 直接交给 Stockfish 自带的 `UCI_Elo` 限强；
更低的部分它够不到，用「浅深度 + 候选池温度采样 + 少量随机着」模拟，主要输在看不懂战术。

想知道某档到底多强，实测一下（和锚点对打若干局换算 Elo）：

```bash
.venv/bin/python tools/pve.py elotest --candidate 入门 --anchor 1320 --games 120
```

注意：锚点按「Stockfish 的 UCI_Elo 标定」当真值；得分接近 0 或 1 时要非常多的局数才收得窄。

## 作为 Codex 插件（工具层）

仓库本身就是插件：`.codex-plugin/plugin.json` 是清单，`.mcp.json` 指向
`mcp/server.py`（不依赖第三方 MCP SDK 的 stdio 服务），`skills/chess/SKILL.md`
说明什么时候用、怎么用。

暴露的工具：`list_games`、`show_game`、`analyze_pgn`、`render_replay`、`render_board`、
`pve_new`、`pve_move`、`pve_finish`、`elo_test`、`cache_stats`。

每个工具都是薄封装，直接调用 `tools/` 里的同一套函数，所以命令行和插件行为一致。
注册方式是在 `~/.agents/plugins/marketplace.json` 里加一条指向本仓库的本地源；
登记之后 Codex 就能直接调用这些工具，不用再敲命令。

改了插件内容后，用官方工具刷新缓存戳再重装：

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py .
```
