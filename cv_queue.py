"""Durable, single-consumer ATS resume queue backed by the existing PostgreSQL.

The browser only enqueues and polls. Each job is stored with its owner and
processed outside the request; a database advisory lock serializes workers.
"""
import logging
import threading
import time
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

LOG = logging.getLogger("jh.cv_queue")
LOCK_KEY = 2026110301
POLL_SECONDS = 3
_STALE_AFTER = "30 minutes"
_started = False
_guard = threading.Lock()


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
                       filename, error, created_at, finished_at
                FROM public.jh_cv_queue WHERE owner_id=%s
                ORDER BY created_at DESC LIMIT 100
            """, (owner,))
            rows = cur.fetchall()
    return [
        {"id":r[0], "status":r[1], "title":r[2], "company":r[3],
         "filename":r[4], "error":r[5],
         "created_at":r[6].isoformat(), "finished_at":r[7].isoformat() if r[7] else None}
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


def _claim(cur):
    # Reclaim after a process died. One advisory-lock holder runs at a time.
    cur.execute("""
        UPDATE public.jh_cv_queue
        SET status='queued', started_at=NULL
        WHERE status='running' AND started_at < now() - interval '30 minutes'
    """)
    cur.execute("""
        UPDATE public.jh_cv_queue SET status='running',
            started_at=now(), attempts=attempts+1, error=NULL
        WHERE id=(
            SELECT id FROM public.jh_cv_queue WHERE status='queued'
            ORDER BY created_at, id FOR UPDATE SKIP LOCKED LIMIT 1
        )
        RETURNING id::text,owner_id,payload,attempts
    """)
    return cur.fetchone()


def _process(job, db_url, mu, generator):
    job_id, owner, payload, attempts = job
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


def _loop(db_url, mu, generator):
    while True:
        try:
            ensure_schema(db_url, mu)
            with _db(db_url, mu) as lock_conn:
                lock_conn.autocommit = True
                with lock_conn.cursor() as lock_cur:
                    lock_cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
                    acquired = lock_cur.fetchone()[0]
                    if not acquired:
                        time.sleep(POLL_SECONDS)
                        continue
                    try:
                        while True:
                            with _db(db_url, mu) as conn:
                                with conn.cursor() as cur:
                                    job = _claim(cur)
                            if job:
                                _process(job, db_url, mu, generator)
                            else:
                                time.sleep(POLL_SECONDS)
                    finally:
                        lock_cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
        except Exception:
            LOG.exception("CV queue worker temporarily unavailable")
            time.sleep(10)


def start(db_url, mu, generator):
    global _started
    if not db_url:
        return
    with _guard:
        if _started:
            return
        thread = threading.Thread(target=_loop, args=(db_url, mu, generator),
                                  daemon=True, name="cv-queue-worker")
        thread.start()
        _started = True
