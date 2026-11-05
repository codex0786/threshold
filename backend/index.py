"""Vercel entry point for the public, read-only deployment."""
import os
from pathlib import Path

_snapshot = Path(__file__).resolve().parent / "snapshot" / "threshold.db"
os.environ.update({
    # immutable: the serverless filesystem is read-only, so SQLite must not try to create a journal.
    "DATABASE_URL": f"sqlite:///file:{_snapshot}?mode=ro&immutable=1&uri=true",
    "ENVIRONMENT": "production",
    "READ_ONLY": "true",
    "RATE_LIMIT_PER_MINUTE": "150",
})

from app.main import app  # noqa: E402,F401
