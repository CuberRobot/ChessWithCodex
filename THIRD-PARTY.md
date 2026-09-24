# 第三方组件与许可

本项目自己的代码是 **MIT**（见 `LICENSE`）。下面这些是它用到的第三方东西，各自许可见链接与随附文件。

| 组件 | 用在哪 | 许可 | 是否随仓库分发 |
| --- | --- | --- | --- |
| [chess.js](https://github.com/jhlywa/chess.js)（`assets/js/chess.js`） | 对弈界面的规则库（走法校验、FEN、SAN） | MIT（`assets/js/chess-LICENSE.txt`） | 是 |
| 棋组 `chessnut`（`assets/pieces/chessnut/`） | 棋盘棋子 | Apache-2.0 | 是 |
| 棋组 `spatial`（`assets/pieces/spatial/`） | 棋盘棋子（备选） | MIT | 是 |
| [Stockfish](https://github.com/official-stockfish/Stockfish)（`stockfish-single.js`） | 分析与对局引擎 | **GPLv3**（`assets/js/stockfish-LICENSE.txt`） | **否** |

## 为什么引擎不进仓库

Stockfish 是 GPLv3，把它编出来的产物放进仓库就等于整包按 GPL 分发，
而我们希望自己的代码保持 MIT。所以采用"引擎按需获取"的方式：

- **Python 侧（分析/复盘）**：装一个系统版 Stockfish 即可（mac `brew install stockfish`、
  Windows `winget install stockfish`、Linux `apt install stockfish`），
  路径用环境变量 `CHESSPLUGIN_ENGINE` 或 `--engine` 指定。
- **浏览器侧（对弈界面里的内嵌引擎）**：用 `tools/build/build_engine.sh` 自己编一次，
  产物放到 `engines/stockfish-single.js`（该目录已被 gitignore）。
  自己编译、自己分发时请遵守 GPLv3。

引擎缺失时，对弈界面会自动退回自带的轻量搜索，**功能不会坏，只是对手变弱**。
