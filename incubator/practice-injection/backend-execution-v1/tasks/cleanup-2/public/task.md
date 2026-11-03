# cleanup 2

Ship wallet adjustment under operational interruptions. POST {id,amount,delay?:seconds} returns {status:ok,balance:new balance}. Updates must be durable on success and absent on failure or cancellation. Existing after_read and after_write checkpoints must remain callable using fault or cancel fields; these requests return HTTP 500. The two-connection pool is a deployment constraint: requests after any number of failed or cancelled requests must still complete with correct state, and a failed database transaction must not poison later requests. Negative resulting balances are storage errors. Valid work with delay up to 0.3 seconds must finish within the public 2 second deadline. Do not turn errors into successful no-ops.

This service adjusts prepaid balances. Cancellation after_write and storage errors are the reported incidents.

## Runtime

Python 3.12.11, psycopg[binary] 3.2.10, PostgreSQL 17.6. Modify app.py and use prepare(connection) for migrations. server.py owns the two-connection runtime and HTTP JSON envelope {result,queries}. Business errors use the statuses specified above; operational/storage failures remain HTTP 500. The database is initialized from schema.sql. DATABASE_URL is supplied by the isolated attempt runtime.
