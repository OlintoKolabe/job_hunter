"""Catalog-driven collection: reads seed + optional private inventory in Neon."""
import json, re, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from xml.etree import ElementTree
from collectors import pull, TITLE_RE, item
from source_extensions import extra as expanded_pull

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

def extra_pull(source,slug):
    jobs=[]
    if source=="greenhouse_eu":
        try:
            raw,_=read("https://boards-api.greenhouse.io/v1/boards/"+urllib.parse.quote(slug)+"/jobs?content=false")
            data=json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code !=404:raise
            raw,_=read("https://job-boards.eu.greenhouse.io/"+urllib.parse.quote(slug))
            p=BoardHTML();p.feed(raw.decode("utf-8","replace"))
            for href,title in p.links:
                if TITLE_RE.search(title):
                    url=urllib.parse.urljoin("https://job-boards.eu.greenhouse.io/"+slug,href)
                    value=item(slug,title,url,"",source)
                    if value:jobs.append(value)
            return jobs,"ok"
        for j in data.get("jobs",[]):
            location=j.get("location") or {}
            val=item(slug,j.get("title"),j.get("absolute_url"),location.get("name","") if isinstance(location,dict) else location,source)
            if val and TITLE_RE.search(val["title"]):jobs.append(val)
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
        base="https://jobs.quickin.io/"+urllib.parse.quote(slug)+"/jobs"
        seen=set()
        for page in range(1,7):
            raw,_=read(base+"?page="+str(page))
            p=BoardHTML();p.feed(raw.decode("utf-8","replace"))
            new=0
            for href,title in p.links:
                if ("/jobs/" not in href and "/job/" not in href) or not TITLE_RE.search(title):continue
                url=urllib.parse.urljoin(base,href)
                if url in seen:continue
                seen.add(url);new+=1
                v=item(slug,title,url,"",source)
                if v:jobs.append(v)
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
        if source in ("smartrecruiters","teamtailor","recruitee","personio","workable_account","dynamite","linkedin_guest","gupy"):
            jobs,state,count=expanded_pull(source,slug)
            return {"source":source,"slug":slug,"state":state,"received":count,"target":len(jobs)},jobs
        jobs,_=extra_pull(source,slug)
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
        future=[pool.submit(run_task,source,slug) for source,slug in tasks]
        for f in as_completed(future):
            d,j=f.result()
            out.append(d);jobs.extend(j)
    return out,jobs
