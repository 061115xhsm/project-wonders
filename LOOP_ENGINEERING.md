# Project WONDERS — Loop Engineering 设计书

> 万泰新天地智能运营中台 · Loop Engineering V1.0

## 一、Loop 总览

本项目的 Loop 体系由 **1个主Loop + 4个子Loop** 构成，覆盖从数据生产到前端交付的全流程。

```
                    ┌─────────────────────────┐
                    │   Master Loop (调度器)    │
                    │   触发: 手动 / 定时       │
                    └──────┬──────────────────┘
                           │ 按Phase顺序调度
            ┌──────────────┼──────────────┬──────────────┐
            ▼              ▼              ▼              ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │ Data Loop     │ │ Algo Loop     │ │ Frontend Loop │ │ QA Loop       │
    │ 数据工厂      │ │ 算法引擎      │ │ 前端构建      │ │ 测试验收      │
    │ 验证: 数据质量 │ │ 验证: 模型输出 │ │ 验证: 页面渲染 │ │ 验证: 全链路  │
    └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

## 二、Loop 设计原则（从菜鸟教程 & Addy Osmani 总结提炼）

| 原则 | 本项目如何落实 |
|------|---------------|
| 从窄任务开始 | 每个子Loop只做一件事：Data只管数据、Algo只管算法 |
| 告诉Agent如何验证 | 每个Loop都有明确的验证命令和成功标准 |
| 偏好小的可逆变更 | 每次迭代只改一个模块，验证通过后再进下一个 |
| 人类保持判断席位 | 每个Phase完成后暂停，人工确认再继续 |
| 沉淀可复用Loop | Loop配置固化为CLAUDE.md中的Skill |

## 三、Master Loop — 总调度

### 触发方式
- 手动：`claude -p "@loop-master 启动项目构建"`
- 定时（可选）：每天早上9点检查进度

### 调度逻辑
```
1. 读取 LOOP_STATE.md，了解当前进度
2. 找到下一个未完成的Phase
3. 调度对应的子Loop
4. 子Loop完成后，更新 LOOP_STATE.md
5. 如果所有Phase完成 → 触发QA Loop做最终验收
6. 如果任一Phase失败 → 记录错误，暂停，等待人工介入
```

### 状态文件：LOOP_STATE.md
```markdown
# Loop 状态追踪

最后更新：2026-07-08 (自动更新)

## Phase 进度
- [x] Phase 1: 项目骨架 + 配置 (完成于 07-08 10:30)
- [ ] Phase 2: 数据工厂
  - [x] generate_foot_traffic() — 已生成 35040 行
  - [x] generate_members() — 已生成 5000 行
  - [ ] generate_shops() — 待执行
- [ ] Phase 3: 算法引擎
- [ ] Phase 4: 前端Dashboard
- [ ] Phase 5: 测试 + 交付

## 阻塞项
(无)

## 上次验证结果
- 数据质量检查：✅ 通过 (07-08 10:35)
```

---

## 四、子Loop详细设计

### 4.1 Data Loop — 数据工厂

**目标**：生成符合万泰新天地真实商业规律的模拟数据

**Intent（意图）**：
```
生成3个数据集：
1. foot_traffic_2023.csv — 客流明细（15分钟粒度，约35040行）
2. members_2023.csv — 会员数据（5000条）
3. shops_master.csv — 商铺主数据（30家）

数据必须符合：
- 工作日双峰（午高峰12-13点，晚高峰18-20点）
- 周末客流+40%，节假日+100%，雨天-20%
- 会员消费与等级正相关
- 商铺楼层/业态分布合理（1F零售→5F影院）
```

**Context（上下文）**：
- 万泰新天地：20万㎡、5层、优衣库/奈雪/雅莹等品牌
- 普宁县级市消费特征（非一线城市）
- 项目目录：/home/qq/project_wonders/

**Action（行动）**：
```bash
# Step 1: 生成客流数据
python3 app/data_generator.py --only foot_traffic

# Step 2: 生成会员数据
python3 app/data_generator.py --only members

# Step 3: 生成商铺数据
python3 app/data_generator.py --only shops

# Step 4: 数据质量自检
python3 app/data_generator.py --validate
```

**Observation（观察/验证）**：
```bash
# 验证1：行数正确
python3 -c "
import pandas as pd
ft = pd.read_csv('data/raw/foot_traffic_2023.csv')
mb = pd.read_csv('data/raw/members_2023.csv')
sh = pd.read_csv('data/raw/shops_master.csv')
assert 34000 <= len(ft) <= 36000, f'客流行数异常: {len(ft)}'
assert len(mb) == 5000, f'会员行数异常: {len(mb)}'
assert len(sh) == 30, f'商铺行数异常: {len(sh)}'
print('✅ 行数验证通过')
"

# 验证2：无空值、无负数
python3 -c "
import pandas as pd
for f in ['foot_traffic_2023','members_2023','shops_master']:
    df = pd.read_csv(f'data/raw/{f}.csv')
    assert df.isnull().sum().sum() == 0, f'{f}有空值'
    assert (df.select_dtypes(include='number') < 0).sum().sum() == 0, f'{f}有负数'
print('✅ 数据质量验证通过')
"

# 验证3：分布合理性（周末客流>工作日）
python3 -c "
import pandas as pd
ft = pd.read_csv('data/raw/foot_traffic_2023.csv')
wk = ft[ft['is_weekend']==False]['visitor_count'].mean()
we = ft[ft['is_weekend']==True]['visitor_count'].mean()
assert we > wk * 1.3, f'周末客流未高于工作日: wk={wk:.0f}, we={we:.0f}'
print(f'✅ 分布验证通过: 工作日均值{wk:.0f}, 周末均值{we:.0f}')
"
```

**Adjustment（调整）**：
- 如果验证1失败 → 检查生成逻辑中的日期范围/采样间隔
- 如果验证2失败 → 检查Faker locale或随机种子
- 如果验证3失败 → 检查周末/节假日乘数逻辑

**停止条件**：3个验证全部通过

---

### 4.2 Algo Loop — 算法引擎

**目标**：实现RFM分层、商铺评分、客流热力图、营销推荐4个核心算法

**Intent**：
```
1. ETL: 数据清洗 + 脱敏 + 特征工程
2. RFM模型: fit() + predict() + 动态标签映射（不硬编码簇编号）
3. 商铺评分: 归一化 + 加权求分 + 排名
4. 客流模型: 7x24热力图 + 峰值检测 + 天气/节假日影响
5. 营销引擎: 基于分层的规则推荐
```

**Action**：
```bash
# Step 1: ETL处理
python3 app/processor.py

# Step 2: 算法验证（用模拟数据跑一遍）
python3 -c "
from app.models import RFMModel, calculate_shop_score
from app.processor import clean_data, mask_sensitive_data
import pandas as pd

# 加载并清洗数据
members = pd.read_csv('data/raw/members_2023.csv')
shops = pd.read_csv('data/raw/shops_master.csv')
members_clean = clean_data(members)
members_masked = mask_sensitive_data(members_clean)

# RFM
rfm = RFMModel()
labels = rfm.fit(members_masked)
assert len(labels) == 5000
assert set(labels).issubset({'高价值','潜力','沉睡','新客'})
print(f'✅ RFM验证通过: {dict(zip(*np.unique(labels, return_counts=True)))}')

# 商铺评分
scored = calculate_shop_score(shops)
assert scored['score'].min() >= 0
assert scored['score'].max() <= 100
print(f'✅ 商铺评分验证通过: 均值{scored[\"score\"].mean():.1f}')
"
```

**Observation**：
```bash
# 验证：RFM分层结果符合商业逻辑
python3 -c "
import pandas as pd, numpy as np
from app.models import RFMModel
from app.processor import clean_data, mask_sensitive_data

members = pd.read_csv('data/raw/members_2023.csv')
members = mask_sensitive_data(clean_data(members))
rfm = RFMModel()
labels = rfm.fit(members)
members['segment'] = labels

# 高价值会员的消费应显著高于沉睡会员
vip_spent = members[members['segment']=='高价值']['total_spent'].mean()
sleep_spent = members[members['segment']=='沉睡']['total_spent'].mean()
assert vip_spent > sleep_spent * 2, f'高价值消费未显著高于沉睡: VIP={vip_spent:.0f}, 沉睡={sleep_spent:.0f}'
print(f'✅ 商业逻辑验证: VIP均值{vip_spent:.0f}元, 沉睡均值{sleep_spent:.0f}元')
"
```

**停止条件**：所有assert通过 + 商业逻辑验证通过

---

### 4.3 Frontend Loop — 前端Dashboard

**目标**：构建5页Streamlit应用，所有图表可交互

**Intent**：
```
1. main.py: 入口 + CSS + 侧边栏
2. 首页: 4个KPI卡片 + 趋势图 + Top5商铺
3. 客流: 7x24热力图 + 天气影响 + 节假日效应
4. 会员: 等级饼图 + RFM柱状图 + 年龄直方图 + 雷达图
5. 商铺: 评分表 + 雷达图 + 楼层对比 + 坪效散点图
6. 营销: 策略生成器 + 效果预测
```

**Action**：
```bash
# Step 1: 启动Streamlit（后台）
streamlit run app/main.py --server.port 8501 &

# Step 2: 等待启动
sleep 5

# Step 3: 验证页面可访问
curl -s http://localhost:8501 | head -5
```

**Observation**：
```bash
# 验证1：页面返回200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8501

# 验证2：无Python报错（检查Streamlit日志）
# 人眼验证：浏览器打开 http://localhost:8501 逐页检查
```

**停止条件**：
- HTTP 200
- 5个页面都能渲染
- 无Python traceback
- 图表可交互（悬停显示数值）

---

### 4.4 QA Loop — 测试验收

**目标**：全链路测试，确保项目可交付

**Intent**：
```
1. 单元测试全部通过
2. 数据→算法→前端全链路跑通
3. 性能达标（页面加载<2秒，数据处理<5秒）
4. 生成README和路演话术
```

**Action**：
```bash
# Step 1: 跑pytest
cd /home/qq/project_wonders && python3 -m pytest tests/ -v

# Step 2: 全链路测试
python3 -c "
import time
start = time.time()
# 模拟完整流程：加载数据→清洗→RFM→商铺评分→生成策略
from app.data_generator import generate_all
from app.processor import clean_data, mask_sensitive_data
from app.models import RFMModel, calculate_shop_score
generate_all()
# ... 完整流程
elapsed = time.time() - start
assert elapsed < 5, f'全链路耗时{elapsed:.1f}秒，超过5秒限制'
print(f'✅ 全链路测试通过: {elapsed:.1f}秒')
"
```

**停止条件**：
- pytest 0 failures
- 全链路 < 5秒
- Streamlit所有页面正常

---

## 五、Loop 执行剧本

### 方式A：让Claude Code一次性跑完（推荐）

把以下内容整体输入Claude Code：

```markdown
# Loop Engineering: Project WONDERS 全量构建

## 目标
构建万泰新天地智能运营中台MVP，包含数据工厂、算法引擎、Streamlit Dashboard。

## 执行规则
1. 每完成一个Phase，运行对应的验证命令
2. 验证失败 → 修复 → 重新验证，最多重试3次
3. 验证通过 → 更新LOOP_STATE.md → 继续下一个Phase
4. 所有Phase完成 → 运行QA Loop

## Phase 1: 项目骨架
创建 /home/qq/project_wonders/ 目录结构和 config.py
验证: 所有目录存在 && config.py可导入

## Phase 2: 数据工厂
编写 data_generator.py，生成客流/会员/商铺数据
验证: 3个CSV行数正确 + 无空值 + 无负数 + 周末客流>工作日

## Phase 3: 算法引擎
编写 processor.py + models.py
验证: RFM标签正确 + 商铺评分0-100 + VIP消费>沉睡消费

## Phase 4: 前端Dashboard
编写 main.py + 5个页面
验证: streamlit run 启动成功 + 5页可渲染

## Phase 5: 测试交付
编写 pytest + README.md + 路演话术
验证: pytest全过 + 全链路<5秒
```

### 方式B：分Phase逐步执行（更安全）

```bash
# Phase 1
claude -p "创建 /home/qq/project_wonders/ 项目结构，包含data/raw、data/processed、app/、tests/目录，以及config.py（商场名万泰新天地、营业10-22点、RFM_K=4、商铺权重sales0.4/traffic0.3/rent0.2/conversion0.1）。验证：config.py可导入。"

# Phase 2
claude -p "在/home/qq/project_wonders/编写data_generator.py，生成3个数据集：客流(15分钟粒度,工作日双峰,周末+40%,节假日+100%,雨天-20%)、会员(5000人,等级分布普通60%/银卡25%/金卡13%/黑金2%)、商铺(30家,虚构品牌,5层分布)。运行并验证行数+无空值+分布合理。"

# Phase 3
claude -p "在/home/qq/project_wonders/编写processor.py(ETL+脱敏)和models.py(RFM+商铺评分+客流热力图+营销推荐)。RFM的KMeans标签必须按聚类中心M值动态映射，不硬编码簇编号。验证：RFM标签正确+评分0-100+VIP消费>沉睡。"

# Phase 4
claude -p "在/home/qq/project_wonders/编写Streamlit Dashboard：main.py入口+5个页面(首页/客流/会员/商铺/营销)。深蓝背景#0E1117+金色#FFD700+青色#00CED1。所有数据加载加@st.cache_data。验证：streamlit run启动成功。"

# Phase 5
claude -p "在/home/qq/project_wonders/编写pytest测试(test_pipeline.py)和README.md。验证：pytest全过。"
```

### 方式C：用Hermes直接执行（最快，我帮你干）

我直接用terminal/file工具逐步构建，每步验证，你看着就行。

---

## 六、故障模式预案

| 故障 | 表现 | 检测方式 | 修复动作 |
|------|------|---------|---------|
| 空转 | Agent反复改同一文件不收敛 | 同一文件连续修改>3次 | 缩小修改范围，加更具体的验证 |
| 过拟合测试 | 测试通过但功能不对 | 人工抽查RFM分层结果 | 加商业逻辑断言 |
| 上下文漂移 | 基于过期假设工作 | 验证命令用了不存在的文件 | 重新读取项目结构 |
| API限流 | ZDCloud 429错误 | HTTP状态码429 | 切换到讯飞API或等待 |

---

## 七、与原白皮书的差异

| 原方案 | 本Loop方案 | 变更原因 |
|--------|-----------|---------|
| 5个Phase串行 | Master Loop调度+4个子Loop | Loop Engineering范式 |
| 无状态追踪 | LOOP_STATE.md记录进度 | Loop六大要素之"记忆" |
| 无验证命令 | 每Phase有明确assert | Loop六大要素之"观察" |
| 硬编码KMeans标签 | 动态映射 | 避免随机性 |
| 依赖锁版本 | 用系统已有包 | 避免版本冲突 |
| 编造路演数字 | 从模拟数据计算 | 避免穿帮 |
| PyInstaller打包 | streamlit run部署 | 实际可行 |
