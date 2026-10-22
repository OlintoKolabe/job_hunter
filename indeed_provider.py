"""On-demand Indeed Brazil via JobSpy. No credentials, no proxy, bounded calls."""
from collectors import item

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
