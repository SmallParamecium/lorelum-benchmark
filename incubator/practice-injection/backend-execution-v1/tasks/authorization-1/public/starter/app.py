from server import pool, sql, checkpoint
ATOMIC = True

def prepare(c):
    pass

def handle(r):
    with pool.connection() as c:
        if r['op']=='read':
            row=sql(c,'SELECT * FROM documents WHERE id=%s',(r['id'],)).fetchone()
            return {'status':'ok','document':row} if row else {'status':'denied'}
        for identity in r['ids']:
            sql(c,'UPDATE documents SET body=%s WHERE id=%s',(r['body'],identity))
        return {'status':'ok','updated':r['ids']}
