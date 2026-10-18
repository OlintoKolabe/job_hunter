"""Persistent versioned scoring and transactional API spend reservations."""
import hashlib
import json
import os
from datetime import datetime,timezone,timedelta
from psycopg.types.json import Jsonb
PROFILE_VERSION="profile-oct-2026"
RUBRIC_VERSION="block4.1-v5-professional-core"
MONTHLY_CAP_USD=5.0
MAX_REQUEST_USD=0.002
def key_for(roles):return hashlib.sha256(roles.encode()).hexdigest()
def get_cached(cur,url,jd_hash,roles):
    require_hybrid=os.getenv('JH_AI_ENABLED')=='1' and bool(os.getenv('OPENAI_API_KEY'))
    cur.execute("""SELECT result,model,created_at FROM jh_score_cache WHERE normalized_url=%s AND jd_hash=%s
        AND profile_version=%s AND rubric_version=%s AND roles_hash=%s
        AND (%s=FALSE OR model IN ('hybrid','ai_error','hard_exclusion'))""",
        (url,jd_hash,PROFILE_VERSION,RUBRIC_VERSION,key_for(roles),require_hybrid))
    item=cur.fetchone()
    if not item:return None
    result=item[0]
    if not isinstance(result,dict):return None
    if item[1]=='ai_error':return result
    return result if result.get('score') is not None or (require_hybrid and item[1]=='hybrid') else None
def get_previous_semantic(cur,url,jd_hash,roles):
    """Re-score already paid-for extraction after a rubric change; never call AI."""
    cur.execute("""SELECT result FROM jh_score_cache WHERE normalized_url=%s AND jd_hash=%s
        AND profile_version=%s AND rubric_version=%s AND roles_hash=%s
        AND model='hybrid'""",
        (url,jd_hash,PROFILE_VERSION,"block4.1-v4-transferable-evidence",key_for(roles)))
    row=cur.fetchone()
    if not isinstance(row,(tuple,list)) or len(row)<1 or not isinstance(row[0],dict):return None
    requirements=row[0].get("requirements") or []
    if not isinstance(requirements,list) or not requirements:return None
    return [{"name":r.get("name"),"type":r.get("type"),
             "skill_id":r.get("evidence_id") if isinstance(r.get("evidence_id"),str) and r.get("evidence_id") in __import__("block4_score").SKILLS else None,"relationship":r.get("match_level")}
            for r in requirements if isinstance(r,dict)]

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
