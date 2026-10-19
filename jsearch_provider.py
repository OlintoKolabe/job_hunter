"""Bounded JSearch aggregator provider. This is NOT an official Indeed API."""
import os
import urllib.parse
from collectors import fetch_json,item

HOST="jsearch.p.rapidapi.com"
MAX_QUERY_CHARS=100

def search(roles,country="BR",limit=20):
    key=os.environ.get("JH_JSEARCH_RAPIDAPI_KEY","").strip()
    if not key:
        return [],{"source":"jsearch","slug":"jsearch","state":"not_configured","received":0,"error":"Chave JSearch não configurada"}
    if country not in ("BR","LATAM","GLOBAL"):
        return [],{"source":"jsearch","slug":"jsearch","state":"unsupported_country","received":0,"error":"Fonte JSearch habilitada inicialmente para Brasil"}
    # Fixed single query per explicit click to conserve the free monthly allowance.
    terms=[x.strip() for x in (roles or "").split(",") if x.strip()][:3]
    query=" OR ".join(terms)[:MAX_QUERY_CHARS] or "Product Manager"
    params={"query":query+" in Brazil","page":"1","num_pages":"1","country":"br","date_posted":"month"}
    url="https://"+HOST+"/search?"+urllib.parse.urlencode(params)
    try:
        payload=fetch_json(url,headers={"X-RapidAPI-Key":key,"X-RapidAPI-Host":HOST})
        jobs=[]
        for raw in (payload.get("data") or [])[:max(1,min(limit,30))]:
            if not isinstance(raw,dict):continue
            link=raw.get("job_apply_link") or raw.get("job_google_link") or ""
            if not isinstance(link,str) or not link.startswith("https://"):continue
            location=", ".join(x for x in (raw.get("job_city"),raw.get("job_state"),raw.get("job_country")) if isinstance(x,str) and x)
            if raw.get("job_is_remote"):location=("Remote, "+location).strip(", ")
            position=item(raw.get("employer_name"),raw.get("job_title"),link,location,"jsearch",raw.get("job_posted_at_datetime_utc") or "",raw.get("job_description") or "")
            if position:jobs.append(position)
        return jobs,{"source":"jsearch","slug":"jsearch","state":"validado","received":len(jobs),"target":len(jobs)}
    except Exception as exc:
        return [],{"source":"jsearch","slug":"jsearch","state":"error","received":0,"error":type(exc).__name__}
