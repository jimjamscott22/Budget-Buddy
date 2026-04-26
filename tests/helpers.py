from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def make_db_path() -> Path:
    root = Path(__file__).resolve().parent.parent / "test_dbs"
    root.mkdir(exist_ok=True)
    return root / f"{uuid4().hex}.db"
