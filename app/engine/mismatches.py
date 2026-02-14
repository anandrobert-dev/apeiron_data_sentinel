"""Cross-file mismatch detection engine using Polars."""

import polars as pl


def detect_mismatches(
    df1: pl.DataFrame,
    df2: pl.DataFrame,
    join_field: str,
    compare_field: str,
    tolerance: float = 0.0,
    label1: str = "file_1",
    label2: str = "file_2",
) -> pl.DataFrame:
    """
    Detect mismatches between two files joined on a common key.

    For numeric fields, applies tolerance-based comparison.
    For text fields, does exact comparison.
    """
    if join_field not in df1.columns or join_field not in df2.columns:
        return pl.DataFrame()
    if compare_field not in df1.columns or compare_field not in df2.columns:
        return pl.DataFrame()

    # Rename compare fields to avoid collision
    col1 = f"{compare_field}_{label1}"
    col2 = f"{compare_field}_{label2}"

    merged = df1.select([join_field, compare_field]).rename({compare_field: col1}).join(
        df2.select([join_field, compare_field]).rename({compare_field: col2}),
        on=join_field,
        how="inner",
    )

    if merged.is_empty():
        return pl.DataFrame()

    # Determine if numeric comparison
    dtype1 = merged.schema[col1]
    is_numeric = dtype1 in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)

    if is_numeric and tolerance > 0:
        mismatches = merged.filter(
            (pl.col(col1) - pl.col(col2)).abs() > tolerance
        )
    else:
        mismatches = merged.filter(
            pl.col(col1).cast(pl.Utf8) != pl.col(col2).cast(pl.Utf8)
        )

    if mismatches.is_empty():
        return pl.DataFrame()

    result = mismatches.with_columns(
        pl.lit("mismatch").alias("issue_type"),
        pl.lit(compare_field).alias("checked_field"),
        pl.lit(f"{label1} vs {label2}").alias("compared_files"),
    )

    return result


def detect_missing_keys(
    df1: pl.DataFrame,
    df2: pl.DataFrame,
    join_field: str,
    label1: str = "file_1",
    label2: str = "file_2",
) -> pl.DataFrame:
    """Find records in df1 that have no corresponding match in df2."""
    if join_field not in df1.columns or join_field not in df2.columns:
        return pl.DataFrame()

    missing = df1.join(
        df2.select(join_field).unique(),
        on=join_field,
        how="anti",
    )

    if missing.is_empty():
        return pl.DataFrame()

    result = missing.with_columns(
        pl.lit("missing_in_" + label2).alias("issue_type"),
        pl.lit(join_field).alias("checked_field"),
        pl.lit(label1).alias("source_file"),
    )

    return result
