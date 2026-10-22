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
from block4_score import score_job,merge_semantic_requirements,hard_role_mismatch,recommend_application
from jd_retrieval import extract_public_jd
from score_repository import get_cached,get_previous_semantic,save,reserve,settle,PROFILE_VERSION,RUBRIC_VERSION,key_for
from ai_resume_matcher import (evaluate as evaluate_ai, to_ranking, estimate_cost,
                               reset_billable_usage, billable_usage)
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

def fallback_public_jd(job):
    """Single full-JD reader shared by ranking and CV creation.

    Prefer a provider's existing public detail API where available. For Indeed
    the exact requisition key must match before JobSpy content is accepted.
    """
    url=str(job.get('url') or '')
    detail=remote_detail(job)
    if detail:
        try:
            endpoint,headers=detail
            result=fetch_json(endpoint,headers) if headers else fetch_json(endpoint)
            value=(result.get('jobPage') or result.get('page') or result) if isinstance(result,dict) else {}
            if isinstance(value,dict):
                content=value.get('content') or value.get('description') or value.get('jobDescription') or ''
                if not content and isinstance(value.get('job'),dict):
                    content=value['job'].get('description') or ''
                if isinstance(content,str) and len(content.strip())>=300:
                    return content[:MAX_JD_CHARS]
        except Exception:
            pass
    if urlsplit(url).hostname in ('br.indeed.com','www.indeed.com','indeed.com'):
        try:
            from indeed_provider import description_for_job
            content=description_for_job(url,str(job.get('title') or ''),str(job.get('company') or ''))
            if content and len(content.strip())>=300:
                return content[:MAX_JD_CHARS]
        except Exception:
            pass
    return extract_public_jd(url)

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
        return key,fallback_public_jd(job)
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
        ai_status='cache_or_disabled'
        # Requires approved migration before deployment.
        if description:
            evaluation=get_cached(cursor,key,jd_hash,roles)
            if evaluation is not None:ai_status='cached_failure' if evaluation.get('_ai_failed') else 'cache'
        if evaluation is None:
            evaluation=score_job(complete,roles)
            model='deterministic'
            is_technical_role=hard_role_mismatch(complete)
            if is_technical_role:
                evaluation.update({"score":0,"fit":0,"confidence":"hard_role_mismatch",
                   "reason":"Cargo de desenvolvimento ou QA técnico, sem experiência profissional comprovada nessa função; não é um julgamento da capacidade de aprendizado."})
                model='hard_exclusion'
                ai_status='not_needed'
            # Resume Matcher-inspired, evidence-grounded AI replaces the legacy
            # extraction + deterministic grading on opt-in; one paid call per JD.
            if description and not is_technical_role and os.getenv('JH_AI_ENABLED')=='1' and os.getenv('OPENAI_API_KEY'):
                with psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=7) as budget_conn:
                    with budget_conn.cursor() as budget_cur:
                        usage_id=reserve(budget_cur,key,amount=0.015)
                if usage_id is not None:
                    successful=False
                    reset_billable_usage()
                    try:
                        result=evaluate_ai(description,str(complete.get('title') or ''),
                                           str(complete.get('company') or ''))
                        evaluation=to_ranking(complete,roles,result)
                        model='ai_matcher'
                        ai_status='interpreted'
                        successful=True
                    except Exception as exc:
                        ai_status='failed'
                        # Surface only the exception class and a bounded diagnostic;
                        # never log the JD, evidence catalog, key, or model output.
                        diagnostic=str(exc)[:100] if isinstance(exc,ValueError) else ''
                        print('JH_AI_MATCHER_FAILURE',type(exc).__name__,repr(diagnostic),flush=True)
                        evaluation.update({'score':None,'fit':None,'confidence':'ai_error',
                           'reason':'Análise por IA não concluída; nenhuma nota substituta foi inventada'})
                        model='ai_error'
                    finally:
                        # As in the CV flow, failed validation after a provider
                        # response is billable, but never assume full reservation.
                        actual=min(0.015,estimate_cost(billable_usage()))
                        with psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=7) as budget_conn:
                            with budget_conn.cursor() as budget_cur:
                                settle(budget_cur,usage_id,actual,successful)
                else:
                    ai_status='budget_exhausted'
                    evaluation.update({'score':None,'fit':None,'confidence':'ai_budget_exhausted'})
            elif description and not is_technical_role:
                ai_status='disabled'
                evaluation.update({'score':None,'fit':None,'confidence':'ai_disabled',
                                   'reason':'IA desligada: é necessária a chave OpenAI e JH_AI_ENABLED=1'})
            if description and (evaluation.get('score') is not None or model=='hard_exclusion'):save(cursor,key,jd_hash,roles,evaluation,model)
        recommendation=recommend_application(complete,evaluation)
        # Persist the secondary judgment alongside an existing score without
        # changing the score key, spending API credits or changing the model.
        if description and evaluation.get("application_recommendation")!=recommendation:
            from psycopg.types.json import Jsonb
            cursor.execute("""UPDATE jh_score_cache
                SET result=jsonb_set(result,'{application_recommendation}',%s::jsonb,true)
                WHERE normalized_url=%s AND jd_hash=%s AND profile_version=%s
                  AND rubric_version=%s AND roles_hash=%s""",
                (Jsonb(recommendation),key,jd_hash,PROFILE_VERSION,RUBRIC_VERSION,key_for(roles)))
        evaluation["application_recommendation"]=recommendation
        output.append({**j,"ranking":evaluation,"jd_evidence":signals(complete,roles),
                       "ai_status":ai_status,"jd_status":origin if description else ("pendente" if (key,j) in pending[limit:] else "indisponivel")})
    return output,count
