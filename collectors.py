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
TITLE_RE=re.compile(r"product|project|marketing|growth|business analyst|gerente de (projetos|produto)|gestor de (projetos|produto)|analista de neg[oó]cios|pmo",re.I)

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

def item(company,title,url,location,source,published="",description=""):
    if not isinstance(url,str) or not url.startswith(("https://","http://")) or not title:return None
    return {"company":str(company or "")[:200],"title":str(title)[:300],"url":url[:2000],
            "location":str(location or "")[:200],"published":str(published or "")[:80],"source":source,"description":str(description or "")[:18000]}

def pull(source,slug,location='brazil'):
    jobs=[]
    if source=="Jobgether":
        params={"keyword":slug,"sort":"date","limit":25}
        if location:params["locations"]=location
        url="https://jobgether.com/api/v1/jobs?"+urllib.parse.urlencode(params)
        payload=fetch_json(url)
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            c=j.get("companyName") or j.get("company") or j.get("employer") or ""
            if isinstance(c,dict):c=c.get("name","")
            value=item(c,j.get("title") or j.get("jobTitle") or j.get("position"),
                j.get("url") or j.get("jobUrl") or j.get("applyUrl") or j.get("hostedUrl"),
                j.get("location") or j.get("country"),source,j.get("publishedAt") or j.get("createdAt"),j.get("description") or j.get("jobDescription") or j.get("content") or "")
            if value:jobs.append(value)
    elif source=="Workable":
        params={"query":slug,"limit":20}
        if location:params["location"]=location
        url="https://jobs.workable.com/api/v1/jobs?"+urllib.parse.urlencode(params)
        payload=fetch_json(url)
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            c=j.get("company") or j.get("companyName") or ""
            if isinstance(c,dict):c=c.get("name","")
            value=item(c,j.get("title") or j.get("jobTitle"),j.get("url") or j.get("jobUrl") or j.get("applicationUrl"),
                j.get("location") or j.get("workplace"),source,j.get("publishedAt"),j.get("descriptionHtml") or j.get("description") or "")
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
        endpoint="https://boards-api.greenhouse.io/v1/boards/"+urllib.parse.quote(slug)+"/jobs"
        try:
            payload=fetch_json(endpoint+"?content=true")
        except ValueError as error:
            if "response above" not in str(error):raise
            # Never fail a whole board because its full descriptions exceed the bound.
            payload=fetch_json(endpoint+"?content=false")
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            location=j.get("location") or {}
            if isinstance(location,dict):location=location.get("name","")
            value=item(slug,j.get("title"),j.get("absolute_url"),location,source,j.get("first_published"),j.get("content") or "")
            if value:jobs.append(value)
    elif source=="Lever":
        payload=fetch_json("https://api.lever.co/v0/postings/"+urllib.parse.quote(slug)+"?mode=json"+("&location=Brazil" if slug.casefold()=="jobgether" else ""))
        if isinstance(payload,dict) and payload.get("ok") is False:
            raise ValueError("Slug Lever rejeitado apesar de HTTP 200")
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            cats=j.get("categories") or {}
            value=item(slug,j.get("text"),j.get("hostedUrl"),cats.get("location") or "",source,j.get("createdAt"),j.get("descriptionPlain") or j.get("description") or "")
            if value:jobs.append(value)
    elif source=="inHire":
        payload=fetch_json("https://api.inhire.app/job-posts/public/pages",{"X-Tenant":slug})
        if isinstance(payload,list):
            if not payload:raise ValueError("Tenant inHire inexistente ou resposta vazia")
            records=payload
            tenant_name=slug
        elif isinstance(payload,dict):
            records=payload.get("jobsPage")
            tenant_name=payload.get("tenantName") or slug
            if isinstance(records,dict):
                records=records.get("jobs") or records.get("items") or records.get("content")
            if records is None:
                records=as_list(payload)
        else:records=[]
        if not isinstance(records,list):raise ValueError("Formato inHire jobsPage inesperado")
        for j in records:
            if not isinstance(j,dict):continue
            title=j.get("displayName") or j.get("title") or j.get("name")
            id_=j.get("jobId") or j.get("id")
            job_slug=re.sub(r"[^a-z0-9]+","-",str(title or "").lower()).strip("-")
            url=j.get("publicUrl") or j.get("jobUrl") or (f"https://{slug}.inhire.app/vagas/{id_}/{job_slug}" if id_ and job_slug else "")
            loc=j.get("location") or ""
            if isinstance(loc,dict):loc=" ".join(str(v) for v in loc.values() if isinstance(v,str))
            workplace=j.get("workplaceType") or ""
            value=item(tenant_name,title,url,(str(loc)+" "+str(workplace)).strip(),source,j.get("publishedAt") or j.get("createdAt"),j.get("description") or j.get("jobDescription") or "")
            if value:
                value["workplaceType"]=workplace
                jobs.append(value)
    if source=="inHire" and not jobs:
        raise ValueError("inHire returned no parsed jobs; API response format requires verification")
    # Keep all parsed jobs. Role relevance belongs to search_filters, not the collector.
    return {"source":source,"term":slug,"status":"ok","received":len(jobs),"target":len(jobs)},jobs

def collect(terms=None,country="BR",only_source="all"):
    country_locations={"BR":"Brazil","AR":"Argentina","CL":"Chile","CO":"Colombia","MX":"Mexico","PE":"Peru","UY":"Uruguay","PY":"Paraguay","BO":"Bolivia","EC":"Ecuador","CR":"Costa Rica","PA":"Panama","GT":"Guatemala","DO":"Dominican Republic","VE":"Venezuela","US":"United States","CA":"Canada","PT":"Portugal","ES":"Spain","GB":"United Kingdom"}
    location=country_locations.get(country,"")
    terms=[str(t).strip()[:100] for t in (terms or TERMS) if str(t).strip()][:12]
    tasks=[("Jobgether",t) for t in terms]+[("Workable",t) for t in terms]+[(source,slug) for source,slugs in BOARDS.items() for slug in slugs]
    if only_source!="all":tasks=[(src,slug) for src,slug in tasks if src.lower()==only_source.lower()]
    found={};details=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(pull,source,slug,location if source in ("Jobgether","Workable") else "brazil"):(source,slug) for source,slug in tasks}
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
