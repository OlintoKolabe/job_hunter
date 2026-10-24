"""Catalog-driven collection: reads seed + optional private inventory in Neon."""
import json, re, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from xml.etree import ElementTree
from collectors import pull, TITLE_RE, item, preserve_eligibility_fields
from source_extensions import extra as expanded_pull
from scrapling_fallback import js_fallback

SEED=json.loads((Path(__file__).parent/"catalog_seed.json").read_text())
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; JobHunter/0.3)","Accept":"application/json,text/html,application/xml"}
def read(url,headers=None,size=750000):
    req=urllib.request.Request(url,headers={**HEADERS,**(headers or {})})
    with urllib.request.urlopen(req,timeout=8) as res:
        body=res.read(size+1)
        if len(body)>size:raise ValueError("large response")
        return body,res.status
def source_tasks():
    tasks=[(s,slug) for s,slugs in SEED.items() for slug in slugs]
    return [(source,slug) for source,slug in tasks if slug.casefold() not in ("kraken","kraken.com","payward")]

class BoardHTML(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.href=None;self.buffer=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href");self.buffer=[]
    def handle_data(self,data):
        if self.href is not None:self.buffer.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            self.links.append((self.href," ".join(self.buffer).strip()))
            self.href=None;self.buffer=[]

class QuickinJobHTML(HTMLParser):
    """Extract displayed vacancy text, excluding scripts and styles."""
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript"):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript") and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip and data.strip():self.parts.append(data.strip())

def quickin_detail(url):
    """Populate only evidence visible on the published posting."""
    raw,_=read(url,size=500000)
    page=QuickinJobHTML();page.feed(raw.decode("utf-8","replace"))
    body=" ".join(page.parts)[:18000]
    # Quickin job headings show city and modality together (e.g. SP Remote).
    prefix=body[:420]
    city=r"(?:S[aã]o Paulo|SP|Rio de Janeiro|RJ|Belo Horizonte|Bras[ií]lia|Curitiba|Goi[aâ]nia|Brasil|Brazil)"
    mode=r"(?:Remote|Remoto|Remota|Hybrid|H[ií]brido|On-site|Onsite|Presencial)"
    match=re.search(r"(?<!\w)"+city+r"(?:\s*[,/\-]\s*|\s+)"+mode+r"(?!\w)",prefix,re.I)
    location=match.group(0) if match else ""
    if location and re.match(r"^(?:SP|RJ)\b",location,re.I):
        location=("São Paulo" if location[:2].upper()=="SP" else "Rio de Janeiro")+location[2:]
    return location,body

def extra_pull(source,slug):
    jobs=[]
    if source=="greenhouse_eu":
        try:
            endpoint="https://boards-api.greenhouse.io/v1/boards/"+urllib.parse.quote(slug)+"/jobs"
            try:
                raw,_=read(endpoint+"?content=true",size=6000000)
            except ValueError as error:
                if "large response" not in str(error):raise
                raw,_=read(endpoint+"?content=false")
            data=json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code !=404:raise
            raw,_=read("https://job-boards.eu.greenhouse.io/"+urllib.parse.quote(slug))
            p=BoardHTML();p.feed(raw.decode("utf-8","replace"))
            for href,title in p.links:
                if title.strip():
                    url=urllib.parse.urljoin("https://job-boards.eu.greenhouse.io/"+slug,href)
                    value=item(slug,title,url,"",source)
                    if value:jobs.append(value)
            return jobs,"ok"
        for j in data.get("jobs",[]):
            location=j.get("location") or {}
            val=item(slug,j.get("title"),j.get("absolute_url"),location.get("name","") if isinstance(location,dict) else location,source,j.get("first_published"),j.get("content") or "")
            if val:jobs.append(val)
        return jobs,"ok"
    if source=="bamboohr":
        raw,_=read("https://"+slug+".bamboohr.com/careers/list")
        data=json.loads(raw)
        records=data.get("result") or data.get("jobs") or []
        if isinstance(records,dict):records=records.get("jobs",[])
        for j in records:
            if not isinstance(j,dict):continue
            title=j.get("jobOpeningName") or j.get("title")
            id_=j.get("id") or j.get("jobId")
            link=j.get("url") or (f"https://{slug}.bamboohr.com/careers/{id_}" if id_ else "")
            val=item(slug,title,link,j.get("location"),source,j.get("datePosted"))
            if val and TITLE_RE.search(val["title"]):jobs.append(val)
        return jobs,"ok"
    if source=="quickin":
        # Official public career API; it needs no access token.
        # Keep the existing HTML parser as a fallback for unsupported account IDs.
        try:
            endpoint="https://api.quickin.io/public/"+urllib.parse.quote(slug,safe="")+"/jobs?sort=-created_at"
            data=json.loads(read(endpoint,size=3500000)[0])
            records=data if isinstance(data,list) else (
                data.get("jobs") or data.get("data") or data.get("results") or []
                if isinstance(data,dict) else [])
            if isinstance(records,dict):
                records=records.get("jobs") or records.get("data") or []
            if not isinstance(records,list):
                raise ValueError("Quickin invalid jobs response")
            for row in records:
                if not isinstance(row,dict) or row.get("publicate","published")!="published":continue
                title=row.get("title")
                if not title:continue
                company=row.get("company_id")
                name=company.get("name") if isinstance(company,dict) else slug
                job_id=row.get("_id")
                url=row.get("career_url") or (
                    "https://jobs.quickin.io/"+urllib.parse.quote(slug,safe="")+"/apply?job_id="+urllib.parse.quote(str(job_id),safe="")
                    if job_id else "")
                def text_field(value):
                    return value if isinstance(value,str) else ""
                location=", ".join(text_field(row.get(x)) for x in ("city","region","country") if text_field(row.get(x)))
                mode=next((text_field(row.get(x)) for x in ("workplaceType","workplace_type","workMode","modality","job_type") if text_field(row.get(x))),"")
                description=" ".join(text_field(row.get(x)) for x in ("description","requirements"))
                value=item(name,title,url,location,source,row.get("published_at"),description)
                if value:
                    if mode:value["workplaceType"]=mode
                    if isinstance(row.get("remote"),bool):value["remote"]=row["remote"]
                    if isinstance(row.get("isRemote"),bool):value["remote"]=row["isRemote"]
                    jobs.append(preserve_eligibility_fields(value,row))
            return jobs,"ok"
        except (ValueError,TypeError,KeyError,urllib.error.URLError,TimeoutError,json.JSONDecodeError):
            jobs=[]
        base="https://jobs.quickin.io/"+urllib.parse.quote(slug)+"/jobs"
        seen=set()
        for page in range(1,7):
            raw,_=read(base+"?page="+str(page))
            p=BoardHTML();p.feed(raw.decode("utf-8","replace"))
            new=0
            for href,title in p.links:
                if ("/jobs/" not in href and "/job/" not in href)  :continue
                url=urllib.parse.urljoin(base,href)
                if url in seen:continue
                seen.add(url);new+=1
                v=item(slug,title,url,"",source)
                if v:
                    # The board link alone has no location or work mode.
                    # Only inspect roles relevant to search, never invent eligibility.
                    if TITLE_RE.search(v["title"]):
                        try:
                            location,description=quickin_detail(url)
                            v["location"]=location
                            v["description"]=description
                        except (urllib.error.URLError,ValueError,TimeoutError):
                            pass
                    jobs.append(v)
            if new==0:break
        return jobs,"ok"
    if source=="solides":
        url="https://"+slug+".vagas.solides.com.br/"
    elif source=="zoho":
        url="https://"+slug+".zohorecruit.com/jobs/Careers"
    elif source=="trakstar":
        url="https://"+slug+".hire.trakstar.com/jobs"
    elif source=="compleo":
        url="https://"+slug+".compleo.com.br/"
    else:
        raise ValueError("unsupported ATS "+source)
    raw,_=read(url)
    p=BoardHTML();p.feed(raw.decode("utf-8","replace"))
    for href,title in p.links:
        if TITLE_RE.search(title):
            v=item(slug,title,urllib.parse.urljoin(url,href),"",source)
            if v:jobs.append(v)
    return jobs,"ok"

def run_task(source,slug):
    try:
        if source in ("ashby","greenhouse","inhire","lever"):
            detail,jobs=pull(source.capitalize() if source!="inhire" else "inHire",slug)
            return {"source":source,"slug":slug,"state":"validado" if detail["received"] else "sem_vagas",
                "received":detail["received"],"target":len(jobs)},jobs
        if source in ("smartrecruiters","teamtailor","recruitee","personio","workable_account","dynamite","linkedin_guest","gupy","kaszek","jobbol"):
            jobs,state,count=expanded_pull(source,slug)
            if not jobs and source in ("dynamite","gupy","kaszek","jobbol"):
                try:
                    fallback=js_fallback(source,slug)
                    if fallback:jobs=fallback;state="validado";count=len(jobs)
                except RuntimeError:pass
            return {"source":source,"slug":slug,"state":state,"received":count,"target":len(jobs)},jobs
        jobs,_=extra_pull(source,slug)
        if not jobs and source=="quickin":
            jobs=js_fallback(source,slug)
        uncertain=source in ("quickin","zoho","solides","trakstar","compleo")
        state=("validado" if jobs else ("pendente" if uncertain else "sem_vagas"))
        return {"source":source,"slug":slug,"state":state,"received":len(jobs),"target":len(jobs)},jobs
    except urllib.error.HTTPError as e:
        return {"source":source,"slug":slug,"state":"pendente","received":0,"error":str(e.code)},[]
    except Exception as e:
        return {"source":source,"slug":slug,"state":"pendente","received":0,"error":str(e)[:140]},[]

def scan(tasks,workers=6):
    out=[];jobs=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future={pool.submit(run_task,source,slug):(source,slug) for source,slug in tasks}
        for f in as_completed(future):
            source,slug=future[f]
            d,j=f.result()
            out.append(d)
            jobs.extend({**job,"board_slug":slug,"board_source":source} for job in j)
    return out,jobs
