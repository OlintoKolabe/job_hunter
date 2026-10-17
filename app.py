import os
import secrets
import json
import re
import urllib.request
import urllib.error
import urllib.parse
import csv
import io
import hashlib
import unicodedata
from urllib.parse import urlsplit

from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel
import psycopg
from collectors import collect
from catalog_engine import source_tasks,scan

app = FastAPI(docs_url=None, redoc_url=None)
DIST = Path(__file__).resolve().parent / "dist"
COOKIE = "jh_session"
SECRET = os.environ.get("APP_SECRET", "")
PASSWORD = os.environ.get("APP_PASSWORD", "")
DATABASE = os.environ.get("DATABASE_URL", "")
serializer = URLSafeTimedSerializer(SECRET) if SECRET else None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class Credentials(BaseModel):
    password: str

def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()

def auth_record():
    with psycopg.connect(DATABASE, connect_timeout=8) as conn:
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

def pair_key(empresa,cargo):
    return " ".join(normalized(empresa).split())+"|"+ " ".join(normalized(cargo).split())

@app.get("/health")
def health():
    return {"service":"job-hunter","alive":True}

@app.get("/api/me")
def me(request: Request):
    require_auth(request)
    return {"authenticated":True}

@app.post("/api/login")
def login(payload: Credentials, response: Response):
    if not serializer or not DATABASE:
        raise HTTPException(503, "Acesso não configurado")
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
    require_auth(request)
    if len(payload.new_password)<12 or len(payload.new_password)>128:
        raise HTTPException(400,"A nova senha deve ter entre 12 e 128 caracteres")
    if secrets.compare_digest(payload.current_password,payload.new_password):
        raise HTTPException(400,"A nova senha deve ser diferente")
    with psycopg.connect(DATABASE,connect_timeout=8) as conn:
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

@app.post("/api/search-jobs")
def search_jobs(request: Request):
    require_auth(request)
    items,sources=collect()
    with psycopg.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            keys=[url_key(j["url"]) for j in items]
            known_urls=set()
            known_pairs=set()
            if keys:
                cur.execute("SELECT normalized_url FROM jh_history WHERE normalized_url=ANY(%s)",(keys,))
                known_urls={row[0] for row in cur.fetchall()}
            pairs=[pair_key(j["company"],j["title"]) for j in items if j["company"]]
            if pairs:
                cur.execute("SELECT pair_key FROM jh_history WHERE pair_key=ANY(%s)",(pairs,))
                known_pairs={row[0] for row in cur.fetchall()}
    fresh=[j for j in items if not any(b in normalized(j["company"]) for b in ("kraken","payward")) and url_key(j["url"]) not in known_urls and
           (not j["company"] or pair_key(j["company"],j["title"]) not in known_pairs)]
    return {"source":"Multifuente","queried":len(sources),"total":len(items),
        "new":len(fresh),"duplicates":len(items)-len(fresh),"items":fresh[:100],"details":sources,
        "notice":"Vagas coletadas, ainda sem triagem de elegibilidade Brasil/remoto ou score."}




SOURCE_CADENCE_DAYS={"inhire":3,"quickin":3,"dynamite":3,"greenhouse":7,"greenhouse_eu":30,
 "ashby":7,"lever":7,"gupy":7,"linkedin_guest":7,"teamtailor":14,"recruitee":30,
 "smartrecruiters":30,"workable_account":7,"personio":30,"bamboohr":30,
 "zoho":30,"trakstar":30,"compleo":30,"solides":30}

def source_freshness(source, checked_at):
    from datetime import datetime,timezone,timedelta
    days=SOURCE_CADENCE_DAYS.get(source,30)
    if not checked_at:return {"interval_days":days,"due":True,"next_check":None}
    next_time=checked_at+timedelta(days=days)
    return {"interval_days":days,"due":next_time<=datetime.now(timezone.utc),
            "next_check":next_time.isoformat()}

def active_source_tasks():
    tasks=set(source_tasks())
    with psycopg.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source,slug FROM jh_catalog_source")
            tasks.update(cur.fetchall())
    return sorted((source,slug) for source,slug in tasks if slug.casefold() not in ("kraken","kraken.com","payward"))

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
    with psycopg.connect(DATABASE,connect_timeout=10) as conn:
        with conn.cursor() as cur:
            for ats,slug in sorted(imported):
                cur.execute("INSERT INTO jh_catalog_source(source,slug) VALUES(%s,%s) ON CONFLICT DO NOTHING",(ats,slug))
    return {"imported":len(imported),"total_active":len(active_source_tasks())}

@app.get("/api/catalog")
def catalog(request: Request):
    require_auth(request)
    from collections import Counter
    tasks=active_source_tasks()
    with psycopg.connect(DATABASE,connect_timeout=8) as conn:
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
              "Scrapling":"sem ponte MCP no Render","Indeed":"MCP disponível apenas no ChatGPT",
              "Nimble":"exige acesso autenticado e quota","Firecrawl":"exige chave e quota no Render"}}

@app.get("/api/catalog/checks")
def catalog_checks(request: Request):
    require_auth(request)
    with psycopg.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source,slug,state,received,error,checked_at::text FROM jh_catalog_checks ORDER BY checked_at DESC LIMIT 500")
            rows=[dict(zip(("source","slug","state","received","error","checked_at"),r)) for r in cur.fetchall()]
    return {"total":len(rows),"items":rows}

@app.post("/api/catalog/scan")
def catalog_scan(request: Request, offset:int=0,limit:int=12):
    require_auth(request)
    tasks=active_source_tasks()
    offset=max(0,min(offset,len(tasks)))
    limit=max(1,min(limit,15))
    batch=tasks[offset:offset+limit]
    details,found=scan(batch,workers=6)
    unique={}
    pairset=set()
    for job in found:
        key=url_key(job["url"])
        pair=pair_key(job["company"],job["title"]) if job["company"] else ""
        if not key or key in unique or (pair and pair in pairset):continue
        unique[key]=job
        if pair:pairset.add(pair)
    items=list(unique.values())
    urls=[url_key(v["url"]) for v in items]
    pairs=[pair_key(v["company"],v["title"]) for v in items if v["company"]]
    known_urls=set();known_pairs=set()
    with psycopg.connect(DATABASE,connect_timeout=7) as conn:
        with conn.cursor() as cur:
            for entry in details:
                cur.execute("""INSERT INTO jh_catalog_checks(source,slug,state,received,error)
                    VALUES(%s,%s,%s,%s,%s) ON CONFLICT(source,slug) DO UPDATE SET
                    state=EXCLUDED.state,received=EXCLUDED.received,error=EXCLUDED.error,checked_at=now()""",
                    (entry["source"],entry["slug"],entry["state"],entry["received"],entry.get("error","")))
            if urls:
                cur.execute("SELECT normalized_url FROM jh_history WHERE normalized_url=ANY(%s)",(urls,))
                known_urls={r[0] for r in cur.fetchall()}
            if pairs:
                cur.execute("SELECT pair_key FROM jh_history WHERE pair_key=ANY(%s)",(pairs,))
                known_pairs={r[0] for r in cur.fetchall()}
    fresh=[j for j in items if url_key(j["url"]) not in known_urls and (not j["company"] or pair_key(j["company"],j["title"]) not in known_pairs)]
    return {"total_sources":len(tasks),"offset":offset,"next_offset":offset+len(batch),
            "complete":offset+len(batch)>=len(tasks),"details":details,
            "found":len(items),"new":len(fresh),"duplicates":len(items)-len(fresh),
            "items":fresh[:80],"notice":"Vagas candidatas: remoto/Brasil e requisitos ainda aguardam análise completa."}

@app.get("/api/history")
def history(request: Request, q: str="", state: str="", limit:int=50, offset:int=0):
    require_auth(request)
    limit=max(1,min(limit,100));offset=max(0,offset)
    where=[];params=[]
    if q:
        where.append("(empresa ILIKE %s OR cargo ILIKE %s OR url ILIKE %s)")
        params.extend(["%"+q[:100]+"%"]*3)
    if state:
        where.append("estado=%s");params.append(state[:60])
    clause=" WHERE "+" AND ".join(where) if where else ""
    with psycopg.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jh_history"+clause,params)
            total=cur.fetchone()[0]
            cur.execute("SELECT id,url,empresa,cargo,estado,data,fonte,motivo FROM jh_history"+clause+" ORDER BY id DESC LIMIT %s OFFSET %s",params+[limit,offset])
            rows=[dict(zip(("id","url","empresa","cargo","estado","data","fonte","motivo"),r)) for r in cur.fetchall()]
    return {"total":total,"items":rows}

@app.get("/api/history-stats")
def history_stats(request: Request):
    require_auth(request)
    with psycopg.connect(DATABASE,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT estado,COUNT(*) FROM jh_history GROUP BY estado")
            counts=dict(cur.fetchall())
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
    with psycopg.connect(DATABASE,connect_timeout=12) as conn:
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

@app.get("/api/status")
def status(request: Request):
    require_auth(request)
    if not DATABASE:
        return {"database":"not_configured","mode":"phase2"}
    try:
        with psycopg.connect(DATABASE, connect_timeout=5) as conn:
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
        return FileResponse(DIST/"index.html")
    return JSONResponse({"detail":"Build React não encontrado"},status_code=503)
