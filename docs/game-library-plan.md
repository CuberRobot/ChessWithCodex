# 方案：外部棋谱库 + 插件侧获取（只规划，暂不实施）

## 一、想要什么

现在插件自带的棋谱是**打包装在仓库里**的（`pgn/` 五盘教学与名局），
另外有个临时工具 `tools/fetch_games.py` 能从 Lichess 按棋手拉。

但更该有的形态是：**棋谱库是一个独立的仓库（甚至静态站），插件里配置一下来源，
之后就能持续地列出、按需拉取、更新棋谱。** 这样：

- 加棋谱是**内容工作**，不用改插件代码、不用发版；
- 一台机器可以同时挂多个来源（官方预置库 / 自己的私有库 / 别人的公开库）；
- 别人也能拿这个契约做自己的库，生态自然长出来。

## 二、为什么必须拆成两块

| | 数据侧（棋谱库仓库） | 插件侧（本项目） |
| --- | --- | --- |
| 产出 | PGN 文件 + 索引 + 说明 | 同步、检索、渲染、分析 |
| 迭代节奏 | 随时加内容 | 跟代码版本走 |
| 谁来维护 | 你（或社区任何人） | 代码仓库 |

两块之间只靠**一个稳定契约**连接（下一节），所以可以各自独立地做、独立地验收。

## 三、契约（先定这个，两边才好并行）

**数据侧的最小结构**：

```
index.json            # 库的总索引（必须；插件只读它就能列出全部棋谱，不必克隆整库）
collections.json      # 集合清单：标题 / 描述 / 条数 / 更新日期
games/
  classics/xxx.pgn
  teaching/xxx.pgn
  openings/xxx.pgn
```

**`index.json` 每局一条**（字段先定这些，留 `schema` 版本号以便以后演进）：

```jsonc
{
  "schema": 1,
  "name": "chess-library-classics",
  "games": [
    {
      "id": "reti-tartakower-1910",
      "collection": "classics",
      "path": "games/classics/reti-tartakower-1910.pgn",
      "white": "Reti, Richard", "black": "Tartakower, Savievly",
      "date": "1910.??.??", "result": "1-0", "eco": "B15",
      "plies": 21,
      "tags": ["弃后", "王暴露", "教学"],
      "source": "Vienna 1910",
      "license": "public-domain",              // 每局都要能查到出处与许可
      "sha256": "…"                            // 拉下来校验，避免半截文件
    }
  ]
}
```

**发布方式**：GitHub 仓库就够用（raw 地址即"静态站"，插件直接取 `index.json`）；
要好看再叠一层 GitHub Pages。**不需要后端。**

### 可用来源（2026-09 实测）

**① Lichess 按棋手导出 —— 免 token，实测可用**

```
GET https://lichess.org/api/games/user/{用户名}?max=20&clocks=true&evals=true&opening=true&analysed=true
```

- `Accept: application/x-chess-pgn` 拿 PGN；换成 `application/x-ndjson` 拿逐行 JSON（便于只取元数据）。
- 参数支持 `max / since / until / rated / perfType / color / analysed / moves / tags / clocks / evals / opening`。
- **必须带 User-Agent**（实测不带会被挡）；读公开对局不需要 token。
- 一个实测细节：`[%eval]` 只出现在 **Lichess 自己分析过**的对局里（想只要这类就加 `analysed=true`）。
  没有也无所谓——我们自己用本地引擎重算，有缓存，很便宜。

**② 整库镜像 —— 免 token，实测 200**

```
https://database.lichess.org/standard/lichess_db_standard_rated_YYYY-MM.pgn.zst
```

按月分文件、单月几十 GB 级，适合**离线批量建库**，不适合按需拉取（那个用 ①）。

**③ 开局统计 explorer —— 实测返回 401**

`explorer.lichess.ovh` 现在需要授权（带 UA 也是 401），**不要依赖它**；
要开局统计就自己从本地库里算。

**④ 其他**：单局导出 `/game/export/{id}`、公开研究 `/{studyId}.pgn` 等需要**真实 ID**
（我用编造的 ID 测出来是 404，那是 ID 不存在，不是接口不可用）。

**礼貌与条款**：带能识别用途的 User-Agent、别狂刷接口（批量走镜像）、公开数据可用于学习研究；
**现代对局进公共库之前仍要逐条确认来源条款。**

## 四、插件侧要加什么

新增一个工具 `tools/library.py`（或并进 `chessmem.py` 作为子命令），命令面：

```bash
library sources                              # 看配置了哪些来源
library update                               # 只拉 index（相当于 apt update）
library list [--collection classics|--tag 教学|--player Reti]
library pull --id reti-tartakower-1910 [--analyze]     # 按需下载单局，可选入库分析
library pull --collection teaching --analyze
```

要点：

- **来源配置**：环境变量 `CHESSPLUGIN_LIBRARIES`（逗号分隔），或数据目录里的 `config.json`；
  支持两种来源——**HTTP(S) 静态地址**（读它的 `index.json`）和**本地目录**（等价于现在的预置 `pgn/`）。
- **离线优先**：索引与已拉棋谱都落盘，**没网时一切照常**（只是不能 update/pull）。
- **拉下来的进数据目录**的 `pgn/` → 现有 `analyze-all` 自动就能吃到（这条链路已经通了）。
- **只当数据对待**：只允许 http/https 与本地路径；只写 `pgn/`；校验 `sha256`；不执行任何下载内容。

## 五、分步做，每步都能单独验收

| 步骤 | 做什么 | 验收标准 |
| --- | --- | --- |
| 1 | 定契约 + 做一个最小库：把现在这 5 盘搬成一个 `collections/classics` 集合，产出 `index.json` | 用文本编辑器就能看懂；字段与本文一致 |
| 2 | 插件侧支持**本地目录来源** | `library list` 能列出预置集合；`library pull --collection classics` 把棋谱拷进数据目录 |
| 3 | 插件侧支持**HTTP 来源** | 从远端 `index.json` 列出；成功拉取一局并通过 sha256 校验 |
| 4 | 增量更新与去重（按 id/sha256） | 重复 pull 不产生重复文件；update 只拉变化的条目 |
| 5 | （可选）GitHub Pages 做个浏览页 | 能用浏览器按棋手/标签翻，页面数据直接来自 `index.json` |

## 六、版权与来源：这类内容到底能不能收

一句话：**着法本身基本不受版权保护，但要小心别人的讲解、编排和平台条款。**

**不受保护的（可以放心收）**

- **着法序列本身**：棋谱（谁在第几手走了什么）在各主要法域普遍被视为**事实**或**受规则约束的选择**，
  缺少可版权作品所需的独创性表达 → 整理一盘棋的着法通常没问题。
- **历史对局**：1929 年前的对局本身属公有领域（美国口径；其他地区通常更早或相当）。

**受保护 / 有限制的（别碰或要标清楚）**

- **别人的评注和讲解**——这是明确的作品，不能抄。本项目的规矩是：**只收着法，讲解一律自己写**
  （写在 `notes/<id>.json`），从源头上避开这条。
- **书籍或数据库的"选择与编排"**：单局着法不受保护，但一本精心挑选编排的棋谱集，
  在欧盟还可能触发**数据库权**（实质性投入的采集/校验/呈现）。所以要小心"整库搬运"。
- **平台条款**：Lichess 的公开库大体可自由使用（鼓励注明来源）；Chess.com 等明确禁止抓取；
  ChessBase 一类的库是商业产品。**条款是合同问题，与版权无关，但一样要守。**

**本项目因此定下的三条规矩**

1. 只存着法 + 元数据，**不存他人评注**；讲解永远自己写。
2. **每局都带 `source` 与 `license`** 字段（所以 index 里必须有这两项）。
3. **从网上拉的棋谱不进仓库**，只留在使用者自己的数据目录里；
   要进公共库时，优先选 **公有领域 / CC0** 来源（历史名局、Lichess 公开库）。

> 以上是工程惯例，不是法律意见。真要公开一个库，最稳的做法是：只收 PD/CC0 来源、逐局标注来源与许可、
> 不收录任何第三方评注。

## 七、边界与风险

- **版权**：历史对局本身是事实、可自由分发；**现代对局**（比如从 Lichess 拉的）要看来源条款，
  所以库里每局都必须带 `source` 与 `license` 字段——这也是它放在 index 里的原因。
- **别把离线体验做坏**：现在整套东西不联网也能用，库功能必须是"锦上添花"而不是必需。
- **契约版本**：`schema: 1` 写死在 index 里，以后改字段时插件能识别并给出清楚提示。
- **不做的事**：账号体系、上传、评分、社交功能；棋谱的**讲解**仍由人写（那是内容工作，不是库的事）。

## 八、和现有东西的关系

- 现有 `pgn/` 里的 5 盘（三步杀、四步杀、贪吃中兵、Légal、Réti–Tartakower、歌剧院之战）
  就是"最小库"的雏形，第 1 步把它们整理成集合即可。
- `tools/fetch_games.py`（按棋手从 Lichess 拉、或下任意 PGN 链接）**保留**：
  它解决"临时想找某人的棋"；本方案解决"长期、可配置、多来源地获取"。
- 拉下来的棋谱走同一条路：进 `pgn/` → `analyze-all` → 渲染回放台（都已就绪）。
