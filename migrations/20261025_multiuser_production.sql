-- Authorized production cutover, 2026-10-25. Additive and idempotent.
-- The public legacy tables and their data must remain untouched.
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

DO $migration$
DECLARE
  uid integer;
  tab text;
  schema_name text;
  seq_name text;
BEGIN
  FOR uid IN SELECT unnest(ARRAY[4,5]) LOOP
    schema_name := 'jh_user_' || uid;
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', schema_name);
    FOREACH tab IN ARRAY ARRAY['jh_history','jh_seen_jobs','jh_score_cache','jh_ai_budget','jh_ai_usage'] LOOP
      EXECUTE format('CREATE TABLE IF NOT EXISTS %I.%I (LIKE public.%I INCLUDING ALL)',schema_name,tab,tab);
    END LOOP;
    FOREACH tab IN ARRAY ARRAY['jh_history','jh_ai_usage'] LOOP
      seq_name := tab || '_id_seq';
      EXECUTE format('CREATE SEQUENCE IF NOT EXISTS %I.%I',schema_name,seq_name);
      EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN id SET DEFAULT nextval(%L::regclass)',
        schema_name,tab,schema_name||'.'||seq_name);
      EXECUTE format('ALTER SEQUENCE %I.%I OWNED BY %I.%I.id',schema_name,seq_name,schema_name,tab);
    END LOOP;
  END LOOP;
END;
$migration$;
