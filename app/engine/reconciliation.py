"""Reconciliation engine — GL existence checks and summary generation."""

import polars as pl


def check_gl_existence(
    data_df: pl.DataFrame,
    gl_df: pl.DataFrame,
    data_gl_field: str = "gl_code",
    gl_ref_field: str = "gl_code",
) -> pl.DataFrame:
    """
    Verify that GL codes in the data file exist in the GL reference file.
    Returns records with invalid/missing GL codes.
    """
    if data_gl_field not in data_df.columns:
        return pl.DataFrame()
    if gl_ref_field not in gl_df.columns:
        return pl.DataFrame()

    invalid = data_df.join(
        gl_df.select(gl_ref_field).unique().rename({gl_ref_field: data_gl_field}),
        on=data_gl_field,
        how="anti",
    )

    if invalid.is_empty():
        return pl.DataFrame()

    return invalid.with_columns(
        pl.lit("invalid_gl_code").alias("issue_type"),
        pl.lit(data_gl_field).alias("checked_field"),
    )


def generate_reconciliation_summary(
    df1: pl.DataFrame,
    df2: pl.DataFrame,
    join_field: str,
    amount_field: str | None = None,
    label1: str = "file_1",
    label2: str = "file_2",
) -> dict:
    """
    Generate a reconciliation summary between two files.
    Returns counts and optional amount totals.
    """
    if join_field not in df1.columns or join_field not in df2.columns:
        return {"error": f"Join field '{join_field}' not found in both files"}

    total_1 = df1.height
    total_2 = df2.height

    matched = df1.join(df2.select(join_field).unique(), on=join_field, how="semi")
    unmatched_1 = df1.join(df2.select(join_field).unique(), on=join_field, how="anti")
    unmatched_2 = df2.join(df1.select(join_field).unique(), on=join_field, how="anti")

    summary = {
        f"total_{label1}": total_1,
        f"total_{label2}": total_2,
        "matched": matched.height,
        f"unmatched_{label1}": unmatched_1.height,
        f"unmatched_{label2}": unmatched_2.height,
        "match_rate_pct": round(matched.height / max(total_1, 1) * 100, 2),
    }

    if amount_field and amount_field in df1.columns and amount_field in df2.columns:
        try:
            sum_1 = df1[amount_field].cast(pl.Float64).sum()
            sum_2 = df2[amount_field].cast(pl.Float64).sum()
            summary[f"total_amount_{label1}"] = float(sum_1)
            summary[f"total_amount_{label2}"] = float(sum_2)
            summary["amount_difference"] = round(float(sum_1 - sum_2), 2)
        except Exception:
            pass  # Skip if amount field can't be cast to numeric

    return summary
