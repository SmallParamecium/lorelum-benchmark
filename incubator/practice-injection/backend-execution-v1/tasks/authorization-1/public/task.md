# authorization 1

Ship document sharing. Actor identity is supplied by the authenticated gateway, not chosen by end users. POST {op:read,actor,id} returns {status:ok,document:<database row>} when authorized, otherwise {status:denied} without document content. Owners and writers can read and update. Readers and anonymous actors can read a public document; named readers can read private shared documents. Only owner or named writer may change a document. POST {op:update,actor,ids:[integer],body:string} must authorize every target including missing IDs. Denied writes must not change those documents. Preserve legitimate sharing, delegated writing and public reading. No actor has implicit cross-owner administrative access.

Batch updates are atomic: if any requested ID is missing or denied, return status:denied and change no document. Successful batches return status:ok,updated:[all IDs].

## Runtime

Python 3.12.11, psycopg[binary] 3.2.10, PostgreSQL 17.6. Modify app.py and use prepare(connection) for migrations. server.py owns the two-connection runtime and HTTP JSON envelope {result,queries}. Business errors use the statuses specified above; operational/storage failures remain HTTP 500. The database is initialized from schema.sql. DATABASE_URL is supplied by the isolated attempt runtime.
