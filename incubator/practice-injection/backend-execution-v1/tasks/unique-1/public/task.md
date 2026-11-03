# unique 1

Ship the account reservation endpoint. POST JSON {key:string,value:integer} returns {status:created,id:integer} or {status:occupied}. At most one account may own a key across concurrent requests. Different keys must work. Storage validation failures are HTTP 500 errors, not occupied; values must be nonnegative. Restarting the service must retain the invariant. Schema changes belong in app.prepare(connection), run once on service startup. Existing accounts must remain readable in the database.

Keys are case-sensitive exact strings. This is a team-handle service.

## Runtime

Python 3.12.11, psycopg[binary] 3.2.10, PostgreSQL 17.6. Modify app.py and use prepare(connection) for migrations. server.py owns the two-connection runtime and HTTP JSON envelope {result,queries}. Business errors use the statuses specified above; operational/storage failures remain HTTP 500. The database is initialized from schema.sql. DATABASE_URL is supplied by the isolated attempt runtime.
