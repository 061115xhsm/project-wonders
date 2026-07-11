"""工具函数"""
import os
import pandas as pd

def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)

def get_data_dir(subdir: str = "raw") -> str:
    """获取数据目录路径"""
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", subdir)
    ensure_dir(base)
    return base

def load_csv(filename: str, subdir: str = "raw") -> pd.DataFrame:
    """加载CSV文件"""
    path = os.path.join(get_data_dir(subdir), filename)
    return pd.read_csv(path)

def save_csv(df: pd.DataFrame, filename: str, subdir: str = "raw"):
    """保存CSV文件"""
    path = os.path.join(get_data_dir(subdir), filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path

def save_parquet(df: pd.DataFrame, filename: str, subdir: str = "processed"):
    """保存Parquet文件"""
    path = os.path.join(get_data_dir(subdir), filename.replace(".csv", ".parquet"))
    df.to_parquet(path, index=False)
    return path
