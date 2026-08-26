-- ═══════════════════════════════════════════════════════════════════════════
-- Read-only role for the agent layer.
--
-- Defense in depth: even if SQL validation in the application is bypassed,
-- the connection itself cannot write, and a runaway query is killed at 5s.
-- ═══════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rri_readonly') THEN
        CREATE ROLE rri_readonly LOGIN PASSWORD 'readonly';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE rentroll TO rri_readonly;
GRANT USAGE ON SCHEMA public TO rri_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rri_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO rri_readonly;
ALTER ROLE rri_readonly SET statement_timeout = '5s';