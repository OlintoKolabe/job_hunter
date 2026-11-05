"""Read-only collector for public Manatal Careers Page employer boards.

No application endpoint is contacted. An empty board is different from a
failed or unparseable response, and the caller's normal filters remain final.
"""
import re
import json
import threading
import time
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from collectors import item, TITLE_RE

_CACHE = {}
_LOCK = threading.RLock()
_OK_TTL = 900  # Avoid fetching the same public board for every user search.
_LIMIT_TTL = 300  # Give rate-limited boards a quiet period.


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


def _verified_job_metadata(raw):
    """Use Scrapling on already-fetched HTML; no extra HTTP/browser calls.

    Only public JobPosting JSON-LD is trusted for dates and remote/location
    metadata. Missing information must remain missing for the normal filters.
    """
    try:
        from scrapling import Selector
    except ImportError:
        return {}
    page = Selector(raw)
    for script in page.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(str(script.text or ""))
        except (TypeError, ValueError):
            continue
        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if isinstance(obj, dict) and isinstance(obj.get("@graph"), list):
                objects.extend(obj["@graph"])
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            kinds = obj.get("@type", [])
            if not isinstance(kinds, list):
                kinds = [kinds]
            if "JobPosting" not in kinds:
                continue
            posted = obj.get("datePosted", "")
            location = obj.get("jobLocation", {})
            if isinstance(location, list):
                location = location[0] if location else {}
            address = location.get("address", {}) if isinstance(location, dict) else {}
            if not isinstance(address, dict):
                address = {}
            country = address.get("addressCountry", "")
            city = address.get("addressLocality", "")
            if isinstance(country, dict):
                country = country.get("name", "")
            remote = str(obj.get("jobLocationType") or "").upper() == "TELECOMMUTE"
            return {"published": posted if isinstance(posted, str) else "",
                    "location": ", ".join(str(v) for v in (city, country) if isinstance(v, str) and v),
                    "remote": remote}
    return {}


def collect_board(slug, read, *, max_pages=6, max_details=8):
    """Bounded collection of explicitly configured public employer pages."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", slug):
        raise ValueError("invalid Careers Page employer slug")
    # Only real HTTP collectors share a cache. Mocked readers remain isolated
    # for deterministic tests, and no private user state is ever cached.
    use_cache = getattr(read, "__module__", "") == "catalog_engine"
    with _LOCK:
        cached = _CACHE.get(slug) if use_cache else None
        if cached and time.monotonic() < cached[0]:
            return [dict(row) for row in cached[1]], cached[2]
    base = f"https://{slug}.careers-page.com/"
    links = []
    seen = set()
    relevant_links = []
    known_titles = {}
    rate_limited = False
    last_board = None
    for number in range(1, max_pages + 1):
        try:
            raw, _ = read(base + (f"?page={number}" if number > 1 else ""), size=1500000)
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                raise
            rate_limited = True
            break
        board = _PublicHTML()
        board.feed(raw.decode("utf-8", "replace"))
        last_board = board
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
                if title:
                    known_titles[address] = title
                if title and TITLE_RE.search(title):
                    relevant_links.append(address)
        if not any("?page=" in href for href in board.urls):
            break
    jobs = []
    failures = 0
    # Prefer cards with matching published titles across all pages. Legacy
    # boards without card metadata retain the original bounded fallback.
    candidates = relevant_links if known_titles else links
    for address in ([] if rate_limited else candidates[:max_details]):
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
            metadata = _verified_job_metadata(raw)
            location = metadata.get("location") or location
            value = item(slug, title, address, location, "careers_page", metadata.get("published", ""), content[:18000])
            if value:
                if metadata.get("remote"):
                    value["remote"] = True
                    value["workplaceType"] = "Remote"
                jobs.append(value)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                rate_limited = True
                break
            failures += 1
        except (OSError, ValueError):
            failures += 1
    if rate_limited:
        # Only retain the actual titles from published cards. Missing country,
        # modality, date and JD remain unknown and go to review, not confirmed.
        detailed = {row["url"] for row in jobs}
        for address in candidates[:max_details]:
            if address in detailed or not known_titles.get(address):
                continue
            value = item(slug,known_titles[address],address,"","careers_page")
            if value:
                jobs.append(value)
    if candidates and failures == min(len(candidates), max_details) and not rate_limited:
        raise ValueError("Careers Page detail retrieval failed")
    if not links and not rate_limited and not (last_board and "open positions" in " ".join(last_board.parts).lower()):
        raise ValueError("Careers Page board format unrecognized")
    # The absence of a target title is a legitimate zero, provided the board
    # supplied card titles. Never call it a collection failure.
    state = "rate_limited" if rate_limited else ("partial" if failures else "ok")
    if use_cache:
        with _LOCK:
            _CACHE[slug] = (time.monotonic() + (_LIMIT_TTL if rate_limited else _OK_TTL),
                            [dict(row) for row in jobs], state)
    return jobs, state
