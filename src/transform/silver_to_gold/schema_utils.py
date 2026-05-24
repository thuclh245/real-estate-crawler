from __future__ import annotations

from pyspark.sql import functions as F
from pyspark.sql import types as T


def cast_void_columns_to_string(input_df):
    result_df = input_df
    for field in result_df.schema.fields:
        if isinstance(field.dataType, T.NullType):
            result_df = result_df.withColumn(
                field.name, F.col(field.name).cast("string")
            )
    return result_df


def ensure_columns(df, columns_with_default):
    for col_name, default_value in columns_with_default.items():
        if col_name not in df.columns:
            df = df.withColumn(col_name, F.lit(default_value))
    return df
