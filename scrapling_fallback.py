"""Bounded JS fallback, local to Render (no paid MCP service).

Only called for selected public job boards when HTTP extraction cannot resolve
a page. Browser is launched on demand; errors remain auditable as pending.
"""
import os
import threading
from urllib.parse import urljoin
from html.parser import HTMLParser
from collectors import TITLE_RE,item

_LOCK=threading.BoundedSemaphore(1)
_JS_SOURCES={"quickin","dynamite","gupy","kaszek","jobbol"}

class Links(HTMLParser):
    def __init__(self):super().__init__();self.href=None;self.parts=[];self.found=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.href=dict(attrs).get("href");self.parts=[]
    def handle_data(self,data):
        if self.href is not None:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            self.found.append((self.href," ".join(self.parts).strip()))
            self.href=None;self.parts=[]

def js_fallback(source,slug):
    if source not in _JS_SOURCES:
        raise ValueError("Scrapling JS fallback unsupported for "+source)
    if os.environ.get("JH_SCRAPLING_JS","0")!="1":
        raise RuntimeError("Scrapling JS desativado até homologação de recursos do Render Free")
    from scrapling.fetchers import DynamicFetcher
    if source=="quickin":
        base="https://jobs.quickin.io/"+slug+"/jobs"
    elif source=="dynamite":
        base="https://dynamitejobs.com/country/remote-jobs-in-brazil"
    elif source=="gupy":
        from urllib.parse import quote
        base="https://portal.gupy.io/job-search/term="+quote(slug)
    elif source=="kaszek":
        base="https://jobs.kaszek.com/jobs"
    else:
        base="https://www.jobbol.com.br/home-office/"+slug.replace("_","-")
    if not _LOCK.acquire(timeout=2):
        raise RuntimeError("Scrapling JS ocupado; tentar depois")
    try:
        page=DynamicFetcher.fetch(base,headless=True,network_idle=False,disable_resources=True,timeout=15000)
        html=str(getattr(page,"html_content","") or "")
        if not html:
            html=str(getattr(page,"body","") or "")
        p=Links();p.feed(html[:2000000])
        out=[];seen=set()
        for href,title in p.found:
            if not TITLE_RE.search(title):continue
            url=urljoin(base,href)
            if not url.startswith("https://") or url in seen:continue
            seen.add(url)
            job=item(slug,title,url,"",source)
            if job:out.append(job)
        return out
    finally:
        _LOCK.release()
