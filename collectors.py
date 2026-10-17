"""Phase 3: bounded, free public API collectors. Do not require paid MCPs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
import re

TERMS=("product manager","product owner","project manager","marketing","growth")
BOARDS={
 "Ashby": ("docplanner","truelogic","latamcent","arq","belvo"),
 "Greenhouse": ("arionkoder","vagasinternas","rdstation","ilia","cresteo"),
 "inHire": ("amcom","zallpy","radix","brq","trinca","vinta"),
 "Lever": ("jobgether",),
}
TITLE_RE=re.compile(r"product|project|marketing|growth|business analyst|gerente de projetos|analista de neg[oó]cios|pmo",re.I)

def fetch_json(url,headers=None):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"Mozilla/5.0 JobHunter/0.3",**(headers or {})})
    with urllib.request.urlopen(req,timeout=9) as response:
        data=response.read(6_000_001)
        if len(data)>6_000_000:
            raise ValueError("response above 2MB")
    return json.loads(data)

def as_list(payload):
    if isinstance(payload,list):return payload
    if isinstance(payload,dict):
        for key in ("jobs","jobPosts","jobPostings","postings","results","items","data","content","records","rows","page"):
            found=payload.get(key)
            if isinstance(found,list):return found
            if isinstance(found,dict):
                result=as_list(found)
                if result:return result
    return []

def item(company,title,url,location,source,published=""):
    if not isinstance(url,str) or not url.startswith(("https://","http://")) or not title:return None
    return {"company":str(company or "")[:200],"title":str(title)[:300],"url":url[:2000],
            "location":str(location or "")[:200],"published":str(published or "")[:80],"source":source}

def pull(source,slug):
    jobs=[]
    if source=="Jobgether":
        url="https://jobgether.com/api/v1/jobs?"+urllib.parse.urlencode({"keyword":slug,"locations":"brazil","sort":"date","limit":25})
        payload=fetch_json(url)
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            c=j.get("companyName") or j.get("company") or j.get("employer") or ""
            if isinstance(c,dict):c=c.get("name","")
            value=item(c,j.get("title") or j.get("jobTitle") or j.get("position"),
                j.get("url") or j.get("jobUrl") or j.get("applyUrl") or j.get("hostedUrl"),
                j.get("location") or j.get("country"),source,j.get("publishedAt") or j.get("createdAt"))
            if value:jobs.append(value)
    elif source=="Workable":
        url="https://jobs.workable.com/api/v1/jobs?"+urllib.parse.urlencode({"query":slug,"location":"Brazil","limit":20})
        payload=fetch_json(url)
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            c=j.get("company") or j.get("companyName") or ""
            if isinstance(c,dict):c=c.get("name","")
            value=item(c,j.get("title") or j.get("jobTitle"),j.get("url") or j.get("jobUrl") or j.get("applicationUrl"),
                j.get("location") or j.get("workplace"),source,j.get("publishedAt"))
            if value:jobs.append(value)
    elif source=="Ashby":
        payload=fetch_json("https://api.ashbyhq.com/posting-api/job-board/"+urllib.parse.quote(slug))
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            loc=j.get("location") or ""
            if j.get("secondaryLocations"):
                loc=str(loc)+" / "+", ".join(str(x.get("location") or x.get("name") or "") if isinstance(x,dict) else str(x) for x in j["secondaryLocations"])
            value=item(slug,j.get("title"),j.get("jobUrl") or j.get("applyUrl"),loc,source,j.get("publishedAt"))
            if value:jobs.append(value)
    elif source=="Greenhouse":
        payload=fetch_json("https://boards-api.greenhouse.io/v1/boards/"+urllib.parse.quote(slug)+"/jobs?content=false")
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            location=j.get("location") or {}
            if isinstance(location,dict):location=location.get("name","")
            value=item(slug,j.get("title"),j.get("absolute_url"),location,source,j.get("first_published"))
            if value:jobs.append(value)
    elif source=="Lever":
        payload=fetch_json("https://api.lever.co/v0/postings/"+urllib.parse.quote(slug)+"?mode=json"+("&location=Brazil" if slug.casefold()=="jobgether" else ""))
        if isinstance(payload,dict) and payload.get("ok") is False:
            raise ValueError("Slug Lever rejeitado apesar de HTTP 200")
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            cats=j.get("categories") or {}
            value=item(slug,j.get("text"),j.get("hostedUrl"),cats.get("location") or "",source,j.get("createdAt"))
            if value:jobs.append(value)
    elif source=="inHire":
        payload=fetch_json("https://api.inhire.app/job-posts/public/pages",{"X-Tenant":slug})
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            value=item(slug,j.get("title") or j.get("name"),
                j.get("url") or j.get("jobUrl") or j.get("publicUrl") or j.get("link"),
                j.get("location") or j.get("workplaceType"),source,j.get("createdAt"))
            if value:jobs.append(value)
    if source=="inHire" and not jobs:
        raise ValueError("inHire returned no parsed jobs; API response format requires verification")
    # Avoid counting unrelated engineering jobs as matches
    target=[j for j in jobs if TITLE_RE.search(j["title"])]
    return {"source":source,"term":slug,"status":"ok","received":len(jobs),"target":len(target)},target

def collect():
    tasks=[("Jobgether",t) for t in TERMS]+[("Workable",t) for t in ("product manager","product owner")]+[(source,slug) for source,slugs in BOARDS.items() for slug in slugs]
    found={};details=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(pull,source,slug):(source,slug) for source,slug in tasks}
        for future in as_completed(futures):
            source,slug=futures[future]
            try:
                detail,items=future.result()
                details.append(detail)
                for job in items:
                    key=job["url"].lower().rstrip("/")
                    if key not in found:found[key]=job
            except Exception as exc:
                details.append({"source":source,"term":slug,"status":"error","received":0,"detail":str(exc)[:150]})
    details.sort(key=lambda d:(d["source"],d["term"]))
    return list(found.values()),details
