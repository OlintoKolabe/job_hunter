"""On-demand Brazil Indeed listing adapter; requires explicit HasData key."""
import json, os, urllib.parse, urllib.request
from collectors import item

API="https://api.hasdata.com/scrape/indeed/listing"
def enabled():
    return bool(os.environ.get("HASDATA_API_KEY","").strip())

def search(keyword):
    key=os.environ.get("HASDATA_API_KEY","").strip()
    if not key:raise RuntimeError("Indeed indisponível: configure HASDATA_API_KEY")
    params=urllib.parse.urlencode({"keyword":keyword,"location":"Brasil","domain":"br.indeed.com","sort":"date","start":0})
    req=urllib.request.Request(API+"?"+params,headers={"x-api-key":key,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=90) as res:
        payload=json.loads(res.read(2_000_000))
    rows=payload.get("jobs") if isinstance(payload,dict) else None
    if not isinstance(rows,list):raise ValueError("Resposta Indeed sem lista de vagas")
    jobs=[]
    for row in rows:
        if not isinstance(row,dict):continue
        v=item(row.get("company"),row.get("title"),row.get("url"),row.get("location"),"indeed",row.get("isoDate") or "",row.get("description") or "")
        if v:jobs.append(v)
    return jobs
