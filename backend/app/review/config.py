import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REVIEW_DATA_ROOT = Path(
    os.getenv(
        "REVIEW_DATA_ROOT",
        str(PROJECT_ROOT / "data" / "review"),
    )
).resolve()
DEFAULT_BATCH_ROOT = REVIEW_DATA_ROOT / "1"
INBOX_ROOT = DEFAULT_BATCH_ROOT / "current"
REVIEW_ROOT = DEFAULT_BATCH_ROOT / "state"
RESULT_ROOT = REVIEW_ROOT / "results"
EXPORT_ROOT = REVIEW_ROOT / "exports"
SCHEMA_PATH = INBOX_ROOT / "graph_property_schema_v3_6.json"
