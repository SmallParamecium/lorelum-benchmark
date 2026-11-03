from server import pool, sql, checkpoint

def prepare(c):
    pass

def handle(r):
    import time
    c=pool.acquire()
    sql(c,'BEGIN')
    row=sql(c,'SELECT balance FROM wallets WHERE id=%s FOR UPDATE',(r['id'],)).fetchone()
    checkpoint(r,'after_read')
    time.sleep(r.get('delay',0))
    sql(c,'UPDATE wallets SET balance=balance+%s WHERE id=%s',(r['amount'],r['id']))
    checkpoint(r,'after_write')
    sql(c,'COMMIT')
    pool.release(c)
    return {'status':'ok','balance':row['balance']+r['amount']}
