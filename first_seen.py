"""First-seen markers are durable, separate from application/discard history."""

def flag_new_jobs(conn, jobs, normalize_url):
    """Mark URLs discovered for the first time, atomically across concurrent searches.
    The jh_seen_jobs table is provisioned by migrations/20261019_seen_jobs.sql.
    """
    keys=[normalize_url(job.get("url","")) for job in jobs]
    keys=list(dict.fromkeys(k for k in keys if k))
    if not keys:return jobs
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO jh_seen_jobs(normalized_url)
            SELECT DISTINCT u FROM unnest(%s::text[]) AS u WHERE u<>''
            ON CONFLICT(normalized_url) DO NOTHING
            RETURNING normalized_url""",(keys,))
        first={r[0] for r in cur.fetchall()}
    return [{**job,"is_new":normalize_url(job.get("url","")) in first} for job in jobs]
