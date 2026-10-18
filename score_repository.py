"""Persistent versioned scoring and transactional API spend reservations."""
import hashlib
import json
import os
from datetime import datetime,timezone
from psycopg.types.json import Jsonb
PROFILE_VERSION="profile-oct-2026"
RUBRIC_VERSION="block4.1-v1"
MONTHLY_CAP_USD=5.0
MAX_REQUEST_USD=0.002
def key_for(roles):return hashlib.sha256(roles.encode()).hexdigest()
def get_cached(cur,url,jd_hash,roles):
    require_hybrid=os.getenv('JH_AI_ENABLED')=='1' and bool(os.getenv('OPENAI_API_KEY'))
    cur.execute("""SELECT result FROM jh_score_cache WHERE normalized_url=%s AND jd_hash=%s
        AND profile_version=%s AND rubric_version=%s AND roles_hash=%s
        AND (%s=FALSE OR model='hybrid')""",
        (url,jd_hash,PROFILE_VERSION,RUBRIC_VERSION,key_for(roles),require_hybrid))
    item=cur.fetchone();return item[0] if item else None
def save(cur,url,jd_hash,roles,result,model):
    cur.execute("""INSERT INTO jh_score_cache
        (normalized_url,jd_hash,profile_version,rubric_version,roles_hash,result,model)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (normalized_url,jd_hash,profile_version,rubric_version,roles_hash)
        DO UPDATE SET result=EXCLUDED.result,model=EXCLUDED.model,created_at=NOW()""",
        (url,jd_hash,PROFILE_VERSION,RUBRIC_VERSION,key_for(roles),Jsonb(result),model))
def reserve(cur,url,amount=MAX_REQUEST_USD):
    period=datetime.now(timezone.utc).strftime("%Y-%m")
    cur.execute("""INSERT INTO jh_ai_budget(period) VALUES (%s) ON CONFLICT DO NOTHING""",(period,))
    cur.execute("SELECT reserved_usd,spent_usd FROM jh_ai_budget WHERE period=%s FOR UPDATE",(period,))
    pending,spent=cur.fetchone()
    if float(pending)+float(spent)+amount>MONTHLY_CAP_USD:return None
    cur.execute("UPDATE jh_ai_budget SET reserved_usd=reserved_usd+%s WHERE period=%s",(amount,period))
    cur.execute("""INSERT INTO jh_ai_usage(normalized_url,period,reserved_usd,state)
        VALUES(%s,%s,%s,'reserved') RETURNING id""",(url,period,amount))
    return cur.fetchone()[0]
def settle(cur,usage_id,actual,successful):
    cur.execute("SELECT period,reserved_usd FROM jh_ai_usage WHERE id=%s FOR UPDATE",(usage_id,))
    row=cur.fetchone()
    if not row:return
    period,reserved=row
    cur.execute("""UPDATE jh_ai_budget SET reserved_usd=reserved_usd-%s,
        spent_usd=spent_usd+%s WHERE period=%s""",(reserved,actual,period))
    cur.execute("UPDATE jh_ai_usage SET actual_usd=%s,state=%s WHERE id=%s",
        (actual,"ok" if successful else "error",usage_id))
