"""ETL + 数据脱敏处理"""
import pandas as pd
import numpy as np

from app.config import PHONE_MASK_PATTERN, PHONE_MASK_REPLACEMENT
from app.utils import save_parquet


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """数据清洗 + 特征工程

    - 数值型缺失用中位数填充，类别型用众数填充
    - 日期格式统一为 %Y-%m-%d
    - 去除重复行
    - 特征工程：age_group / weekday_desc / is_weekend（仅当缺失时生成）
    """
    df = df.copy()
    df = df.drop_duplicates().reset_index(drop=True)

    # 日期列统一格式为 %Y-%m-%d
    date_cols = [c for c in df.columns if "date" in c.lower()]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

    # 缺失值填充：数值型中位数、类别型众数
    for col in df.columns:
        if df[col].isna().sum() == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
        else:
            mode = df[col].mode()
            df[col] = df[col].fillna(mode.iloc[0] if not mode.empty else "未知")

    # 特征工程：age_group [18-25, 26-35, 36-45, 45+]
    if "age" in df.columns and "age_group" not in df.columns:
        age = pd.to_numeric(df["age"], errors="coerce")
        df["age_group"] = pd.cut(
            age,
            bins=[-np.inf, 25, 35, 45, np.inf],
            labels=["18-25", "26-35", "36-45", "45+"],
        ).astype(str)

    # 特征工程：weekday_desc / is_weekend（客流数据可能本身已有，缺失才补）
    if "date" in df.columns:
        dt = pd.to_datetime(df["date"], errors="coerce")
        weekday_zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        if "weekday_desc" not in df.columns:
            df["weekday_desc"] = dt.dt.weekday.map(
                lambda w: weekday_zh[int(w)] if pd.notna(w) else None
            )
        if "is_weekend" not in df.columns:
            df["is_weekend"] = dt.dt.weekday.isin([5, 6])

    return df


def mask_sensitive_data(df: pd.DataFrame) -> pd.DataFrame:
    """敏感字段脱敏（仅处理存在的列，不存在就跳过）

    - 手机号：中间4位替换为 ****
    - 姓名：首字保留 + **（长度>2保留首字+**，否则首字+*）
    """
    df = df.copy()

    if "phone" in df.columns:
        df["phone"] = df["phone"].astype(str).str.replace(
            PHONE_MASK_PATTERN, PHONE_MASK_REPLACEMENT, regex=True
        )

    if "name" in df.columns:
        df["name"] = df["name"].astype(str).apply(
            lambda x: x[0] + "**" if len(x) > 2 else x[0] + "*"
        )

    return df


def save_processed(df: pd.DataFrame, filename: str):
    """保存为 parquet 格式到 data/processed/ 目录"""
    return save_parquet(df, filename, subdir="processed")
