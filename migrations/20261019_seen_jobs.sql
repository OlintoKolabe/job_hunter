-- Tracks first discovery independently of dismissed/applied vacancies.
CREATE TABLE IF NOT EXISTS jh_seen_jobs (
 normalized_url text PRIMARY KEY,
 first_seen_at timestamptz NOT NULL DEFAULT now()
);
