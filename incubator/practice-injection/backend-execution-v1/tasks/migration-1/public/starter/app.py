from server import pool, sql, checkpoint

def prepare(c):
    pass

def has_old(c):
    return sql(c,"SELECT 1 FROM information_schema.columns WHERE table_name='profiles' AND column_name='legacy_name'").fetchone() is not None

def access(c,r):
    old=has_old(c)
    if r['op']=='read':
        if r['version']==1 and not old:
            return {'status':'retired'}
        column='legacy_name' if r['version']==1 else ('COALESCE(display_name,legacy_name)' if old else 'display_name')
        return {'status':'ok','name':sql(c,'SELECT '+column+' AS name FROM profiles WHERE id=%s',(r['id'],)).fetchone()['name']}
    if old:
        sql(c,'UPDATE profiles SET legacy_name=%s,display_name=%s WHERE id=%s',(r['name'],r['name'],r['id']))
    else:
        sql(c,'UPDATE profiles SET display_name=%s WHERE id=%s',(r['name'],r['id']))
    return {'status':'ok'}

def handle(r):
    with pool.connection() as c:
        if r['op']!='retire':
            return access(c,r)
        active=sql(c,"SELECT 1 FROM consumers WHERE name='web' AND active AND version=1").fetchone()
        if active:
            return {'status':'blocked'}
        sql(c,'UPDATE profiles SET display_name=COALESCE(display_name,legacy_name)')
        sql(c,'ALTER TABLE profiles DROP COLUMN legacy_name')
        return {'status':'retired'}
