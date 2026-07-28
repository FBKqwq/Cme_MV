import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REVIEW_DATA_ROOT = Path(
    os.getenv(
        "REVIEW_DATA_ROOT",
        str(PROJECT_ROOT / "data" / "review"),
    )
).resolve()
INBOX_ROOT = REVIEW_DATA_ROOT / "current"
REVIEW_ROOT = REVIEW_DATA_ROOT / "state"
DATABASE_PATH = REVIEW_ROOT / "review.sqlite3"
EXPORT_ROOT = REVIEW_ROOT / "exports"
SCHEMA_PATH = INBOX_ROOT / "graph_property_schema_v3_6.json"
