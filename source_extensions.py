"""Additional documented free sources; honest status, no fabricated success."""
import re, json, urllib.parse, urllib.request, urllib.error
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from collectors import TITLE_RE, item, fetch_json, as_list, preserve_eligibility_fields

PUBLIC_JOB_HOSTS={"www.geekhunter.com","www.nerdin.com.br"}

def public_board_html(url):
    """Read only official public job pages; never follow redirects off-host."""
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!="https" or parsed.hostname not in PUBLIC_JOB_HOSTS:
        raise ValueError("Unsupported public job host")
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                                            "Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=8) as response:
        final=urllib.parse.urlsplit(response.geturl())
        if final.scheme!="https" or final.hostname!=parsed.hostname:
            raise ValueError("Unexpected public job redirect")
        raw=response.read(1_500_001)
        if len(raw)>1_500_000:raise ValueError("Public job page too large")
    return raw.decode("utf-8","replace")

class PublicJobMarkup(HTMLParser):
    def __init__(self):
        super().__init__();self.scripts=[];self.links=[];self._script=False;self._text=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="script" and attrs.get("type","").lower()=="application/ld+json":
            self._script=True;self._text=[]
        if tag=="div" and "vaga-card" in attrs.get("class","").split():
            href=attrs.get("data-href","")
            if href.startswith("vaga_emprego/") and href.endswith(".php"):
                self.links.append(href)
    def handle_data(self,data):
        if self._script:self._text.append(data)
    def handle_endtag(self,tag):
        if tag=="script" and self._script:
            try:self.scripts.append(json.loads("".join(self._text)))
            except (ValueError,TypeError):pass
            self._script=False;self._text=[]

def public_jsonld_jobs(markup):
    parsed=PublicJobMarkup();parsed.feed(markup)
    stack=list(parsed.scripts);objects=[]
    while stack:
        entry=stack.pop()
        if isinstance(entry,list):stack.extend(entry)
        elif isinstance(entry,dict):
            objects.append(entry)
            if isinstance(entry.get("@graph"),list):stack.extend(entry["@graph"])
    return parsed,objects

def public_posting(source,url,markup):
    _,objects=public_jsonld_jobs(markup)
    posting=next((o for o in objects if o.get("@type")=="JobPosting"),None)
    if not posting or not isinstance(posting.get("description"),str) or not posting.get("title"):
        raise ValueError("Public JobPosting metadata missing")
    organization=posting.get("hiringOrganization") or {}
    company=organization.get("name","") if isinstance(organization,dict) else ""
    locations=posting.get("jobLocation") or []
    if isinstance(locations,dict):locations=[locations]
    names=[];countries=[]
    for loc in locations if isinstance(locations,list) else []:
        address=loc.get("address",{}) if isinstance(loc,dict) else {}
        if not isinstance(address,dict):continue
        city=address.get("addressLocality") or ""
        state=address.get("addressRegion") or ""
        country=address.get("addressCountry") or ""
        names.append(", ".join(str(v) for v in (city,state,country) if v))
        if country:countries.append(str(country))
    restrictions=posting.get("applicantLocationRequirements") or []
    if isinstance(restrictions,dict):restrictions=[restrictions]
    for place in restrictions if isinstance(restrictions,list) else []:
        if isinstance(place,dict) and place.get("name"):countries.append(str(place["name"]))
    remote=str(posting.get("jobLocationType") or "").upper()=="TELECOMMUTE"
    location=" / ".join(s for s in names if s) or (", ".join(dict.fromkeys(countries)))
    if remote:location=("Remote / "+location).strip(" / ")
    value=item(company,posting["title"],url,location,source,posting.get("datePosted"),posting["description"])
    if not value:raise ValueError("JobPosting has no valid direct URL")
    if remote:value["workplaceType"]="remote"
    if any(x.upper() in ("BR","BRA","BRAZIL","BRASIL") for x in countries):
        value["countryCode"]="BR"
    employment=posting.get("employmentType")
    if isinstance(employment,list):employment=", ".join(str(x) for x in employment)
    if isinstance(employment,str) and employment:value["employmentType"]=employment[:200]
    salary=posting.get("baseSalary") or {}
    if isinstance(salary,dict):
        amount=salary.get("value") or {}
        if isinstance(amount,dict):
            extracted={k:amount[key] for k,key in (("min","minValue"),("max","maxValue"),
                         ("unit","unitText")) if isinstance(amount.get(key),(int,float,str))}
            if isinstance(salary.get("currency"),str):extracted["currency"]=salary["currency"]
            if extracted:value["salary"]=extracted
    identifier=posting.get("identifier") or {}
    if isinstance(identifier,dict) and identifier.get("value"):
        value["source_job_id"]=str(identifier["value"])[:160]
    return value

def public_jobs(source,slug):
    if source=="geekhunter":
        root="https://www.geekhunter.com/pt/confidential/jobs"
        search_term=slug[7:].strip()[:70] if slug.startswith("search:") else ""
        links=[]
        for page in (1,2):
            params={}
            if search_term:params["searchTerm"]=search_term
            if page==2:params["page"]=2
            url=root+("?"+urllib.parse.urlencode(params) if params else "")
            html=public_board_html(url)
            _,objects=public_jsonld_jobs(html)
            listing=next((o for o in objects if o.get("@type")=="ItemList"),None)
            if not listing:
                if re.search(r"\b0 vagas dispon[ií]veis\b|nenhuma vaga",html,re.I):break
                raise ValueError("GeekHunter public ItemList unavailable")
            entries=listing.get("itemListElement") or []
            if not isinstance(entries,list):raise ValueError("GeekHunter listing format changed")
            for entry in entries:
                url=entry.get("url") if isinstance(entry,dict) else ""
                if isinstance(url,str) and url.startswith(root+"/"):
                    links.append(url)
            if len(entries)<10:break
    else:
        query=urllib.parse.urlencode({"busca":slug[:100]})
        html=public_board_html("https://www.nerdin.com.br/vagas.php?"+query)
        parsed,_=public_jsonld_jobs(html)
        links=[urllib.parse.urljoin("https://www.nerdin.com.br/",path) for path in parsed.links]
        if not links and not re.search(r"\b0 vagas dispon[ií]veis\b|nenhuma vaga",html,re.I):
            raise ValueError("Nerdin listing markup missing")
    links=list(dict.fromkeys(links))[:12]
    def fetch(url):
        try:return public_posting(source,url,public_board_html(url)),True
        except (ValueError,TimeoutError,urllib.error.URLError):return None,False
    with ThreadPoolExecutor(max_workers=6) as pool:
        received=list(pool.map(fetch,links))
    jobs=[value for value,ok in received if ok]
    failures=sum(not ok for _,ok in received)
    state="pendente" if failures else ("validado" if jobs else "sem_vagas")
    return jobs,state,len(links)

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
        if not title.strip():continue
        if pattern and not re.search(pattern,href,re.I):continue
        link=urllib.parse.urljoin(final_url,href)
        val=item("",title,link,"","")
        if val:results.append(val)
    return results

class LinkedInCards(HTMLParser):
    """Parse the public LinkedIn job-card fields without inferring eligibility."""
    def __init__(self):
        super().__init__();self.cards=[];self.depth=0;self.card=None;self.field=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=a.get("class","")
        if self.card is None and tag=="li" and ("base-card" in classes or "job-search-card" in classes):
            self.card={"title":"","company":"","location":"","url":"","published":""};self.depth=1;return
        if self.card is None:return
        if tag not in ("img","br","hr","input","meta","link","source","wbr","area"):self.depth+=1
        if tag=="a" and (re.search(r"/jobs/view/|/jobs-guest/jobs/api/jobPosting/",a.get("href",""),re.I)):
            self.card["url"]=a["href"]
        if tag=="h3" or ("base-search-card__title" in classes):self.field="title"
        elif tag=="h4" or ("base-search-card__subtitle" in classes):self.field="company"
        elif "job-search-card__location" in classes:self.field="location"
        elif tag=="time" and a.get("datetime"):self.card["published"]=a["datetime"]
    def handle_data(self,data):
        if self.card is not None and self.field and data.strip():
            self.card[self.field]+=" "+data.strip()
    def handle_endtag(self,tag):
        if self.card is None:return
        if tag in ("h3","h4","span","time"):self.field=None
        if tag not in ("img","br","hr","input","meta","link","source","wbr","area"):self.depth-=1
        if self.depth==0:
            self.cards.append(self.card);self.card=None;self.field=None

def linkedin_cards(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=10) as resp:
        body=resp.read(2_000_001)
        if len(body)>2_000_000:raise ValueError("response too large")
        base=resp.url
    parsed=LinkedInCards();parsed.feed(body.decode("utf-8","replace"))
    jobs=[]
    for card in parsed.cards:
        link=urllib.parse.urljoin(base,card["url"])
        value=item(card["company"].strip(),card["title"].strip(),link,card["location"].strip(),"linkedin_guest",card["published"])
        if value:jobs.append(value)
    return jobs

def extra(source,slug):
    if source in ("geekhunter","nerdin"):
        return public_jobs(source,slug)
    jobs=[]
    if source=="smartrecruiters":
        d=fetch_json("https://api.smartrecruiters.com/v1/companies/"+urllib.parse.quote(slug)+"/postings?limit=100")
        for j in d.get("content",[]) if isinstance(d,dict) else []:
            loc=j.get("location") or {}
            title=j.get("name") or j.get("title")
            url=j.get("ref") or j.get("jobAdUrl") or j.get("applyUrl")
            if not url and j.get("id"):url="https://jobs.smartrecruiters.com/"+slug+"/"+str(j["id"])
            v=item(slug,title,url,loc.get("city") or loc.get("country") or "" if isinstance(loc,dict) else loc,source,j.get("releasedDate"))
            if v:jobs.append(preserve_eligibility_fields(v,j))
        # SmartRecruiters 200/0 does NOT prove valid slug
        state="pendente" if not d.get("totalFound",0) else "validado"
        return jobs,state,len(d.get("content",[]))
    if source=="teamtailor":
        for page in range(1,4):
            d=fetch_json("https://"+slug+".teamtailor.com/jobs.json?per_page=100&page="+str(page))
            entries=d.get("items",[]) if isinstance(d,dict) else []
            for j in entries:
                v=item(slug,j.get("title"),j.get("url") or j.get("external_url"),j.get("location") or "",source,j.get("date_published"))
                if v:jobs.append(preserve_eligibility_fields(v,j))
            if len(entries)<100:break
        return jobs,"validado" if jobs else "sem_vagas",len(jobs)
    if source=="recruitee":
        d=fetch_json("https://"+slug+".recruitee.com/api/offers/")
        records=d.get("offers",[]) if isinstance(d,dict) else []
        for j in records:
            v=item(slug,j.get("title"),j.get("careers_url") or j.get("url"),j.get("location") or "",source,j.get("published_at"))
            if v:jobs.append(preserve_eligibility_fields(v,j))
        return jobs,"validado" if records else "sem_vagas",len(records)
    if source=="personio":
        url="https://"+slug+".jobs.personio.de/search.json"
        d=fetch_json(url)
        records=as_list(d)
        for j in records:
            v=item(slug,j.get("name") or j.get("title"),j.get("url") or j.get("link"),j.get("office") or j.get("location"),source)
            if v:jobs.append(preserve_eligibility_fields(v,j))
        return jobs,"validado" if records else "sem_vagas",len(records)
    if source=="workable_account":
        d=fetch_json("https://apply.workable.com/api/v1/widget/accounts/"+urllib.parse.quote(slug)+"?details=true")
        jobs_raw=as_list(d)
        for j in jobs_raw:
            v=item(slug,j.get("title"),j.get("url") or j.get("shortlink"),j.get("location"),source,j.get("published_on"))
            if v:jobs.append(preserve_eligibility_fields(v,j))
        return jobs,"validado" if jobs_raw else "sem_vagas",len(jobs_raw)
    if source=="kaszek":
        jobs=html_links("https://jobs.kaszek.com/jobs",r"/jobs/|/companies/|/job/")
        for j in jobs:j["source"]="Kaszek"
        return jobs,"validado" if jobs else "pendente",len(jobs)
    if source=="jobbol":
        city=slug.replace("_","-")
        jobs=html_links("https://www.jobbol.com.br/home-office/"+city,r"/vaga/|/vagas/|/emprego/")
        for j in jobs:j["source"]="Jobbol"
        return jobs,"validado" if jobs else "pendente",len(jobs)
    if source=="dynamite":
        jobs=html_links("https://dynamitejobs.com/country/remote-jobs-in-brazil",r"/remote-job/")
        for j in jobs:j["source"]="Dynamite Jobs"
        return jobs,"validado" if jobs else "pendente",len(jobs)
    if source=="linkedin_guest":
        url="https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"+urllib.parse.urlencode(
            {"keywords":slug,"location":"Brazil","f_WT":"2","f_TPR":"r604800","start":"0"})
        jobs=linkedin_cards(url)
        return jobs,"validado" if jobs else "pendente",len(jobs)
    if source=="gupy":
        jobs=[];received=0
        for offset in (0,100,200):
            url="https://employability-portal.gupy.io/api/v1/jobs?"+urllib.parse.urlencode({"jobName":slug,"limit":100,"offset":offset})
            payload=fetch_json(url)
            records=(payload.get("data") or payload.get("jobs") or payload.get("results") or []) if isinstance(payload,dict) else payload
            if isinstance(records,dict):records=records.get("jobs") or records.get("results") or records.get("data") or []
            if not isinstance(records,list):raise ValueError("Gupy formato inesperado")
            received+=len(records)
            for j in records:
                if not isinstance(j,dict):continue
                title=j.get("name") or j.get("title")
                company=j.get("careerPageName") or j.get("companyName") or j.get("company") or ""
                link=j.get("jobUrl") or j.get("applyUrl") or j.get("url")
                if not link:continue
                mode=j.get("workplaceType") or ""
                loc=" ".join(str(x) for x in (j.get("city"),j.get("state"),"Brasil",mode) if x)
                val=item(company,title,link,loc,"Gupy",j.get("publishedAt") or j.get("publishedDate"))
                if val:
                    val["workplaceType"]=mode
                    jobs.append(preserve_eligibility_fields(val,j))
            if len(records)<100:break
        return jobs,"validado" if received else "pendente",received
    raise ValueError("adaptador inexistente: "+source)

# Nonintegrated MCPs must be presented as unavailable, never as scanned.
CONNECTORS={
 "Scrapling":"Não configurado no backend Render",
 "Indeed MCP":"Conectado ao ChatGPT, não ao Render",
 "Nimble":"Credenciais e orçamento não configurados",
 "Firecrawl":"Conectado ao ChatGPT, não ao Render",
 "Claude in Chrome":"Sessão humana externa ao Render",
}
