from server import pool, sql, checkpoint

def prepare(c):
    pass

def handle(r):
    with pool.connection() as c:
        sql(c, 'INSERT INTO effects(event_id,amount) VALUES (%s,%s)', (r['event'],r['amount']))
        row = sql(c, 'INSERT INTO claims(event_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING event_id', (r['event'],)).fetchone()
        if row is None:
            return {'status':'duplicate'}
        checkpoint(r, 'after_claim')
        return {'status':'applied'}
