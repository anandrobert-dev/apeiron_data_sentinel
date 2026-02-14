"""Core validation engine — orchestrates rules against loaded DataFrames."""

from datetime import date
from typing import Any

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.duplicates import detect_cross_file_duplicates, detect_duplicates
from app.engine.mismatches import detect_mismatches, detect_missing_keys
from app.engine.reconciliation import check_gl_existence, generate_reconciliation_summary
from app.models.rule import Rule


async def load_active_rules(
    db: AsyncSession,
    client_id: str | None = None,
    rule_type: str | None = None,
) -> list[Rule]:
    """Load all active, approved rules for a client (including global rules)."""
    today = date.today()
    query = select(Rule).where(
        Rule.enabled == True,
        Rule.approved_by.isnot(None),
        (Rule.effective_from.is_(None) | (Rule.effective_from <= today)),
        (Rule.effective_to.is_(None) | (Rule.effective_to >= today)),
    )

    if client_id:
        query = query.where(
            (Rule.client_id == client_id) | (Rule.client_id.is_(None))
        )
    else:
        query = query.where(Rule.client_id.is_(None))

    if rule_type:
        query = query.where(Rule.rule_type == rule_type)

    result = await db.execute(query)
    return list(result.scalars().all())


def apply_rules(
    rules: list[Rule],
    dataframes: dict[str, pl.DataFrame],
    gl_reference: pl.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Apply a set of rules against loaded DataFrames.

    Args:
        rules: List of active Rule ORM objects
        dataframes: Dict mapping file labels to Polars DataFrames
        gl_reference: Optional GL code reference DataFrame

    Returns:
        Dict with issues, summary, counts, and detailed stats
    """
    all_issues: list[pl.DataFrame] = []
    error_counts: dict[str, int] = {}
    warning_counts: dict[str, int] = {}
    
    # Validation stats collection
    total_records = sum(df.height for df in dataframes.values())
    duplicates_found = 0
    duplicate_fields = set()
    sample_rows = []

    file_labels = list(dataframes.keys())

    for rule in rules:
        issue_df = pl.DataFrame()
        rule_key = f"{rule.rule_type}:{rule.primary_field}"

        try:
            if rule.rule_type == "duplicate":
                # Handle composite keys (comma-separated)
                fields = [f.strip() for f in rule.primary_field.split(",")]
                field_arg = fields[0] if len(fields) == 1 else fields
                
                # Check duplicates within each file that has the field(s)
                for label, df in dataframes.items():
                    # Check if all required fields exist
                    missing = [f for f in fields if f not in df.columns]
                    if not missing:
                        result = detect_duplicates(
                            df, field_arg, source_label=label
                        )
                        if not result.is_empty():
                            issue_df = pl.concat([issue_df, result]) if not issue_df.is_empty() else result
                            
                            # Update stats
                            duplicates_found += result.height
                            duplicate_fields.add(rule.primary_field)
                            
                            # Collect sample rows (up to 100)
                            if len(sample_rows) < 100:
                                samples = result.head(100 - len(sample_rows)).to_dicts()
                                sample_rows.extend(samples)
                    else:
                        warning_msg = f"Rule '{rule.name}' skipped for '{label}': Missing fields {missing}"
                        warning_counts[rule.primary_field] = warning_counts.get(rule.primary_field, 0) + 1
                        # Ideally log this or add to a warnings list in the report


                # Cross-file duplicates if secondary_field specifies second file
                # (Note: composite keys not yet supported for cross-file in this version)
                if rule.secondary_field and len(file_labels) >= 2:
                    for i in range(len(file_labels)):
                        for j in range(i + 1, len(file_labels)):
                            df1 = dataframes[file_labels[i]]
                            df2 = dataframes[file_labels[j]]
                            if rule.primary_field in df1.columns and rule.primary_field in df2.columns:
                                result = detect_cross_file_duplicates(
                                    df1, df2, rule.primary_field,
                                    label1=file_labels[i], label2=file_labels[j],
                                )
                                if not result.is_empty():
                                    issue_df = pl.concat([issue_df, result]) if not issue_df.is_empty() else result

            elif rule.rule_type == "match":
                # Cross-file field matching
                if rule.secondary_field and len(file_labels) >= 2:
                    for i in range(len(file_labels)):
                        for j in range(i + 1, len(file_labels)):
                            df1 = dataframes[file_labels[i]]
                            df2 = dataframes[file_labels[j]]
                            result = detect_mismatches(
                                df1, df2,
                                join_field=rule.primary_field,
                                compare_field=rule.secondary_field,
                                tolerance=rule.tolerance or 0.0,
                                label1=file_labels[i], label2=file_labels[j],
                            )
                            if not result.is_empty():
                                issue_df = pl.concat([issue_df, result]) if not issue_df.is_empty() else result

            elif rule.rule_type == "existence":
                # GL code existence check
                if gl_reference is not None:
                    for label, df in dataframes.items():
                        result = check_gl_existence(
                            df, gl_reference,
                            data_gl_field=rule.primary_field,
                            gl_ref_field=rule.secondary_field or rule.primary_field,
                        )
                        if not result.is_empty():
                            issue_df = pl.concat([issue_df, result]) if not issue_df.is_empty() else result

            elif rule.rule_type == "numeric_compare":
                # Numeric field comparison across files
                if rule.secondary_field and rule.operator:
                    for i in range(len(file_labels)):
                        for j in range(i + 1, len(file_labels)):
                            df1 = dataframes[file_labels[i]]
                            df2 = dataframes[file_labels[j]]
                            result = detect_mismatches(
                                df1, df2,
                                join_field=rule.primary_field,
                                compare_field=rule.secondary_field,
                                tolerance=rule.tolerance or 0.0,
                                label1=file_labels[i], label2=file_labels[j],
                            )
                            if not result.is_empty():
                                issue_df = pl.concat([issue_df, result]) if not issue_df.is_empty() else result

        except Exception as e:
            # Log but don't stop processing
            error_counts[f"rule_error:{rule_key}"] = 1
            print(f"Error applying rule {rule.name}: {e}")
            continue

        if not issue_df.is_empty():
            # Add severity from the rule
            issue_df = issue_df.with_columns(
                pl.lit(rule.severity).alias("severity"),
                pl.lit(rule.name).alias("rule_name"),
            )
            all_issues.append(issue_df)

            count = issue_df.height
            target = error_counts if rule.severity == "error" else warning_counts
            target[rule_key] = target.get(rule_key, 0) + count

    # Generate reconciliation summary for first two files
    summary = {}
    if len(file_labels) >= 2:
        df1 = dataframes[file_labels[0]]
        df2 = dataframes[file_labels[1]]
        # Find common field for join
        common_fields = set(df1.columns) & set(df2.columns)
        if common_fields:
            join_field = next(iter(common_fields))
            summary = generate_reconciliation_summary(
                df1, df2, join_field=join_field,
                label1=file_labels[0], label2=file_labels[1],
            )

    return {
        "issues": all_issues,
        "summary": summary,
        "error_counts": error_counts,
        "warning_counts": warning_counts,
        "total_errors": sum(error_counts.values()),
        "total_warnings": sum(warning_counts.values()),
        "rules_applied": len(rules),
        "total_records": total_records,
        "duplicates_found": duplicates_found,
        "duplicate_fields": list(duplicate_fields),
        "sample_rows": sample_rows,
    }
