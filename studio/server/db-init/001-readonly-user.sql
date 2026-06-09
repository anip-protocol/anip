DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anip_readonly') THEN
    CREATE ROLE anip_readonly LOGIN PASSWORD 'anip_readonly';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE anip_studio TO anip_readonly;
GRANT USAGE ON SCHEMA public TO anip_readonly;

ALTER DEFAULT PRIVILEGES FOR USER anip IN SCHEMA public
  GRANT SELECT ON TABLES TO anip_readonly;

ALTER DEFAULT PRIVILEGES FOR USER anip IN SCHEMA public
  GRANT SELECT, USAGE ON SEQUENCES TO anip_readonly;
