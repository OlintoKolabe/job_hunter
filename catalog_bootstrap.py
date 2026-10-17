"""Bounded catalog bootstrap on Render; checkpoint per ATS in Neon.

Starts only when JH_CATALOG_BOOTSTRAP=1.  A single PostgreSQL advisory lock
prevents duplicate runs. A verified record is written only after an actual
network attempt. Zero matches from JS-only sources remain 'pendente'.
"""
import os
import logging
import threading
from datetime import datetime, timezone
import psycopg
from catalog_engine import scan

LOGGER=logging.getLogger("jobhunter.catalog")
LOCK_ID=730301

def run_bootstrap(db_url):
    conn=None
    try:
        conn=psycopg.connect(db_url,connect_timeout=12,autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)",(LOCK_ID,))
            locked=cur.fetchone()[0]
        if not locked:
            LOGGER.info("catalog sweep skipped: another instance owns the lock")
            return
        LOGGER.info("catalog sweep started")
        with conn.cursor() as cur:
            cur.execute("SELECT source,slug FROM jh_catalog_source")
            tasks=set(cur.fetchall())
        from catalog_engine import source_tasks
        tasks.update(source_tasks())
        tasks=sorted((s,v) for s,v in tasks if v.casefold() not in ("kraken","kraken.com","payward"))
        with conn.cursor() as cur:
            cur.execute("SELECT source,slug FROM jh_catalog_checks")
            done=set(cur.fetchall())
        priority=os.environ.get("JH_BR_VERIFY","0")=="1"
        if priority:
            remaining=[t for t in tasks if t[0] in ("inhire","quickin","gupy")]
        else:
            remaining=[t for t in tasks if t not in done]
        LOGGER.info("catalog sweep targets=%d already_checked=%d remaining=%d",len(tasks),len(tasks)-len(remaining),len(remaining))
        for index in range(0,len(remaining),8):
            chunk=remaining[index:index+8]
            details,_=scan(chunk,workers=4)
            with conn.cursor() as cur:
                for d in details:
                    cur.execute("""INSERT INTO jh_catalog_checks(source,slug,state,received,error,checked_at)
                      VALUES(%s,%s,%s,%s,%s,now()) ON CONFLICT(source,slug) DO UPDATE SET
                      state=EXCLUDED.state,received=EXCLUDED.received,error=EXCLUDED.error,checked_at=now()""",
                      (d["source"],d["slug"],d["state"],d["received"],d.get("error","")))
            LOGGER.info("catalog sweep checkpoint %d/%d; verified=%d",min(index+8,len(remaining)),len(remaining),len(details))
        LOGGER.info("catalog sweep complete targets=%d",len(tasks))
    except Exception:
        LOGGER.exception("catalog sweep interrupted; checkpoints retained")
    finally:
        if conn:
            try:
                with conn.cursor() as cur:cur.execute("SELECT pg_advisory_unlock(%s)",(LOCK_ID,))
            except Exception:pass
            conn.close()

def maybe_start(db_url):
    if (os.environ.get("JH_CATALOG_BOOTSTRAP")!="1" and os.environ.get("JH_BR_VERIFY")!="1") or not db_url:
        return
    thread=threading.Thread(target=run_bootstrap,args=(db_url,),daemon=True,name="catalog-bootstrap")
    thread.start()
