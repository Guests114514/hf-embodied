# Hugging Face 具身智能一周扫描

一周内完成的 HF 数据采集与展示项目：抓 HF Hub 公开接口写入 SQLite，用 FastAPI 渲染成四个页面。
所有数据都是单次快照或每日快照，不含人工挑选的结果。

## 1. 我做了什么

| 任务 | 实现 | 页面 |
|---|---|---|
| 一周 trending，按天展示 | 每天一次 Top100 快照，`trending_daily` 表 | `/` |
| 具身领域粉丝 top10 大V 及关注网络 | 机构成员展开 + 粉丝/关注双向抓取 + 度数统计 + 网络图 | `/users` |
| 最火热的 10 个具身项目 + GitHub 链接 + Space | 关键词标注排序 + README 正则 + GitHub API 交叉验证 | `/projects` |
| 代码开源 | 本仓库 | `/notes` |

## 2. 怎么跑

    python -m venv .venv
    source .venv/Scripts/Activate.ps1
    pip install -r requirements.txt
    python crawl_trending.py      # 每天跑一次，积累榜单历史
    python crawl_users.py         # 候选池 + 作者账号
    python fill_tags.py           # 用 raw/ 里的缓存补 tags，不联网
    python make_labels.py         # 具身/非具身标注
    python crawl_members.py       # 按判据展开机构成员
    python reset_edges.py         # 只在重抓网络时用
    python crawl_edges.py         # 抓关注边 + 二跳枢纽
    python draw.py                # 输出 static/graph.png
    python crawl_projects.py      # top 项目 + GitHub + Space
    uvicorn app:app --port 8000   # 打开 http://127.0.0.1:8000

顺序有依赖：`crawl_users` / `crawl_members` / `crawl_edges` 都读 `labels` 表，
必须排在 `make_labels` 之后。判据阈值全部集中在 `config.py`。

每天的最小重复动作是 `crawl_trending.py` → `fill_tags.py` → `make_labels.py`，
因为快照会带进新仓库，新仓库没进 `labels` 之前，页面上的具身标记会漏算它们。

## 3. 文件分工

- `config.py` 唯一的参数入口：接口地址、阈值、关键词表。
- `hfapi.py` 唯一的网络出口：重试、`full=true`、401/403/404 的处理、raw 缓存。
- `db.py` 唯一的 SQL：建表、upsert、所有页面查询。其余脚本只做流程。
- `crawl_trending` / `crawl_users` / `crawl_members` / `crawl_edges` / `crawl_projects`
  五个抓取脚本，各自只负责一张表。
- `fill_tags.py` / `make_labels.py` 领域判据两步：先从 raw 缓存补 tags（不联网），
  再算 `labels`。
- `reset_edges.py` / `reset_projects.py` 只在需要重抓那两张表时用，工作流没有别的作用。
- `check_db.py` 在一个内存库里执行 SCHEMA 并打印列名，用来验证"空库能不能建对"。
  `repos.tags` 和 `users.source` 这两列都是它抓出来漏在 SCHEMA 之外的。表名从
  `sqlite_master` 里读，所以 SCHEMA 新增一张表不用改这个脚本。
- `draw.py` 输出 `static/graph.png`，网页只引用这个静态文件，不跑任何 JS。
- `app.py` + `templates/` 四个页面，全部服务端渲染，一句 SQL 都不写在模板或路由里。
- `raw/` 每次请求的原始 JSON 与 README 正文落盘，是全部结论的证据，也用来离线重算。
  体积上百 MB，不入库，clone 后重跑一遍就有。
- `hf.db` 数据文件，不入库，需要时用第 2 节的顺序重建。

## 4. 具身智能怎么判定

`make_labels.py` 两级判据，结果写进 `labels` 表并保留命中的理由：

- 硬命中：tag 里有 `robotics` 或 `arxiv:cs.RO`，直接算具身。
- 软命中：tags + 仓库名 + pipeline_tag 里命中 ≥ 2 个具身词（VLA、manipulation、
  locomotion、teleop、dexterous、sim2real、lerobot、world model、humanoid 等）。

当前 712 个仓库里 378 个判为具身（53%）。自检查询列出"判为非具身但 likes 最高"的
仓库，逐条人工看过：Qwen3.8-27B、LTX-2.5、sam3、Llama-3、unsloth 量化版、all-MiniLM——
全是应该排除的通用模型，没有误杀。误召的边界情况是 world model 类视频生成模型，
下面的已知局限单独说明。

### 全站 trending 里具身为 0，这不是抓取失败

两天快照（2026-11-20、2026-11-21）各 100 条，判为具身的都是 0 条。为确认不是连接或
标注出了问题，做了三条交叉验证：

- 同一批 `repos` 行里带 `robotics` 标签的仓库有 232 个，说明标签数据本身是抓到的；
- 11-20 的 100 条全部能连上 `labels`，11-21 有 96 条能连上（4 条是当天新抓进来、
  还没重跑标注的仓库，所以理论上限是 4 而不是 100）；
- 全站榜单里 `pipeline_tag = robotics` 的条目数为 0。

结论是内容本身：全模型 trending 前 100 名被通用多模态、图像生成、语音和 GGUF 量化
版本占据，具身智能的热度读不出全站榜单。所以第 3 项任务不复用 trending，而是走
`pipeline_tag=robotics` 加关键词检索的领域入口——`crawl_users.py` 的候选池就是这么建的。

## 5. 大V 怎么定义

- 只统计个人账号。机构账号的粉丝列表同样截断在 500，且 `nvidia`、`microsoft`
  这类机构会淹没榜单；机构热度放在第二张表里单独看。
- 排除搬运号：名下仓库数 ≥ 500 的账号（`mradermacher` 有 73859 个自动转换仓库）。
- 领域门槛：自有具身仓库 ≥ 1，或同时挂在 ≥ 2 家通过占比检验的具身机构下。
  后者用来捞"没有自己仓库、但确实属于这个圈子"的研究者。
- 机构展开前先过三道检验：具身仓库 ≥ 3、具身占比 ≥ 0.5、具身 likes ≥ 50。
  最后一条是看到 `CoRL2026-CSI`（13 个仓库 0 赞，成员粉丝 0–1，是挑战赛投稿号）
  之后加的。成员超过 60 人的机构跳过，因为拿到的是一小撮随机成员，没有代表性。

## 6. 阈值是怎么定下来的

没有一个数字是先验合理的，全部是被具体账号或具体接口行为逼出来的。判据一共收紧过四轮：
第一轮榜头是 `mradermacher`（73859 个自动转换仓库）这类搬运号，加了 `num_models` 上限；
第二轮是巨型机构的成员污染了个人榜，改成先过机构判据再展开成员；第三轮机构排序用了池内
likes，把 `pyannote`、`deepseek-ai` 请了进来，换成 `labels` 的具身仓库数；第四轮看到
`CoRL2026-CSI`（13 个仓库 0 赞、成员粉丝 0–1 的挑战赛投稿号），加了具身 likes 下限。

| 参数 | 值 | 定它的依据 |
|---|---|---|
| `SNAPSHOT_LIMIT` | 100 | HF 全站 trending 页本身就是前 100，再往深名次每天抖动，请求也变慢。 |
| `SLEEP` | 0.4s | 350 个作者约 3 分钟跑完，全程没有触发过 429，再小只是浪费时间。 |
| `BULK_UPLOADER_MIN_MODELS` | 500 | `mradermacher` 有 73859 个转换仓库，正常研究者一辈子传不到 500 个。 |
| `MIN_ORG_EMBODIED` | 3 | 一两个仓库判不出一家机构的方向。代价：`openvla`（1 个仓库）不进成员展开，但它的模型仍在项目榜里。 |
| `MIN_ORG_RATIO` | 0.5 | 过半仓库具身才算这家机构在做机器人；`nvidia` 是 12/16 = 75% 通过，语音和 OCR 机构被挡。 |
| `MIN_ORG_EMBLIKES` | 50 | 为 `CoRL2026-CSI`、`Cache-SCA` 这类 0 赞投稿号加的。代价要写明：`X-Humanoid`（45 赞，`Pelican-VLA`、`WoW`，是真做 humanoid 的）也被挡在成员展开之外。 |
| `MAX_MEMBERS_PER_ORG` | 60 | 通过判据的真实规模是 pollen 31 / lerobot 19 / bfl 41 / NU 6，60 全收；`nvidia` 那 500 人只反映"谁被随机排在前面"，没有代表性。 |
| `MAX_ORGS` | 5 | 每展开一家就要按成员逐个查 overview，这是请求预算。实际只有 4 家通过全部判据。 |
| `MIN_SOFT`（`make_labels.py`） | 2 | 单个词太容易撞——`navigation` 同时是网页导航和地图术语，必须两个词同时命中才判具身。 |
| `TOP_V` | 10 | 任务书要求 top10。 |
| `HOP2` | 15 | 只抓一跳时"入度最多"必然等于"粉丝最多的种子"，统计是同义反复；15 个枢纽约 30 份列表。 |
| `MAX_NODES` | 200 | 674 个节点时标签完全不可读，200 是能看清结构又不丢主干的规模。 |
| `LIST_CAP` | 500 | 不是我们定的，是 HF 接口的上限。`thomwolf` 报 2006 粉丝而边表只有 506 条。 |

## 7. 已知局限（这些是数据本身的限制，不是代码没写完）

1. **trending 无法回溯。** HF 没有提供历史榜单接口，`/api/trending` 只有当前值。
   所以"一周 trending"只能靠每天跑一次快照攒出来，交付时最多 5 天。
2. **粉丝/关注列表上限 500。** 个人账号、机构账号都一样。自检里 `thomwolf`
   报 2006 粉丝、边表只有 506 条，就是这条上限。因此网络抓取阶段用 `overview`
   的精确计数当闸门，任一计数 ≥ 500 的候选节点直接不展开，避免残缺样本决定统计。
3. **度数是在"抓全的节点集合"上的下界。** 只抓了 25 个账号的双向列表，
   其余几千个节点只作为边的一端出现，它们的真实关注数没有计入。
4. **关键词判据会漏召和误召。** 漏召主要是卡片不打 tag 的新仓库；
   误召主要是 `world model` 命名的视频生成模型（`black-forest-labs/flux-3-action-*`
   确实是 action-conditioned 视频模型，so101 / DROID 是真实机械臂与数据集，
   所以判为具身，但它不是机器人策略模型）。
5. **gated 仓库读不到 README。** 匿名请求 raw 文件返回 401，20 个项目里 3 个因此
   没有 GitHub 链接，`projects.note` 逐行记了原因。
6. **downloads 不能当热度。** 新建仓库普遍为 0，所以项目榜用 likes 排序。
7. **"出度最多"不等于重要。** 出度榜第一名 `Ash444` 是 470 关注 / 17 粉丝，
   更像互关注册账号。入度和共同被关注才是有意义的中心性指标。

## 8. 数据规模（2026-11-21 快照）

| 表 | 行数 | 说明 |
|---|---|---|
| `repos` | 712 | 池内候选 + 每日 trending 里出现过的仓库，703 行有 tags |
| `labels` | 708 | 关键词判据结果，其中 378 行 `is_embodied = 1` |
| `trending_daily` | 200 | 两天 × 100 条 |
| `users` | 358 | 264 个池内作者 + 94 个机构成员 |
| `edges` | 5923 | 25 个账号的双向完整列表展开出的有向边，2492 个节点 |
| `crawled` | 50 | 哪个账号的哪个方向抓全了；触 500 上限的 0 份 |
| `projects` | 20 | 具身项目候选，14 行拿到 GitHub 链接，6 行在 `note` 里写明原因 |

同一份数字由 `db.summary()` 产生，直接印在首页顶部，不在这里手填第二遍。