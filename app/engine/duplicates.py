"""Duplicate detection engine using Polars."""

import polars as pl


def detect_duplicates(
    df: pl.DataFrame,
    field: str | list[str],
    source_label: str = "file",
) -> pl.DataFrame:
    """
    Detect duplicate values in a single field or composite key within a DataFrame.
    Returns a DataFrame of duplicate records with their count.
    """
    fields = [field] if isinstance(field, str) else field
    
    # Check if all fields exist
    missing = [f for f in fields if f not in df.columns]
    if missing:
        return pl.DataFrame({"error": [f"Fields {missing} not found in {source_label}"]})

    duplicates = (
        df.filter(pl.all_horizontal([pl.col(f).is_not_null() for f in fields]))
        .group_by(fields)
        .agg(pl.count().alias("count"))
        .filter(pl.col("count") > 1)
        .sort("count", descending=True)
    )

    if duplicates.is_empty():
        return pl.DataFrame()

    # Join back to get full duplicate records
    result = df.join(duplicates.select(fields), on=fields, how="semi")
    
    # Create descriptive "checked_field" string
    checked_field_str = field if isinstance(field, str) else ", ".join(field)
    
    result = result.with_columns(
        pl.lit(source_label).alias("source_file"),
        pl.lit("duplicate").alias("issue_type"),
        pl.lit(checked_field_str).alias("checked_field"),
    )

    return result


def detect_cross_file_duplicates(
    df1: pl.DataFrame,
    df2: pl.DataFrame,
    field: str,
    label1: str = "file_1",
    label2: str = "file_2",
) -> pl.DataFrame:
    """
    Detect values that appear in both files for a given field.
    This is useful for catching duplicate invoices across payment + accrual reports.
    """
    if field not in df1.columns or field not in df2.columns:
        return pl.DataFrame()

    vals1 = df1.select(field).filter(pl.col(field).is_not_null()).unique()
    vals2 = df2.select(field).filter(pl.col(field).is_not_null()).unique()

    common = vals1.join(vals2, on=field, how="inner")

    if common.is_empty():
        return pl.DataFrame()

    result = common.with_columns(
        pl.lit(f"{label1} & {label2}").alias("found_in"),
        pl.lit("cross_file_duplicate").alias("issue_type"),
        pl.lit(field).alias("checked_field"),
    )

    return result
