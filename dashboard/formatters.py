import pandas as pd


def format_pct(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")
