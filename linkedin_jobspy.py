"""LinkedIn search using the maintained JobSpy collector.

The original guest HTML collector remains available for rollback, but the
catalog's LinkedIn path uses this provider exclusively.
"""
import logging
import math
import threading

from collectors import item

_CALL_SLOTS = threading.BoundedSemaphore(2)


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "nat", "none", "<na>") else text


def _location(value):
    if isinstance(value, dict):
        return ", ".join(_clean(value.get(k)) for k in ("city", "state", "country") if _clean(value.get(k)))
    if value is not None and not isinstance(value, str):
        parts = [_clean(getattr(value, k, None)) for k in ("city", "state", "country")]
        if any(parts):
            return ", ".join(p for p in parts if p)
    return _clean(value)


def search(keyword, mode="remote"):
    """Return source-evidenced jobs; never claim an unknown mode is remote."""
    if mode not in ("remote", "onsite", "hybrid", "all"):
        raise ValueError("Invalid LinkedIn work mode")
    from jobspy import scrape_jobs

    kwargs = dict(site_name="linkedin", search_term=keyword, location="Brazil",
                  results_wanted=15, fetch_description=True,
                  verbose=0)
    if mode == "remote":
        kwargs["is_remote"] = True
    # LinkedIn can throttle bursts; limit simultaneous expensive detail fetches.
    with _CALL_SLOTS:
        frame = scrape_jobs(**kwargs)
    errors = getattr(frame, "attrs", {}).get("errors", {})
    if errors.get("linkedin"):
        raise RuntimeError(f"JobSpy LinkedIn: {str(errors['linkedin'])[:120]}")
    jobs = []
    for row in frame.to_dict("records"):
        job = item(row.get("company"), row.get("title"),
                   _clean(row.get("job_url") or row.get("job_url_direct")),
                   _location(row.get("location")), "linkedin_guest",
                   _clean(row.get("date_posted")), _clean(row.get("description")))
        if not job:
            continue
        # JobSpy derives this from source metadata, unlike our old search URL.
        # A false flag does not establish onsite: hybrid is also possible.
        if row.get("is_remote") is True:
            job["remote"] = True
        for key in ("workplaceType", "workArrangement", "remoteType", "workMode"):
            if _clean(row.get(key)):
                job[key] = _clean(row[key])[:200]
        job["collector"] = "jobspy_linkedin"
        jobs.append(job)
    logging.info("JH_JOBSPY_LINKEDIN mode=%s term=%s raw=%d remote_flag=%d described=%d",
                 mode, keyword[:60], len(jobs), sum(j.get("remote") is True for j in jobs),
                 sum(bool(j.get("description")) for j in jobs))
    return jobs
