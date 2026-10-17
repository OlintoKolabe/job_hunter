"""Additional documented free sources; honest status, no fabricated success."""
import re, json, urllib.parse, urllib.request, urllib.error
from html.parser import HTMLParser
from datetime import datetime, timezone
from collectors import TITLE_RE, item, fetch_json, as_list

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.current=None;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.current=dict(attrs).get("href");self.parts=[]
    def handle_data(self,data):
        if self.current is not None:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.current:
            self.links.append((self.current," ".join(self.parts).strip()))
            self.current=None;self.parts=[]

def html_links(url,pattern=None):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=10) as resp:
        body=resp.read(2_000_001)
        if len(body)>2_000_000:raise ValueError("response too large")
        final_url=resp.url
    p=Links();p.feed(body.decode("utf-8","replace"))
    results=[]
    for href,title in p.links:
        if not TITLE_RE.search(title):continue
        if pattern and not re.search(pattern,href,re.I):continue
        link=urllib.parse.urljoin(final_url,href)
        val=item("",title,link,"","")
        if val:results.append(val)
    return results

def extra(source,slug):
    jobs=[]
    if source=="smartrecruiters":
        d=fetch_json("https://api.smartrecruiters.com/v1/companies/"+urllib.parse.quote(slug)+"/postings?limit=100")
        for j in d.get("content",[]) if isinstance(d,dict) else []:
            loc=j.get("location") or {}
            title=j.get("name") or j.get("title")
            url=j.get("ref") or j.get("jobAdUrl") or j.get("applyUrl")
            if not url and j.get("id"):url="https://jobs.smartrecruiters.com/"+slug+"/"+str(j["id"])
            v=item(slug,title,url,loc.get("city") or loc.get("country") or "" if isinstance(loc,dict) else loc,source,j.get("releasedDate"))
            if v and TITLE_RE.search(v["title"]):jobs.append(v)
        # SmartRecruiters 200/0 does NOT prove valid slug
        state="pendente" if not d.get("totalFound",0) else "validado"
        return jobs,state,len(d.get("content",[]))
    if source=="teamtailor":
        for page in range(1,4):
            d=fetch_json("https://"+slug+".teamtailor.com/jobs.json?per_page=100&page="+str(page))
            entries=d.get("items",[]) if isinstance(d,dict) else []
            for j in entries:
                v=item(slug,j.get("title"),j.get("url") or j.get("external_url"),j.get("location") or "",source,j.get("date_published"))
                if v and TITLE_RE.search(v["title"]):jobs.append(v)
            if len(entries)<100:break
        return jobs,"validado" if jobs else "sem_vagas",len(jobs)
    if source=="recruitee":
        d=fetch_json("https://"+slug+".recruitee.com/api/offers/")
        records=d.get("offers",[]) if isinstance(d,dict) else []
        for j in records:
            v=item(slug,j.get("title"),j.get("careers_url") or j.get("url"),j.get("location") or "",source,j.get("published_at"))
            if v and TITLE_RE.search(v["title"]):jobs.append(v)
        return jobs,"validado" if records else "sem_vagas",len(records)
    if source=="personio":
        url="https://"+slug+".jobs.personio.de/search.json"
        d=fetch_json(url)
        records=as_list(d)
        for j in records:
            v=item(slug,j.get("name") or j.get("title"),j.get("url") or j.get("link"),j.get("office") or j.get("location"),source)
            if v and TITLE_RE.search(v["title"]):jobs.append(v)
        return jobs,"validado" if records else "sem_vagas",len(records)
    if source=="workable_account":
        d=fetch_json("https://apply.workable.com/api/v1/widget/accounts/"+urllib.parse.quote(slug)+"?details=true")
        jobs_raw=as_list(d)
        for j in jobs_raw:
            v=item(slug,j.get("title"),j.get("url") or j.get("shortlink"),j.get("location"),source,j.get("published_on"))
            if v and TITLE_RE.search(v["title"]):jobs.append(v)
        return jobs,"validado" if jobs_raw else "sem_vagas",len(jobs_raw)
    if source=="dynamite":
        jobs=html_links("https://dynamitejobs.com/country/remote-jobs-in-brazil",r"/remote-job/")
        for j in jobs:j["source"]="Dynamite Jobs"
        return jobs,"validado" if jobs else "pendente",len(jobs)
    if source=="linkedin_guest":
        url="https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"+urllib.parse.urlencode(
            {"keywords":slug,"location":"Brazil","f_WT":"2","f_TPR":"r604800","start":"0"})
        jobs=html_links(url,r"/jobs/view/|/jobs-guest/jobs/api/jobPosting/")
        for j in jobs:j["source"]="LinkedIn guest"
        return jobs,"validado" if jobs else "pendente",len(jobs)
    if source=="gupy":
        url="https://portal.gupy.io/job-search/term="+urllib.parse.quote(slug)
        jobs=html_links(url,r"/job/|/jobs/")
        for j in jobs:j["source"]="Gupy (sem currículo PDF)"
        return jobs,"validado" if jobs else "pendente",len(jobs)
    raise ValueError("adaptador inexistente: "+source)

# Nonintegrated MCPs must be presented as unavailable, never as scanned.
CONNECTORS={
 "Scrapling":"Não configurado no backend Render",
 "Indeed MCP":"Conectado ao ChatGPT, não ao Render",
 "Nimble":"Credenciais e orçamento não configurados",
 "Firecrawl":"Conectado ao ChatGPT, não ao Render",
 "Claude in Chrome":"Sessão humana externa ao Render",
}
