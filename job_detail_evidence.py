"""Bounded verification of missing eligibility fields on trusted job pages."""
import json
import logging
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urlsplit

from collectors import location_text

HOSTS={"jobgether.com","jobsbylevel.com","remotejobs.org","jobs.workable.com","www.linkedin.com"}
SOURCES={"jobgether","leveljobs","remotejobs_org","workable","linkedin_guest"}

class LinkedInDescription(HTMLParser):
    """Extract only visible text of LinkedIn's public guest job description."""
    def __init__(self):
        super().__init__();self.depth=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        classes=dict(attrs).get("class","")
        if self.depth or "show-more-less-html__markup" in classes.split():
            self.depth+=1
    def handle_data(self,data):
        if self.depth and data.strip():self.parts.append(data.strip())
    def handle_endtag(self,tag):
        if self.depth:self.depth-=1

class StructuredJobs(HTMLParser):
    def __init__(self):
        super().__init__();self.collect=False;self.parts=[];self.documents=[]
    def handle_starttag(self,tag,attrs):
        if tag=="script":
            attributes=dict(attrs)
            self.collect=attributes.get("type","").lower().strip()=="application/ld+json"
            self.parts=[]
    def handle_data(self,data):
        if self.collect:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=="script" and self.collect:
            try:self.documents.append(json.loads("".join(self.parts)))
            except (ValueError,TypeError):pass
            self.collect=False;self.parts=[]

def _job_posting(value):
    if isinstance(value,list):
        for child in value:
            match=_job_posting(child)
            if match:return match
    if isinstance(value,dict):
        types=value.get("@type") or []
        if isinstance(types,str):types=[types]
        if "JobPosting" in types:return value
        if "@graph" in value:return _job_posting(value["@graph"])
    return None

def extract(html):
    parser=StructuredJobs();parser.feed(html)
    for document in parser.documents:
        posting=_job_posting(document)
        if not posting:continue
        evidence={}
        location=posting.get("jobLocation") or posting.get("applicantLocationRequirements")
        if isinstance(location,dict):
            location=location.get("address") or location
        elif isinstance(location,list):
            location=[entry.get("address",entry) if isinstance(entry,dict) else entry for entry in location]
        if isinstance(location,dict):
            location={"city":location.get("addressLocality"),"region":location.get("addressRegion"),
                      "countryName":location.get("addressCountry") or location.get("name")}
        elif isinstance(location,list):
            location=[{"city":e.get("addressLocality"),"region":e.get("addressRegion"),
                       "countryName":e.get("addressCountry") or e.get("name")} if isinstance(e,dict) else e for e in location]
        label=location_text(location)
        if label:evidence["location"]=label
        work=str(posting.get("jobLocationType") or "").upper()
        if work=="TELECOMMUTE":evidence["remote"]=True
        published=posting.get("datePosted")
        if isinstance(published,str) and re.match(r"^\d{4}-\d{2}-\d{2}",published):
            evidence["published"]=published[:80]
        description=posting.get("description")
        if isinstance(description,str) and description.strip():evidence["description"]=description[:18000]
        return evidence
    return {}

def recover(job):
    url=str(job.get("url") or "")
    parts=urlsplit(url)
    host=(parts.hostname or "").lower()
    if job.get("source","").lower() not in SOURCES or parts.scheme!="https" or host not in HOSTS:
        return job
    try:
        if job.get("source","").lower()=="linkedin_guest":
            match=re.search(r"/jobs/view/(\d+)",parts.path)
            if not match:return job
            url="https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/"+match.group(1)
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
        with urllib.request.urlopen(req,timeout=3) as response:
            if not (response.headers.get("Content-Type") or "").lower().startswith("text/html"):
                return job
            raw=response.read(450_001)
        if len(raw)>450_000:return job
        html=raw.decode("utf-8","replace")
        evidence=extract(html)
        if job.get("source","").lower()=="linkedin_guest" and not evidence.get("description"):
            parsed=LinkedInDescription();parsed.feed(html)
            if parsed.parts:evidence["description"]=" ".join(parsed.parts)[:18000]
        updated=dict(job)
        for key,value in evidence.items():
            if not updated.get(key):updated[key]=value
        updated["source_detail_status"]="recovered" if evidence else "source_absent"
        return updated
    except Exception as exc:
        logging.info("JH_DETAIL_UNAVAILABLE source=%s reason=%s",job.get("source"),type(exc).__name__)
        return job

def enrich(jobs,limit=4,roles=None):
    """Recover evidence for the most relevant incomplete listings first.

    Never spend a limited detail-fetch slot on an unrelated title while a
    requested role from the same batch still lacks publication/mode evidence.
    """
    from search_filters import role_match, search_terms
    terms=search_terms(roles) if roles else []
    candidates=[i for i,job in enumerate(jobs) if job.get("source","").lower() in SOURCES
                and (not job.get("published") or not job.get("location") or
                     (job.get("source","").lower()=="linkedin_guest" and not job.get("description")) or
                     not job.get("remote") and not any(job.get(k) for k in
                         ("workplaceType","workArrangement","remoteType","workMode","workplace")))]
    candidates.sort(key=lambda i:(not role_match(jobs[i].get("title") or "",terms) if terms else False,
                                  bool(jobs[i].get("published")),
                                  bool(jobs[i].get("description"))))
    # LinkedIn cards omit workplace type and JD; four detail lookups for a
    # typical 80-card batch leave nearly every posting unclassifiable. Bound
    # the additional requests to role-relevant candidates and parallelism.
    linkedin_count=sum(job.get("source","").lower()=="linkedin_guest" for job in jobs)
    if linkedin_count:
        limit=max(limit,min(24,linkedin_count))
    targets=candidates[:limit]
    if not targets:return jobs
    result=list(jobs)
    with ThreadPoolExecutor(max_workers=min(len(targets),8)) as pool:
        for index,updated in zip(targets,pool.map(recover,(jobs[i] for i in targets))):
            result[index]=updated
    return result
