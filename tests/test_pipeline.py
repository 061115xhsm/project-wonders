"""万泰新天地智能运营中台 - 单元测试"""
import pytest
import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import MALL_NAME, RFM_K_CLUSTERS, SHOP_WEIGHTS
from app.utils import load_csv
from app.processor import clean_data, mask_sensitive_data
from app.models import (
    RFMModel, calculate_shop_score,
    build_traffic_heatmap, analyze_weather_impact,
    analyze_holiday_effect, generate_marketing_strategy,
)


class TestDataQuality:
    """数据质量测试"""

    def test_foot_traffic_rows(self):
        ft = load_csv("foot_traffic_2023.csv", "raw")
        assert 43000 <= len(ft) <= 45000, f"客流行数异常: {len(ft)}"

    def test_members_rows(self):
        mb = load_csv("members_2023.csv", "raw")
        assert len(mb) == 5000

    def test_shops_rows(self):
        sh = load_csv("shops_master.csv", "raw")
        # 真实商户清单:60个去重品牌,跨层主力店(沃尔玛3层/中影2层/魅力金座3层)→65条记录
        assert len(sh) == 65, f"商铺记录数异常: {len(sh)}"
        assert sh["name"].nunique() == 60, f"去重品牌数异常: {sh['name'].nunique()}"

    def test_no_nulls(self):
        for fname in ["foot_traffic_2023.csv", "members_2023.csv", "shops_master.csv"]:
            df = load_csv(fname, "raw")
            # note 列是可选备注(主力店跨层标注),允许空;其余列不得有空值
            cols = [c for c in df.columns if c != "note"]
            nulls = df[cols].isnull().sum().sum()
            assert nulls == 0, f"{fname}有空值(排除note列后): {nulls}"

    def test_no_negative_numbers(self):
        for fname in ["foot_traffic_2023.csv", "members_2023.csv", "shops_master.csv"]:
            df = load_csv(fname, "raw")
            assert (df.select_dtypes(include='number') < 0).sum().sum() == 0

    def test_weekend_traffic_higher(self):
        ft = load_csv("foot_traffic_2023.csv", "raw")
        wk = ft[ft['is_weekend'] == False]['visitor_count'].mean()
        we = ft[ft['is_weekend'] == True]['visitor_count'].mean()
        assert we > wk * 1.2, f"周末客流未高于工作日: wk={wk:.0f}, we={we:.0f}"


class TestProcessor:
    """ETL和脱敏测试"""

    def test_clean_data_adds_features(self):
        members = load_csv("members_2023.csv", "raw")
        cleaned = clean_data(members)
        assert 'age_group' in cleaned.columns

    def test_phone_masking(self):
        members = load_csv("members_2023.csv", "raw")
        cleaned = clean_data(members)
        masked = mask_sensitive_data(cleaned)
        # 检查手机号有****模式
        assert masked['phone'].str.contains(r'\*{4}').any(), "手机号未脱敏"

    def test_name_masking(self):
        members = load_csv("members_2023.csv", "raw")
        cleaned = clean_data(members)
        masked = mask_sensitive_data(cleaned)
        # 检查姓名有*号
        assert masked['name'].str.contains(r'\*').any(), "姓名未脱敏"


class TestRFMModel:
    """RFM模型测试"""

    def test_fit_returns_correct_length(self):
        members = load_csv("members_2023.csv", "raw")
        cleaned = clean_data(members)
        masked = mask_sensitive_data(cleaned)
        rfm = RFMModel()
        labels = rfm.fit(masked)
        assert len(labels) == 5000

    def test_labels_are_valid(self):
        members = load_csv("members_2023.csv", "raw")
        cleaned = clean_data(members)
        masked = mask_sensitive_data(cleaned)
        rfm = RFMModel()
        labels = rfm.fit(masked)
        assert set(labels).issubset({'高价值', '潜力', '新客', '沉睡'})

    def test_vip_spends_more_than_sleeping(self):
        members = load_csv("members_2023.csv", "raw")
        cleaned = clean_data(members)
        masked = mask_sensitive_data(cleaned)
        rfm = RFMModel()
        labels = rfm.fit(masked)
        masked['segment'] = labels
        vip = masked[masked['segment'] == '高价值']['total_spent'].mean()
        sleeping = masked[masked['segment'] == '沉睡']['total_spent'].mean()
        assert vip > sleeping * 1.5, f"VIP消费未显著高于沉睡: VIP={vip:.0f}, 沉睡={sleeping:.0f}"


class TestShopScore:
    """商铺评分测试"""

    def test_score_range(self):
        shops = load_csv("shops_master.csv", "raw")
        scored = calculate_shop_score(shops)
        assert scored['score'].min() >= 0
        assert scored['score'].max() <= 100

    def test_has_rank(self):
        shops = load_csv("shops_master.csv", "raw")
        scored = calculate_shop_score(shops)
        assert 'rank' in scored.columns


class TestTrafficModel:
    """客流模型测试"""

    def test_heatmap_shape(self):
        traffic = load_csv("foot_traffic_2023.csv", "raw")
        matrix, peaks = build_traffic_heatmap(traffic)
        assert matrix.shape == (7, 24)

    def test_peaks_count(self):
        traffic = load_csv("foot_traffic_2023.csv", "raw")
        matrix, peaks = build_traffic_heatmap(traffic)
        assert len(peaks) == 3

    def test_weather_impact(self):
        traffic = load_csv("foot_traffic_2023.csv", "raw")
        result = analyze_weather_impact(traffic)
        assert '晴' in result and '雨' in result
        assert result['晴'] > result['雨']  # 晴天客流应高于雨天


class TestMarketing:
    """营销引擎测试"""

    @pytest.mark.parametrize("segment", ['高价值', '潜力', '新客', '沉睡'])
    def test_strategy_generation(self, segment):
        strategies = generate_marketing_strategy(segment, 1000, 20)
        assert len(strategies) >= 2, f"{segment}策略太少"
