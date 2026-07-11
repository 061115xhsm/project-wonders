"""万泰新天地智能运营中台 - 模拟数据生成器"""
import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import *
from app.utils import save_csv, get_data_dir
from app.shops_data import ALL_SHOPS, SHOPS_BY_FLOOR, unique_brand_count

fake = Faker('zh_CN')
np.random.seed(42)

# 2023年中国主要节假日
HOLIDAYS_2023 = set()
for d in pd.date_range("2023-01-01", "2023-01-03"): HOLIDAYS_2023.add(d.date())  # 元旦
for d in pd.date_range("2023-01-21", "2023-01-27"): HOLIDAYS_2023.add(d.date())  # 春节
HOLIDAYS_2023.add(pd.Timestamp("2023-04-05").date())  # 清明
for d in pd.date_range("2023-04-29", "2023-05-03"): HOLIDAYS_2023.add(d.date())  # 五一
for d in pd.date_range("2023-06-22", "2023-06-24"): HOLIDAYS_2023.add(d.date())  # 端午
for d in pd.date_range("2023-09-29", "2023-10-06"): HOLIDAYS_2023.add(d.date())  # 中秋+国庆

ZONES = ["A区(主中庭)", "B区(东翼)", "C区(西翼)", "D区(南门)", "E区(北门)"]

# 商铺真实主数据见 app/shops_data.py(按楼层·实勘截图)

AREA_RANGE = {
    "餐饮": (60, 320), "零售": (60, 300), "服饰": (110, 280),
    "娱乐": (200, 3500), "服务": (80, 200), "汽车数码": (120, 320),
}

SALES_PER_SQM = {
    "餐饮": (800, 1500), "零售": (500, 1200), "服饰": (600, 1000),
    "娱乐": (300, 800), "服务": (400, 900), "汽车数码": (600, 1400),
}

CONVERSION_RANGE = {
    "餐饮": (0.15, 0.35), "零售": (0.05, 0.15), "服饰": (0.08, 0.20),
    "娱乐": (0.10, 0.25), "服务": (0.03, 0.10), "汽车数码": (0.04, 0.12),
}

# 主力店面积已在 shops_data 中硬编码(沃尔玛/中影/魅力金座),此处不再用 SHOP_NAMES 覆盖
ANCHOR_SHOPS = {"Walmart沃尔玛", "中影国际", "魅力金座"}


def generate_foot_traffic() -> pd.DataFrame:
    """生成客流明细数据（1小时粒度，按楼层）"""
    rows = []
    start = pd.Timestamp(DATA_START)
    end = pd.Timestamp(DATA_END + " 23:00")
    current = start

    base_hourly = 1200  # 普宁最大商场(20万㎡)基础客流(人/小时)

    while current <= end:
        hour = current.hour
        date = current.date()
        weekday = current.weekday()  # 0=周一
        is_weekend = weekday >= 5
        is_holiday = date in HOLIDAYS_2023

        # 时段系数(拉大峰谷差距,让热力图色彩层次丰富)
        if is_weekend or is_holiday:
            if 14 <= hour <= 20:
                time_factor = 2.8   # 周末/节假日下午-晚间最高峰
            elif 10 <= hour <= 21:
                time_factor = 1.8   # 白天营业时段
            elif 8 <= hour <= 9:
                time_factor = 0.5   # 早场刚开
            else:
                time_factor = 0.02  # 深夜几乎没人
        else:
            if 18 <= hour <= 20:
                time_factor = 3.0   # 工作日晚高峰(下班后逛街)
            elif 12 <= hour <= 13:
                time_factor = 2.2   # 午高峰(午餐)
            elif 10 <= hour <= 17:
                time_factor = 0.5   # 工作日白天偏低
            elif 21 == hour:
                time_factor = 0.8   # 晚间收尾
            elif 8 <= hour <= 9:
                time_factor = 0.15  # 早场
            else:
                time_factor = 0.01  # 深夜极低

        # 日期系数
        if is_holiday:
            date_factor = HOLIDAY_BOOST
        elif is_weekend:
            date_factor = WEEKEND_BOOST
        else:
            date_factor = 1.0

        # 天气
        weather = np.random.choice(list(WEATHER_PROBS.keys()), p=list(WEATHER_PROBS.values()))
        weather_factor = RAIN_PENALTY if weather == "雨" else 1.0

        # 按楼层生成
        for floor in range(1, FLOORS + 1):
            floor_weight = FLOOR_TRAFFIC_WEIGHT[floor]
            count = int(base_hourly * time_factor * date_factor * weather_factor * floor_weight * np.random.normal(1.0, 0.20))
            count = max(0, count)

            rows.append({
                "timestamp": current.strftime("%Y-%m-%d %H:%M"),
                "date": date.strftime("%Y-%m-%d"),
                "hour": hour,
                "weekday": weekday,
                "weekday_desc": ["周一","周二","周三","周四","周五","周六","周日"][weekday],
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "weather": weather,
                "floor": floor,
                "visitor_count": count,
            })

        current += timedelta(hours=1)

    df = pd.DataFrame(rows)
    save_csv(df, "foot_traffic_2023.csv", "raw")
    print(f"客流数据已生成: {len(df)} 行")
    return df


def generate_members(n=MEMBER_COUNT) -> pd.DataFrame:
    """生成会员数据"""
    rows = []
    levels = list(MEMBER_LEVEL_DIST.keys())
    probs = list(MEMBER_LEVEL_DIST.values())

    for i in range(n):
        level = np.random.choice(levels, p=probs)
        gender = np.random.choice(["男", "女"], p=[0.55, 0.45])
        age = int(np.clip(np.random.normal(32, 8), 18, 65))

        # 注册日期：锚定 2021-2023(高等级更早注册)
        if level in ["黑金", "金卡"]:
            reg_date = fake.date_between(start_date=datetime(2021, 1, 1), end_date=datetime(2022, 6, 30))
        elif level == "银卡":
            reg_date = fake.date_between(start_date=datetime(2021, 6, 1), end_date=datetime(2023, 3, 31))
        else:
            reg_date = fake.date_between(start_date=datetime(2021, 1, 1), end_date=datetime(2023, 12, 31))

        # 到店次数
        visit_ranges = {"普通": (5, 30), "银卡": (20, 60), "金卡": (40, 120), "黑金": (80, 200)}
        visit_count = np.random.randint(*visit_ranges[level])

        # 消费
        spend_range = MEMBER_SPEND_RANGE[level]
        avg_spent = np.random.uniform(*spend_range)
        total_spent = round(avg_spent * visit_count * np.random.uniform(0.6, 1.4), 2)
        avg_spent = round(total_spent / visit_count, 2)

        # 最近到店(锚定2023年内,基准2023-12-31)
        # 高等级近期到店;部分会员长期未到店(产生流失风险数据)
        if level in ["黑金", "金卡"]:
            # 20% 高价值长期未到店(>30天 = 流失风险)
            if np.random.random() < 0.20:
                last_visit = fake.date_between(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 11, 15))
            else:
                last_visit = fake.date_between(start_date=datetime(2023, 12, 1), end_date=datetime(2023, 12, 31))
        elif level == "银卡":
            if np.random.random() < 0.15:
                last_visit = fake.date_between(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 10, 31))
            else:
                last_visit = fake.date_between(start_date=datetime(2023, 11, 1), end_date=datetime(2023, 12, 31))
        else:
            if np.random.random() < 0.10:
                last_visit = fake.date_between(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 9, 30))
            else:
                last_visit = fake.date_between(start_date=datetime(2023, 10, 1), end_date=datetime(2023, 12, 31))

        # 偏好品类
        if level in ["黑金", "金卡"]:
            pref = np.random.choice(["餐饮", "零售", "服饰"], p=[0.4, 0.35, 0.25])
        else:
            pref = np.random.choice(["餐饮", "零售", "服饰", "娱乐", "服务"], p=[0.3, 0.2, 0.2, 0.2, 0.1])

        # 注册渠道(支撑痛点②③:线上线下打通 + 数字化获客)
        # 高等级会员更多线下门店注册,普通会员更多线上扫码/支付即会员
        if level in ["黑金", "金卡"]:
            channel = np.random.choice(
                ["线下门店", "微信小程序", "扫码地推", "支付即会员"],
                p=[0.45, 0.25, 0.15, 0.15])
        else:
            channel = np.random.choice(
                ["微信小程序", "支付即会员", "扫码地推", "线下门店"],
                p=[0.35, 0.30, 0.25, 0.10])

        rows.append({
            "member_id": f"M{i+1:05d}",
            "name": fake.name(),
            "phone": fake.phone_number(),
            "gender": gender,
            "age": age,
            "level": level,
            "register_date": str(reg_date),
            "last_visit_date": str(last_visit),
            "visit_count": visit_count,
            "total_spent": total_spent,
            "avg_spent": avg_spent,
            "preferred_category": pref,
            "register_channel": channel,
        })

    df = pd.DataFrame(rows)
    save_csv(df, "members_2023.csv", "raw")
    print(f"会员数据已生成: {len(df)} 行")
    return df


def generate_shops(n=None) -> pd.DataFrame:
    """生成商铺主数据 —— 基于真实商户清单(app/shops_data)

    面积/租金/销售/客流/转化率按业态区间模拟,主力店面积用真实大值。
    跨层品牌(沃尔玛/中影/魅力金座)各层独立记录但 shop_id 关联,体现跨层经营。
    """
    rows = []
    # 跨层品牌 → 统一 shop_id(便于分析关联),但仍按层各自一行
    brand_shop_id = {}
    shop_idx = 0

    for s in ALL_SHOPS:
        # shop_id:同名品牌用同一 id 后缀(如 WALMART),否则顺序号
        if s.is_anchor or s.name in ANCHOR_SHOPS:
            # 主力店跨层,用品牌固定 id
            if s.name not in brand_shop_id:
                brand_shop_id[s.name] = f"S{shop_idx+1:03d}"
                shop_idx += 1
            shop_id = brand_shop_id[s.name]
        else:
            shop_id = f"S{shop_idx+1:03d}"
            shop_idx += 1

        # 面积:主力店用 shops_data 真实值,其他按业态区间随机
        if s.is_anchor or s.area_sqm >= 1000:
            area = s.area_sqm
        else:
            lo, hi = AREA_RANGE.get(s.category, (100, 300))
            area = int(np.random.randint(lo, hi + 1))

        # 租金:1F 约 250 元/㎡/月,每层递减 20%(主力店租金贡献大)
        base_rent = 250 * (0.8 ** (s.floor - 1))
        # 主力店(沃尔玛/影院/KTV)租金单价偏低但面积大,总租金高
        rent_unit = base_rent * (0.4 if s.is_anchor else 1.0)
        monthly_rent = round(rent_unit * area * np.random.uniform(0.9, 1.1), 2)

        # 销售额 = 坪效 × 面积,主力店坪效偏低但面积大,总销售高
        sales_lo, sales_hi = SALES_PER_SQM.get(s.category, (400, 1000))
        sales_per_sqm = np.random.uniform(sales_lo, sales_hi)
        # 主力店坪效折扣(超市/影院单位面积产出低)
        sales_per_sqm *= (0.3 if s.is_anchor else 1.0)
        monthly_sales = round(sales_per_sqm * area * np.random.uniform(0.85, 1.15), 2)

        # 客流:面积 × 楼层客流权重,主力店额外加成
        floor_traffic_w = FLOOR_TRAFFIC_WEIGHT[s.floor]
        traffic_base = area * floor_traffic_w * np.random.uniform(15, 40)
        if s.is_anchor:
            traffic_base *= 2.5  # 主力店强引流
        monthly_traffic = int(traffic_base)

        # 转化率:按业态区间,主力店(超市)转化偏高
        conv_lo, conv_hi = CONVERSION_RANGE.get(s.category, (0.05, 0.15))
        conversion = round(np.random.uniform(conv_lo, conv_hi), 4)
        if s.is_anchor and s.category == "零售":  # 沃尔玛超市转化高
            conversion = round(np.random.uniform(0.30, 0.45), 4)

        # 合同字段(支撑痛点⑤:租户/合同/收租管理)
        contract_start = fake.date_between(start_date="-3y", end_date="-1y")
        contract_years = int(np.random.choice([1, 2, 3], p=[0.3, 0.5, 0.2]))
        contract_end = pd.Timestamp(contract_start) + pd.DateOffset(years=contract_years)
        # 距今天数:正数=未来到期,负数=已逾期
        days_to_end = (pd.Timestamp("2026-07-11") - contract_end).days
        # 收租状态:已收/待收/逾期 —— 已到期合同大部分已续约,仅小部分逾期
        if days_to_end > 60:
            rent_status = np.random.choice(["已收", "待收"], p=[0.80, 0.20])
        elif days_to_end > 0:
            # 60天内到期:部分待收续约
            rent_status = np.random.choice(["已收", "待收"], p=[0.55, 0.45])
        else:
            # 已到期:大部分已续约收讫,约 20% 逾期未收
            rent_status = np.random.choice(["已收", "逾期"], p=[0.80, 0.20])
        # 数据采集完整度(支撑痛点④:0~1,主力店高,小户偏低)
        collection_rate = round(np.random.uniform(0.88, 0.99) if s.is_anchor else np.random.uniform(0.55, 0.92), 3)

        rows.append({
            "shop_id": shop_id,
            "name": s.name,
            "category": s.category,
            "floor": s.floor,
            "area_sqm": area,
            "monthly_rent": monthly_rent,
            "monthly_sales": monthly_sales,
            "monthly_traffic": monthly_traffic,
            "member_conversion_rate": conversion,
            "is_anchor": s.is_anchor,
            "brand_type": s.brand_type,
            "note": s.note,
            "contract_start": str(contract_start),
            "contract_end": str(contract_end.date()),
            "contract_years": contract_years,
            "rent_status": rent_status,
            "collection_rate": collection_rate,
        })

    df = pd.DataFrame(rows)
    save_csv(df, "shops_master.csv", "raw")
    print(f"商铺数据已生成: {len(df)} 行 ({unique_brand_count()} 个去重品牌)")
    return df


# ===== 客户咨询记录(可用数据弹药③) =====
CONSULT_TYPES = {
    "商铺位置咨询": 0.22,   # 在哪/怎么走
    "会员权益咨询": 0.18,   # 积分/等级/折扣
    "活动促销咨询": 0.16,   # 满减/抽奖/节日活动
    "品牌商品咨询": 0.14,   # 有没有某品牌/某商品
    "营业时间咨询": 0.08,
    "停车服务咨询": 0.10,
    "投诉建议": 0.07,
    "租户合作咨询": 0.05,   # 招商/入驻
}
CONSULT_CHANNELS = ["微信小程序", "门店前台", "电话", "公众号留言", "现场扫码"]
CONSULT_TEMPLATES = {
    "商铺位置咨询": ["{}在几楼？", "{}怎么走？", "{}从哪个门进最近？", "{}旁边是什么店？"],
    "会员权益咨询": ["我的积分能换什么？", "金卡有什么权益？", "积分什么时候过期？", "会员日是哪天？", "怎么升级黑金？"],
    "活动促销咨询": ["这周末有什么活动？", "满减怎么用？", "抽奖在哪参加？", "双11有什么优惠？", "消费券怎么领？"],
    "品牌商品咨询": ["有没有{}？", "{}上新款了吗？", "{}在哪层？", "{}有童装吗？", "有奶茶店吗？"],
    "营业时间咨询": ["几点开门？", "晚上几点关门？", "沃尔玛营业到几点？", "停车场几点开放？"],
    "停车服务咨询": ["停车免费吗？", "停车在哪？", "消费抵停车费怎么弄？", "充电桩在哪？"],
    "投诉建议": ["服务态度差", "卫生间太脏", "空调太冷", "建议增加休息区", "排队太久"],
    "租户合作咨询": ["想入驻怎么联系？", "租金多少？", "还有空铺吗？", "招商电话多少？"],
}
ANCHOR_NAMES_REF = ["沃尔玛", "中影国际", "喜茶", "星巴克", "NIKE", "Adidas", "小米之家", "魅力金座"]


def generate_consultations(n=8000) -> pd.DataFrame:
    """生成客户咨询记录(来源:小程序/前台/电话/公众号/扫码)"""
    rows = []
    types = list(CONSULT_TYPES.keys())
    type_probs = list(CONSULT_TYPES.values())

    for i in range(n):
        ctype = np.random.choice(types, p=type_probs)
        channel = np.random.choice(CONSULT_CHANNELS, p=[0.32, 0.28, 0.15, 0.15, 0.10])

        # 咨询内容(从模板生成)
        templates = CONSULT_TEMPLATES[ctype]
        content = np.random.choice(templates)
        if "{}" in content:
            brand = np.random.choice(ANCHOR_NAMES_REF)
            content = content.format(brand)

        # 时间(全年分布,周末/节假日偏多)
        date = fake.date_between(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 12, 31))
        # 工作时间咨询为主
        hour = int(np.clip(np.random.normal(15, 5), 9, 21))

        # 情感倾向(投诉多为负面,其他中性偏正)
        if ctype == "投诉建议":
            sentiment = np.random.choice(["负面", "中性"], p=[0.75, 0.25])
        else:
            sentiment = np.random.choice(["正面", "中性"], p=[0.3, 0.70])

        # 是否已回复
        if sentiment == "负面" and np.random.random() < 0.3:
            status = "待处理"
        else:
            status = np.random.choice(["已回复", "已回复", "已回复", "待处理"], p=[0.7, 0.1, 0.1, 0.1])

        rows.append({
            "consult_id": f"C{i+1:05d}",
            "consult_time": f"{date} {hour:02d}:00",
            "date": str(date),
            "hour": hour,
            "weekday": pd.Timestamp(str(date)).weekday(),
            "consult_type": ctype,
            "channel": channel,
            "content": content,
            "sentiment": sentiment,
            "status": status,
        })

    df = pd.DataFrame(rows)
    save_csv(df, "consultations_2023.csv", "raw")
    print(f"咨询记录已生成: {len(df)} 行")
    return df
    """数据质量自检"""
    print("=" * 50)
    print("数据质量验证")
    print("=" * 50)

    raw_dir = get_data_dir("raw")
    issues = []

    for fname in ["foot_traffic_2023.csv", "members_2023.csv", "shops_master.csv"]:
        path = os.path.join(raw_dir, fname)
        if not os.path.exists(path):
            issues.append(f"❌ {fname} 不存在")
            continue

        df = pd.read_csv(path)
        print(f"\n--- {fname} ({len(df)} 行) ---")
        print(f"  列: {list(df.columns)}")
        print(f"  空值: {df.isnull().sum().sum()}")

        nulls = df.isnull().sum().sum()
        if nulls > 0:
            issues.append(f"❌ {fname} 有 {nulls} 个空值")

        neg = (df.select_dtypes(include='number') < 0).sum().sum()
        if neg > 0:
            issues.append(f"❌ {fname} 有 {neg} 个负数")

        print(f"  数值统计:")
        print(df.describe().to_string())

    if issues:
        print("\n" + "\n".join(issues))
    else:
        print("\n✅ 数据质量验证通过")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["foot_traffic", "members", "shops", "consultations"])
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    if args.validate:
        validate_data()
    elif args.only == "foot_traffic":
        generate_foot_traffic()
    elif args.only == "members":
        generate_members()
    elif args.only == "shops":
        generate_shops()
    elif args.only == "consultations":
        generate_consultations()
    else:
        print("生成全部数据...")
        generate_foot_traffic()
        generate_members()
        generate_shops()
        generate_consultations()
        print("\n全部数据生成完成，运行验证...")
        validate_data()
