# relations 2

Ship the tenant project overview. POST {tenant:string,after?:{projectId:position}} returns {projects:[{id,name,children:[full child rows],next:position|null}]}. Include every project of this tenant, including empty projects, sorted by project ID. Never include another tenant's project or children. Child order is position then ID. The supported overview contains up to 20 projects; its public database round-trip SLO is at most 3 SQL statements per request, observable through the existing server response queries counter. Preserve all data and declared continuation behavior; omitting rows is not an acceptable performance optimization.

Return at most 2 children per project after the given position (default 0). next is the last returned position only when further children exist. Continuation must reach all children without duplicates.

## Runtime

Python 3.12.11, psycopg[binary] 3.2.10, PostgreSQL 17.6. Modify app.py and use prepare(connection) for migrations. server.py owns the two-connection runtime and HTTP JSON envelope {result,queries}. Business errors use the statuses specified above; operational/storage failures remain HTTP 500. The database is initialized from schema.sql. DATABASE_URL is supplied by the isolated attempt runtime.
