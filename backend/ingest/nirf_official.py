"""Confirm JEE institutes' NIRF ranks against the official 2025 Engineering list, and mark them official.

A rank is confirmed only when the institute has NIRF's name at the same rank (ignoring case and
punctuation), or is a reviewed match in data/registry/nirf_2025_engineering_official.yaml.

The loader uses `confirm` for new data. `python -m ingest.nirf_official` applies it to the existing snapshot.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data" / "registry" / "nirf_2025_engineering_official.yaml"
SOURCES = ROOT / "data" / "registry" / "sources.yaml"
SNAPSHOT = ROOT / "backend" / "snapshot" / "threshold.db"
SOURCE_KEY = "nirf_2025_official"


def official_list() -> dict:
    return yaml.safe_load(OFFICIAL.read_text())


def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def confirm(official: dict, slug: str, name: str, rank: int) -> str | None:
    """NIRF's ID for this institute if the official list confirms its rank, otherwise None."""
    at_rank = [row for row in official["ranks"] if row[0] == rank]
    reviewed = official.get("reviewed_matches", {}).get(slug)
    for _, nirf_id, nirf_name in at_rank:
        if nirf_id == reviewed or normalise(nirf_name) == normalise(name):
            return nirf_id
    return None


def promote_snapshot(path: Path = SNAPSHOT) -> tuple[int, list[str]]:
    """Mark confirmed ranks official in a snapshot. Works on a copy, then replaces the file."""
    source = next(s for s in yaml.safe_load(SOURCES.read_text()) if s["key"] == SOURCE_KEY)
    official = official_list()
    work = path.with_suffix(".promoting")
    shutil.copy(path, work)
    con = sqlite3.connect(work)
    con.execute(
        "INSERT OR IGNORE INTO data_sources (key, name, publisher, url, tier, access_method, access_status, terms_note) VALUES (?,?,?,?,?,?,?,?)",
        tuple(source[k] for k in ("key", "name", "publisher", "url", "tier", "access_method", "access_status", "terms_note")),
    )
    source_id = con.execute("SELECT id FROM data_sources WHERE key = ?", (SOURCE_KEY,)).fetchone()[0]
    rows = con.execute(
        "SELECT r.id, i.slug, i.official_name, r.rank FROM institution_rankings r JOIN institutions i ON i.id = r.institution_id "
        "WHERE r.framework = 'NIRF' AND r.category = 'Engineering' AND r.year = 2025"
    ).fetchall()
    unconfirmed = []
    promoted = 0
    for ranking_id, slug, name, rank in rows:
        if confirm(official, slug, name, rank):
            con.execute("UPDATE institution_rankings SET verification_status = 'official', source_id = ? WHERE id = ?", (source_id, ranking_id))
            promoted += 1
        else:
            unconfirmed.append(f"{slug} (rank {rank})")
    con.commit()
    con.close()
    work.replace(path)
    return promoted, unconfirmed


if __name__ == "__main__":
    promoted, unconfirmed = promote_snapshot()
    print(f"{promoted} ranks marked official")
    if unconfirmed:
        print("Not confirmed, left as secondary:", ", ".join(unconfirmed))
