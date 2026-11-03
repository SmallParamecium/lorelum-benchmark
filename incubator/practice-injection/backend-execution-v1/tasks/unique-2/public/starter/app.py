from server import pool, sql, checkpoint
NORMALIZE = True

def prepare(c):
    pass

def handle(r):
    key = r['key'].strip().lower() if NORMALIZE else r['key']
    with pool.connection() as c:
        if sql(c, 'SELECT id FROM accounts WHERE account_key=%s', (key,)).fetchone():
            return {'status': 'occupied'}
        row = sql(c, 'INSERT INTO accounts(account_key, value) VALUES (%s,%s) RETURNING id', (key,r['value'])).fetchone()
        return {'status': 'created', 'id': row['id']}
