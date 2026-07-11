"""核心算法：RFM 聚类 / 商铺评分 / 客流模型 / 营销引擎"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

from app.config import (
    RFM_K_CLUSTERS,
    RFM_REFERENCE_DATE,
    SHOP_WEIGHTS,
)


class RFMModel:
    """RFM 客户分群模型

    R = 最近到店天数（越小越好）
    F = 到店次数（越大越好）
    M = 累计消费（越大越好）
    聚类后按综合评分 (-R + F + M) 降序动态映射标签，不硬编码。
    """

    LABELS = ["高价值", "潜力", "新客", "沉睡"]

    def __init__(self, k=RFM_K_CLUSTERS, reference_date=RFM_REFERENCE_DATE):
        self.k = k
        self.reference_date = pd.Timestamp(reference_date)
        self.scaler = StandardScaler()
        self.model = None
        self.label_map = None  # 动态映射，不硬编码

    def _compute_rfm(self, df: pd.DataFrame) -> pd.DataFrame:
        """从原始数据计算 R/F/M 三列"""
        rfm = pd.DataFrame()
        last_visit = pd.to_datetime(df["last_visit_date"], errors="coerce")
        rfm["R"] = (self.reference_date - last_visit).dt.days
        rfm["F"] = pd.to_numeric(df["visit_count"], errors="coerce")
        rfm["M"] = pd.to_numeric(df["total_spent"], errors="coerce")
        return rfm

    def fit(self, df: pd.DataFrame) -> pd.Series:
        """训练 RFM 模型

        1. 计算 R/F/M
        2. StandardScaler 标准化
        3. KMeans 聚类
        4. 按聚类中心综合评分 (-R+F+M) 降序，动态映射标签
        返回每个样本的分群标签 Series
        """
        rfm = self._compute_rfm(df)

        # 标准化
        X_scaled = self.scaler.fit_transform(rfm)

        # 聚类
        self.model = KMeans(n_clusters=self.k, random_state=42, n_init=10)
        clusters = self.model.fit_predict(X_scaled)

        # 动态标签映射：按综合评分降序
        # centers 列顺序 = [R, F, M]；R 越小越好取负，F/M 越大越好取正
        centers = self.model.cluster_centers_
        composite = -centers[:, 0] + centers[:, 1] + centers[:, 2]
        order = composite.argsort()[::-1]  # 降序，order[0] = 最高价值簇

        labels = self.LABELS[: self.k]
        self.label_map = {order[i]: labels[i] for i in range(self.k)}

        return pd.Series(
            [self.label_map[c] for c in clusters],
            index=df.index,
            name="segment",
        )

    def predict(self, df: pd.DataFrame) -> pd.Series:
        """对新数据预测标签"""
        rfm = self._compute_rfm(df)
        X_scaled = self.scaler.transform(rfm)
        clusters = self.model.predict(X_scaled)
        return pd.Series(
            [self.label_map[c] for c in clusters],
            index=df.index,
            name="segment",
        )

    def get_segment_stats(self, df: pd.DataFrame, labels) -> pd.DataFrame:
        """返回各群体统计摘要"""
        df = df.copy()
        df["segment"] = labels
        return df.groupby("segment").agg(
            total_spent=["mean", "sum"],
            visit_count=["mean"],
            age=["mean"],
        ).round(2)


def calculate_shop_score(df: pd.DataFrame) -> pd.DataFrame:
    """商铺综合评分

    各指标 Min-Max 归一化到 0-100，加权求和：
    sales×0.4 + traffic×0.3 + rent_ratio×0.2 + conversion×0.1
    rent_ratio = monthly_rent / median(monthly_rent) （相对租金贡献）
    返回带 score 和 rank 列的 DataFrame
    """
    df = df.copy()

    def minmax(s: pd.Series) -> pd.Series:
        lo, hi = s.min(), s.max()
        if hi == lo:
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - lo) / (hi - lo) * 100

    sales = minmax(df["monthly_sales"])
    traffic = minmax(df["monthly_traffic"].astype(float))
    conversion = minmax(df["member_conversion_rate"])

    # 相对租金贡献：高于中位数 = 1，线性比例
    rent_median = df["monthly_rent"].median()
    rent_ratio = df["monthly_rent"] / rent_median
    # rent_ratio 归一化到 0-100（基于自身 min/max）
    rent_ratio_norm = minmax(rent_ratio)

    w = SHOP_WEIGHTS
    df["score"] = (
        sales * w["sales"]
        + traffic * w["traffic"]
        + rent_ratio_norm * w["rent_ratio"]
        + conversion * w["conversion"]
    ).round(2)

    df["rank"] = df["score"].rank(ascending=False, method="min").astype(int)
    return df


def build_traffic_heatmap(df: pd.DataFrame):
    """构建 7×24 客流热力图（weekday × hour）

    值 = 平均 visitor_count
    返回 (matrix[7,24], peaks) 其中 peaks 为 Top3 峰值坐标 [(weekday, hour, value), ...]
    """
    work = df.copy()
    work["weekday"] = pd.to_numeric(work["weekday"], errors="coerce")
    work["hour"] = pd.to_numeric(work["hour"], errors="coerce")
    work["visitor_count"] = pd.to_numeric(work["visitor_count"], errors="coerce")

    pivot = work.pivot_table(
        index="weekday", columns="hour", values="visitor_count", aggfunc="mean"
    )
    # 补全 0-6 行 / 0-23 列
    matrix = pivot.reindex(index=range(7), columns=range(24)).fillna(0).values

    # Top3 峰值坐标
    flat_idx = np.argsort(matrix.ravel())[::-1][:3]
    peaks = []
    for idx in flat_idx:
        wd, hr = divmod(int(idx), 24)
        peaks.append((wd, hr, round(float(matrix[wd, hr]), 2)))

    return matrix, peaks


def analyze_weather_impact(df: pd.DataFrame) -> dict:
    """对比晴天 vs 雨天平均客流"""
    work = df.copy()
    work["visitor_count"] = pd.to_numeric(work["visitor_count"], errors="coerce")
    sunny = work[work["weather"] == "晴"]["visitor_count"].mean()
    rainy = work[work["weather"] == "雨"]["visitor_count"].mean()
    diff = sunny - rainy
    ratio = sunny / rainy if rainy else np.nan
    return {
        "晴": round(float(sunny), 2) if pd.notna(sunny) else None,
        "雨": round(float(rainy), 2) if pd.notna(rainy) else None,
        "差异": round(float(diff), 2) if pd.notna(diff) else None,
        "晴雨比": round(float(ratio), 2) if pd.notna(ratio) else None,
    }


def analyze_holiday_effect(df: pd.DataFrame) -> dict:
    """对比节假日 vs 工作日平均客流"""
    work = df.copy()
    work["visitor_count"] = pd.to_numeric(work["visitor_count"], errors="coerce")
    holiday = work[work["is_holiday"]]["visitor_count"].mean()
    workday = work[~work["is_holiday"]]["visitor_count"].mean()
    diff = holiday - workday
    ratio = holiday / workday if workday else np.nan
    return {
        "节假日": round(float(holiday), 2) if pd.notna(holiday) else None,
        "工作日": round(float(workday), 2) if pd.notna(workday) else None,
        "差异": round(float(diff), 2) if pd.notna(diff) else None,
        "节假日倍数": round(float(ratio), 2) if pd.notna(ratio) else None,
    }


def generate_marketing_strategy(segment: str, avg_spent: float, visit_count: float) -> list:
    """营销策略规则引擎

    根据客户分群与消费统计生成策略列表。
    """
    strategies = []

    if segment == "高价值":
        strategies.append("VIP专属活动：定期举办高端品鉴会与私密沙龙")
        strategies.append("积分双倍：消费享双倍积分，加速权益升级")
        strategies.append("新品预览：优先体验限量新品与首发商品")
        if avg_spent > 5000:
            strategies.append("专属客户经理：一对一服务与定制化推荐")
    elif segment == "沉睡":
        strategies.append("大额优惠券：发放高额满减券激活消费")
        strategies.append("限时激活：7天内到店享专属礼包，制造紧迫感")
        strategies.append("个性化推荐：基于历史偏好推送高相关商品")
        if visit_count < 10:
            strategies.append("召回激励：到店即赠热门商品体验装")
    elif segment == "潜力":
        strategies.append("升级权益引导：消费满额即升级会员等级")
        strategies.append("消费满赠：阶梯式满赠刺激客单价提升")
        if avg_spent < 2000:
            strategies.append("品类拓展：推荐关联品类提升消费广度")
    elif segment == "新客":
        strategies.append("首单优惠：首单立减降低决策门槛")
        strategies.append("签到奖励：每日签到得积分培养到店习惯")
        strategies.append("会员日邀请：邀请参与会员日专属活动")
    else:
        strategies.append("通用优惠：发放基础优惠券促进复购")

    return strategies
