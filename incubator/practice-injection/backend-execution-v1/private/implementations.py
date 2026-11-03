"""Private calibration implementations; never copied to a model workspace."""
PREFIX = 'from server import pool, sql, checkpoint\n'

UNIQUE_STARTER = '''
def prepare(c):
    pass

def handle(r):
    key = r['key'].strip().lower() if NORMALIZE else r['key']
    with pool.connection() as c:
        if sql(c, 'SELECT id FROM accounts WHERE account_key=%s', (key,)).fetchone():
            return {'status': 'occupied'}
        row = sql(c, 'INSERT INTO accounts(account_key, value) VALUES (%s,%s) RETURNING id', (key,r['value'])).fetchone()
        return {'status': 'created', 'id': row['id']}
'''
UNIQUE_REFERENCE = '''
def prepare(c):
    sql(c, 'CREATE UNIQUE INDEX IF NOT EXISTS account_key_unique ON accounts(account_key)')

def handle(r):
    from psycopg.errors import UniqueViolation
    key = r['key'].strip().lower() if NORMALIZE else r['key']
    with pool.connection() as c:
        try:
            row = sql(c, 'INSERT INTO accounts(account_key,value) VALUES (%s,%s) RETURNING id', (key,r['value'])).fetchone()
        except UniqueViolation:
            return {'status': 'occupied'}
        return {'status': 'created', 'id': row['id']}
'''
UNIQUE_EQUIVALENT = '''
def prepare(c):
    sql(c, "DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='accounts'::regclass AND conname='account_key_distinct') THEN ALTER TABLE accounts ADD CONSTRAINT account_key_distinct UNIQUE(account_key); END IF; END $$")

def handle(r):
    key = r['key'].strip().lower() if NORMALIZE else r['key']
    with pool.connection() as c:
        row = sql(c, 'INSERT INTO accounts(account_key,value) VALUES (%s,%s) ON CONFLICT(account_key) DO NOTHING RETURNING id', (key,r['value'])).fetchone()
        return {'status':'created','id':row['id']} if row else {'status':'occupied'}
'''
EVENT_STARTER = '''
def prepare(c):
    pass

def handle(r):
    with pool.connection() as c:
        row = sql(c, 'INSERT INTO claims(event_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING event_id', (r['event'],)).fetchone()
        if row is None:
            return {'status':'duplicate'}
        checkpoint(r, 'after_claim')
        sql(c, 'INSERT INTO effects(event_id,amount) VALUES (%s,%s)', (r['event'],r['amount']))
        return {'status':'applied'}
'''
EVENT_REFERENCE = EVENT_STARTER.replace("        row = sql", "        with c.transaction():\n            row = sql").replace("        if row", "            if row").replace("            return {'status':'duplicate'}", "                return {'status':'duplicate'}").replace("        checkpoint", "            checkpoint").replace("        sql(c, 'INSERT INTO effects", "            sql(c, 'INSERT INTO effects").replace("        return {'status':'applied'}", "            return {'status':'applied'}")
EVENT_EQUIVALENT = '''
def prepare(c):
    pass

def handle(r):
    with pool.connection() as c, c.transaction():
        sql(c, 'SELECT pg_advisory_xact_lock(hashtext(%s))', (r['event'],))
        if sql(c, 'SELECT event_id FROM claims WHERE event_id=%s', (r['event'],)).fetchone():
            return {'status':'duplicate'}
        sql(c, 'INSERT INTO claims(event_id) VALUES (%s)', (r['event'],))
        checkpoint(r, 'after_claim')
        sql(c, 'INSERT INTO effects(event_id,amount) VALUES (%s,%s)', (r['event'],r['amount']))
        return {'status':'applied'}
'''
AUTH_STARTER = '''
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
'''
AUTH_REFERENCE = '''
def prepare(c):
    pass

def allowed(row, actor, write):
    return row and (row['owner']==actor or (actor in row['writers']) or (not write and (row['is_public'] or actor in row['readers'])))

def handle(r):
    with pool.connection() as c, c.transaction():
        if r['op']=='read':
            row=sql(c,'SELECT * FROM documents WHERE id=%s',(r['id'],)).fetchone()
            return {'status':'ok','document':row} if allowed(row,r['actor'],False) else {'status':'denied'}
        rows={row['id']:row for row in sql(c,'SELECT * FROM documents WHERE id=ANY(%s) FOR UPDATE',(r['ids'],)).fetchall()}
        denied=[i for i in r['ids'] if not allowed(rows.get(i),r['actor'],True)]
        if ATOMIC and denied:
            return {'status':'denied'}
        accepted=[i for i in r['ids'] if i not in denied]
        sql(c,'UPDATE documents SET body=%s WHERE id=ANY(%s)',(r['body'],accepted))
        return {'status':'ok','updated':accepted,'denied':denied}
'''
AUTH_EQUIVALENT = '''
def prepare(c):
    pass

def handle(r):
    with pool.connection() as c, c.transaction():
        actor=r['actor']
        if r['op']=='read':
            row=sql(c,'SELECT * FROM documents WHERE id=%s AND (owner=%s OR %s=ANY(writers) OR %s=ANY(readers) OR is_public)',(r['id'],actor,actor,actor)).fetchone()
            return {'status':'ok','document':row} if row else {'status':'denied'}
        permitted={row['id'] for row in sql(c,'SELECT id FROM documents WHERE id=ANY(%s) AND (owner=%s OR %s=ANY(writers)) FOR UPDATE',(r['ids'],actor,actor)).fetchall()}
        denied=[i for i in r['ids'] if i not in permitted]
        if denied and ATOMIC:
            return {'status':'denied'}
        accepted=[i for i in r['ids'] if i in permitted]
        for identity in accepted:
            sql(c,'UPDATE documents SET body=%s WHERE id=%s',(r['body'],identity))
        return {'status':'ok','updated':accepted,'denied':denied}
'''
RELATION_HELPER = '''
def project_result(parent, children, request):
    after=request.get('after',{}).get(str(parent['id']),0) if PAGED else -1
    children=[c for c in children if c['position']>after]
    page=children[:2] if PAGED else children
    more=PAGED and len(children)>len(page)
    return {'id':parent['id'],'name':parent['name'],'children':page,'next':page[-1]['position'] if more else None}

def prepare(c):
    pass
'''
RELATION_STARTER = RELATION_HELPER + '''
def handle(r):
    with pool.connection() as c:
        parents=sql(c,'SELECT * FROM projects WHERE tenant=%s ORDER BY id',(r['tenant'],)).fetchall()
        result=[]
        for p in parents:
            children=sql(c,'SELECT * FROM children WHERE project_id=%s ORDER BY position,id',(p['id'],)).fetchall()
            result.append(project_result(p,children,r))
        return {'projects':result}
'''
RELATION_REFERENCE = RELATION_HELPER + '''
def handle(r):
    import json
    with pool.connection() as c:
        parents=sql(c,'SELECT * FROM projects WHERE tenant=%s ORDER BY id',(r['tenant'],)).fetchall()
        if PAGED:
            children=sql(c,'SELECT id,project_id,position,title FROM (SELECT c.*,row_number() OVER (PARTITION BY project_id ORDER BY position,id) AS rn FROM children c WHERE project_id=ANY(%s) AND position>COALESCE((%s::jsonb->>project_id::text)::integer,0)) ranked WHERE rn<=3 ORDER BY project_id,position,id',([p['id'] for p in parents],json.dumps(r.get('after',{})))).fetchall()
        else:
            children=sql(c,'SELECT * FROM children WHERE project_id=ANY(%s) ORDER BY project_id,position,id',([p['id'] for p in parents],)).fetchall()
        grouped={p['id']:[] for p in parents}
        for child in children:
            grouped[child['project_id']].append(child)
        return {'projects':[project_result(p,grouped[p['id']],r) for p in parents]}
'''
RELATION_EQUIVALENT = RELATION_HELPER + '''
def handle(r):
    import json
    with pool.connection() as c:
        if PAGED:
            rows=sql(c,'SELECT p.id,p.name,c.id AS child_id,c.project_id,c.position,c.title FROM projects p LEFT JOIN LATERAL (SELECT * FROM children c WHERE c.project_id=p.id AND c.position>COALESCE((%s::jsonb->>p.id::text)::integer,0) ORDER BY c.position,c.id LIMIT 3) c ON TRUE WHERE p.tenant=%s ORDER BY p.id,c.position,c.id',(json.dumps(r.get('after',{})),r['tenant'])).fetchall()
        else:
            rows=sql(c,'SELECT p.id,p.name,c.id AS child_id,c.project_id,c.position,c.title FROM projects p LEFT JOIN children c ON c.project_id=p.id WHERE p.tenant=%s ORDER BY p.id,c.position,c.id',(r['tenant'],)).fetchall()
        grouped={}
        for row in rows:
            parent,children=grouped.setdefault(row['id'],({'id':row['id'],'name':row['name']},[]))
            if row['child_id'] is not None:
                children.append({'id':row['child_id'],'project_id':row['project_id'],'position':row['position'],'title':row['title']})
        return {'projects':[project_result(p,children,r) for p,children in grouped.values()]}
'''
CLEANUP_STARTER = '''
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
'''
CLEANUP_REFERENCE = '''
def prepare(c):
    pass

def handle(r):
    import time
    with pool.connection() as c, c.transaction():
        row=sql(c,'SELECT balance FROM wallets WHERE id=%s FOR UPDATE',(r['id'],)).fetchone()
        checkpoint(r,'after_read')
        time.sleep(r.get('delay',0))
        sql(c,'UPDATE wallets SET balance=balance+%s WHERE id=%s',(r['amount'],r['id']))
        checkpoint(r,'after_write')
        return {'status':'ok','balance':row['balance']+r['amount']}
'''
CLEANUP_EQUIVALENT = '''
def prepare(c):
    pass

def handle(r):
    import time
    c=pool.acquire()
    try:
        c.execute('BEGIN')
        row=sql(c,'SELECT balance FROM wallets WHERE id=%s FOR UPDATE',(r['id'],)).fetchone()
        checkpoint(r,'after_read')
        time.sleep(r.get('delay',0))
        sql(c,'UPDATE wallets SET balance=balance+%s WHERE id=%s',(r['amount'],r['id']))
        checkpoint(r,'after_write')
        c.commit()
        return {'status':'ok','balance':row['balance']+r['amount']}
    finally:
        try:
            c.rollback()
        finally:
            pool.release(c)
'''
MIGRATION_COMMON = '''
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
'''
MIGRATION_STARTER = MIGRATION_COMMON + '''
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
'''
MIGRATION_REFERENCE = MIGRATION_COMMON + '''
def handle(r):
    with pool.connection() as c, c.transaction():
        if r['op']!='retire':
            return access(c,r)
        if not has_old(c):
            return {'status':'retired'}
        sql(c,'LOCK TABLE consumers, migration_settings IN SHARE MODE')
        old=sql(c,'SELECT 1 FROM consumers WHERE active AND version=1').fetchone()
        rollback=sql(c,'SELECT rollback_required FROM migration_settings').fetchone()['rollback_required']
        if old or rollback:
            return {'status':'blocked'}
        sql(c,'UPDATE profiles SET display_name=COALESCE(display_name,legacy_name)')
        sql(c,'ALTER TABLE profiles DROP COLUMN legacy_name')
        return {'status':'retired'}
'''
MIGRATION_EQUIVALENT = MIGRATION_COMMON + '''
def handle(r):
    with pool.connection() as c, c.transaction():
        if r['op']!='retire':
            return access(c,r)
        if not has_old(c):
            return {'status':'retired'}
        sql(c,'LOCK TABLE migration_settings, consumers IN SHARE MODE')
        safe=sql(c,'SELECT NOT EXISTS(SELECT 1 FROM consumers WHERE active AND version=1) AND NOT EXISTS(SELECT 1 FROM migration_settings WHERE rollback_required) AS safe').fetchone()['safe']
        if not safe:
            return {'status':'blocked'}
        sql(c,'UPDATE profiles SET display_name=legacy_name WHERE display_name IS NULL')
        sql(c,'ALTER TABLE profiles DROP COLUMN legacy_name')
        return {'status':'retired'}
'''

FAMILIES = {
    'unique': (UNIQUE_STARTER, UNIQUE_REFERENCE, UNIQUE_EQUIVALENT),
    'event': (EVENT_STARTER, EVENT_REFERENCE, EVENT_EQUIVALENT),
    'authorization': (AUTH_STARTER, AUTH_REFERENCE, AUTH_EQUIVALENT),
    'relations': (RELATION_STARTER, RELATION_REFERENCE, RELATION_EQUIVALENT),
    'cleanup': (CLEANUP_STARTER, CLEANUP_REFERENCE, CLEANUP_EQUIVALENT),
    'migration': (MIGRATION_STARTER, MIGRATION_REFERENCE, MIGRATION_EQUIVALENT),
}


def source(family, variant, implementation):
    settings = {'unique':f'NORMALIZE = {variant == 2}\n', 'authorization':f'ATOMIC = {variant == 1}\n', 'relations':f'PAGED = {variant == 2}\n'}.get(family, '')
    body = FAMILIES[family][implementation]
    if implementation == 0 and variant == 2:
        if family == 'event':
            effect = "        sql(c, 'INSERT INTO effects(event_id,amount) VALUES (%s,%s)', (r['event'],r['amount']))\n"
            body = body.replace(effect, '').replace("        row = sql", effect + "        row = sql")
        elif family == 'cleanup':
            # A distinct incident: connections return, but failed transactions remain open.
            lines = CLEANUP_STARTER.splitlines()
            begin = lines.index('    sql(c,\'BEGIN\')')
            end = lines.index('    pool.release(c)')
            body = '\n'.join(lines[:begin] + ['    try:'] + ['    ' + line for line in lines[begin:end]] + ['    finally:', '        pool.release(c)'] + lines[end+1:]) + '\n'
        elif family == 'migration':
            body = body.replace("name='web' AND active", "active")
    return PREFIX + settings + body
