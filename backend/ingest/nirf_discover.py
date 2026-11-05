"""Look for NIRF submissions on institutes' own websites. Writes candidates for review.

Usage: python -m ingest.nirf_discover
Only public pages are read: the home page, /nirf, and pages the home page links to about
NIRF or rankings. Each site gets one request at a time, with a pause between requests.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml

from ingest.nirf_fetch import USER_AGENT

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "import" / "nirf_candidates.json"
DELAY_SECONDS = 1.0
_HREF = re.compile(r"""(?:href|src)\s*=\s*["']([^"'#]+)["']""", re.I)
_DOC = re.compile(r"nirf|ranking|india.?rank|data.?capturing|submitted", re.I)
_YEAR = re.compile(r"202[56]")
_CATEGORY = re.compile(r"engg|engineering|overall|_e_|-e-|ir-e-", re.I)
_EXCLUDE = re.compile(r"management|innovation|architecture|pharmacy|sdg|sustainab|research|faculty|certificate|law|medical|college", re.I)


def get(session: requests.Session, url: str) -> str | None:
    try:
        response = session.get(url, timeout=15, allow_redirects=True)
    except requests.RequestException:
        return None
    finally:
        time.sleep(DELAY_SECONDS)
    if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
        return None
    return response.text


def pdf_links(html: str, base: str) -> set[str]:
    found = set()
    for href in _HREF.findall(html):
        url = urljoin(base, href.strip())
        lowered = url.lower()
        if ".pdf" in lowered and _YEAR.search(lowered) and _CATEGORY.search(lowered) and not _EXCLUDE.search(lowered.rsplit("/", 1)[-1]):
            found.add(url)
    return found


def discover(slug: str, domain: str) -> tuple[str, dict]:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    home = f"https://{domain}/"
    pages = [home, urljoin(home, "nirf")]
    seen: set[str] = set()
    pdfs: set[str] = set()
    index = 0
    while index < len(pages) and len(seen) < 6:
        page = pages[index]
        index += 1
        if page in seen:
            continue
        seen.add(page)
        html = get(session, page)
        if not html:
            continue
        pdfs |= pdf_links(html, page)
        for href in _HREF.findall(html):
            url = urljoin(page, href.strip())
            same_site = urlparse(url).netloc.removeprefix("www.").endswith(domain.removeprefix("www."))
            if same_site and _DOC.search(url) and not url.lower().endswith(".pdf") and url not in pages:
                pages.append(url)
    return slug, {"domain": domain, "pages_read": sorted(seen), "pdfs": sorted(pdfs)}


def main() -> None:
    domains = yaml.safe_load((ROOT / "data" / "registry" / "institute_domains.yaml").read_text())
    known = yaml.safe_load((ROOT / "data" / "registry" / "nirf_documents.yaml").read_text())
    todo = {slug: domain for slug, domain in domains.items() if not known.get(slug)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(lambda item: discover(*item), todo.items()))
    OUTPUT.write_text(json.dumps(results, indent=2))
    with_pdfs = {slug: r for slug, r in results.items() if r["pdfs"]}
    print(f"{len(with_pdfs)} of {len(results)} institutes have candidate documents")
    for slug, r in results.items():
        print(f"{slug}: {len(r['pdfs'])} pdfs, {len(r['pages_read'])} pages")


if __name__ == "__main__":
    main()
