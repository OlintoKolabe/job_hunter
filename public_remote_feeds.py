"""Public remote-job feeds. Bounded requests and source-attributed links."""
import datetime
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from collectors import fetch_json,item

def _date(value):
    if isinstance(value,(int,float)):
        return datetime.datetime.fromtimestamp(value/1000 if value>100000000000 else value,datetime.timezone.utc).isoformat()
    return str(value or "")

def _entries(payload):
    if isinstance(payload,list):return payload
    if isinstance(payload,dict):
        for key in ("jobs","data","results","items"):
            value=payload.get(key)
            if isinstance(value,list):return value
            if isinstance(value,dict):
                nested=_entries(value)
                if nested:return nested
    return []

def _tavily_search(query):
    token=os.getenv("TAVILY_API_KEY","").strip()
    if not token:return None
    body=json.dumps({"query":query,"search_depth":"basic","max_results":10,
                     "include_answer":False,"include_raw_content":False}).encode()
    req=urllib.request.Request("https://api.tavily.com/search",data=body,
             headers={"Content-Type":"application/json","Authorization":"Bearer "+token},method="POST")
    with urllib.request.urlopen(req,timeout=10) as response:
        return json.loads(response.read(500000))

_CACHE={}
_LOCK=threading.RLock()
_TAVILY_DISABLED_UNTIL=0.0

def fetch(source,roles="",country="BR"):
    selected=tuple(dict.fromkeys(term.strip()[:90] for term in roles.split(",") if term.strip()))[:12]
    queried=source in ("himalayas","leveljobs","remotejobs_org","tavily")
    cache_key=(source,selected if queried else (),country if queried else "")
    with _LOCK:
        entry=_CACHE.get(cache_key)
        if entry and time.monotonic()-entry[0]<21600:
            return list(entry[1])
    jobs=[]
    if source=="himalayas":
        # Source search is single-term; query each requested role, then dedupe.
        seen=set()
        def search_role(q):
            params={"q":q,"sort":"recent","page":1}
            if country=="BR":params["country"]="BR"
            try:
                return fetch_json("https://himalayas.app/jobs/api/search?"+urllib.parse.urlencode(params))
            except Exception as exc:
                logging.warning("JH_HIMALAYAS_ROLE_FAILED role=%r error=%s",q,type(exc).__name__)
                return None
        queries=selected or ("Product Manager",)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses=list(pool.map(search_role,queries))
        if all(response is None for response in responses):
            raise ValueError("Himalayas: todas as consultas de cargo falharam")
        for data in responses:
            if not isinstance(data,dict):continue
            entries=data.get("jobs",[])
            for j in entries if isinstance(entries,list) else []:
                restrictions=j.get("locationRestrictions") or []
                names=[]
                for loc in restrictions if isinstance(restrictions,list) else []:
                    name=loc if isinstance(loc,str) else loc.get("name") if isinstance(loc,dict) else None
                    if isinstance(name,str) and name.strip():names.append(name.strip())
                # A malformed nonempty restriction is unknown, not worldwide.
                location="Worldwide" if restrictions==[] else ", ".join(names)
                v=item(j.get("companyName"),j.get("title"),j.get("applicationLink"),location,
                       "himalayas",_date(j.get("pubDate")),j.get("description") or j.get("excerpt") or "")
                if v and v["url"] not in seen:
                    seen.add(v["url"]);jobs.append(v)
    elif source in ("leveljobs","remotejobs_org","tavily"):
        if source=="tavily" and not os.getenv("TAVILY_API_KEY","").strip():
            raise ValueError("Tavily não configurado")
        if source=="tavily" and time.monotonic()<_TAVILY_DISABLED_UNTIL:
            raise ValueError("Tavily em pausa por limite ou indisponibilidade")
        seen=set()
        queries=(selected[:2] if source=="tavily" else selected[:5]) or ("Product Manager",)
        def search_role(q):
            try:
                if source=="leveljobs":
                    params={"query":q,"remote":1,"sort":"recent","page":1,"posted_within_hours":168}
                    return fetch_json("https://jobsbylevel.com/api/v1/jobs?"+urllib.parse.urlencode(params))
                if source=="remotejobs_org":
                    params={"q":q,"sort":"recent","limit":50,"offset":0,"workArrangement":"remote"}
                    return fetch_json("https://remotejobs.org/api/v1/jobs?"+urllib.parse.urlencode(params))
                return _tavily_search('site:jobs.lever.co OR site:boards.greenhouse.io OR site:jobs.ashbyhq.com '+q+' remote Brazil LATAM job')
            except urllib.error.HTTPError as exc:
                if source=="tavily" and exc.code in (401,402,403,429):
                    global _TAVILY_DISABLED_UNTIL
                    with _LOCK:_TAVILY_DISABLED_UNTIL=time.monotonic()+3600
                logging.warning("JH_PUBLIC_FEED_HTTP_FAILED source=%s status=%d",source,exc.code)
                return None
            except Exception as exc:
                logging.warning("JH_PUBLIC_FEED_QUERY_FAILED source=%s query=%r error=%s",source,q,type(exc).__name__)
                return None
        with ThreadPoolExecutor(max_workers=min(5,len(queries))) as pool:
            responses=list(pool.map(search_role,queries))
        if all(response is None for response in responses):
            raise ValueError(source+": todas as consultas falharam")
        for payload in responses:
            for entry in _entries(payload):
                if not isinstance(entry,dict):continue
                company=entry.get("company") or entry.get("company_name") or entry.get("companyName")
                if isinstance(company,dict):company=company.get("name")
                title=entry.get("title") or entry.get("job_title")
                link=entry.get("url") or entry.get("apply_url") or entry.get("link")
                if source=="leveljobs" and not link and entry.get("slug"):
                    link="https://jobsbylevel.com/jobs/"+str(entry["slug"])
                if source=="tavily":
                    # The result is a search snippet, not a verified job posting.
                    # Country, modality and publication date must remain unknown.
                    title=entry.get("title")
                    company=""
                location=entry.get("location") or ""
                if isinstance(location,dict):location=location.get("name") or location.get("text") or ""
                v=item(company,title,link,location,source,
                       "" if source=="tavily" else _date(entry.get("posted_at") or entry.get("postedAt") or entry.get("published_at") or entry.get("published") or entry.get("date")),
                       entry.get("description") or entry.get("content") or entry.get("snippet") or "")
                if v and v["url"] not in seen:
                    seen.add(v["url"])
                    if source=="remotejobs_org":
                        normalized=entry.get("location_normalization")
                        if isinstance(normalized,dict) and normalized.get("work_arrangement")=="remote":v["remote"]=True
                    jobs.append(v)
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
