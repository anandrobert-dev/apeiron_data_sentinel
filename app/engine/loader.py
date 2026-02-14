"""File loader — parse Excel/CSV uploads into Polars DataFrames."""

import os
from pathlib import Path

import polars as pl

from app.config import settings

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE = settings.upload_max_size_mb * 1024 * 1024  # bytes


def validate_upload(filename: str, file_size: int) -> None:
    """Validate file type and size before processing."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}"
        )
    if file_size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large ({file_size / 1024 / 1024:.1f}MB). "
            f"Max: {settings.upload_max_size_mb}MB"
        )


def load_file(filepath: str | Path) -> pl.DataFrame:
    """
    Load a CSV or Excel file into a Polars DataFrame.
    Normalizes column names to lowercase with underscores.
    """
    filepath = Path(filepath)
    ext = filepath.suffix.lower()

    if ext == ".csv":
        df = pl.read_csv(filepath, infer_schema_length=10000, ignore_errors=True)
    elif ext in (".xlsx", ".xls"):
        df = pl.read_excel(filepath, infer_schema_length=10000)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Normalize column names: strip, lowercase, replace spaces with underscores, handle #
    rename_map = {}
    for col in df.columns:
        new_col = col.strip().lower()
        new_col = new_col.replace(" ", "_").replace("-", "_")
        new_col = new_col.replace("#", "number").replace(".", "")
        # Remove multiple underscores
        while "__" in new_col:
            new_col = new_col.replace("__", "_")
        rename_map[col] = new_col

    df = df.rename(rename_map)

    return df


def save_upload(content: bytes, filename: str, client_code: str, run_id: str) -> Path:
    """Save uploaded file to disk and return the path."""
    upload_dir = Path(settings.upload_dir) / client_code / run_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    filepath.write_bytes(content)
    return filepath
