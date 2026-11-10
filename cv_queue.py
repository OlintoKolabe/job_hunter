"""Durable ATS resume queue backed by the existing PostgreSQL.

The browser only enqueues and polls. Each job is stored with its owner and
processed outside the request; row-level SKIP LOCKED claims bound AI concurrency.
"""
import logging
import threading
import time
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

LOG = logging.getLogger("jh.cv_queue")
_STALE_AFTER = "30 minutes"
_started = False
_guard = threading.Lock()
_schema_guard = threading.Lock()
_schema_ready = False


def _db(db_url, mu):
    return mu.public_connect(db_url, connect_timeout=8)


def ensure_schema(db_url, mu):
    with _db(db_url, mu) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.jh_cv_queue (
                    id uuid PRIMARY KEY,
                    owner_id bigint NOT NULL,
                    payload jsonb NOT NULL,
                    status text NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','running','ready','failed')),
                    filename text,
                    docx bytea,
                    error text,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    started_at timestamptz,
                    finished_at timestamptz,
                    attempts integer NOT NULL DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS jh_cv_queue_owner_created_idx
                ON public.jh_cv_queue (owner_id, created_at DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS jh_cv_queue_claim_idx
                ON public.jh_cv_queue (status, created_at)
            """)


def enqueue(db_url, mu, owner, payload):
    job_id = str(uuid4())
    with _db(db_url, mu) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO public.jh_cv_queue (id, owner_id, payload)
                VALUES (%s,%s,%s)
            """, (job_id, owner, Jsonb(payload)))
    return job_id


def list_jobs(db_url, mu, owner):
    with _db(db_url, mu) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id::text, status, payload->>'title', payload->>'company',
                       filename, error, created_at, finished_at, started_at
                FROM public.jh_cv_queue WHERE owner_id=%s
                ORDER BY created_at DESC LIMIT 100
            """, (owner,))
            rows = cur.fetchall()
    return [
        {"id":r[0], "status":r[1], "title":r[2], "company":r[3],
         "filename":r[4], "error":r[5],
         "created_at":r[6].isoformat(), "finished_at":r[7].isoformat() if r[7] else None,
         "started_at":r[8].isoformat() if r[8] else None}
        for r in rows
    ]


def get_document(db_url, mu, owner, job_id):
    with _db(db_url, mu) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, filename, docx FROM public.jh_cv_queue
                WHERE owner_id=%s AND id=%s
            """, (owner, job_id))
            return cur.fetchone()


def delete_job(db_url, mu, owner, job_id):
    """Permanently remove only non-running jobs owned by this account."""
    with _db(db_url, mu) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM public.jh_cv_queue
                WHERE owner_id=%s AND id=%s
                  AND status IN ('queued','ready','failed')
                RETURNING id
            """, (owner, job_id))
            if cur.fetchone():
                return "deleted"
            cur.execute("""
                SELECT status FROM public.jh_cv_queue
                WHERE owner_id=%s AND id=%s
            """, (owner, job_id))
            return "running" if cur.fetchone() else "missing"


def delete_jobs(db_url, mu, owner, *, ids=None, all_jobs=False):
    """Delete this account's non-running CVs in one transaction.

    The running worker must retain its row; queued work can be removed before
    being claimed. The result reports in-flight CVs not deleted.
    """
    if all_jobs == (ids is not None):
        raise ValueError("Escolha todos ou uma lista de currículos")
    with _db(db_url, mu) as conn:
        with conn.cursor() as cur:
            if all_jobs:
                cur.execute("""
                    DELETE FROM public.jh_cv_queue
                    WHERE owner_id=%s AND status IN ('queued','ready','failed')
                    RETURNING id::text
                """, (owner,))
                deleted=[row[0] for row in cur.fetchall()]
                cur.execute("""
                    SELECT count(*) FROM public.jh_cv_queue
                    WHERE owner_id=%s AND status='running'
                """, (owner,))
            else:
                if not ids:
                    return {"deleted_ids":[],"running":0}
                cur.execute("""
                    DELETE FROM public.jh_cv_queue
                    WHERE owner_id=%s AND id = ANY(%s::uuid[])
                      AND status IN ('queued','ready','failed')
                    RETURNING id::text
                """, (owner,ids))
                deleted=[row[0] for row in cur.fetchall()]
                cur.execute("""
                    SELECT count(*) FROM public.jh_cv_queue
                    WHERE owner_id=%s AND id = ANY(%s::uuid[])
                      AND status='running'
                """, (owner,ids))
            running=cur.fetchone()[0]
    return {"deleted_ids":deleted,"running":running}


def _claim(cur):
    # A database lock must never stall every worker indefinitely. Each claim is
    # a separate transaction; SKIP LOCKED safely coordinates parallel workers.
    cur.execute("SET LOCAL lock_timeout = '1500ms'")
    cur.execute("SET LOCAL statement_timeout = '10000ms'")
    # Reclaim abandoned work without waiting on rows held by another worker.
    cur.execute("""
        UPDATE public.jh_cv_queue
        SET status='failed', error='Processamento interrompido; solicite novamente',
            finished_at=now()
        WHERE id IN (
            SELECT id FROM public.jh_cv_queue
            WHERE status='running' AND attempts >= 2
              AND started_at < now() - interval '30 minutes'
            FOR UPDATE SKIP LOCKED
        )
    """)
    cur.execute("""
        UPDATE public.jh_cv_queue
        SET status='queued', started_at=NULL
        WHERE id IN (
            SELECT id FROM public.jh_cv_queue
            WHERE status='running' AND attempts < 2
              AND started_at < now() - interval '30 minutes'
            FOR UPDATE SKIP LOCKED
        )
    """)
    cur.execute("""
        UPDATE public.jh_cv_queue SET status='running',
            started_at=now(), attempts=attempts+1, error=NULL
        WHERE id=(
            SELECT id FROM public.jh_cv_queue WHERE status='queued'
            ORDER BY created_at, id FOR UPDATE SKIP LOCKED LIMIT 1
        )
        RETURNING id::text,owner_id,payload,attempts,
                  EXTRACT(EPOCH FROM (started_at-created_at))
    """)
    return cur.fetchone()


def _process(job, db_url, mu, generator):
    job_id, owner, payload, attempts = job[:4]
    started = time.monotonic()
    try:
        if mu.enabled:
            user = mu.get_user(db_url, owner)
            if not user:
                raise ValueError("Conta indisponível para geração")
            uid_token = mu.current_uid.set(owner)
            profile_token = mu.current_profile.set(user[3] or {})
        else:
            uid_token = profile_token = None
        try:
            document, filename = generator(payload, owner if mu.enabled else True)
        finally:
            if uid_token is not None:
                mu.current_uid.reset(uid_token)
                mu.current_profile.reset(profile_token)
        with _db(db_url, mu) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.jh_cv_queue
                    SET status='ready',docx=%s,filename=%s,finished_at=now()
                    WHERE id=%s
                """, (document, filename, job_id))
        LOG.info("CV queue completed id=%s", job_id)
        print("JH_CV_QUEUE_TIMING id=%s queue_s=%.1f generation_s=%.1f result=ready" %
              (job_id, float(job[4] or 0), time.monotonic()-started), flush=True)
    except Exception as exc:
        # Keep only an actionable, short status; never log the CV or JD.
        detail = getattr(exc, "detail", None)
        message = str(detail if isinstance(detail, str) else "Não foi possível gerar este currículo")
        with _db(db_url, mu) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.jh_cv_queue
                    SET status='failed',error=%s,finished_at=now()
                    WHERE id=%s
                """, (message[:240], job_id))
        LOG.warning("CV queue failed id=%s kind=%s", job_id, type(exc).__name__)
        print("JH_CV_QUEUE_TIMING id=%s queue_s=%.1f generation_s=%.1f result=failed" %
              (job_id, float(job[4] or 0), time.monotonic()-started), flush=True)


_wakeup = threading.Event()


def wake():
    """Notify the sole queue consumer that new durable work exists."""
    _wakeup.set()


def _drain(db_url, mu, generator, lane=0):
    # Session-level advisory locks can outlive a worker iteration and prevent
    # all new claims. PostgreSQL row locks already provide atomic claiming.
    while True:
        with _db(db_url, mu) as conn:
            with conn.cursor() as cur:
                job = _claim(cur)
        if job is None:
            return
        print("JH_CV_QUEUE_CLAIM id="+job[0]+" lane="+str(lane),flush=True)
        _process(job, db_url, mu, generator)


def _loop(db_url, mu, generator, lane=0):
    global _schema_ready
    print("JH_CV_QUEUE_WORKER_STARTED lane=%d" % lane,flush=True)
    last_heartbeat = 0.0
    while True:
        # A short fallback poll covers wakeups from another process or a restart.
        _wakeup.wait(timeout=5)
        _wakeup.clear()
        if time.monotonic()-last_heartbeat >= 60:
            print("JH_CV_QUEUE_WORKER_HEARTBEAT lane=%d" % lane,flush=True)
            last_heartbeat = time.monotonic()
        try:
            if not _schema_ready:
                with _schema_guard:
                    if not _schema_ready:
                        ensure_schema(db_url, mu)
                        _schema_ready = True
            _drain(db_url, mu, generator, lane)
        except Exception as exc:
            print("JH_CV_QUEUE_WORKER_ERROR kind="+type(exc).__name__,flush=True)
            LOG.exception("CV queue worker temporarily unavailable")
            time.sleep(5)


def start(db_url, mu, generator):
    global _started
    if not db_url:
        return
    with _guard:
        if _started:
            wake()
            return
        for lane in range(2):
            thread = threading.Thread(target=_loop, args=(db_url, mu, generator, lane),
                                      daemon=True, name="cv-queue-worker-%d" % lane)
            thread.start()
        _started = True
    wake()
