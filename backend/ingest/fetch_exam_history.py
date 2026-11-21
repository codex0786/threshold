"""Download the past-year documents listed in data/registry/exam_history.yaml.

Usage: python -m ingest.fetch_exam_history [--route neet-ug]

Saves each file as data/raw/<route>/<year>/<label>.pdf, skips files already present, keeps only real PDFs,
and writes data/raw/<route>/history.json with each file's source, size and sha256. Polite: one request at a time,
two seconds apart. Rerun to resume.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import requests
import yaml

from ingest.nirf_fetch import USER_AGENT

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry" / "exam_history.yaml"


def main(only: str | None = None) -> int:
    registry = yaml.safe_load(REGISTRY.read_text())
    failures = 0
    for code, route in registry["routes"].items():
        if only and code != only:
            continue
        folder = ROOT / "data" / "raw" / code
        manifest_path = folder / "history.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        for year, documents in sorted(route["years"].items()):
            for label, doc in documents.items():
                path = folder / str(year) / f"{label}.pdf"
                key = f"{year}/{label}"
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        response = requests.get(doc["url"], headers={"User-Agent": USER_AGENT}, timeout=180)
                    except requests.RequestException as error:
                        print(f"{code} {key}: {type(error).__name__}, run again later")
                        failures += 1
                        continue
                    if response.status_code != 200 or not response.content.startswith(b"%PDF"):
                        print(f"{code} {key}: HTTP {response.status_code}, not a PDF")
                        failures += 1
                        continue
                    path.write_bytes(response.content)
                    print(f"{code} {key}: saved {len(response.content) / 1e6:.1f} MB")
                    time.sleep(2)
                content = path.read_bytes()
                manifest[key] = {"title": doc["title"], "url": doc["url"], "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        folder.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=1))
    print("All documents present." if not failures else f"{failures} document(s) missing. Run the command again.")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--route")
    raise SystemExit(main(parser.parse_args().route))
