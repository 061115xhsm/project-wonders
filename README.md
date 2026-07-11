# 🏪 万泰新天地智能运营中台 (Project WONDERS)

> WanTai New District Intelligent Operation System

## 项目简介

万泰新天地智能运营中台是一个面向商业综合体的数据驱动运营决策系统，聚焦**客流画像、会员分层、商铺评估、智能营销**四大核心场景，帮助商场从"凭经验拍脑袋"转向"看数据做决策"。

### 核心价值

- **全景视图**：一屏掌握商场客流、会员、商铺、营销全貌
- **洞察驱动**：RFM模型自动识别高价值/沉睡会员，商铺评分模型发现经营盲区
- **模拟先行**：在没有真实数据对接的情况下，利用符合商业规律的模拟数据验证算法模型
- **合规安全**：内置数据脱敏机制，满足《个人信息保护法》要求

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 前端 | Streamlit + Plotly | 交互式可视化大屏 |
| 算法 | scikit-learn | RFM+K-Means聚类、商铺评分 |
| 数据 | pandas + numpy | ETL、特征工程、模拟数据生成 |
| 存储 | CSV + Parquet | 轻量级文件存储 |

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 生成模拟数据
python3 app/data_generator.py

# 3. 启动应用
streamlit run app/main.py
```

浏览器打开 http://localhost:8501 即可访问。

## 项目结构

```
project_wonders/
├── data/
│   ├── raw/              # 原始模拟数据
│   │   ├── foot_traffic_2023.csv   # 客流明细(43800行)
│   │   ├── members_2023.csv        # 会员数据(5000条)
│   │   └── shops_master.csv        # 商铺主数据(30家)
│   └── processed/        # 清洗后数据(Parquet)
├── app/
│   ├── main.py           # Streamlit主入口
│   ├── config.py         # 全局配置
│   ├── data_generator.py # 模拟数据生成器
│   ├── processor.py      # ETL + 数据脱敏
│   ├── models.py         # RFM + 商铺评分 + 客流模型 + 营销引擎
│   ├── utils.py          # 工具函数
│   └── pages/            # Streamlit多页面
│       ├── 2_客流分析.py
│       ├── 3_会员洞察.py
│       ├── 4_商铺评估.py
│       └── 5_营销助手.py
├── tests/
│   └── test_pipeline.py  # 21个单元测试
├── LOOP_ENGINEERING.md   # Loop Engineering设计文档
├── LOOP_STATE.md         # Loop状态追踪
├── requirements.txt
└── README.md
```

## 核心算法

### 1. RFM会员分层模型
- **R** (Recency)：最近到店天数
- **F** (Frequency)：到店次数
- **M** (Monetary)：累计消费金额
- K-Means聚类(K=4)，**动态标签映射**（按聚类中心综合评分排序，不硬编码簇编号）
- 输出：高价值/潜力/新客/沉睡 四类群体

### 2. 商铺综合评分模型
$$Score = 0.4 \times N(Sales) + 0.3 \times N(Traffic) + 0.2 \times N(RentRatio) + 0.1 \times N(Conversion)$$

### 3. 客流时空模型
- 7×24热力图（星期×时段）
- 天气影响分析（晴天vs雨天）
- 节假日效应分析

### 4. 智能营销推荐引擎
- 基于RFM分层的规则引擎
- 每类群体自动生成2-4条营销策略
- 效果预测（基于模拟数据估算）

## 数据安全

- 手机号脱敏：138****5678
- 姓名脱敏：王**
- 身份证号：完全隐藏
- 数据文件不进Git仓库

## 测试

```bash
python3 -m pytest tests/ -v
# 21个测试全部通过
```

## Loop Engineering

本项目采用 Loop Engineering 范式构建，详见 [LOOP_ENGINEERING.md](LOOP_ENGINEERING.md)

---

**Project WONDERS** · 万泰新天地智能运营中台 · 2026
