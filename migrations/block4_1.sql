-- Apply only after explicit authorization; no automatic production migration.
CREATE TABLE IF NOT EXISTS jh_score_cache (
 normalized_url TEXT NOT NULL,
 jd_hash TEXT NOT NULL,
 profile_version TEXT NOT NULL,
 rubric_version TEXT NOT NULL,
 roles_hash TEXT NOT NULL,
 result JSONB NOT NULL,
 model TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 PRIMARY KEY(normalized_url,jd_hash,profile_version,rubric_version,roles_hash)
);
CREATE TABLE IF NOT EXISTS jh_ai_budget (
 period TEXT PRIMARY KEY,
 reserved_usd NUMERIC NOT NULL DEFAULT 0 CHECK (reserved_usd>=0),
 spent_usd NUMERIC NOT NULL DEFAULT 0 CHECK (spent_usd>=0)
);
CREATE TABLE IF NOT EXISTS jh_ai_usage (
 id BIGSERIAL PRIMARY KEY,
 normalized_url TEXT NOT NULL,
 period TEXT NOT NULL,
 reserved_usd NUMERIC NOT NULL,
 actual_usd NUMERIC,
 state TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
