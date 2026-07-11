"""万泰新天地真实商户主数据(按楼层 · 来源:现场实勘截图)

字段:
  name: 商户名(按截图原文,保留中英双名)
  category: 业态分类(餐饮/零售/服饰/娱乐/服务/汽车数码)
  floor: 楼层 1-5
  brand_type: 品牌类型(主力店/连锁品牌/本土品牌/服务配套)
  is_anchor: 是否主力店(大面积/强引流,如沃尔玛/中影/魅力金座)
  area_sqm: 面积(估算,主力店偏大)
  note: 备注(跨层/特殊)
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Shop:
    name: str
    category: str
    floor: int
    brand_type: str = "连锁品牌"
    is_anchor: bool = False
    area_sqm: int = 150
    note: str = ""


# ===== L1 (1F) 37 家 — 零售主力 + 餐饮 + 服饰 + 汽车数码 =====
L1_SHOPS: List[Shop] = [
    Shop("Adidas阿迪达斯", "服饰", 1, "连锁品牌", area_sqm=220),
    Shop("AITU", "服饰", 1, "本土品牌", area_sqm=120),
    Shop("ANTA安踏", "服饰", 1, "连锁品牌", area_sqm=200),
    Shop("啊一柠檬茶", "餐饮", 1, "本土品牌", area_sqm=60),
    Shop("百丽BELLE", "服饰", 1, "连锁品牌", area_sqm=130),
    Shop("BANANA BABY", "服饰", 1, "本土品牌", area_sqm=110),
    Shop("拌饭达人", "餐饮", 1, "本土品牌", area_sqm=90),
    Shop("霸王茶姬CHAGEE", "餐饮", 1, "连锁品牌", area_sqm=80),
    Shop("必胜客Pizza Hut", "餐饮", 1, "连锁品牌", area_sqm=260),
    Shop("波比艾斯", "餐饮", 1, "本土品牌", area_sqm=70),
    Shop("潮乐盟", "餐饮", 1, "本土品牌", area_sqm=100),
    Shop("汉堡王BURGER KING", "餐饮", 1, "连锁品牌", area_sqm=180),
    Shop("吉利银河", "汽车数码", 1, "连锁品牌", area_sqm=300, note="新能源展厅"),
    Shop("零跑汽车", "汽车数码", 1, "连锁品牌", area_sqm=300, note="新能源展厅"),
    Shop("LI-NING李宁", "服饰", 1, "连锁品牌", area_sqm=200),
    Shop("六福珠寶", "零售", 1, "连锁品牌", area_sqm=100, note="珠宝"),
    Shop("麦吉丽", "零售", 1, "连锁品牌", area_sqm=110, note="美妆"),
    Shop("NIKE耐克", "服饰", 1, "连锁品牌", is_anchor=True, area_sqm=260),
    Shop("OPPO", "汽车数码", 1, "连锁品牌", area_sqm=120, note="数码"),
    Shop("PM照相馆", "服务", 1, "本土品牌", area_sqm=80),
    Shop("柒小螺", "餐饮", 1, "本土品牌", area_sqm=70),
    Shop("HONOR荣耀", "汽车数码", 1, "连锁品牌", area_sqm=120, note="数码"),
    Shop("luckin coffee瑞幸咖啡", "餐饮", 1, "连锁品牌", area_sqm=70),
    Shop("RÓYEN润妍美妆", "零售", 1, "本土品牌", area_sqm=100, note="美妆"),
    Shop("炭丸烧肉名门", "餐饮", 1, "本土品牌", area_sqm=220),
    Shop("THE COLORIST调色师", "零售", 1, "连锁品牌", area_sqm=180, note="美妆"),
    Shop("The Green Party", "零售", 1, "连锁品牌", area_sqm=200, note="生活百货"),
    Shop("天福便利店C", "零售", 1, "连锁品牌", area_sqm=60, note="便利店"),
    Shop("VeroLatte维罗咖啡", "餐饮", 1, "本土品牌", area_sqm=70),
    Shop("唯驰古色WHICHI", "服饰", 1, "本土品牌", area_sqm=120),
    Shop("Walmart沃尔玛", "零售", 1, "连锁品牌", is_anchor=True, area_sqm=12000, note="主力超市跨层"),
    Shop("小米之家MI", "汽车数码", 1, "连锁品牌", area_sqm=200, note="数码"),
    Shop("小鹏汽车XPENG", "汽车数码", 1, "连锁品牌", area_sqm=300, note="新能源展厅"),
    Shop("喜茶", "餐饮", 1, "连锁品牌", area_sqm=80),
    Shop("星巴克", "餐饮", 1, "连锁品牌", area_sqm=150),
    Shop("倚桐YITONG", "服饰", 1, "本土品牌", area_sqm=120),
    Shop("之味集JI YUMMM", "餐饮", 1, "本土品牌", area_sqm=90),
]

# ===== L2 (2F) 13 家 — 母婴/童/服务/沃尔玛延续 =====
L2_SHOPS: List[Shop] = [
    Shop("爱婴岛", "零售", 2, "连锁品牌", area_sqm=200, note="母婴"),
    Shop("江博士DR·KONG", "零售", 2, "连锁品牌", area_sqm=100, note="童鞋童装"),
    Shop("拉比", "零售", 2, "连锁品牌", area_sqm=120, note="母婴"),
    Shop("浪漫春天", "服饰", 2, "连锁品牌", area_sqm=180, note="内衣"),
    Shop("篮小侠", "零售", 2, "本土品牌", area_sqm=120, note="童装/运动"),
    Shop("乐琪游乐", "娱乐", 2, "本土品牌", area_sqm=300, note="儿童游乐"),
    Shop("乐玩客", "娱乐", 2, "本土品牌", area_sqm=200, note="儿童游乐"),
    Shop("MOZI默兹", "服饰", 2, "本土品牌", area_sqm=130),
    Shop("诗碧曼", "服务", 2, "本土品牌", area_sqm=80, note="养发"),
    Shop("丝域养发", "服务", 2, "连锁品牌", area_sqm=80),
    Shop("Walmart沃尔玛", "零售", 2, "连锁品牌", is_anchor=True, area_sqm=12000, note="主力超市跨层"),
    Shop("熊兮兮", "零售", 2, "本土品牌", area_sqm=110, note="童装"),
    Shop("猿创编程", "服务", 2, "本土品牌", area_sqm=150, note="少儿编程"),
]

# ===== L3 (3F) 6 家 — 餐饮 + 娱乐 =====
L3_SHOPS: List[Shop] = [
    Shop("潮漫谷超级密室", "娱乐", 3, "本土品牌", area_sqm=400, note="密室"),
    Shop("拢好粤味", "餐饮", 3, "本土品牌", area_sqm=300),
    Shop("魅力金座", "娱乐", 3, "连锁品牌", area_sqm=600, note="KTV跨层"),
    Shop("厅四季椰子鸡", "餐饮", 3, "本土品牌", area_sqm=260),
    Shop("Walmart沃尔玛", "零售", 3, "连锁品牌", is_anchor=True, area_sqm=12000, note="主力超市跨层"),
    Shop("许府牛", "餐饮", 3, "本土品牌", area_sqm=240),
]

# ===== L4 (4F) 6 家 — 影院 + KTV + 餐饮 =====
L4_SHOPS: List[Shop] = [
    Shop("FUNDAY", "娱乐", 4, "本土品牌", area_sqm=350, note="运动娱乐"),
    Shop("魅力金座", "娱乐", 4, "连锁品牌", area_sqm=600, note="KTV跨层"),
    Shop("蛙来哒", "餐饮", 4, "连锁品牌", area_sqm=200),
    Shop("优客哩哩", "餐饮", 4, "本土品牌", area_sqm=260),
    Shop("中影国际", "娱乐", 4, "连锁品牌", is_anchor=True, area_sqm=3500, note="影院跨层"),
    Shop("钻石KTV", "娱乐", 4, "本土品牌", area_sqm=500),
]

# ===== L5 (5F) 3 家 — 娱乐主力 =====
L5_SHOPS: List[Shop] = [
    Shop("魅力金座", "娱乐", 5, "连锁品牌", area_sqm=600, note="KTV跨层"),
    Shop("金海娱乐", "娱乐", 5, "本土品牌", area_sqm=800),
    Shop("中影国际", "娱乐", 5, "连锁品牌", is_anchor=True, area_sqm=3500, note="影院跨层"),
]

ALL_SHOPS: List[Shop] = L1_SHOPS + L2_SHOPS + L3_SHOPS + L4_SHOPS + L5_SHOPS

# 按楼层分组(供 data_generator / 页面使用)
SHOPS_BY_FLOOR = {1: L1_SHOPS, 2: L2_SHOPS, 3: L3_SHOPS, 4: L4_SHOPS, 5: L5_SHOPS}

# 真实总户数(去重品牌跨层后用于报告)
def unique_brand_count() -> int:
    return len({s.name for s in ALL_SHOPS})

if __name__ == "__main__":
    print(f"总记录(含跨层): {len(ALL_SHOPS)}")
    print(f"去重品牌数: {unique_brand_count()}")
    for f in range(1, 6):
        ss = SHOPS_BY_FLOOR[f]
        cats = {}
        for s in ss:
            cats[s.category] = cats.get(s.category, 0) + 1
        print(f"  L{f}: {len(ss)} 家 | {cats}")
