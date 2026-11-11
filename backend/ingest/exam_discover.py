"""Look for NIRF submissions and fee notices on the websites of institutes beyond JEE. Writes candidates for review.

Usage: python -m ingest.exam_discover clat
Reads only public pages: the home page, /nirf, and pages it links to about NIRF, rankings, fees or admissions.
One site at a time per worker, with a pause between requests.
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml

from ingest.nirf_fetch import USER_AGENT

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "registry" / "exam_institute_websites.yaml"
OUTPUT = ROOT / "data" / "import"
DELAY_SECONDS = 1.0
MAX_PAGES = int(__import__("os").environ.get("MAX_PAGES", "14"))
_HREF = re.compile(r"""(?:href|src)\s*=\s*["']([^"'#]+)["']""", re.I)
_PAGE = re.compile(r"nirf|ranking|fee|admission|prospectus|ug-?programme|ba-?llb|b\.?a\.?\s*ll\.?b", re.I)
_NIRF = re.compile(r"nirf|ranking|data.?capturing|dcs|submitted", re.I)
_FEE = re.compile(r"fee", re.I)
_RECENT = re.compile(r"202[56]")


def get(session: requests.Session, url: str) -> str | None:
    try:
        response = session.get(url, timeout=20, allow_redirects=True)
    except requests.RequestException:
        return None
    finally:
        time.sleep(DELAY_SECONDS)
    if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
        return None
    return response.text


def discover(match: str, url: str) -> tuple[str, dict]:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    host = urlparse(url).netloc.removeprefix("www.")
    pages, seen = [url, urljoin(url, "nirf")], set()
    nirf, fees = set(), set()
    index = 0
    while index < len(pages) and len(seen) < MAX_PAGES:
        page = pages[index]
        index += 1
        if page in seen:
            continue
        seen.add(page)
        html = get(session, page)
        if not html:
            continue
        for href in _HREF.findall(html):
            link = urljoin(page, href.strip())
            lowered = link.lower()
            if lowered.endswith(".pdf") or ".pdf?" in lowered:
                name = lowered.rsplit("/", 1)[-1]
                if _NIRF.search(lowered) and _RECENT.search(lowered):
                    nirf.add(link)
                elif _FEE.search(name) and _RECENT.search(lowered):
                    fees.add(link)
            elif urlparse(link).netloc.removeprefix("www.").endswith(host) and _PAGE.search(lowered) and link not in pages:
                pages.append(link)
    return match, {"url": url, "pages_read": sorted(seen), "nirf": sorted(nirf), "fees": sorted(fees)}


def main() -> None:
    route = sys.argv[1]
    if route.endswith(".json"):
        # Candidate sites to search, as {name: url}, such as addresses found on Wikidata. Only used for looking.
        candidates = json.loads(Path(route).read_text())
        entries = [{"match": name, "url": url} for name, url in candidates.items()]
        route = Path(route).stem
    else:
        entries = yaml.safe_load(REGISTRY.read_text())["websites"][route]
    only = set(sys.argv[2:])
    unique = {e["url"]: e["match"] for e in entries if not only or any(o in e["match"] for o in only)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(pool.map(lambda item: discover(item[1], item[0]), unique.items()))
    out = OUTPUT / f"{route}_discovered{'_partial' if only else ''}.json"
    out.write_text(json.dumps(results, indent=2))
    for match, r in results.items():
        print(f"{len(r['pages_read']):>2} pages, {len(r['nirf'])} nirf, {len(r['fees'])} fee  {match}")


if __name__ == "__main__":
    main()
