"""Report generator — create error-annotated Excel exports."""

from pathlib import Path

import polars as pl
import xlsxwriter


def generate_excel_report(
    issues: list[pl.DataFrame],
    summary: dict,
    output_path: str | Path,
    sheet_name: str = "Validation Results",
) -> Path:
    """
    Generate an error-annotated Excel report from validation results.

    Args:
        issues: List of DataFrames with issue details
        summary: Reconciliation summary dict
        output_path: Where to save the .xlsx file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = xlsxwriter.Workbook(str(output_path))

    # --- Formats ---
    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#1a1a2e",
        "font_color": "#ffffff",
        "border": 1,
    })
    error_fmt = workbook.add_format({
        "bg_color": "#ffcccc",
        "border": 1,
    })
    warning_fmt = workbook.add_format({
        "bg_color": "#fff3cd",
        "border": 1,
    })
    normal_fmt = workbook.add_format({"border": 1})
    summary_key_fmt = workbook.add_format({"bold": True})
    summary_val_fmt = workbook.add_format({"num_format": "#,##0.00"})

    # --- Summary Sheet ---
    ws_summary = workbook.add_worksheet("Summary")
    row = 0
    ws_summary.write(row, 0, "Apeiron Data Sentinel — Validation Summary", header_fmt)
    row += 2
    for key, value in summary.items():
        ws_summary.write(row, 0, key.replace("_", " ").title(), summary_key_fmt)
        ws_summary.write(row, 1, value, summary_val_fmt)
        row += 1
    ws_summary.set_column(0, 0, 30)
    ws_summary.set_column(1, 1, 20)

    # --- Issue Sheets ---
    # --- Issue Sheets ---
    used_names = {"Summary"}
    
    for idx, issue_df in enumerate(issues):
        if issue_df.is_empty():
            continue

        # Determine sheet name from issue type
        if "issue_type" in issue_df.columns:
            first_type = issue_df["issue_type"][0]
            base_name = str(first_type).replace("_", " ").title()
        else:
            base_name = f"Issues {idx + 1}"

        # Ensure uniqueness
        ws_name = base_name[:31]
        counter = 1
        while ws_name in used_names:
            suffix = f" {counter}"
            # Truncate base to room for suffix (max 31 chars total)
            allowed_len = 31 - len(suffix)
            ws_name = f"{base_name[:allowed_len]}{suffix}"
            counter += 1
        
        used_names.add(ws_name)

        ws = workbook.add_worksheet(ws_name)
        columns = issue_df.columns

        # Write headers
        for col_idx, col_name in enumerate(columns):
            ws.write(0, col_idx, col_name, header_fmt)

        # Write data
        for row_idx in range(issue_df.height):
            for col_idx, col_name in enumerate(columns):
                value = issue_df[col_name][row_idx]
                # Determine format based on severity
                cell_fmt = normal_fmt
                if "severity" in issue_df.columns:
                    sev = issue_df["severity"][row_idx]
                    if sev == "error":
                        cell_fmt = error_fmt
                    elif sev == "warning":
                        cell_fmt = warning_fmt
                elif "issue_type" in issue_df.columns:
                    cell_fmt = error_fmt

                ws.write(row_idx + 1, col_idx, str(value) if value is not None else "", cell_fmt)

            # Auto-fit columns
        for col_idx, col_name in enumerate(columns):
            max_len = max(len(col_name), 15)
            ws.set_column(col_idx, col_idx, max_len + 2)

    workbook.close()
    return output_path
