"""Isolated accounts for the multiuser canary.

Only the canary sets JH_MULTIUSER=1. Existing single-user deployments keep
their previous authentication and database behavior.
"""
import os
import re
import secrets
import hashlib
from collections.abc import Sequence, Mapping
from contextvars import ContextVar
import psycopg
from psycopg.types.json import Jsonb

enabled = os.getenv("JH_MULTIUSER") == "1"
current_uid = ContextVar("jh_multiuser_id", default=None)
current_profile = ContextVar("jh_multiuser_profile", default=None)
PRIVATE_TABLES = ("jh_history", "jh_seen_jobs", "jh_score_cache", "jh_ai_budget", "jh_ai_usage")


def experience_integrity_issues(rows):
    """Fail closed on demonstrably broken employer/role attribution.

    This is not an AI quality score. It catches malformed imported headers;
    ambiguous career claims still require the candidate's explicit review.
    """
    issues = []
    duration = re.compile(r"(?i)^\d+\s+(?:anos?|years?|m[eê]s(?:es)?|months?)(?:\s+(?:e\s+)?\d+\s+(?:m[eê]s(?:es)?|months?))?$")
    technology = re.compile(r"(?i)\b(?:posthog|codex|claude code|lovable|figma|jira|confluence|trello|power bi)\b")
    prose = re.compile(r"(?i)\b(?:para otimizar|maximizar receitas|entre as principais atividades|atuação como|focando na)\b")
    employers=[str(row.get("company") or "").strip() for row in rows or []]
    for idx, row in enumerate(rows or []):
        if row.get("verified") is not True:
            continue
        company = str(row.get("company") or "").strip()
        role = str(row.get("role") or "").strip()
        facts = row.get("facts") or []
        if (not company or not role or duration.fullmatch(company)
            or company.casefold().startswith(("stacks:", "skills:", "competências:"))
            or (len(company.split(",")) >= 2 and technology.search(company))
            or prose.search(company) or len(company) > 100):
            issues.append(idx)
        if not isinstance(facts,list) or any(not isinstance(f,str) for f in facts):
            issues.append(idx)
            continue
        for other in employers:
            if not other or other.casefold()==company.casefold() or len(other)<4:
                continue
            # The source claims to work *at* another listed employer. This is
            # a strong indicator that LinkedIn boundaries were misplaced.
            at_other=re.compile(r"(?i)\b(?:na|no|at|within)\s+"+re.escape(other)+r"\b.{0,50}\b(?:atu|work|trabalh|exerc|desempenh)")
            if any(at_other.search(f) for f in facts):
                issues.append(idx)
                break
    return sorted(set(issues))


def digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()


def public_connect(db_url, **kwargs):
    return psycopg.connect(db_url, **kwargs)


def connect(db_url, **kwargs):
    uid = current_uid.get()
    if not enabled:
        return public_connect(db_url, **kwargs)
    if uid is None:
        raise PermissionError("Authenticated user context is required for private data")
    # IDs are sourced from database BIGSERIAL and verified signed sessions.
    schema = "jh_user_" + str(int(uid))
    if not re.fullmatch(r"jh_user_[0-9]+", schema):
        raise ValueError("Invalid tenant schema")
    if "options" in kwargs:
        raise ValueError("Conflicting connection options")
    # Neon pooling should receive the same connection parameters as the
    # already-proven public connection. Set the tenant path on the acquired
    # connection, before any user-owned query executes.
    conn = public_connect(db_url, **kwargs)
    try:
        conn.execute('SET search_path TO "' + schema + '", public')
    except Exception:
        conn.close()
        raise
    return conn


def provision_schema(cursor, user_id):
    schema = "jh_user_" + str(int(user_id))
    cursor.execute('CREATE SCHEMA "' + schema + '"')
    for table in PRIVATE_TABLES:
        cursor.execute('CREATE TABLE "' + schema + '"."' + table +
                       '" (LIKE public."' + table + '" INCLUDING ALL)')
    # LIKE INCLUDING ALL copies serial defaults referencing the original
    # sequence; replace them with independent per-tenant sequences.
    for table in ("jh_history", "jh_ai_usage"):
        seq = table + "_id_seq"
        cursor.execute('CREATE SEQUENCE "' + schema + '"."' + seq + '"')
        cursor.execute('ALTER TABLE "' + schema + '"."' + table +
                       '" ALTER COLUMN id SET DEFAULT nextval(\'' + schema + '.' + seq + '\'::regclass)')
        cursor.execute('ALTER SEQUENCE "' + schema + '"."' + seq +
                       '" OWNED BY "' + schema + '"."' + table + '".id')


def create_account(db_url, email, password, name):
    email = email.strip().casefold()
    name = name.strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        raise ValueError("Email inválido")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("A senha precisa ter 12 a 128 caracteres")
    if not 2 <= len(name) <= 120:
        raise ValueError("Informe seu nome")
    salt = secrets.token_hex(16)
    with public_connect(db_url, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.jh_users(email,name,password_hash,password_salt,profile)
                VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (email, name, digest(password, salt), salt, Jsonb({
                    "name": name, "email": email, "location": "", "phone": "",
                    "linkedin": "", "summary": "", "experience": [],
                    "education": [], "skills": [], "certifications": [],
                    "languages": [], "roles": [], "country": "BR",
                    "mode": "remote", "seniority": "", "days": 7
                })))
            user_id = cur.fetchone()[0]
            provision_schema(cur, user_id)
    return user_id


def authenticate(db_url, email, password):
    with public_connect(db_url, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,password_hash,password_salt,session_version
                FROM public.jh_users WHERE email=%s AND active=true""",
                (email.strip().casefold(),))
            rec = cur.fetchone()
    if not rec or not secrets.compare_digest(digest(password, rec[2]), rec[1]):
        return None
    return (rec[0], rec[3])


def get_user(db_url, uid):
    with public_connect(db_url, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,name,email,profile,session_version
                FROM public.jh_users WHERE id=%s AND active=true""",(int(uid),))
            rec = cur.fetchone()
    return rec


def set_context(user):
    current_uid.set(user[0])
    current_profile.set(user[3] or {})


def update_profile(db_url, uid, profile):
    with public_connect(db_url, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.jh_users SET profile=%s,name=%s,updated_at=now()
                WHERE id=%s AND active=true""",
                (Jsonb(profile),profile["name"],int(uid)))
            if cur.rowcount != 1:
                raise ValueError("Conta não encontrada")
    current_profile.set(profile)


def change_password(db_url, uid, current, new):
    if not 12 <= len(new) <= 128 or secrets.compare_digest(current,new):
        raise ValueError("Senha nova inválida")
    with public_connect(db_url, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT password_hash,password_salt,session_version
                FROM public.jh_users WHERE id=%s FOR UPDATE""",(int(uid),))
            rec = cur.fetchone()
            if not rec or not secrets.compare_digest(digest(current,rec[1]),rec[0]):
                raise ValueError("Senha atual incorreta")
            salt=secrets.token_hex(16)
            version=rec[2]+1
            cur.execute("""UPDATE public.jh_users SET password_hash=%s,password_salt=%s,
                session_version=%s,updated_at=now() WHERE id=%s""",
                (digest(new,salt),salt,version,int(uid)))
    return version


def factual_experience():
    profile = current_profile.get() or {}
    if experience_integrity_issues(profile.get("experience", [])):
        # Never pass partially contaminated career records to the CV model.
        return []
    result = []
    for item in profile.get("experience", []):
        # Verified profile entries may contain PDF fragments (e.g. a city or a
        # single skill). Preserve the saved profile, but do not treat those
        # fragments as auditable professional achievements in an ATS CV.
        facts = [text for f in item.get("facts",[])
                 if (text := str(f).strip()) and len(text) >= 18
                 and len(text.split()) >= 3]
        if item.get("verified") is True and facts:
            result.append({"role":str(item.get("role") or "")[:140],
                           "company":str(item.get("company") or "")[:140],
                           "dates":str(item.get("dates") or "")[:100],
                           "facts":facts})
    return result


class ProfileSequence(Sequence):
    def __init__(self, legacy, getter):
        self.legacy = legacy
        self.getter = getter
    def _items(self):
        return self.getter() if enabled else self.legacy
    def __getitem__(self, index):
        return self._items()[index]
    def __len__(self):
        return len(self._items())
    def __iter__(self):
        return iter(self._items())


class ProfileContact(Mapping):
    def __init__(self, legacy):
        self.legacy = legacy
    def _contact(self):
        if not enabled:
            return self.legacy
        p = current_profile.get() or {}
        return {k:str(p.get(k) or "") for k in ("name","email","location","phone","linkedin")}
    def __getitem__(self,key):
        return self._contact()[key]
    def __iter__(self):
        return iter(self._contact())
    def __len__(self):
        return len(self._contact())


def profile_education():
    p = current_profile.get() or {}
    name = str(p.get("name") or "").casefold().strip()
    name_words = [x for x in re.findall(r"\w+", name) if len(x) > 1]
    skills = {str(x).casefold().strip() for x in p.get("skills", [])}
    sidebar_technologies = {"python", "sql", "databricks", "power bi", "pyspark",
                            "spark", "streamlit", "n8n", "generative ai & process automation"}
    output = []
    for collection in (p.get("education", []), p.get("certifications", [])):
      for raw in collection:
        item = str(raw).strip(" •·\t\n")
        key = item.casefold()
        words = [x for x in re.findall(r"\w+", key) if len(x) > 1]
        # A LinkedIn footer often repeats an abbreviated display name, then
        # places headline, skill tags and location inside certifications.
        repeated_name = (len(name_words) >= 2 and len(words) >= 2 and
                         words[:2] == name_words[:2] and
                         sum(w in name_words for w in words) >= min(3,len(words)) and
                         sum(w in name_words for w in words)/len(words) >= .75)
        if repeated_name:
            break
        if (len(item) < 4 or key == name or key in skills or
            key in sidebar_technologies or "@" in item or
            "linkedin.com" in key or key.startswith("data scientist &")):
            continue
        if output and re.search(r"(?i)\b(?:com|meu|de|with|for)$",output[-1]):
            output[-1] += " " + item
            continue
        output.append(item)
    return output
