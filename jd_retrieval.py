"""Bounded, SSRF-resistant public-page JD extraction; no browser or paid scraper."""
import html
import ipaddress
import json
import re
import socket
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

MAX_HTML=750000
ALLOWED_PORTS=(None,443)
class Extractor(HTMLParser):
    def __init__(self):
        super().__init__();self.text=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","nav","footer"):self.skip+=1
        if tag in ("p","li","h1","h2","h3","div"):self.text.append("\n")
    def handle_endtag(self,tag):
        if tag in ("script","style","nav","footer") and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.text.append(data)
def safe_public_url(url):
    p=urlsplit(url)
    if p.scheme!="https" or not p.hostname or p.username or p.password or p.port not in ALLOWED_PORTS:return False
    hostname=p.hostname.lower()
    if hostname in ("localhost",) or hostname.endswith((".local",".internal")):return False
    try:
        addresses=socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (OSError,ValueError):return False
def extract_public_jd(url):
    if not safe_public_url(url):return None
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    opener=urllib.request.build_opener(NoRedirect)
    req=urllib.request.Request(url,headers={"User-Agent":"JobHunter/1.0 (+public job-description reader)","Accept":"text/html"})
    try:
        with opener.open(req,timeout=6) as response:
            ct=response.headers.get("Content-Type","").lower()
            if "text/html" not in ct:return None
            raw=response.read(MAX_HTML+1)
            if len(raw)>MAX_HTML:return None
        page=raw.decode("utf-8","replace")
        for match in re.findall(r"<script[^>]*type=.[aA]pplication/ld[+]json.[^>]*>(.*?)</script>",page,re.I|re.S):
            try:
                obj=json.loads(match)
                candidates=obj if isinstance(obj,list) else [obj]
                for row in candidates:
                    if isinstance(row,dict) and row.get("@type")=="JobPosting":
                        value=row.get("description")
                        if isinstance(value,str) and len(value)>250:return html.unescape(re.sub("<[^>]+>"," ",value))[:90000]
            except (ValueError,TypeError):pass
        parser=Extractor();parser.feed(page)
        text=re.sub(r"\s+"," "," ".join(parser.text)).strip()
        return text[:90000] if len(text)>=300 else None
    except Exception:return None
