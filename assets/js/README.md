# assets/js

第三方前端依赖（都内嵌进产物，运行时不需要联网）：

| 文件 | 用途 | 许可 |
| --- | --- | --- |
| `chess.js` | 规则库（走子校验、FEN、SAN） | MIT（`chess-LICENSE.txt`） |
| （引擎不在本目录） | 浏览器版引擎是 GPLv3 的第三方产物，**不随仓库分发**：自己编（配方见 `tools/build/build_engine.sh`）后放到 `engines/stockfish-single.js`，详见 `THIRD-PARTY.md` | GPLv3（`stockfish-LICENSE.txt`） |

第三方现成构建（`stockfish.js` / `stockfish.wasm.js` / `stockfish.wasm`）**已删除**：
它们用 2015 年的 emscripten，胶水会按相对路径去找 `stockfish.wasm`（被沙箱 CSP 拦掉且静默失败），
开头还会用 `moduleOverrides` 接管 `Module`、丢掉外部注入的二进制。自己编的版本没有这些问题。

**注意 GPLv3**：Stockfish 是 GPLv3，把它内嵌进产物属于分发行为，对外发布时要遵守 GPL。
个人本地使用不受影响。
