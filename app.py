import os
import secrets
import json
import re
import urllib.request
import urllib.error
import urllib.parse
import csv
import io
import io
import hashlib
import unicodedata
from urllib.parse import urlsplit

from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel
import psycopg
from psycopg.types.json import Jsonb
import multiuser as mu
from public_remote_feeds import fetch as fetch_public_remote
from indeed_provider import search as indeed_search, enabled as indeed_enabled
from collectors import collect,source_field_coverage
from search_filters import analyze_filters,apply_filters,search_terms,discovery_queries,requested_families,DEFAULT_ROLES,COUNTRIES
from first_seen import flag_new_jobs
from catalog_engine import source_tasks,scan
from catalog_bootstrap import maybe_start
from jd_enrichment import hydrate_jobs, persist_listing_jds, cached_jds_for_filter
from eligibility_enrichment import enrich_inhire_before_filter
from resume_engine import build_plan, render_docx, audit, evaluate_rendered_resume

app = FastAPI(docs_url=None, redoc_url=None)
DIST = Path(__file__).resolve().parent / "dist"
COOKIE = "jh_session"
SECRET = os.environ.get("APP_SECRET", "")
PASSWORD = os.environ.get("APP_PASSWORD", "")
DATABASE = os.environ.get("DATABASE_URL", "")
serializer = URLSafeTimedSerializer(SECRET) if SECRET else None

from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP

cv_mcp=FastMCP("Cacador de Vagas CV", stateless_http=True, streamable_http_path="/")

@cv_mcp.tool()
def fetch_cv_job(url:str,title:str="")->dict:
    """Read a selected vacancy JD and the verified evidence IDs."""
    from resume_engine import EXPERIENCE,EDUCATION
    key,jd=_cv_source(url)
    return {"url":key,"title":title,"jd":jd[:24000],
            "evidence":[{"id":f"{i}:{j}","company":e["company"],"role":e["role"],"fact":fact}
                for i,e in enumerate(EXPERIENCE) for j,fact in enumerate(e["facts"])],
            "education":EDUCATION}

@cv_mcp.tool()
def prepare_verified_cv(url:str, fact_ids:list[str], title:str="",company:str="")->dict:
    """Create a signed 15-minute DOCX download ticket from existing verified evidence IDs only."""
    from resume_engine import EXPERIENCE
    key,jd=_cv_source(url)
    allowed={f"{i}:{j}" for i,e in enumerate(EXPERIENCE) for j,_ in enumerate(e["facts"])}
    if not 1<=len(fact_ids)<=24 or len(set(fact_ids))!=len(fact_ids) or not set(fact_ids)<=allowed:
        raise ValueError("Invalid evidence selection")
    if not serializer:raise ValueError("Signing unavailable")
    packed={"url":key,"title":title[:120],"company":company[:100],"ids":fact_ids,
            "jd_hash":hashlib.sha256(jd.encode()).hexdigest()}
    ticket=serializer.dumps(packed,salt="cv-action-download-v1")
    return {"download_url":"https://olinto-job-hunter.onrender.com/api/gpt-action/download?ticket="+urllib.parse.quote(ticket),
            "expires_in_seconds":900}

@asynccontextmanager
async def cv_lifespan(app):
    maybe_start(DATABASE)
    async with cv_mcp.session_manager.run():
        yield

app.router.lifespan_context=cv_lifespan
# The MCP mount is deliberately authenticated at the ASGI boundary.
# The GPT/ChatGPT client must supply CV_ACTION_TOKEN in its bearer-header connection.
class _CVAuthorizedMCP:
    def __init__(self, inner):
        self.inner=inner
    async def __call__(self, scope, receive, send):
        if scope["type"]=="http":
            if mu.enabled:
                response=JSONResponse({"detail":"MCP legado indisponível no modo multiusuário"},status_code=403)
                await response(scope,receive,send)
                return
            headers=dict(scope.get("headers",[]))
            token=os.environ.get("CV_ACTION_TOKEN","")
            provided=headers.get(b"authorization",b"").decode("latin1")
            if not token or not secrets.compare_digest(provided,"Bearer "+token):
                response=JSONResponse({"detail":"Unauthorized"},status_code=401,
                    headers={"WWW-Authenticate":"Bearer","Cache-Control":"no-store"})
                await response(scope,receive,send)
                return
        await self.inner(scope,receive,send)

app.mount("/cv-mcp",_CVAuthorizedMCP(cv_mcp.streamable_http_app()))

@app.on_event("startup")
def bootstrap_catalog_if_requested():
    maybe_start(DATABASE)

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class Credentials(BaseModel):
    password: str
    email: str = ""

class Registration(BaseModel):
    name: str
    email: str
    password: str

class ProfileUpdate(BaseModel):
    profile: dict

def validated_profile(value, current):
    """Explicit user-provided facts; verified evidence must be approved by user."""
    if len(json.dumps(value,ensure_ascii=False))>60000:
        raise HTTPException(413,"Perfil muito extenso")
    clean={**current}
    for key in ("name","location","phone","linkedin","summary","seniority","country","mode"):
        if key in value:
            clean[key]=str(value[key]).strip()[:1500 if key=="summary" else 260]
    clean["name"]=clean.get("name","").strip()
    if not clean["name"]:
        raise HTTPException(400,"Nome obrigatório")
    for key in ("roles","education","skills","certifications","languages"):
        if key in value:
            seq=value[key]
            if not isinstance(seq,list) or len(seq)>60:
                raise HTTPException(400,"Lista inválida: "+key)
            clean[key]=list(dict.fromkeys(str(x).strip()[:200] for x in seq if str(x).strip()))
    if "days" in value:
        try:clean["days"]=max(0,min(90,int(value["days"])))
        except (ValueError,TypeError):raise HTTPException(400,"Período inválido")
    if "experience" in value:
        items=value["experience"]
        if not isinstance(items,list) or len(items)>40:
            raise HTTPException(400,"Experiência inválida")
        verified=[]
        for item in items:
            if not isinstance(item,dict):raise HTTPException(400,"Experiência inválida")
            facts=item.get("facts",[])
            if not isinstance(facts,list) or len(facts)>25:
                raise HTTPException(400,"Evidências inválidas")
            row={k:str(item.get(k) or "").strip()[:200] for k in ("role","company","dates")}
            row["facts"]=list(dict.fromkeys(str(f).strip()[:500] for f in facts if str(f).strip()))
            row["verified"]=item.get("verified") is True
            # LinkedIn exports sometimes list a position without bullet points.
            # Keep the position for review, but never use it as factual AI
            # evidence until actual source-backed facts are available.
            if row["role"] and row["company"]:
                verified.append(row)
        clean["experience"]=verified
    return clean

def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()

def auth_record():
    with mu.connect(DATABASE, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash,password_salt,version FROM jh_auth WHERE id=1")
            return cur.fetchone()

def check_password(value, record):
    if record:
        return secrets.compare_digest(password_digest(value, record[1]), record[0])
    return bool(PASSWORD) and secrets.compare_digest(value, PASSWORD)

def require_auth(request: Request):
    if not serializer or not DATABASE:
        raise HTTPException(503, "Acesso indisponível")
    if mu.enabled:
        try:
            token=serializer.loads(request.cookies.get(COOKIE) or "",max_age=604800,salt="multiuser-v1")
            if not isinstance(token,list) or len(token)!=2:
                raise HTTPException(401,"Sessão inválida")
            user=mu.get_user(DATABASE,token[0])
            if not user or user[4]!=token[1]:
                raise HTTPException(401,"Sessão expirada")
            mu.set_context(user)
            return user[0]
        except (BadSignature,SignatureExpired,ValueError,TypeError):
            raise HTTPException(401,"Acesso não autorizado")
    try:
        value = serializer.loads(request.cookies.get(COOKIE) or "", max_age=604800)
        record = auth_record()
        expected = f"owner:{record[2] if record else 0}"
        if not secrets.compare_digest(str(value), expected):
            raise HTTPException(401, "Sessão expirada")
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Acesso não autorizado")
    except psycopg.Error:
        raise HTTPException(503, "Banco indisponível")
    return True

def normalized(value):
    return ''.join(ch for ch in unicodedata.normalize("NFKD", (value or "").casefold()) if not unicodedata.combining(ch)).strip()

def url_key(value):
    v=(value or "").strip()
    if not v:
        return ""
    if "://" not in v:
        v="https://"+v
    x=urlsplit(v)
    host=x.netloc.casefold().removeprefix("www.").removeprefix("br.")
    return (host+x.path.rstrip("/")+(("?"+x.query) if x.query else "")).strip().lower()

def terminal_url_key(value):
    """Compare the actual vacancy URL while ignoring common tracking-only query params."""
    from urllib.parse import parse_qsl, urlencode
    key=url_key(value)
    if "?" not in key:return key
    base,query=key.split("?",1)
    trackers={"fbclid","gclid","msclkid","ref","referrer","source","utm_source","utm_medium","utm_campaign","utm_content","utm_term"}
    clean=[(k,v) for k,v in parse_qsl(query,keep_blank_values=True)
           if k.lower() not in trackers and not k.lower().startswith("utm_")]
    return base+("?" + urlencode(sorted(clean)) if clean else "")

def terminal_url_bases(jobs):
    return list({url_key(j["url"]).split("?",1)[0] for j in jobs if j.get("url")})

def pair_key(empresa,cargo):
    return " ".join(normalized(empresa).split())+"|"+ " ".join(normalized(cargo).split())

@app.get("/health")
def health():
    return {"service":"job-hunter","alive":True,"ai_ready":os.getenv("JH_AI_ENABLED")=="1" and bool(os.getenv("OPENAI_API_KEY"))}

@app.get("/api/me")
def me(request: Request):
    uid=require_auth(request)
    return {"authenticated":True,"user":(
        {"id":uid,"name":mu.current_profile.get().get("name"),"email":mu.current_profile.get().get("email")}
        if mu.enabled else None)}

@app.post("/api/register")
def register(payload: Registration, response: Response):
    if not mu.enabled:raise HTTPException(404,"Indisponível")
    try:uid=mu.create_account(DATABASE,payload.email,payload.password,payload.name)
    except psycopg.errors.UniqueViolation:raise HTTPException(409,"Email já cadastrado")
    except ValueError as exc:raise HTTPException(400,str(exc))
    user=mu.get_user(DATABASE,uid)
    response.set_cookie(COOKIE,serializer.dumps([uid,user[4]],salt="multiuser-v1"),
                        httponly=True,secure=True,samesite="lax",max_age=604800)
    return {"authenticated":True,"id":uid}

@app.get("/api/profile")
def get_profile(request: Request):
    if not mu.enabled:raise HTTPException(404,"Indisponível")
    require_auth(request)
    return {"profile":mu.current_profile.get()}

@app.post("/api/profile/import-linkedin")
async def import_linkedin_pdf(request: Request):
    if not mu.enabled:
        raise HTTPException(404,"Indisponível")
    require_auth(request)
    if request.headers.get("content-type", "").split(";",1)[0].strip().lower() != "application/pdf":
        raise HTTPException(415,"Envie um arquivo PDF exportado do LinkedIn")
    from linkedin_pdf import MAX_PDF_BYTES,parse_linkedin_pdf
    try:
        length=int(request.headers.get("content-length") or 0)
    except ValueError:
        raise HTTPException(400,"Tamanho do PDF inválido")
    if length > MAX_PDF_BYTES:
        raise HTTPException(413,"O PDF deve ter no máximo 8 MB")
    data=bytearray()
    async for part in request.stream():
        data.extend(part)
        if len(data)>MAX_PDF_BYTES:
            raise HTTPException(413,"O PDF deve ter no máximo 8 MB")
    try:
        # Source PDF exists only in memory for extraction; nothing is
        # persisted until the user reviews and explicitly saves the profile.
        return parse_linkedin_pdf(bytes(data))
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.put("/api/profile")
def save_profile(payload: ProfileUpdate, request: Request):
    if not mu.enabled:raise HTTPException(404,"Indisponível")
    uid=require_auth(request)
    profile=validated_profile(payload.profile,mu.current_profile.get())
    mu.update_profile(DATABASE,uid,profile)
    return {"saved":True,"profile":profile}

@app.post("/api/login")
def login(payload: Credentials, response: Response):
    if not serializer or not DATABASE:
        raise HTTPException(503, "Acesso não configurado")
    if mu.enabled:
        user=mu.authenticate(DATABASE,payload.email,payload.password)
        if not user:raise HTTPException(401,"Credenciais incorretas")
        response.set_cookie(COOKIE,serializer.dumps(list(user),salt="multiuser-v1"),
                            httponly=True,secure=True,samesite="lax",max_age=604800)
        return {"authenticated":True}
    try:
        record=auth_record()
    except psycopg.Error:
        raise HTTPException(503, "Banco indisponível")
    if not check_password(payload.password,record):
        raise HTTPException(401, "Senha incorreta")
    response.set_cookie(COOKIE,serializer.dumps(f"owner:{record[2] if record else 0}"),httponly=True,secure=True,samesite="lax",max_age=604800)
    return {"authenticated":True}

@app.post("/api/change-password")
def change_password(payload: ChangePassword, request: Request, response: Response):
    uid=require_auth(request)
    if mu.enabled:
        try:version=mu.change_password(DATABASE,uid,payload.current_password,payload.new_password)
        except ValueError as exc:raise HTTPException(400,str(exc))
        response.set_cookie(COOKIE,serializer.dumps([uid,version],salt="multiuser-v1"),
                            httponly=True,secure=True,samesite="lax",max_age=604800)
        return {"ok":True}
    if len(payload.new_password)<12 or len(payload.new_password)>128:
        raise HTTPException(400,"A nova senha deve ter entre 12 e 128 caracteres")
    if secrets.compare_digest(payload.current_password,payload.new_password):
        raise HTTPException(400,"A nova senha deve ser diferente")
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash,password_salt,version FROM jh_auth WHERE id=1 FOR UPDATE")
            rec=cur.fetchone()
            if not check_password(payload.current_password,rec):
                raise HTTPException(401,"Senha atual incorreta")
            salt=secrets.token_hex(16)
            digest=password_digest(payload.new_password,salt)
            version=(rec[2]+1) if rec else 1
            cur.execute("""INSERT INTO jh_auth(id,password_hash,password_salt,version)
                VALUES (1,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET
                password_hash=EXCLUDED.password_hash,password_salt=EXCLUDED.password_salt,
                version=EXCLUDED.version,updated_at=now()""",(digest,salt,version))
    response.set_cookie(COOKIE,serializer.dumps(f"owner:{version}"),httponly=True,secure=True,samesite="lax",max_age=604800)
    return {"ok":True}


SEARCH_TERMS = ("product manager","product owner","project manager","marketing","growth")
JOBGETHER_API = "https://jobgether.com/api/v1/jobs"

def extract_jobs(data):
    if isinstance(data,list):
        return data
    if not isinstance(data,dict):
        return []
    for key in ("jobs","results","items","data"):
        value=data.get(key)
        if isinstance(value,list):
            return value
        if isinstance(value,dict):
            jobs=extract_jobs(value)
            if jobs:return jobs
    return []

def exclude_history_matches(items,review,known_urls,known_pairs):
    """Hide history entries from BOTH confirmed and review results.
    The sets are always queried fresh during every search/catalog batch.
    """
    def is_known(job):
        # A different URL can represent a different requisition even when
        # company and role are identical. Only fall back to the pair key when
        # a listing has no URL at all.
        key=terminal_url_key(job.get("url",""))
        return (key in known_urls) if key else (
            bool(job.get("company")) and pair_key(job["company"],job["title"]) in known_pairs
        )
    confirmed=[job for job in items if not is_known(job)]
    pending=[job for job in review if not is_known(job)]
    return confirmed,pending,(len(items)+len(review)-len(confirmed)-len(pending))

def restore_persisted_scores(cursor, jobs, roles, url_key):
    """Restore only version-matched scores for the current, verified JD content.

    No remote fetch or AI invocation: the initial search stays responsive.
    Unverified jobs must never enter this path.
    """
    from score_repository import PROFILE_VERSION, RUBRIC_VERSION, key_for
    if not jobs:
        return jobs, 0
    keys = [url_key(j.get("url", "")) for j in jobs]
    cursor.execute("""SELECT s.normalized_url, s.jd_hash, s.result, s.model,
                             d.content_hash, d.fetched_at
        FROM jh_score_cache s
        LEFT JOIN jh_jd_cache d ON d.normalized_url=s.normalized_url
        WHERE s.normalized_url = ANY(%s)
          AND s.profile_version=%s AND s.rubric_version=%s AND s.roles_hash=%s
        ORDER BY s.created_at DESC""",
        (keys, PROFILE_VERSION, RUBRIC_VERSION, key_for(roles)))
    require_hybrid = os.getenv("JH_AI_ENABLED") == "1" and bool(os.getenv("OPENAI_API_KEY"))
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    by_url = {}
    for key, jd_hash, result, model, cache_hash, fetched_at in cursor.fetchall():
        if key in by_url or not isinstance(result, dict):
            continue
        if require_hybrid and model not in ("ai_matcher", "hard_exclusion"):
            continue
        if result.get("score") is None:
            continue
        by_url[key] = (jd_hash, result, cache_hash, fetched_at)
    restored = 0
    output = []
    for job, key in zip(jobs, keys):
        candidate = by_url.get(key)
        original_description = str(job.get("description") or "")
        expected = job.get("_listing_jd_hash") or (hashlib.sha256(original_description.encode()).hexdigest() if len(original_description) >= 300 else None)
        if candidate:
            jd_hash, result, cache_hash, fetched_at = candidate
            fresh = fetched_at is not None and fetched_at >= now - timedelta(days=7)
            if (expected and expected == jd_hash) or (not expected and fresh and cache_hash == jd_hash):
                output.append({**job, "ranking": result, "jd_status": "cache"})
                restored += 1
                continue
        # Do not erase an already evidence-validated local estimate merely
        # because no paid/cached AI score exists for this exact JD and role.
        # Such a number is explicitly labelled local in the UI.
        local=job.get("ranking") if job.get("jd_available") else None
        if isinstance(local,dict) and isinstance(local.get("score"),(int,float)) and not isinstance(local.get("score"),bool):
            output.append({**job,"ranking":{**local,"method":"local","cost_usd":0},"jd_status":"avaliacao_local"})
        else:
            output.append({**job, "ranking": local if isinstance(local,dict) else None,
                           "jd_status": "pendente" if job.get("jd_available") else "indisponivel"})
    return output, restored


@app.post("/api/search-jobs")
def search_jobs(request: Request, roles:str=DEFAULT_ROLES,country:str="BR",mode:str="remote",days:int=30,sort:str="newest",source:str="all"):
    require_auth(request)
    allowed_sources={"all","inhire","quickin","gupy","greenhouse","ashby","lever","bamboohr","dynamite","linkedin_guest","jobgether","workable","himalayas","remotive","remoteok","indeed","geekhunter","nerdin","recruitee"}
    if source not in allowed_sources:raise HTTPException(400,"Fonte não reconhecida")
    if source=="indeed":
        if not indeed_enabled():raise HTTPException(503,"Indeed indisponível")
        queries=discovery_queries(roles,limit=2)[:2]
        if not queries:queries=["product manager"]
        items=[]
        try:
            for term in queries:items.extend(indeed_search(term))
        except Exception as exc:
            raise HTTPException(502,"Indeed indisponível: "+type(exc).__name__) from exc
        sources=[{"source":"indeed","state":"validado","received":len(items)}]
    elif source in ("himalayas","remotive","remoteok"):
        try:
            items=fetch_public_remote(source,roles,country)
        except Exception as exc:
            raise HTTPException(502,"Fonte "+source+" indisponível: "+type(exc).__name__) from exc
        sources=[{"source":source,"state":"validado","received":len(items)}]
    else:
        items,sources=collect(discovery_queries(roles),country,source) if source in ("all","jobgether","workable") else ([],[])
        if source=="all":
            for feed in ("himalayas","remotive","remoteok"):
                try:
                    added=fetch_public_remote(feed,roles,country)
                    items.extend(added)
                    sources.append({"source":feed,"state":"validado","received":len(added)})
                except Exception as exc:
                    sources.append({"source":feed,"state":"error","received":0,"error":type(exc).__name__})
    raw_count=len(items)
    items,eligibility_fetch=enrich_inhire_before_filter(items,roles)
    raw_jobs=list(items)
    field_coverage=source_field_coverage(raw_jobs)
    filter_quality=source_filter_quality(raw_jobs,roles,country,mode,days)
    try: items,review,filter_stats=analyze_filters(cached_jds_for_filter(items,url_key,DATABASE),roles,country,mode,days,sort)
    except ValueError as e: raise HTTPException(400,str(e))
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            source_jd_stats=persist_listing_jds(cur,raw_jobs,items+review,url_key)
            keys=[url_key(j["url"]) for j in items+review]
            known_urls=set()
            known_pairs=set()
            if keys:
                cur.execute("SELECT normalized_url FROM jh_history WHERE split_part(normalized_url,'?',1)=ANY(%s) AND lower(estado) IN ('candidatado','descartado','descartada')",(terminal_url_bases(items+review),))
                known_urls={terminal_url_key(row[0]) for row in cur.fetchall()}
            pairs=[pair_key(j["company"],j["title"]) for j in items+review if j["company"]]
            if pairs:
                cur.execute("SELECT pair_key FROM jh_history WHERE pair_key=ANY(%s) AND lower(estado) IN ('candidatado','descartado','descartada')",(pairs,))
                known_pairs={row[0] for row in cur.fetchall()}
    visible,pending,history_excluded=exclude_history_matches(items,review,known_urls,known_pairs)
    visible=[j for j in visible if not any(b in normalized(j["company"]) for b in ("kraken","payward"))]
    pending=[j for j in pending if not any(b in normalized(j["company"]) for b in ("kraken","payward"))]
    # First seen is persisted independently of the terminal application history.
    with mu.connect(DATABASE,connect_timeout=8) as seen_conn:
        flagged=flag_new_jobs(seen_conn,visible+pending,url_key)
    visible=flagged[:len(visible)]
    pending=flagged[len(visible):]
    # Initial results must not wait for scoring or open another database connection.
    coverage={"cached":0,"fetched":0,"missing":0,"not_attempted":len(visible)}
    with mu.connect(DATABASE,connect_timeout=7) as score_conn:
        with score_conn.cursor() as score_cur:
            visible,restored=restore_persisted_scores(score_cur,visible,roles,url_key)
    coverage["cached"]=restored
    coverage["not_attempted"]=len(visible)-restored
    if sort in ("score", "recommendation"):
        visible.sort(key=lambda j: (
            isinstance(j.get("ranking"), dict) and isinstance(j["ranking"].get("score"), (int, float)),
            float(j["ranking"]["score"]) if isinstance(j.get("ranking"), dict) and isinstance(j["ranking"].get("score"), (int, float)) else -1
        ), reverse=True)
    pending=[{**j,"jd_status":"avaliacao_local" if j.get("jd_available") else "indisponivel"} for j in pending]
    # Pending eligibility is not automatically enriched or scored.
    fresh_count=len(visible)
    return {"source":"Multifuente","queried":len(sources),"total":len(items),
        "new":fresh_count,"duplicates":history_excluded,"jd_coverage":coverage,"source_jd_stats":source_jd_stats,"source_field_stats":field_coverage,"source_filter_quality":filter_quality,"eligibility_fetch":eligibility_fetch,"flow_stats":{"raw":raw_count,"classified_confirmed":len(items),"classified_review":len(review),"history_excluded":history_excluded,"display_confirmed":len(visible),"display_review":len(pending)},"items":visible[:100],"review_items":pending[:150],"filter_stats":filter_stats,"raw_count":raw_count,"details":sources,
        "notice":"Vagas coletadas, ainda sem triagem de elegibilidade Brasil/remoto ou score."}




SOURCE_CADENCE_DAYS={"inhire":3,"quickin":3,"dynamite":3,"greenhouse":7,"greenhouse_eu":30,
 "ashby":7,"lever":7,"gupy":7,"linkedin_guest":7,"teamtailor":14,"recruitee":30,
 "smartrecruiters":30,"kaszek":7,"jobbol":7,"workable_account":7,"personio":30,"bamboohr":30,
 "zoho":30,"trakstar":30,"compleo":30,"solides":30,"geekhunter":3,"nerdin":3}

def source_freshness(source, checked_at):
    from datetime import datetime,timezone,timedelta
    days=SOURCE_CADENCE_DAYS.get(source,30)
    if not checked_at:return {"interval_days":days,"due":True,"next_check":None}
    next_time=checked_at+timedelta(days=days)
    return {"interval_days":days,"due":next_time<=datetime.now(timezone.utc),
            "next_check":next_time.isoformat()}

def active_source_tasks(roles=DEFAULT_ROLES):
    tasks=set(source_tasks())
    # Search the complete default role family on keyword-based LinkedIn guest.
    # Do not expand Gupy here: its current public endpoint returns HTTP 404.
    linkedin_terms=("product manager","product owner","project manager",
        "gerente de projetos","gerente de produto","product marketing",
        "marketing","growth","business analyst","analista de negocios","pmo")
    if roles.strip()!=DEFAULT_ROLES:
        linkedin_terms=tuple(discovery_queries(roles,limit=8))
    tasks.update(("linkedin_guest",term) for term in linkedin_terms)
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source,slug FROM jh_catalog_source")
            tasks.update(cur.fetchall())
    # Both public boards expose their own keyword search. Restrict discovery
    # to selected families instead of crawling fixed unrelated vacancy lists.
    tasks={task for task in tasks if task[0] not in ("geekhunter","nerdin")}
    family_order=("product","projects","marketing","growth","business")
    families=requested_families(search_terms(roles))
    geek_terms={"product":"product","projects":"project","marketing":"marketing",
                "growth":"growth","business":"business"}
    nerdin_terms={"product":"product manager","projects":"project manager",
                  "marketing":"marketing","growth":"growth","business":"business analyst"}
    for family in family_order:
        if family in families:
            tasks.add(("geekhunter","search:"+geek_terms[family]))
            tasks.add(("nerdin",nerdin_terms[family]))
    # Include an exact selected title when it adds a distinct public query.
    for term in search_terms(roles)[:3]:
        if len(term)>2 and term not in nerdin_terms.values():
            tasks.add(("nerdin",term))
    return sorted((source,slug) for source,slug in tasks if slug.casefold() not in ("kraken","kraken.com","payward"))

def source_filter_quality(jobs,roles,country,mode,days):
    """Source-level filter outcomes, without extra HTTP or AI calls."""
    from search_filters import classify
    terms=search_terms(roles)
    result={}
    fields=("raw","confirmed","review","excluded","excluded_cargo",
            "excluded_pais","excluded_modalidade","excluded_data",
            "review_date","review_country","review_mode","review_role")
    for job in jobs:
        source=str(job.get("source") or "unknown").lower()
        row=result.setdefault(source,{field:0 for field in fields})
        row["raw"]+=1
        bucket,reason=classify(job,terms,country,mode,days)
        row[bucket]+=1
        if bucket=="excluded" and "excluded_"+reason in row:
            row["excluded_"+reason]+=1
        elif bucket=="review":
            for marker,key in (("data","review_date"),("pais","review_country"),
                               ("modalidade","review_mode"),("cargo_a_confirmar","review_role")):
                if marker in reason.split(","):row[key]+=1
    return result

@app.post("/api/catalog/import")
async def catalog_import(request: Request):
    require_auth(request)
    raw=await request.body()
    if len(raw)>1_200_000:
        raise HTTPException(413,"Catálogo grande demais")
    try:
        data=json.loads(raw)
    except (ValueError,UnicodeDecodeError):
        raise HTTPException(400,"JSON inválido")
    mapping={"greenhouse":"greenhouse","lever":"lever","ashby":"ashby","inhire":"inhire"}
    imported=set()
    for name,ats in mapping.items():
        group=data.get(name)
        if not isinstance(group,dict):continue
        for key in ("validados_200","validados_47_em_31_08","tenants_novos_22_09","a_validar","dominio_eu"):
            for slug in group.get(key,[]) if isinstance(group.get(key),list) else []:
                if not isinstance(slug,str) or len(slug)>100:continue
                kind="greenhouse_eu" if key=="dominio_eu" else ats
                if re.fullmatch(r"[a-zA-Z0-9_.-]+",slug):imported.add((kind,slug))
    other=data.get("outros_ats",{})
    if isinstance(other,dict):
        for key,kind in (("quickin","quickin"),("inhire","inhire"),("zoho_recruit","zoho"),("trakstar","trakstar"),("compleo","compleo"),("bamboohr","bamboohr")):
            value=other.get(key,[])
            if isinstance(value,list):
                for slug in value:
                    if isinstance(slug,str) and re.fullmatch(r"[a-zA-Z0-9_.-]{2,100}",slug):imported.add((kind,slug))
    with mu.connect(DATABASE,connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO jh_catalog_document(id,document) VALUES(1,%s) ON CONFLICT(id) DO UPDATE SET document=EXCLUDED.document,imported_at=now()", (Jsonb(data),))
            for ats,slug in sorted(imported):
                cur.execute("INSERT INTO jh_catalog_source(source,slug) VALUES(%s,%s) ON CONFLICT DO NOTHING",(ats,slug))
    return {"imported":len(imported),"document_keys":len(data),"total_active":len(active_source_tasks())}

@app.get("/api/search-filters")
def available_filters(request: Request):
    require_auth(request)
    return {"roles":DEFAULT_ROLES,"countries":[{"value":k,"label":v} for k,v in COUNTRIES],"sources":[{"value":"all","label":"Todas as fontes"},{"value":"inhire","label":"inHire"},{"value":"quickin","label":"Quickin"},{"value":"gupy","label":"Gupy"},{"value":"greenhouse","label":"Greenhouse"},{"value":"ashby","label":"Ashby"},{"value":"lever","label":"Lever"},{"value":"bamboohr","label":"BambooHR"},{"value":"recruitee","label":"Recruitee"},{"value":"dynamite","label":"Dynamite Jobs"},{"value":"linkedin_guest","label":"LinkedIn"},{"value":"jobgether","label":"Jobgether"},{"value":"workable","label":"Workable"},{"value":"himalayas","label":"Himalayas (remoto)"},{"value":"remotive","label":"Remotive (remoto)"},{"value":"remoteok","label":"Remote OK (remoto)"},{"value":"geekhunter","label":"GeekHunter"},{"value":"nerdin","label":"Nerdin"}]+([{"value":"indeed","label":"Indeed"}] if indeed_enabled() else [])}

@app.get("/api/catalog")
def catalog(request: Request):
    require_auth(request)
    from collections import Counter
    tasks=active_source_tasks()
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source,slug,state,received,error,checked_at FROM jh_catalog_checks")
            history={(r[0],r[1]):r[2:] for r in cur.fetchall()}
    sources=[]
    due=0
    for source,slug in tasks:
        h=history.get((source,slug))
        timing=source_freshness(source,h[3] if h else None)
        if timing["due"]:due+=1
        sources.append({"source":source,"slug":slug,"state":h[0] if h else "nao_verificado",
             "last_received":h[1] if h else 0,"last_error":h[2] if h else "",
             "checked_at":h[3].isoformat() if h else None,**timing})
    return {"total":len(tasks),"due":due,"by_source":dict(Counter(s for s,_ in tasks)),
            "sources":sources,"mcp_status":{
              "Scrapling":("Biblioteca local instalada; fallback JS habilitado" if os.environ.get("JH_SCRAPLING_JS")=="1" else "Biblioteca local instalada; fallback JS protegido por configuração"),"Indeed":"JobSpy no Render — consulta sob demanda (sem credencial)",
              "Nimble":"exige acesso autenticado e quota","Firecrawl":"exige chave e quota no Render"}}

@app.get("/api/catalog/checks")
def catalog_checks(request: Request):
    require_auth(request)
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source,slug,state,received,error,checked_at::text FROM jh_catalog_checks ORDER BY checked_at DESC LIMIT 500")
            rows=[dict(zip(("source","slug","state","received","error","checked_at"),r)) for r in cur.fetchall()]
    return {"total":len(rows),"items":rows}

def unique_jobs_by_url(found):
    """Only collapse exact listing URLs, never distinct postings sharing a title."""
    unique={}
    for job in found:
        key=url_key(job.get("url",""))
        if key and key not in unique:
            unique[key]=job
    return unique

@app.post("/api/catalog/scan")
def catalog_scan(request: Request, offset:int=0,limit:int=12,due_only:bool=False,roles:str=DEFAULT_ROLES,country:str="BR",mode:str="remote",days:int=30,sort:str="newest",source:str="all"):
    require_auth(request)
    if source not in {"all","inhire","quickin","gupy","greenhouse","ashby","lever","bamboohr","dynamite","linkedin_guest","jobgether","workable","himalayas","remotive","remoteok","geekhunter","nerdin","recruitee"}:raise HTTPException(400,"Fonte não reconhecida")
    tasks=active_source_tasks(roles)
    if source!="all":
        tasks=[(src,slug) for src,slug in tasks if src==source or (source=="greenhouse" and src=="greenhouse_eu")]
    if due_only:
        with mu.connect(DATABASE,connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT source,slug,state,checked_at FROM jh_catalog_checks")
                checked={(r[0],r[1]):(r[2],r[3]) for r in cur.fetchall()}
        due=[]
        for source,slug in tasks:
            previous=checked.get((source,slug))
            timing=source_freshness(source,previous[1] if previous else None)
            if previous and previous[0]=="pendente":
                from datetime import datetime,timezone,timedelta
                timing["due"]=previous[1]+timedelta(days=1)<=datetime.now(timezone.utc)
            if timing["due"]:due.append((source,slug))
        tasks=due
        offset=0
    offset=max(0,min(offset,len(tasks)))
    limit=max(1,min(limit,15))
    batch=tasks[offset:offset+limit]
    details,found=scan(batch,workers=6)
    # Only deduplicate identical URLs. Company + role can represent distinct
    # openings, offices or requisition IDs and must not discard jobs here.
    unique=unique_jobs_by_url(found)
    raw_count=len(unique)
    prepared,eligibility_fetch=enrich_inhire_before_filter(list(unique.values()),roles)
    raw_jobs=list(prepared)
    field_coverage=source_field_coverage(raw_jobs)
    filter_quality=source_filter_quality(raw_jobs,roles,country,mode,days)
    try: items,review,filter_stats=analyze_filters(cached_jds_for_filter(prepared,url_key,DATABASE),roles,country,mode,days,sort)
    except ValueError as e:raise HTTPException(400,str(e))
    # Offer out-of-filter vacancies for explicit decisions without treating them
    # as eligible. Bound the response: this is a review sample, not bulk export.
    from search_filters import classify,search_terms
    terms=search_terms(roles)
    rejected=[]
    for job in prepared:
        verdict,reason=classify(job,terms,country,mode,days)
        if verdict=="excluded" and len(rejected)<25:
            rejected.append({k:job.get(k,"") for k in ("url","title","company","source","location","published")}|{"excluded_reason":reason})
    urls=[url_key(v["url"]) for v in items+review+rejected]
    pairs=[pair_key(v["company"],v["title"]) for v in items+review+rejected if v["company"]]
    known_urls=set();known_pairs=set()
    with mu.connect(DATABASE,connect_timeout=7) as conn:
        with conn.cursor() as cur:
            source_jd_stats=persist_listing_jds(cur,raw_jobs,items+review,url_key)
            for entry in details:
                cur.execute("""INSERT INTO jh_catalog_checks(source,slug,state,received,error)
                    VALUES(%s,%s,%s,%s,%s) ON CONFLICT(source,slug) DO UPDATE SET
                    state=EXCLUDED.state,received=EXCLUDED.received,error=EXCLUDED.error,checked_at=now()""",
                    (entry["source"],entry["slug"],entry["state"],entry["received"],entry.get("error","")))
            if urls:
                cur.execute("SELECT normalized_url FROM jh_history WHERE split_part(normalized_url,'?',1)=ANY(%s) AND lower(estado) IN ('candidatado','descartado','descartada')",(terminal_url_bases(items+review),))
                known_urls={terminal_url_key(r[0]) for r in cur.fetchall()}
            if pairs:
                cur.execute("SELECT pair_key FROM jh_history WHERE pair_key=ANY(%s) AND lower(estado) IN ('candidatado','descartado','descartada')",(pairs,))
                known_pairs={r[0] for r in cur.fetchall()}
    visible,pending,history_excluded=exclude_history_matches(items,review,known_urls,known_pairs)
    _,rejected,_=exclude_history_matches([],rejected,known_urls,known_pairs)
    rejected=[j for j in rejected if not any(b in normalized(j["company"]) for b in ("kraken","payward"))]
    visible=[j for j in visible if not any(b in normalized(j["company"]) for b in ("kraken","payward"))]
    pending=[j for j in pending if not any(b in normalized(j["company"]) for b in ("kraken","payward"))]
    # First seen is persisted independently of the terminal application history.
    with mu.connect(DATABASE,connect_timeout=8) as seen_conn:
        flagged=flag_new_jobs(seen_conn,visible+pending,url_key)
    visible=flagged[:len(visible)]
    pending=flagged[len(visible):]
    # Initial results must not wait for scoring or open another database connection.
    coverage={"cached":0,"fetched":0,"missing":0,"not_attempted":len(visible)}
    with mu.connect(DATABASE,connect_timeout=7) as score_conn:
        with score_conn.cursor() as score_cur:
            visible,restored=restore_persisted_scores(score_cur,visible,roles,url_key)
    coverage["cached"]=restored
    coverage["not_attempted"]=len(visible)-restored
    if sort in ("score", "recommendation"):
        visible.sort(key=lambda j: (
            isinstance(j.get("ranking"), dict) and isinstance(j["ranking"].get("score"), (int, float)),
            float(j["ranking"]["score"]) if isinstance(j.get("ranking"), dict) and isinstance(j["ranking"].get("score"), (int, float)) else -1
        ), reverse=True)
    pending=[{**j,"jd_status":"avaliacao_local" if j.get("jd_available") else "indisponivel"} for j in pending]
    # Pending eligibility is not automatically enriched or scored.
    fresh_count=len(visible)
    return {"total_sources":len(tasks),"due_only":due_only,"offset":offset,"next_offset":offset+len(batch),
            "complete":offset+len(batch)>=len(tasks),"details":details,
            "found":len(items),"new":fresh_count,"duplicates":history_excluded,"raw_count":raw_count,"filter_stats":filter_stats,"eligibility_fetch":eligibility_fetch,"flow_stats":{"raw":raw_count,"classified_confirmed":len(items),"classified_review":len(review),"history_excluded":history_excluded,"display_confirmed":len(visible),"display_review":len(pending)},
            "jd_coverage":coverage,"source_jd_stats":source_jd_stats,"source_field_stats":field_coverage,"source_filter_quality":filter_quality,"review_items":pending[:150],"excluded_items":rejected,"items":visible[:80],"notice":"Vagas candidatas: remoto/Brasil e requisitos ainda aguardam análise completa."}

class JDRequest(BaseModel):
    jobs: list[dict]
    roles: str=DEFAULT_ROLES
    manual: bool=False

class ShortlistRequest(BaseModel):
    jobs: list[dict]
    roles: str=DEFAULT_ROLES
    limit: int=40

@app.post('/api/ranking/shortlist')
def ranking_shortlist(request: Request, payload: ShortlistRequest):
    """Cost-free shortlist over the *whole* collected set, before AI spending."""
    require_auth(request)
    if len(payload.jobs)>2500 or len(payload.roles)>700:
        raise HTTPException(400,'Seleção grande demais')
    from ai_resume_matcher import shortlist_jobs
    return {'urls':shortlist_jobs(payload.jobs,payload.roles,payload.limit),
            'total_considered':len(payload.jobs),'ai_calls':0}

@app.post("/api/jd/enrich")
def jd_enrich(request: Request, payload: JDRequest):
    require_auth(request)
    if len(payload.jobs)>10:raise HTTPException(400,"Máximo de 10 vagas por lote")
    if len(payload.roles)>700:raise HTTPException(400,"Filtro inválido")
    rows=[]
    for j in payload.jobs:
        if not isinstance(j,dict):raise HTTPException(400,"Vaga inválida")
        if not payload.manual and j.get('needs_verification'):
            raise HTTPException(400,'Vaga não confirmada exige avaliação manual')
        if not str(j.get("url","")).startswith("https://"):raise HTTPException(400,"URL inválida")
        if len(str(j.get("url","")))>2000:raise HTTPException(400,"URL inválida")
        rows.append({k:j.get(k,"") for k in ("url","title","company","source","description","location","published","detected_mode","needs_verification")})
    with mu.connect(DATABASE,connect_timeout=7) as conn:
        with conn.cursor() as cur:
            # History is a discovery filter, not a scoring/cache filter.
            # Repeated searches must return persisted scores for previously seen jobs.
            result,coverage=hydrate_jobs(cur,rows,payload.roles,url_key,limit=10)
    return {"items":result,"jd_coverage":coverage}

class JobDisposition(BaseModel):
    url: str
    title: str
    company: str
    state: str
    source: str = ""

@app.post("/api/jobs/disposition")
def mark_job_disposition(payload: JobDisposition, request: Request):
    """Persist an explicit decision in the same history used by search exclusion.
    Idempotent by URL or company+role: one vacancy contributes one history entry.
    """
    require_auth(request)
    if payload.state not in ("Candidatado", "Descartado"):
        raise HTTPException(400, "Estado deve ser Candidatado ou Descartado")
    url=payload.url.strip()[:2000]
    company=payload.company.strip()[:300]
    title=payload.title.strip()[:300]
    uk=url_key(url)
    if not uk or not title:
        raise HTTPException(400, "Vaga sem URL ou cargo válido")
    pk=pair_key(company,title) if company else ""
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            # Serialize decisions on the same vacancy to avoid duplicate history rows.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",("job-disposition:"+uk,))
            cur.execute("""SELECT id,estado,normalized_url FROM jh_history
                WHERE normalized_url=%s OR (pair_key=%s AND %s<>'' )
                ORDER BY CASE WHEN normalized_url=%s THEN 0 ELSE 1 END,id LIMIT 1""",(uk,pk,pk,uk))
            existing=cur.fetchone()
            # A company/title match is not necessarily the same job posting.
            # Preserve both independently when their normalized URLs differ.
            same_url=bool(existing and existing[2]==uk)
            if same_url:
                old_state=str(existing[1] or "")
                if old_state.casefold()==payload.state.casefold():
                    return {"saved":True,"already_recorded":True,"updated":False,"state":payload.state}
                cur.execute("""UPDATE jh_history SET estado=%s, data=TO_CHAR(CURRENT_DATE,'YYYY-MM-DD'),
                    motivo=%s WHERE id=%s""",
                    (payload.state,"Decisão alterada manualmente na busca",existing[0]))
                return {"saved":True,"already_recorded":True,"updated":True,"state":payload.state}
            # ux_jh_history_pair is unique; a distinct URL with a reused role
            # must not steal or overwrite the older entry's pair key.
            insert_pk="" if existing else pk
            cur.execute("""INSERT INTO jh_history
                (url,normalized_url,empresa,cargo,pair_key,estado,data,fonte,motivo)
                VALUES (%s,%s,%s,%s,%s,%s,TO_CHAR(CURRENT_DATE,'YYYY-MM-DD'),%s,%s)""",
                (url,uk,company,title,insert_pk,payload.state,
                 (payload.source or "Caçador")[:120],"Decisão manual na busca"))
    return {"saved":True,"already_recorded":False,"state":payload.state}

# The imported history uses both ISO dates and Brazilian DD/MM/YYYY dates.
# Normalize for filtering without rewriting any historical records.
HISTORY_DAY_SQL = """CASE WHEN data ~ '^\\d{4}-\\d{2}-\\d{2}$' THEN data
    WHEN data ~ '^\\d{2}/\\d{2}/\\d{4}$'
    THEN substring(data from 7 for 4)||'-'||substring(data from 4 for 2)||'-'||substring(data from 1 for 2)
    ELSE NULL END"""

def history_date_filters(from_date="", to_date="", dates=""):
    import re
    from datetime import date as calendar_date
    choices=[s.strip() for s in dates.split(",") if s.strip()]
    if len(choices)>100:raise HTTPException(400,"Máximo de 100 dias selecionados")
    for value in [from_date,to_date,*choices]:
        if value:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):raise ValueError()
                calendar_date.fromisoformat(value)
            except ValueError:raise HTTPException(400,"Data inválida; use AAAA-MM-DD")
    if from_date and to_date and from_date>to_date:raise HTTPException(400,"Período invertido")
    clauses=[];params=[]
    if from_date:clauses.append(f"({HISTORY_DAY_SQL}) >= %s");params.append(from_date)
    if to_date:clauses.append(f"({HISTORY_DAY_SQL}) <= %s");params.append(to_date)
    if choices:
        clauses.append(f"({HISTORY_DAY_SQL}) = ANY(%s)")
        params.append(choices)
    return clauses,params

@app.get("/api/history")
def history(request: Request, q: str="", state: str="", limit:int=50, offset:int=0,
            from_date: str="", to_date: str="", dates: str=""):
    require_auth(request)
    limit=max(1,min(limit,100));offset=max(0,offset)
    where,params=history_date_filters(from_date,to_date,dates)
    if q:
        where.append("(empresa ILIKE %s OR cargo ILIKE %s OR url ILIKE %s)")
        params.extend(["%"+q[:100]+"%"]*3)
    if state:
        if state=="Candidatado":where.append("lower(estado)='candidatado'")
        elif state=="Descartado":where.append("lower(estado) IN ('descartado','descartada')")
        else:where.append("lower(estado)=lower(%s)");params.append(state[:60])
    clause=" WHERE "+" AND ".join(where) if where else ""
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jh_history"+clause,params)
            total=cur.fetchone()[0]
            cur.execute("SELECT id,url,empresa,cargo,estado,data,fonte,motivo FROM jh_history"+clause+
                        " ORDER BY id DESC LIMIT %s OFFSET %s",params+[limit,offset])
            rows=[dict(zip(("id","url","empresa","cargo","estado","data","fonte","motivo"),r)) for r in cur.fetchall()]
    return {"total":total,"items":rows}

@app.get("/api/history-daily")
def history_daily(request: Request, from_date: str="", to_date: str="", dates: str=""):
    require_auth(request)
    where,params=history_date_filters(from_date,to_date,dates)
    where.append("lower(estado) IN ('candidatado','descartado','descartada')")
    clause=" WHERE "+" AND ".join(where)
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute(f"""SELECT ({HISTORY_DAY_SQL}) AS dia,
                    COUNT(*) FILTER (WHERE lower(estado)='candidatado')::int,
                    COUNT(*) FILTER (WHERE lower(estado) IN ('descartado','descartada'))::int
                FROM jh_history {clause}
                GROUP BY dia ORDER BY dia DESC""",params)
            rows=[{"day":d,"candidatado":a,"descartado":b} for d,a,b in cur.fetchall()]
    return {"days":rows,"candidatado":sum(v["candidatado"] for v in rows),
            "descartado":sum(v["descartado"] for v in rows)}

@app.get("/api/history-stats")
def history_stats(request: Request):
    require_auth(request)
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT lower(trim(estado)),COUNT(*) FROM jh_history GROUP BY lower(trim(estado))")
            raw=dict(cur.fetchall())
            counts={"Candidatado":raw.pop("candidatado",0),
                    "Descartado":raw.pop("descartado",0)+raw.pop("descartada",0)}
            counts.update(raw)
    return {"total":sum(counts.values()),"states":counts}

@app.post("/api/history-import")
async def history_import(request: Request):
    require_auth(request)
    body=await request.body()
    if len(body)>2_000_000:
        raise HTTPException(413,"Arquivo acima de 2 MB")
    try:
        parsed=list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    except (UnicodeDecodeError,csv.Error):
        raise HTTPException(400,"CSV inválido ou não UTF-8")
    required={"url","empresa","cargo","estado","data","fonte","motivo"}
    if not parsed or not required.issubset(parsed[0].keys()):
        raise HTTPException(400,"Colunas obrigatórias ausentes")
    if len(parsed)>20000:
        raise HTTPException(413,"Muitas linhas")
    inserted=0;duplicates=0;invalid=0
    with mu.connect(DATABASE,connect_timeout=12) as conn:
        with conn.cursor() as cur:
            for item in parsed:
                company=(item.get("empresa") or "").strip()[:300]
                title=(item.get("cargo") or "").strip()[:300]
                url=(item.get("url") or "").strip()[:2000]
                if not url and (not company or not title):
                    invalid+=1;continue
                uk=url_key(url);pk=pair_key(company,title) if company and title else ""
                cur.execute("SELECT 1 FROM jh_history WHERE (pair_key=%s AND %s<>'') OR (normalized_url=%s AND %s<>'') LIMIT 1",(pk,pk,uk,uk))
                if cur.fetchone():
                    duplicates+=1;continue
                cur.execute("""INSERT INTO jh_history(url,normalized_url,empresa,cargo,pair_key,estado,data,fonte,motivo)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
                    (url,uk,company,title,pk,*(str(item.get(k) or "")[:2000] for k in ("estado","data","fonte","motivo"))))
                if cur.fetchone():inserted+=1
                else:duplicates+=1
    return {"received":len(parsed),"inserted":inserted,"duplicates":duplicates,"invalid":invalid}

@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok":True}

# Shared cached vacancy lookup for private MCP tools and the signed DOCX download.
def _cv_source(url):
    key=url_key(url)
    if not key or len(key)>500:raise HTTPException(400,"URL da vaga inválida")
    with mu.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT description FROM jh_jd_cache WHERE normalized_url=%s",(key,))
            row=cur.fetchone()
    if not row or not row[0]:raise HTTPException(404,"Descrição da vaga ausente no cache")
    return key,row[0]


class ResumeAIRequest(BaseModel):
    url: str
    title: str
    company: str = ""
    description: str = ""
    confirmed: bool = False
    needs_verification: list[str] = []

@app.post("/api/resume/ai-download")
def ai_resume_download(payload: ResumeAIRequest, request: Request):
    """One-click AI resume download; never silently use the deterministic old CV."""
    authenticated_uid=require_auth(request)
    if mu.enabled:
        if not mu.factual_experience():
            raise HTTPException(422,"Cadastre experiências verificadas em Meu Perfil")
        if not payload.confirmed or payload.needs_verification:
            raise HTTPException(422,"Confirme a elegibilidade da vaga antes de gerar currículo")
    from ai_resume_matcher import (AIUnavailable, tailored_plan, original_evidence_plan, estimate_cost,
                                   reset_billable_usage, billable_usage)
    from score_repository import reserve, settle
    url=payload.url[:2000]
    title=payload.title[:120]
    company=payload.company[:100]
    if not url.startswith("https://") or not title:
        raise HTTPException(400,"Vaga inválida")
    print("JH_CV_STAGE stage=lookup",flush=True)
    try:
        _,jd=_cv_source(url)
    except HTTPException as error:
        if error.status_code!=404:raise
        # Reuse the full JD carried by the current search before fetching it.
        # This avoids losing JobSpy-provided Indeed descriptions when the public
        # page is blocked. No empty/sparse snippet can be treated as a full JD.
        jd=payload.description[:18000] if len(payload.description.strip())>=300 else ""
        if not jd:
            # One canonical JD fallback shared with ranking. JobSpy's exact
            # Indeed requisition match precedes the generic public-page reader.
            from jd_enrichment import fallback_public_jd
            jd=fallback_public_jd({"url":url,"title":title,"company":company}) or ""
    print(f"JH_CV_STAGE stage=jd_ready length={len(jd)}",flush=True)
    from jd_enrichment import valid_listing_jd
    if not valid_listing_jd(jd):
        print("JH_CV_REJECT code=jd_unavailable",flush=True)
        raise HTTPException(422,"Descrição integral indisponível; não é seguro gerar currículo desta vaga")
    if os.getenv("JH_AI_ENABLED")!="1" or not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(503,"Geração por IA indisponível; configure OPENAI_API_KEY e JH_AI_ENABLED=1")
    with mu.connect(DATABASE,connect_timeout=7) as conn:
        with conn.cursor() as cur:
            usage_id=reserve(cur,"resume:"+url_key(url),amount=0.015)
    if usage_id is None:
        print("JH_CV_REJECT code=budget_exhausted",flush=True)
        raise HTTPException(429,"Limite mensal de custo da IA atingido")
    reset_billable_usage()
    success=False
    try:
        print("JH_CV_STAGE stage=ai_selection",flush=True)
        plan=tailored_plan(jd,title,company)
        print(f"JH_CV_STAGE stage=ai_selected tokens={plan.get('ai_usage',{}).get('total_tokens',0)}",flush=True)
        plan["cv_build"]=os.getenv("RENDER_GIT_COMMIT","local")[:12]
        document=render_docx(plan)
        print(f"JH_CV_STAGE stage=docx_rendered bytes={len(document)}",flush=True)
        try:
            audit(plan,document)
        except AssertionError:
            # The LLM's optional bullet wording can collide with another
            # factual line in the complete CV. Keep the AI's fact selection,
            # restore exact source wording and run the same strict audit.
            if (not plan.get("bullet_provenance") and
                    plan.get("summary")==plan.get("source_summary")):
                raise
            print("JH_CV_STAGE stage=restore_original_evidence",flush=True)
            plan=original_evidence_plan(plan)
            document=render_docx(plan)
            audit(plan,document)
        print("JH_CV_STAGE stage=factual_audit_passed",flush=True)
        quality=evaluate_rendered_resume(plan,document,jd)
        if not quality["factual_ok"]:
            print("JH_CV_REJECT code=quality_factual",flush=True)
            raise HTTPException(422,"Auditoria de fatos do currículo reprovada")
        success=True
        print("JH_CV_SUCCESS",flush=True)
    except AIUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
    except (ValueError,AssertionError) as exc:
        # Internal account ID and validation code only: no job description,
        # resume text, name or email is logged.
        print(f"JH_CV_REJECT code=validation user_id={authenticated_uid if mu.enabled else 'legacy'} "
              f"type={type(exc).__name__} reason={str(exc)[:160]}",flush=True)
        if isinstance(exc,ValueError) and str(exc)=="IA não selecionou nenhuma evidência verificada":
            raise HTTPException(422,"A IA não selecionou evidências profissionais desta vaga; tente outra vaga ou revise as experiências verificadas no perfil") from exc
        raise HTTPException(422,"IA não produziu currículo factual auditável") from exc
    except urllib.error.HTTPError as exc:
        raise HTTPException(502,"Provedor de IA indisponível") from exc
    finally:
        # Reservation is a ceiling, not a charge. Failed validation can occur
        # after the provider bills tokens, so account for returned usage even
        # when no usable plan was produced. No response means no known charge.
        cost=min(0.015,estimate_cost(billable_usage()))
        with mu.connect(DATABASE,connect_timeout=7) as conn:
            with conn.cursor() as cur:
                settle(cur,usage_id,cost,success)
    safe=lambda v:re.sub(r"[^\wÀ-ÿ -]","",v).strip()[:75]
    name=(safe(mu.current_profile.get().get("name","")) if mu.enabled else "Olinto Manso Pereira")+" - "+safe(title)+" - "+safe(company or "Empresa")+".docx"
    from urllib.parse import quote
    return StreamingResponse(io.BytesIO(document),
       media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
       headers={"Content-Disposition":f"attachment; filename*=UTF-8''{quote(name)}",
                "Cache-Control":"no-store","X-CV-Mode":"ai_resume_matcher_evidence_v1"})


@app.get("/api/gpt-action/download")
def gpt_cv_download(ticket:str):
    if mu.enabled:raise HTTPException(403,"Gerador legado indisponível para múltiplas contas")
    from resume_engine import EXPERIENCE
    if not serializer:raise HTTPException(503,"Assinatura indisponível")
    try:payload=serializer.loads(ticket,salt="cv-action-download-v1",max_age=900)
    except (BadSignature,SignatureExpired):raise HTTPException(401,"Link expirado ou inválido")
    key,jd=_cv_source(payload.get("url",""))
    if hashlib.sha256(jd.encode()).hexdigest()!=payload.get("jd_hash"):
        raise HTTPException(409,"Descrição da vaga alterada")
    ids=payload.get("ids",[])
    if not isinstance(ids,list) or not 1<=len(ids)<=24 or len(ids)!=len(set(ids)):
        raise HTTPException(400,"Seleção inválida")
    allowed={f"{i}:{j}":(i,f) for i,e in enumerate(EXPERIENCE) for j,f in enumerate(e["facts"])}
    if any(x not in allowed for x in ids):raise HTTPException(400,"Evidência desconhecida")
    plan=build_plan(jd,payload.get("title","") or "Vaga selecionada")
    selected={}
    for id_ in ids:
        i,f=allowed[id_]
        selected.setdefault(i,[]).append(f)
    plan["experience"]=[{"role":EXPERIENCE[i]["role"],"company":EXPERIENCE[i]["company"],
                         "dates":EXPERIENCE[i]["dates"],"facts":facts,"source_index":i}
                        for i,facts in sorted(selected.items())]
    plan["additional_experience"]=[{"role":row["role"],"company":row["company"],
                                    "dates":row["dates"],"source_index":i}
                                   for i,row in enumerate(EXPERIENCE) if i not in selected]
    plan["cv_mode"]="gpt_action_verified_facts"
    plan["cv_build"]=os.getenv("RENDER_GIT_COMMIT","local")[:12]
    data=render_docx(plan)
    audit(plan,data)
    quality=evaluate_rendered_resume(plan,data,jd)
    if not quality["factual_ok"]:raise HTTPException(422,"Falha na auditoria factual")
    safe=lambda v:re.sub(r"[^\wÀ-ÿ -]","",v).strip()[:75]
    filename="Olinto Manso Pereira - "+safe(payload.get("title","Vaga"))+" - "+safe(payload.get("company","Empresa"))+".docx"
    from urllib.parse import quote
    return StreamingResponse(io.BytesIO(data),media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      headers={"Content-Disposition":f"attachment; filename*=UTF-8''{quote(filename)}",
               "Cache-Control":"no-store","X-CV-Mode":"gpt_action_verified_facts"})

@app.get("/api/status")
def status(request: Request):
    require_auth(request)
    if not DATABASE:
        return {"database":"not_configured","mode":"phase2"}
    try:
        with mu.connect(DATABASE, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
        return {"database":"connected","mode":"phase2"}
    except Exception:
        return {"database":"unavailable","mode":"phase1","history":"not_imported"}

if DIST.is_dir():
    app.mount("/assets",StaticFiles(directory=DIST/"assets"),name="assets")

@app.get("/{path:path}")
def home(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    target=(DIST/path).resolve()
    if DIST.is_dir() and target.is_file() and target.is_relative_to(DIST.resolve()):
        return FileResponse(target)
    if (DIST/"index.html").exists():
        return FileResponse(DIST/"index.html",headers={"Cache-Control":"no-store, max-age=0, must-revalidate","Pragma":"no-cache"})
    return JSONResponse({"detail":"Build React não encontrado"},status_code=503)
