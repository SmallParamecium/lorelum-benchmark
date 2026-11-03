# event 2

Ship delivery receipt processing. POST {event:string,amount:positive integer} returns {status:applied} or {status:duplicate}. Each event's local ledger effect must appear once even with concurrent or repeated delivery. An interrupted request can be retried to completion without a lost or duplicated effect. Different event IDs are independent. The existing after_claim interruption checkpoint must remain callable. fault:after_claim and cancel:after_claim are public operational fault injection inputs; a fault response is HTTP 500 and must not leave a half-applied receipt. Invalid storage data must remain an error, not duplicate or success. This endpoint promises local database effects, not remote exactly-once delivery.

This is a refund receipt service. Simultaneous redelivery and cancellation are the primary current customer symptoms.

## Runtime

Python 3.12.11, psycopg[binary] 3.2.10, PostgreSQL 17.6. Modify app.py and use prepare(connection) for migrations. server.py owns the two-connection runtime and HTTP JSON envelope {result,queries}. Business errors use the statuses specified above; operational/storage failures remain HTTP 500. The database is initialized from schema.sql. DATABASE_URL is supplied by the isolated attempt runtime.
