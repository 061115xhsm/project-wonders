# 🏪 万泰新天地智能运营中台 (Project WONDERS)

> WanTai New District Intelligent Operation System

## 项目简介

万泰新天地智能运营中台是一个面向商业综合体的数据驱动运营决策系统，聚焦**客流画像、会员分层、商铺评估、智能营销**四大核心场景，帮助商场从"凭经验拍脑袋"转向"看数据做决策"。

### 核心价值

- **全景视图**：一屏掌握商场客流、会员、商铺、营销全貌
- **洞察驱动**：RFM 模型自动识别高价值/沉睡会员，商铺评分模型发现经营盲区
- **AI 原生**：大模型 + RAG 知识库 + ReAct 营销 Agent，方案生成基于真实行业案例，非规则模板
- **时段灵活**：全页面支持时间段筛选（今天/近7天/近30天/本月/全部），数据覆盖最近一年截至今天
- **移动适配**：手机端禁缩放、防误触、Plotly 工具条隐藏，路演投屏 + 移动展示两不误
- **合规安全**：内置数据脱敏机制，满足《个人信息保护法》要求

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 前端 | Streamlit + Plotly | 交互式可视化大屏，10 页多页面应用 |
| 算法 | scikit-learn | RFM + K-Means 聚类、商铺综合评分 |
| 数据 | pandas + numpy | ETL、特征工程、模拟数据生成 |
| AI 层 | OpenAI 兼容 SDK + sentence-transformers | 讯飞 maas-coding 首选 + 智多云多模型 fallback；RAG 向量检索带磁盘缓存 |
| 存储 | CSV + Parquet | 轻量级文件存储，数据文件不进 Git |

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 生成模拟数据(覆盖最近1年,截至今天)
python3 app/data_generator.py

# 3. 配置大模型密钥(复制 .env.example → .env,填入讯飞/智多云 key)
cp .env.example .env

# 4. 启动应用
streamlit run app/main.py
```

浏览器打开 http://localhost:8501 即可访问。

## 项目结构

```
project_wonders/
├── data/
│   ├── raw/                # 模拟数据(最近1年至今天)
│   │   ├── foot_traffic_2023.csv   # 客流明细(小时粒度,按楼层)
│   │   ├── members_2023.csv        # 会员数据(5000条,含RFM字段)
│   │   ├── shops_master.csv        # 商铺主数据(65条/60真实品牌)
│   │   └── consultations_2023.csv  # 客户咨询记录(8000条)
│   └── rag_index/          # RAG 向量索引缓存(pickle)
├── app/
│   ├── main.py             # Streamlit 主入口 + 全局时间段筛选器
│   ├── config.py           # 全局配置(含 DATA_TODAY 数据基准日)
│   ├── date_filter.py      # 时间段筛选共享组件(10页统一调用)
│   ├── data_generator.py   # 模拟数据生成器(节假日锚定2025-2026)
│   ├── processor.py        # ETL + 数据脱敏
│   ├── models.py           # RFM + 商铺评分 + 客流模型 + 营销引擎
│   ├── llm_client.py       # 大模型客户端(自动 fallback + 冷却)
│   ├── rag.py              # RAG 向量检索(带缓存)
│   ├── rag_corpus.py       # 知识库语料(102条:商户/企业/方法论/指标/行业案例)
│   ├── agent.py            # 营销 ReAct Agent + 运营问答 + 催租/获客/画像
│   ├── viz_theme.py        # 暗色设计系统 + 移动端防误触
│   ├── shops_data.py       # 真实商户清单(按楼层实勘)
│   └── pages/              # 10 个 Streamlit 页面
│       ├── 1_首页概览.py       # KPI + AI运营日报 + 客流趋势
│       ├── 2_客流分析.py       # 时空热力图 + 天气/节假日效应
│       ├── 3_会员洞察.py       # RFM分层 + 流失预警
│       ├── 4_商铺评估.py       # 综合评分排行
│       ├── 5_营销助手.py       # ReAct Agent 生成营销方案
│       ├── 6_全渠道营销.py     # 统一会员ID + 触点矩阵
│       ├── 7_数字化获客.py     # 渠道ROI + AI拉新方案
│       ├── 8_数据采集.py       # 采集覆盖率 + AI建议
│       ├── 9_租户管理.py       # 合同/收租 + AI催租话术
│       └── 10_咨询洞察.py      # 咨询分析 + AI自动回复
├── tests/
│   └── test_pipeline.py    # 单元测试(21个)
├── docs/                   # 飞书文档草稿 + 技术文档(tex/docx/pdf) + 路演讲稿
├── poster/                 # 海报(HTML + PDF)
├── requirements.txt
└── README.md
```

## 核心算法

### 1. RFM 会员分层模型

- **R** (Recency)：最近到店天数（越小越好）
- **F** (Frequency)：到店次数（越大越好）
- **M** (Monetary)：累计消费金额（越大越好）

K-Means 聚类（K=4），**动态标签映射**——按聚类中心综合评分排序，不硬编码簇编号：

$$Score_{cluster} = -\bar{R} + \bar{F} + \bar{M}$$

输出四类群体：高价值 / 潜力 / 新客 / 沉睡。参考日锚定 `DATA_TODAY`（数据基准日=今天），保证 R 值与数据范围对齐。

### 2. 商铺综合评分模型

$$Score = 0.4 \times N(Sales) + 0.3 \times N(Traffic) + 0.2 \times N(RentRatio) + 0.1 \times N(Conversion)$$

其中 $N(\cdot)$ 为归一化后的指标（0-1），权重对应销售/客流/租售比/会员转化率。

### 3. 客流时空模型

- 7×24 热力图（星期 × 时段）
- 天气影响分析（晴/阴/雨 × 楼层）
- 节假日效应分析（工作日/周末/节假日 × 楼层）
- 极端场景对比（雨天工作日 vs 晴天节假日）

客流按商业规律生成：基础客流 × 时段系数 × 日期系数(周末/节假日) × 天气系数 × 楼层权重。

### 4. 营销 ROI 估算模型

按 RFM 群体区分投放成本占比与转化率，估算增量营收与 ROI：

$$ROI = \frac{EstRevenue}{Cost}, \quad Cost = EstRevenue \times CostRatio_{segment}$$

其中 $CostRatio_{segment}$ 按群体差异化（沉睡 0.25 / 高价值 0.17 / 潜力 0.18 / 新客 0.20），ROI 上限保护：AI 返回值超 6 或 ≤0 时用规则估算替换，防数字虚高。

## AI 能力（技术创新）

| 能力 | 实现 | 兜底 |
|------|------|------|
| 营销 ReAct Agent | 大模型自主调 4 工具（查群体/查商铺/检索知识/估ROI）多轮生成方案 | 规则引擎 |
| RAG 知识库 | 102 条语料（商户/企业/方法论/指标/**行业营销案例**），sentence-transformers 向量检索 | 空 context |
| 运营问答 | 多轮对话，注入真实数据统计 + RAG context | 检索结果摘要 |
| AI 运营日报 | 基于全局统计生成 3 条洞察 | 规则模板 |
| 催租/获客/画像/咨询 | 各场景专用 prompt + JSON 结构化输出 | 规则兜底 |

**行业营销案例库**：从 800+ 篇真实行业营销方案中提炼 8 类精华（服装店定位/微信集赞/双微矩阵/节日营销/口碑五要素/路演框架/感恩回馈/中庭演出），每条浓缩核心机制 + 万泰场景映射，供 Agent 检索真实玩法。

大模型配置：首选讯飞 maas-coding（auto，200k 上下文），备用智多云（glm-5.2 / deepseek-v4-pro / kimi-k2.6 等），自动 fallback + 连续失败冷却 5 分钟。

## 时间段筛选

侧边栏全局筛选器，**10 个页面统一生效**：

- 快捷范围：今天 / 近7天 / 近30天 / 本月 / 全部
- 自定义日期区间
- 默认近7天，切换后本页数据自动重算
- 客流/咨询按日期过滤；会员显示"时段内活跃会员数"（RFM 分群保持全量存量结构）；商铺/租户为存量数据标注不受影响

## 移动端适配

- **禁用缩放**：viewport meta 永久锁定 `maximum-scale=1, user-scalable=no`（源头改 Streamlit index.html）+ JS MutationObserver 持续锁定 + 拦截 gesturestart/双击/多指 touchmove
- **防误触**：Plotly 工具条隐藏、按钮最小点击区 44px、禁用长按菜单、body 仅允许纵向滚动
- **响应式布局**：≤768px 单列、KPI 卡片自适应列数

## 数据安全

- 手机号脱敏：`138****5678`
- 姓名脱敏：`王**`
- 身份证号：完全隐藏
- 数据文件不进 Git 仓库（`.gitignore` 排除 `data/`、`.env`、`.streamlit/`）

## 测试

```bash
python3 -m pytest tests/ -v
# 21 个测试全部通过

# 全页面无异常验证(Streamlit AppTest)
python3 -c "from streamlit.testing.v1 import AppTest; ..."
```

## Loop Engineering

本项目采用 Loop Engineering 范式构建，详见 [LOOP_ENGINEERING.md](LOOP_ENGINEERING.md)

---

**Project WONDERS** · 万泰新天地智能运营中台 · 2026
