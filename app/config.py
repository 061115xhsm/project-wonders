"""万泰新天地智能运营中台 - 全局配置"""

# ===== 商场基础配置 =====
MALL_NAME = "万泰新天地"
MALL_CITY = "普宁"
MALL_AREA_SQM = 200000  # 总建筑面积20万㎡
FLOORS = 5
OPEN_HOUR = 10
CLOSE_HOUR = 22

# ===== 模拟数据参数 =====
DATA_YEAR = 2023
DATA_START = "2023-01-01"
DATA_END = "2023-12-31"
MEMBER_COUNT = 5000
SHOP_COUNT = 60  # 去重品牌数(跨层主力店沃尔玛/中影/魅力金座各计1);实际商铺记录65条(含跨层)
TRAFFIC_INTERVAL_MINUTES = 15  # 客流采样粒度（分钟）

# 客流规律
WEEKEND_BOOST = 1.4       # 周末客流倍数
HOLIDAY_BOOST = 2.0       # 节假日客流倍数
RAIN_PENALTY = 0.8        # 雨天客流系数
WEATHER_PROBS = {"晴": 0.70, "雨": 0.20, "阴": 0.10}

# 会员等级分布
MEMBER_LEVEL_DIST = {"普通": 0.60, "银卡": 0.25, "金卡": 0.13, "黑金": 0.02}

# 会员月均消费（元）- 与等级正相关
MEMBER_SPEND_RANGE = {
    "普通": (100, 500),
    "银卡": (500, 2000),
    "金卡": (2000, 8000),
    "黑金": (8000, 30000),
}

# 楼层业态分布
FLOOR_CATEGORIES = {
    1: {"零售": 0.5, "餐饮": 0.2, "服饰": 0.2, "服务": 0.1},
    2: {"服饰": 0.5, "零售": 0.2, "餐饮": 0.2, "服务": 0.1},
    3: {"餐饮": 0.5, "服饰": 0.2, "零售": 0.15, "娱乐": 0.15},
    4: {"娱乐": 0.4, "餐饮": 0.4, "服务": 0.2},
    5: {"娱乐": 0.6, "餐饮": 0.3, "服务": 0.1},
}

# 楼层客流权重（1F最高，逐层递减）
FLOOR_TRAFFIC_WEIGHT = {1: 1.0, 2: 0.75, 3: 0.55, 4: 0.35, 5: 0.20}

# ===== 模型参数 =====
RFM_K_CLUSTERS = 4
RFM_REFERENCE_DATE = "2023-12-31"

# 商铺评分权重
SHOP_WEIGHTS = {
    "sales": 0.4,       # 销售额权重
    "traffic": 0.3,     # 客流量权重
    "rent_ratio": 0.2,  # 租金贡献比权重
    "conversion": 0.1,  # 会员转化率权重
}

# ===== UI配置 =====
# 主题 token 已迁移至 app/viz_theme.py(经 dataviz validator 验证的 CVD 友好暗色调色板)。
# 此处保留 THEME 名做向后兼容,值指向新 token;新代码请直接 import viz_theme.PALETTE。
from app.viz_theme import PALETTE as _PALETTE
THEME = {
    "bg_color": _PALETTE["page_bg"],
    "text_color": _PALETTE["text_primary"],
    "accent_gold": _PALETTE["cat_gold"],
    "accent_cyan": _PALETTE["cat_blue"],
    "accent_green": _PALETTE["cat_aqua"],
    "card_bg": _PALETTE["surface"],
}

# ===== 数据安全 =====
SENSITIVE_FIELDS = ["phone", "name", "id_card"]
PHONE_MASK_PATTERN = r"(\d{3})\d{4}(\d{4})"
PHONE_MASK_REPLACEMENT = r"\1****\2"
