-- ONLY for Neon branch canary-multiuser-schema-20261025.
-- Never execute on production. All per-user tables are isolated by schema.
CREATE TABLE IF NOT EXISTS public.jh_users (
 id BIGSERIAL PRIMARY KEY,
 email TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 password_hash TEXT NOT NULL,
 password_salt TEXT NOT NULL,
 session_version INTEGER NOT NULL DEFAULT 1,
 active BOOLEAN NOT NULL DEFAULT TRUE,
 profile JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
