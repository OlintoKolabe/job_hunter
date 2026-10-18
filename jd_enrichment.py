"""Bounded post-filter JD hydration (Block 4 only).
Never fetch full job details for every listing on a board.
Read cached descriptions first; fetch Greenhouse job detail endpoints for
eligible listings only, then update the score. Missing JDs remain unscored.
"""
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit,quote
from collectors import fetch_json
from jd_signals import signals
from block4_score import score_job,merge_semantic_requirements
from jd_retrieval import extract_public_jd
from score_repository import get_cached,save,reserve,settle
from ai_interpreter import interpret
import os
import psycopg
from search_filters import detect_work_mode

TTL_DAYS=7
PER_BATCH_LIMIT=10
MAX_JD_CHARS=90000

def greenhouse_detail_url(job):
    source=str(job.get("source") or "").lower()
    if source not in ("greenhouse","greenhouse_eu"):return None
    url=str(job.get("url") or "")
    match=re.search(r"/jobs/(\d+)",url) or re.search(r"[?&]gh_jid=(\d+)",url)
    board=str(job.get("company") or "").strip()
    if not match or not re.fullmatch(r"[a-zA-Z0-9_-]{2,100}",board):return None
    return "https://boards-api.greenhouse.io/v1/boards/"+board+"/jobs/"+match.group(1)

def inhire_detail(job):
    url=urlsplit(str(job.get("url") or ""))
    if url.scheme!="https" or not re.fullmatch(r"[a-z0-9-]+\.inhire\.app",url.hostname or ""):
        return None
    match=re.match(r"/vagas/([a-zA-Z0-9_-]+)(?:/|$)",url.path)
    if not match:return None
    tenant=url.hostname.split(".")[0]
    return ("https://api.inhire.app/job-posts/public/pages/"+quote(match.group(1)),{"X-Tenant":tenant})

def remote_detail(job):
    gh=greenhouse_detail_url(job)
    if gh:return gh,None
    return inhire_detail(job)

def hydrate_jobs(cursor,jobs,roles,url_key,limit=PER_BATCH_LIMIT):
    """Return scored public dictionaries and coverage counts. Cursor is request-scoped.
    Only up to limit fresh remote requests, cached hits are unrestricted.
    """
    if not jobs:return [],{"cached":0,"fetched":0,"missing":0,"not_attempted":0}
    keys=[url_key(j.get("url","")) for j in jobs]
    cursor.execute("SELECT normalized_url,description,fetched_at FROM jh_jd_cache WHERE normalized_url=ANY(%s)",(keys,))
    cached={row[0]:(row[1],row[2]) for row in cursor.fetchall()}
    now=datetime.now(timezone.utc)
    updates={}
    pending=[]
    for j,key in zip(jobs,keys):
        existing=str(j.get("description") or "")
        cached_item=cached.get(key)
        if cached_item and cached_item[1]>=now-timedelta(days=TTL_DAYS):
            updates[key]=(cached_item[0],"cache")
        elif existing and len(existing)>=300:
            updates[key]=(existing,"listing")
        else:
            pending.append((key,j))
    def fetch(pair):
        key,job=pair
        try:
            detail=remote_detail(job)
            if not detail:return key,extract_public_jd(str(job.get('url') or ''))
            endpoint,headers=detail
            result=fetch_json(endpoint,headers) if headers else fetch_json(endpoint)
            value=(result.get("jobPage") or result.get("page") or result) if isinstance(result,dict) else {}
            if not isinstance(value,dict):return key,extract_public_jd(str(job.get("url") or ""))
            content=value.get("content") or value.get("description") or value.get("jobDescription") or ""
            if not content and isinstance(value.get("job"),dict):content=value["job"].get("description") or ""
            if not isinstance(content,str) or not content.strip():return key,extract_public_jd(str(job.get('url') or ''))
            return key,content[:MAX_JD_CHARS]
        except Exception:return key,extract_public_jd(str(job.get('url') or ''))
    fetched=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch,p) for p in pending[:limit]]):
            key,content=future.result()
            if content:
                updates[key]=(content,"fetched")
                cursor.execute("""INSERT INTO jh_jd_cache(normalized_url,description,content_hash,fetched_at,source)
                    VALUES(%s,%s,%s,NOW(),%s)
                    ON CONFLICT(normalized_url) DO UPDATE SET
                    description=EXCLUDED.description,content_hash=EXCLUDED.content_hash,
                    fetched_at=NOW(),source=EXCLUDED.source""",
                    (key,content,hashlib.sha256(content.encode()).hexdigest(),str(next((job.get("source") for k,job in pending if k==key),"public_html"))[:64]))
                fetched+=1
    output=[]
    count={"cached":0,"fetched":fetched,"missing":0,"not_attempted":max(0,len(pending)-limit)}
    for j,key in zip(jobs,keys):
        description,origin=updates.get(key,(j.get("description") or "","listing"))
        if origin=="cache":count["cached"]+=1
        if not description:count["missing"]+=1
        complete={**j,"description":description}
        jd_hash=hashlib.sha256(description.encode()).hexdigest() if description else ''
        evaluation=None
        # Requires approved migration before deployment.
        if description:
            evaluation=get_cached(cursor,key,jd_hash,roles)
        if evaluation is None:
            evaluation=score_job(complete,roles)
            model='deterministic'
            # AI must never run without explicit activation, cached miss and a reserved budget.
            if description and os.getenv('JH_AI_ENABLED')=='1' and os.getenv('OPENAI_API_KEY'):
                with psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=7) as budget_conn:
                    with budget_conn.cursor() as budget_cur:
                        usage_id=reserve(budget_cur,key)
                if usage_id is not None:
                    extracted=None; actual=0.002
                    try:
                        extracted=interpret(description)
                        if extracted:
                            usage=extracted.get('usage',{})
                            actual=min(0.002,(usage.get('prompt_tokens',0)*0.20+usage.get('completion_tokens',0)*1.20)/1000000)
                    except Exception:
                        pass
                    finally:
                        with psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=7) as budget_conn:
                            with budget_conn.cursor() as budget_cur:
                                settle(budget_cur,usage_id,actual,extracted is not None)
                    if extracted:
                        evaluation=merge_semantic_requirements(evaluation,extracted['requirements'])
                        evaluation['ai_interpreted']=True
                        model='hybrid'
            if description:save(cursor,key,jd_hash,roles,evaluation,model)
        output.append({**j,"ranking":evaluation,"jd_evidence":signals(complete,roles),
                       "jd_status":origin if description else ("pendente" if (key,j) in pending[limit:] else "indisponivel")})
    return output,count
