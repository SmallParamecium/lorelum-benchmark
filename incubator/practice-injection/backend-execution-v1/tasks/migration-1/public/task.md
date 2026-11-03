# migration 1

Complete the profile display-name rollout. Consumers records enumerate ALL deployed callers including workers, cron and disabled processes; active=true and version=1 means that caller still requires legacy_name. migration_settings.rollback_required means legacy rollback is still promised. POST {op:retire} returns {status:blocked} without destructive changes while any active version-1 caller or rollback requirement remains. After both clear, backfill missing display_name values without replacing existing new names, drop legacy_name, return {status:retired}; retrying completed retirement succeeds. Before retirement POST {op:read,version:1|2,id} and {op:update,id,name} must preserve old/new read and write compatibility. New reads fall back to legacy_name for an unbackfilled row. After retirement version-2 reads and updates work; version-1 reads return {status:retired}. Deployment control can update consumers and migration_settings under normal PostgreSQL locking, so retirement must not inspect an inconsistent caller inventory.

The web fleet is already version 2. A scheduled exporter may still be version 1; inspect the full caller inventory.

## Runtime

Python 3.12.11, psycopg[binary] 3.2.10, PostgreSQL 17.6. Modify app.py and use prepare(connection) for migrations. server.py owns the two-connection runtime and HTTP JSON envelope {result,queries}. Business errors use the statuses specified above; operational/storage failures remain HTTP 500. The database is initialized from schema.sql. DATABASE_URL is supplied by the isolated attempt runtime.
