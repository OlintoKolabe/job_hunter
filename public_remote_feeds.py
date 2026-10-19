"""Public remote-job feeds. Bounded requests and source-attributed links."""
import datetime
import threading
import time
import urllib.parse
from collectors import fetch_json,item

def _date(value):
    if isinstance(value,(int,float)):
        return datetime.datetime.fromtimestamp(value/1000 if value>100000000000 else value,datetime.timezone.utc).isoformat()
    return str(value or "")

_CACHE={}
_LOCK=threading.RLock()

def fetch(source,roles="",country="BR"):
    cache_key=(source,roles.split(",")[0].strip() if source=="himalayas" else "",country if source=="himalayas" else "")
    with _LOCK:
        entry=_CACHE.get(cache_key)
        if entry and time.monotonic()-entry[0]<21600:
            return list(entry[1])
    jobs=[]
    if source=="himalayas":
        # Restrict to the searcher's country; worldwide jobs are also eligible.
        terms=[v.strip() for v in roles.split(",") if v.strip()]
        q=terms[0] if terms else "Product Manager"
        params={"q":q[:90],"sort":"recent","page":1}
        if country=="BR":params["country"]="BR"
        data=fetch_json("https://himalayas.app/jobs/api/search?"+urllib.parse.urlencode(params))
        entries=data.get("jobs",[])
        for j in entries if isinstance(entries,list) else []:
            restrictions=j.get("locationRestrictions") or []
            location="Worldwide" if not restrictions else ", ".join(x.get("name","") for x in restrictions if isinstance(x,dict))
            v=item(j.get("companyName"),j.get("title"),j.get("applicationLink"),location,
                   "himalayas",_date(j.get("pubDate")),j.get("description") or j.get("excerpt") or "")
            if v:jobs.append(v)
    elif source=="remotive":
        data=fetch_json("https://remotive.com/api/remote-jobs?limit=200")
        for j in data.get("jobs",[]) if isinstance(data,dict) else []:
            v=item(j.get("company_name"),j.get("title"),j.get("url"),j.get("candidate_required_location") or "Remote",
                   "remotive",j.get("publication_date"),j.get("description") or "")
            if v:jobs.append(v)
    elif source=="remoteok":
        data=fetch_json("https://remoteok.com/api")
        for j in data if isinstance(data,list) else []:
            if not isinstance(j,dict) or not j.get("position"):continue
            link=j.get("url") or ""
            # The API requires a direct link to Remote OK, not an external apply redirect.
            if not link.startswith("https://remoteok.com/") and not link.startswith("https://remoteOK.com/"):continue
            v=item(j.get("company"),j.get("position"),link,j.get("location") or "Remote",
                   "remoteok",j.get("date") or _date(j.get("epoch")),j.get("description") or "")
            if v:jobs.append(v)
    else:raise ValueError("Unknown public source")
    with _LOCK:
        _CACHE[cache_key]=(time.monotonic(),list(jobs))
    return jobs
