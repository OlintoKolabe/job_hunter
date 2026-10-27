"""Phase 3: bounded, free public API collectors. Do not require paid MCPs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
import re
from urllib.parse import urlsplit,quote

def inhire_detail(job):
    """Existing public per-job endpoint shared by filtering, ranking and CV."""
    url=urlsplit(str(job.get("url") or ""))
    if url.scheme!="https" or not re.fullmatch(r"[a-z0-9-]+\.inhire\.app",url.hostname or ""):
        return None
    match=re.match(r"/vagas/([a-zA-Z0-9_-]+)(?:/|$)",url.path)
    if not match:return None
    tenant=url.hostname.split(".")[0]
    return ("https://api.inhire.app/job-posts/public/pages/"+quote(match.group(1)),{"X-Tenant":tenant})

TERMS=("product manager","product owner","project manager","marketing","growth")
BOARDS={
 "Ashby": ("docplanner","truelogic","latamcent","arq","belvo"),
 "Greenhouse": ("arionkoder","vagasinternas","rdstation","ilia","cresteo"),
 "inHire": ("amcom","zallpy","radix","brq","trinca","vinta"),
 "Lever": ("jobgether",),
}
# This is only a cheap prefilter for public HTML/JS fallbacks. Final role,
# seniority, geography and remote eligibility remain in search_filters.
TITLE_RE=re.compile(
    r"product|project|marketing|growth|business analyst|gerente de (projetos|produto)"
    r"|gestor de (projetos|produto)|analista de neg[oó]cios|pmo"
    r"|software|developers?|desenvolvedores?|desenvolvedoras?|desenvolvimento"
    r"|est[aá]gios?|estagi[aá]ri[oa]s?|\binterns?\b|analista de dados|cientista de dados"
    r"|data (?:analyst|scientist|engineer)|machine learning|artificial intelligence"
    r"|ai engineer|analytics|business intelligence|engenheir[oa] de dados",
    re.I,
)

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
    if isinstance(published,(int,float)) or (isinstance(published,str) and published.isdigit()):
        try:
            seconds=float(published)
            if seconds>100_000_000_000:seconds/=1000
            published=datetime.fromtimestamp(seconds,timezone.utc).isoformat()
        except (ValueError,OverflowError,OSError):published=""
    return {"company":str(company or "")[:200],"title":str(title)[:300],"url":url[:2000],
            "location":str(location or "")[:200],"published":str(published or "")[:80],"source":source,"description":str(description or "")[:18000]}

def preserve_eligibility_fields(destination,source):
    """Keep only published collector metadata, without inferring missing eligibility."""
    if destination is None or not isinstance(source,dict):return destination
    for field in ("workplaceType","workArrangement","remoteType","workMode","workplace",
                  "country","countryCode","countryName","city","state","region"):
        if isinstance(source.get(field),str) and source[field].strip():
            destination[field]=source[field][:200]
    for field in ("eligibleLocations","remoteRegions"):
        if isinstance(source.get(field),list):
            destination[field]=[value[:200] for value in source[field] if isinstance(value,str)][:30]
    remote=source.get("isRemote",source.get("remote"))
    if isinstance(remote,bool):destination["remote"]=remote
    # Preserve published metadata for later ranking and display. Do not
    # synthesize salary, seniority or a publication date from other fields.
    for field in ("seniority","seniorityLevel","department","employmentType",
                  "jobType","contractType","salaryCurrency","salaryRange"):
        value=source.get(field)
        if isinstance(value,str) and value.strip():destination[field]=value[:300]
    for field in ("salary","compensation"):
        value=source.get(field)
        if isinstance(value,dict):
            safe={k:v for k,v in value.items() if isinstance(k,str) and
                  isinstance(v,(str,int,float,bool)) and len(k)<60}
            if safe:destination[field]=safe
        elif isinstance(value,(str,int,float)) and str(value).strip():
            destination[field]=str(value)[:300]
    identifier=source.get("jobId") or source.get("id") or source.get("requisitionId")
    if isinstance(identifier,(str,int)) and str(identifier).strip():
        destination["source_job_id"]=str(identifier)[:160]
    return destination

def source_field_coverage(jobs):
    """Count observed source fields, not guessed availability at the origin."""
    by_source={}
    for job in jobs:
        name=str(job.get("source") or "unknown").lower()
        stats=by_source.setdefault(name,{"total":0,"dated":0,"described":0,
            "located":0,"mode_explicit":0,"salary_informed":0,
            "details_recovered":0,"details_pending":0,"details_failed":0,"details_absent":0})
        stats["total"]+=1
        if job.get("published"):stats["dated"]+=1
        if len(str(job.get("description") or "").strip())>=300:stats["described"]+=1
        if any(job.get(field) for field in ("location","country","countryCode","eligibleLocations")):
            stats["located"]+=1
        if job.get("remote") is True or any(job.get(field) for field in
             ("workplaceType","workArrangement","remoteType","workMode","workplace")):
            stats["mode_explicit"]+=1
        if any(job.get(field) for field in ("salary","salaryRange","compensation")):
            stats["salary_informed"]+=1
        state=job.get("source_detail_status")
        if state=="recovered":stats["details_recovered"]+=1
        elif state=="pending":stats["details_pending"]+=1
        elif state=="error":stats["details_failed"]+=1
        elif state=="source_absent":stats["details_absent"]+=1
    return by_source

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
            if value:jobs.append(preserve_eligibility_fields(value,j))
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
            if value:jobs.append(preserve_eligibility_fields(value,j))
    elif source=="Ashby":
        payload=fetch_json("https://api.ashbyhq.com/posting-api/job-board/"+urllib.parse.quote(slug))
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            loc=j.get("location") or ""
            if j.get("secondaryLocations"):
                loc=str(loc)+" / "+", ".join(str(x.get("location") or x.get("name") or "") if isinstance(x,dict) else str(x) for x in j["secondaryLocations"])
            description=j.get("descriptionPlain") or j.get("descriptionHtml") or j.get("description") or ""
            if not isinstance(description,str):description=""
            value=item(slug,j.get("title"),j.get("jobUrl") or j.get("applyUrl"),loc,source,j.get("publishedAt"),description)
            if value:
                # Keep official Ashby eligibility signals for the shared filter engine.
                for field in ("workplaceType","workArrangement","remoteType","country","countryCode","region"):
                    if isinstance(j.get(field),str):value[field]=j[field]
                if isinstance(j.get("isRemote"),bool):value["remote"]=j["isRemote"]
                jobs.append(preserve_eligibility_fields(value,j))
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
            if value:jobs.append(preserve_eligibility_fields(value,j))
    elif source=="Lever":
        payload=fetch_json("https://api.lever.co/v0/postings/"+urllib.parse.quote(slug)+"?mode=json"+("&location=Brazil" if slug.casefold()=="jobgether" else ""))
        if isinstance(payload,dict) and payload.get("ok") is False:
            raise ValueError("Slug Lever rejeitado apesar de HTTP 200")
        for j in as_list(payload):
            if not isinstance(j,dict):continue
            cats=j.get("categories") or {}
            value=item(slug,j.get("text"),j.get("hostedUrl"),cats.get("location") or "",source,j.get("createdAt"),j.get("descriptionPlain") or j.get("description") or "")
            if value:jobs.append(preserve_eligibility_fields(value,j))
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
            value=item(tenant_name,title,url,(str(loc)+" "+str(workplace)).strip(),source,j.get("lastPublishedAt") or j.get("publishedAt"),j.get("description") or j.get("jobDescription") or "")
            if value:
                value["workplaceType"]=workplace
                jobs.append(preserve_eligibility_fields(value,j))
    if source=="inHire" and not jobs and not (isinstance(payload,dict)
            and isinstance(payload.get("jobsPage"),list) and len(payload["jobsPage"])==0):
        raise ValueError("inHire returned no parsed jobs; API response format requires verification")
    # Keep all parsed jobs. Role relevance belongs to search_filters, not the collector.
    return {"source":source,"term":slug,"status":"ok","received":len(jobs),"target":len(jobs)},jobs

def collect(terms=None,country="BR",only_source="all",skip_boards=()):
    country_locations={"BR":"Brazil","AR":"Argentina","CL":"Chile","CO":"Colombia","MX":"Mexico","PE":"Peru","UY":"Uruguay","PY":"Paraguay","BO":"Bolivia","EC":"Ecuador","CR":"Costa Rica","PA":"Panama","GT":"Guatemala","DO":"Dominican Republic","VE":"Venezuela","US":"United States","CA":"Canada","PT":"Portugal","ES":"Spain","GB":"United Kingdom"}
    location=country_locations.get(country,"")
    terms=[str(t).strip()[:100] for t in (terms or TERMS) if str(t).strip()][:12]
    tasks=[("Jobgether",t) for t in terms]+[("Workable",t) for t in terms]+[(source,slug) for source,slugs in BOARDS.items() for slug in slugs]
    if skip_boards:
        skipped={(str(src).lower(),str(slug).lower()) for src,slug in skip_boards}
        tasks=[(src,slug) for src,slug in tasks if (src.lower(),slug.lower()) not in skipped]
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
