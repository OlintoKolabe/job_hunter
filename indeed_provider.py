"""On-demand Indeed Brazil via JobSpy. No credentials, no proxy, bounded calls."""
from collectors import item
from urllib.parse import parse_qs, urlsplit
import re

def enabled():
    return True

def search(keyword):
    from jobspy import scrape_jobs
    df=scrape_jobs(site_name="indeed",search_term=keyword,location="Brazil",
                   country_indeed="Brazil",is_remote=True,results_wanted=15,
                   fetch_description=False,verbose=0)
    jobs=[]
    for row in df.to_dict("records"):
        loc=row.get("location")
        if isinstance(loc,dict):
            location=", ".join(str(loc.get(k) or "") for k in ("city","state","country") if loc.get(k))
        else:
            location=str(loc or "")
        if location.lower() in ("nan","none","<na>"):location=""
        url=row.get("job_url") or row.get("job_url_direct")
        description=row.get("description")
        published=row.get("date_posted")
        value=item(row.get("company"),row.get("title"),url,location,"indeed",
                   str(published or ""),str(description or ""))
        if value:
            if row.get("is_remote") is True:value["remote"]=True
            jobs.append(value)
    return jobs


def description_for_job(url, title, company=""):
    """Look up an Indeed JD through the existing JobSpy integration.

    Search responses contain descriptions; accept one only when its exact
    Indeed requisition key matches the requested URL, never a similar job.
    """
    parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.hostname not in ("br.indeed.com","www.indeed.com","indeed.com"):
        return None
    key=parse_qs(parsed.query).get("jk",[""])[0]
    if not re.fullmatch(r"[a-fA-F0-9]{16}",key):return None
    from jobspy import scrape_jobs
    for term in (f'"{title[:90]}" "{company[:70]}"' if company else title[:90],title[:90]):
        if not term.strip():continue
        try:
            df=scrape_jobs(site_name="indeed",search_term=term,location="Brazil",
                           country_indeed="Brazil",results_wanted=40,
                           fetch_description=True,verbose=0)
            for row in df.to_dict("records"):
                candidate=str(row.get("job_url") or "")
                if parse_qs(urlsplit(candidate).query).get("jk",[""])[0].lower()!=key.lower():continue
                description=row.get("description")
                if isinstance(description,str) and len(description.strip())>=100:
                    return description[:18000]
        except Exception:
            continue
    return None
