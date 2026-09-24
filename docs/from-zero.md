# 从零到现在的样子：怎么引导 Codex 一步一步做出来

这份文档是给**空项目**用的：假设你有一个空文件夹、什么依赖都没装，
想复刻出目前这个 ChessPlugin。每节都有「对 Codex 说」和「验收标准」——
验收没过就别往下走，否则坑会叠在一起。

两边系统不一样的地方都标了【mac】/【Win】；没标的表示命令一致（或直接用 Codex 工具即可）。

---

## 0. 心法（先看这个，能省很多时间）

1. **一次只让 Codex 做一件事，并且要求它当场验证那道验收标准。** 这份文档里最值钱的不是命令，是那些"验收"。
2. **要求它把"数据"和"人写的东西"分开**（本项目里是 `games/` 生成物 vs `notes/` 手写）。所有后续麻烦都源于这两者混在一起。
3. **界面相关的改动，要求它真的在浏览器里跑一遍**再交付——模板里的 JS 错误只有浏览器能发现。
4. **让它把踩过的坑写下来**（就是你正在看的这种文档），否则下个会话会重踩。

---

## 1. 装引擎和 Python 环境

**对 Codex 说**：
> 装 Stockfish 引擎和一个项目自带的 Python 虚拟环境，并把依赖固定到 requirements.txt（python-chess）。

【mac】
```bash
brew install stockfish                     # 落在 /opt/homebrew/bin/stockfish
python3 -m venv .venv
.venv/bin/python -m pip install python-chess
```

【Win】
```powershell
winget install stockfish                   # 或 scoop install stockfish
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install python-chess
```
（引擎若用官网 zip 解压，记得把路径写进环境变量 `CHESSPLUGIN_ENGINE`，Win 下是 `...\stockfish.exe`。）

**验收**：`.venv/bin/python -c "import chess; print(chess.__version__)"`【Win】`.venv\Scripts\python.exe ...` 能打印版本；`stockfish` 能跑出 UCI 横幅。

**坑**：别把 venv 提交进仓库（`.gitignore` 里加 `.venv/`）。Win 的 venv 目录是 `Scripts\` 不是 `bin/`——文档和脚本里写路径时要分开。

---

## 2. 造骨架 + 建 git

**对 Codex 说**：
> 建目录骨架 pgn/ games/ notes/ cache/ tools/ templates/ assets/ tests/，加 .gitignore，然后 git init 并提交一次。

**坑**：

- 【mac】如果 Codex 跑在受限沙箱里，`.git` 是只读的，`git init/add/commit` 会报 `Operation not permitted`——需要你在授权框里放行。
- **提交信息别带英文双引号**：`git commit -m "含 " 引号 " 的消息"` 会被 shell 拆坏（本项目踩过两次），用中文引号或干脆不加引号。
- 【Win】Git 会提示 CRLF→LF（本项目见过 `CRLF will be replaced by LF`）。想让仓库里统一用 LF，加一个 `.gitattributes`（`* text=auto eol=lf`）。

---

## 3. 记忆层：棋谱入库 + 评估缓存

**对 Codex 说**：
> 写 tools/chessmem.py：读 PGN（文件或 stdin）、用 Stockfish 逐手算评估、把结果写进 games/<id>.json；
> 评估按「局面+深度+引擎」缓存在 cache/evals.json；讲解写 notes/<id>.json，
> 重算时要按「第几着 + SAN」把讲解合并回记录；再给 list / show / stats / analyze-all 四个子命令。

**验收**：同一盘棋连跑两次——第一次输出「引擎查询 N 次」，第二次必须是「引擎查询 0 次」。

**坑**：

1. **`games/` 是生成物，不许手改**。要加讲解就写 `notes/`。这是全项目最重要的一条约定。
2. 引擎评分是**行棋方视角**，要 `.pov(chess.WHITE)` 统一成白方视角；`mate: 0` 表示"已经将杀"，谁是胜方要结合 FEN 的走子方判断。
3. 缓存键要含深度和引擎名，否则换深度会拿到旧值（本项目设计成"换深度自然失效"，这是对的）。
4. 找不到引擎、PGN 走不通时要给人话错误，不要甩 Python 堆栈。

---

## 4. 渲染层：模板 + 占位符 + 棋子

**对 Codex 说**：
> 用 HTML 模板 + 构建期占位符替换来做两种界面：单张棋盘（给局面）和回放台（给一盘棋）。
> 棋子用矢量棋组（assets/pieces/ 放 SVG），渲染时只注入用到的那一套；产物必须是 HTML 片段（不含 doctype/html/head/body）。

**验收**：产物里搜不到 `__XXX__` 这样的占位符；在浏览器里打开没有 JS 报错；棋盘上的棋子与 FEN 逐格一致。

**坑**：

1. **代码里的棋盘渲染是两处重复的**（单张棋盘 + 回放台）→ 一定要抽成共享渲染器（本项目是 `templates/pieces-runtime.js`），否则改一处另一处就旧了。
2. 每套棋子的**留白不一样**，要靠首次使用时离屏 `getBBox()` 量包围盒，再按同一比例、同一条基线摆放。注意：`getBBox()` 要求元素**已经在文档里**，否则拿不到或拿到 0。
3. 版权：棋组要记作者和许可（本项目 `assets/pieces/LICENSE.md`）。GPL 的、CC BY-NC 的要分清。
4. 【通用】把「产物怎么交付」也问清楚：本项目是"写到当前线程的可视化目录，再用可视化引用的方式给出"，不是普通文件链接。

---

## 5. 人机对战第一版（点击落子）

**对 Codex 说**：
> 做一个能点击落子的对弈界面：点棋子 → 点落点；显示双方被吃掉的子和子力差；能悔棋、切难度；
> 规则库内嵌（chess.js），引擎先在产物里自带一个轻量搜索；结束后一键把棋谱交给 Codex 复盘。

**验收**：点着走几步，对手会应手，没有非法着法；吃子后子力差数字正确。

**坑**：

1. **negamax 要的是"当前行棋方视角"**，评估函数若写成白方视角就会反号，表现是"越强的档越乱走"（本项目真的这么错过）。
2. **同步深搜会冻住界面**：必须带时间预算，并在超预算时中止。
3. **`requestAnimationFrame` 在没有渲染帧的环境里可能永远不触发**——要让出主线程就用定时器。
4. **升变选择必须画在棋盘上**（贴在升变那一格），别 append 到图的末尾跑到图外面。
5. **易位要用"点王再点目标格"**；点车只会把车走过去。用户说"易位走不了"时，先查规则（比如 f1 被对方的象盯着），那常常不是 bug。

---

## 6. 把真引擎塞进界面（最难的一段，坑最多）

**对 Codex 说**：
> 把真正的 Stockfish 内嵌进对弈界面：完全离线、不依赖 CDN；
> 引擎就绪前要有可见状态行，20 秒没就绪自动退回轻量引擎，保证棋盘永远能下；难度按 Skill Level 分档。

**为什么不能直接下载一份用**：现成第三方构建（`stockfish.js@10`）用的是 2015 年的 emscripten，它的胶水会**按相对路径去取 `stockfish.wasm`**（被沙箱 CSP 拦掉且**静默失败**），开头还会用 `moduleOverrides` 接管 `Module`、把你注入的二进制丢掉。

**正解是自己编译**（本项目 `tools/build/build_engine.sh`）：

【mac】
```bash
brew install emscripten
git clone --depth 1 https://github.com/niklasf/stockfish.js /private/tmp/sfjs
# 关键：用现代 emscripten，清掉 1.x 时代参数与 wasm 下不合法的 x86/macOS 参数，并加 -s SINGLE_FILE=1
```

【Win】
```powershell
git clone https://github.com/emscripten-core/emsdk
cd emsdk && .\emsdk.bat install latest && .\emsdk.bat activate latest   # 之后新开终端
# 其余同上：改 Makefile 里的参数，再用 make COMP=emscripten ARCH=wasm ... build
```

`-s SINGLE_FILE=1` 的产物是**一个 JS 文件、wasm 以 base64 内嵌**，运行时不需要任何 fetch——这才是在沙箱里能跑的前提。

**这一段的坑（全踩过）**：

1. **必须先就绪再发指令**：建好 worker 就 `postMessage("uci")` 会得到 `null function` / `memory access out of bounds`（运行时还没初始化完）。正确姿势是发 `uci`、**等 `uciok`** 再开始用；`onRuntimeInitialized` 也要等。
2. **引擎代码只走字节**：base64 → `Uint8Array` → `Blob` → worker。**不要**用 `TextDecoder` 转成字符串再执行，会把文件弄坏。
3. **别用无头 Chrome + 虚拟时间判断异步 wasm**：虚拟时间会卡住异步初始化，看起来像"引擎没反应"。判断引擎好坏请用 Node 在真实时间里跑，或在真实界面看状态行。
4. 沙箱 CSP `connect-src` 只有 `blob:`/`data:`（**不能 fetch**），`script-src` 只放行少数 CDN——所有东西都得**内嵌成数据**。
5. 内嵌体积：本项目引擎 671KB，gzip+base64 后约 400KB，产物总共 394KB（片段上限 1MB）。
6. **许可**：Stockfish 是 **GPLv3**，内嵌=分发行为，公开仓库要遵守 GPL。

---

## 7. 插件化（让 Codex 直接调用）

**对 Codex 说**：
> 把这个仓库做成 Codex 插件：`.codex-plugin/plugin.json` + `.mcp.json`（指向 mcp/server.py）+ skills/ 说明；
> MCP 服务走 stdio JSON-RPC，工具要薄封装、直接调用 tools/ 里的同一套函数。

**验收**：官方 `validate_plugin.py` 通过；用管道发 `initialize / tools/list / tools/call` 都有正确回应。

**坑**：

1. **工具必须复用命令行的同一套代码**。本项目踩过：把 argv 直接喂给"接收 Namespace"的函数，结果所有工具全崩——正确做法是 `call(module, argv)` 让模块自己的 argparse 解析。
2. 清单里 **`defaultPrompt` 是数组**（最多 3 条、每条 ≤128 字符），写单个字符串是不合规的；`capabilities` 用 `["Interactive","Write"]` 这种。
3. `.mcp.json` 里用**绝对路径**启动解释器；【Win】JSON 里的反斜杠要转义（`C:\\...`）或用正斜杠。
4. 改完插件要刷新缓存戳再重装。

---

## 8. 棋钟与交互打磨

**对 Codex 说**：
> 加棋钟：1+0 / 2+1 / 3+2 / 5+3 / 10+0 / 15+10 / 不限时；走完才加秒；最后 10 秒变红；超时判负；
> 引擎也要吃自己的钟（按剩余时间决定 movetime）。再加"重新开始"和"对手引擎（真/轻量）"两个开关。

**验收**：计时递减、走子加秒、超时判负、重新开始复位，四条都要在浏览器里实测。

---

## 9. 什么时候开浏览器验证（省事又不丢安全网）

- **动了模板/前端**（`templates/*.html`、`*.js`）→ 必须开浏览器，跑「无 JS 报错 + 棋子与 FEN 逐格一致」。
- **只动后端**（tools/*.py、数据）→ 跑 Python 冒烟测试就够，不必开浏览器。

**坑**：

- 【mac】无头 Chrome 在这台机器上 `--dump-dom` 之后**不会自己退出**：拿完输出就 `kill <pid>`。
- 【Win】同理，用 `taskkill /PID <pid> /T /F`（`/T` 连子进程一起杀）。
- 【mac】无头窗口最小宽度约 500px，测窄屏要用固定宽容器模拟。
- 频繁启动无头 Chrome 会产生**崩溃报告弹窗**（本项目今晚刷了 4 个）——这就是"只在动模板时开浏览器"的理由。

---

## 10. 最终验收清单

```bash
.venv/bin/python dev/tests/smoke.py --browser # 分析→缓存→渲染→浏览器逐格校验→MCP 层
.venv/bin/python tools/chessmem.py stats      # 库与缓存的家底
```

在真实界面里打开对弈盘，确认状态行显示「对手：真 Stockfish ✓」；点着走两步、走一步碰一下棋钟、再看一眼易位和升变。

---

## 附：常见报错速查

| 报错 | 含义 / 处理 |
| --- | --- |
| `RuntimeError: null function` / `memory access out of bounds` | 引擎还没初始化完就发指令了；等 `uciok` |
| 引擎在 worker 里完全没反应、连错误都没有 | 用无头+虚拟时间判断的假象；或引擎在按相对路径找 wasm（被 CSP 拦） |
| `Operation not permitted`（.git） | 沙箱对 `.git` 只读，需要授权放行 |
| `pathspec ... did not match` | 提交信息里的引号把命令拆坏了，去掉引号 |
| 产物里出现 `__XXX__` | 占位符没被替换，说明不是渲染脚本生成的 |
| 棋盘空白 / 没棋子 | 模板 JS 报错；跑 `dev/tests/smoke.py --browser` 看具体哪一行 |
| `找不到引擎` | 装 Stockfish，或用 `--engine` / `CHESSPLUGIN_ENGINE` 指定 |
