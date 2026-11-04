"""Read-only collector for public Manatal Careers Page employer boards.

No application endpoint is contacted. An empty board is different from a
failed or unparseable response, and the caller's normal filters remain final.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from collectors import item, TITLE_RE


class _PublicHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.job_titles = {}
        self.parts = []
        self.title = ""
        self.heading = ""
        self._heading_depth = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag == "a" and attrs.get("href"):
            self.urls.append(attrs["href"])
            if attrs.get("data-job-title"):
                self.job_titles[attrs["href"]] = attrs["data-job-title"]
        if tag == "meta" and attrs.get("property") in ("og:title", "og:description"):
            if attrs.get("property") == "og:title":
                self.title = attrs.get("content", "")[:300]
        if tag in ("h1", "h2", "h3", "h4") and not self.heading:
            self._heading_depth = 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if tag in ("h1", "h2", "h3", "h4"):
            self._heading_depth = 0

    def handle_data(self, data):
        if self._skip or not data.strip():
            return
        part = data.strip()
        self.parts.append(part)
        if self._heading_depth and not self.heading:
            self.heading = part


def collect_board(slug, read, *, max_pages=10, max_details=20):
    """Bounded collection of explicitly configured public employer pages."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", slug):
        raise ValueError("invalid Careers Page employer slug")
    base = f"https://{slug}.careers-page.com/"
    links = []
    seen = set()
    relevant_links = []
    for number in range(1, max_pages + 1):
        raw, _ = read(base + (f"?page={number}" if number > 1 else ""), size=1500000)
        board = _PublicHTML()
        board.feed(raw.decode("utf-8", "replace"))
        for href in board.urls:
            address = urljoin(base, href)
            parts = urlsplit(address)
            if (parts.scheme == "https" and parts.hostname == f"{slug}.careers-page.com"
                    and re.fullmatch(r"/jobs/[a-zA-Z0-9-]+/?", parts.path)
                    and address not in seen):
                seen.add(address)
                links.append(address)
                # The public card publishes a reliable title; use it to avoid
                # spending all detail requests on unrelated first-page jobs.
                title = board.job_titles.get(href)
                if title and TITLE_RE.search(title):
                    relevant_links.append(address)
        if not any("?page=" in href for href in board.urls):
            break
    jobs = []
    failures = 0
    # Prefer cards with matching published titles across all pages. Legacy
    # boards without card metadata retain the original bounded fallback.
    candidates = relevant_links if relevant_links else links
    for address in candidates[:max_details]:
        try:
            raw, _ = read(address, size=1500000)
            page = _PublicHTML()
            page.feed(raw.decode("utf-8", "replace"))
            title = page.title.split(" | ", 1)[0].strip() or page.heading
            if not title or not TITLE_RE.search(title):
                continue
            content = " ".join(page.parts)
            # Only explicit evidence is propagated; never infer Brazil/remote.
            prefix = content[:800]
            location_match = re.search(r"\b(?:Remote|Remoto|Hybrid|On-site|Brazil|Brasil|Argentina|Colombia|Portugal)\b", prefix, re.I)
            location = location_match.group() if location_match else ""
            value = item(slug, title, address, location, "careers_page", "", content[:18000])
            if value:
                jobs.append(value)
        except (OSError, ValueError):
            failures += 1
    if candidates and failures == min(len(candidates), max_details):
        raise ValueError("Careers Page detail retrieval failed")
    if not links and not ("open positions" in " ".join(board.parts).lower()):
        raise ValueError("Careers Page board format unrecognized")
    return jobs, "ok" if jobs or not links else "partial"
