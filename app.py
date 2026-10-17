import os
import secrets
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel
import psycopg

app = FastAPI(docs_url=None, redoc_url=None)
DIST = Path(__file__).resolve().parent / "dist"
COOKIE = "jh_session"
SECRET = os.environ.get("APP_SECRET", "")
PASSWORD = os.environ.get("APP_PASSWORD", "")
DATABASE = os.environ.get("DATABASE_URL", "")
serializer = URLSafeTimedSerializer(SECRET) if SECRET else None

class Credentials(BaseModel):
    password: str

def require_auth(request: Request):
    if not (serializer and PASSWORD):
        raise HTTPException(503, "A autenticação ainda não foi configurada")
    value = request.cookies.get(COOKIE)
    try:
        user = serializer.loads(value or "", max_age=60*60*24*7)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Acesso não autorizado")
    if user != "owner":
        raise HTTPException(401, "Acesso não autorizado")

@app.get("/health")
def health():
    return {"service":"job-hunter","alive":True}

@app.get("/api/me")
def me(request: Request):
    require_auth(request)
    return {"authenticated":True}

@app.post("/api/login")
def login(payload: Credentials, response: Response):
    if not (serializer and PASSWORD):
        raise HTTPException(503, "Senha não configurada no servidor")
    if not secrets.compare_digest(payload.password, PASSWORD):
        raise HTTPException(401, "Senha incorreta")
    response.set_cookie(COOKIE, serializer.dumps("owner"), httponly=True, secure=True, samesite="lax", max_age=604800)
    return {"authenticated":True}

@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok":True}

@app.get("/api/status")
def status(request: Request):
    require_auth(request)
    if not DATABASE:
        return {"database":"not_configured","mode":"phase1","history":"not_imported"}
    try:
        with psycopg.connect(DATABASE, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
        return {"database":"connected","mode":"phase1","history":"not_imported"}
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
