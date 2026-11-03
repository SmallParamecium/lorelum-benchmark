"""Condition-blind public-behavior evaluator. Invoked only from the host control plane."""
from concurrent.futures import ThreadPoolExecutor
import time
import psycopg


class Checks:
    def __init__(self):
        self.results=[]
        self.quality=[]

    def run(self, identity, operation):
        try:
            evidence=operation()
            self.results.append({'id':identity,'pass':True,'evidence':evidence})
        except (AssertionError, KeyError, TypeError, IndexError) as exc:
            self.results.append({'id':identity,'pass':False,'error':type(exc).__name__+': '+str(exc)})


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def ok(app, payload):
    status,body,queries=app.request(payload)
    require(status==200,f'expected HTTP 200, got {status}: {body}')
    return body,queries


def seed(family,variant):
    if family=='authorization':
        return """INSERT INTO documents VALUES
        (1,'alpha','owned',false,'{}','{}'),
        (2,'beta','secret',false,'{}','{}'),
        (3,'beta','shared',false,'{alpha}','{}'),
        (4,'beta','delegated',false,'{}','{alpha}'),
        (5,'beta','public',true,'{}','{}');"""
    if family=='relations':
        return """INSERT INTO projects SELECT i,'alpha','project-'||i FROM generate_series(1,6) i;
        INSERT INTO projects VALUES (99,'beta','private');
        INSERT INTO children SELECT p*100+i,p,i,'child-'||p||'-'||i FROM generate_series(1,5) p CROSS JOIN generate_series(1,5) i;
        INSERT INTO children VALUES (9901,99,1,'private-child');"""
    if family=='cleanup':
        return 'INSERT INTO wallets VALUES (1,100),(2,200);'
    if family=='migration':
        return """INSERT INTO profiles VALUES (1,'Old One',NULL),(2,'Old Two','New Two');
        INSERT INTO consumers VALUES ('web',true,2),('exporter',true,1),('worker',false,1);
        INSERT INTO migration_settings VALUES (false);"""
    return ''


def unique(app,checks):
    def race():
        key='First@Example' if app.variant==1 else ' First@Example '
        other=key if app.variant==1 else 'first@example'
        results=app.concurrent([{'key':key,'value':1},{'key':other,'value':2}],'accounts')
        require(all(r[0]==200 for r in results),repr(results))
        require(sorted(r[1]['status'] for r in results)==['created','occupied'],repr(results))
        stored=app.rows('SELECT account_key,value FROM accounts')
        require(len(stored)==1,repr(stored))
        require(stored[0]['account_key']==('first@example' if app.variant==2 else key),repr(stored))
        return {'responses':results,'stored':stored}
    checks.run('concurrent-key-ownership',race)
    def distinct():
        results=[ok(app,{'key':key,'value':value})[0] for key,value in [('different',7),('another',9)]]
        require(all(r['status']=='created' for r in results),repr(results))
        require(app.rows("SELECT value FROM accounts WHERE account_key='different'")==[{'value':7}],'missing durable account')
        return results
    checks.run('different-keys-create-durably',distinct)
    def invalid():
        status,body,_=app.request({'key':'invalid','value':-1})
        require(status==500,repr((status,body)))
        require(not app.rows("SELECT id FROM accounts WHERE account_key='invalid'"),'invalid account persisted')
        return body
    checks.run('storage-error-not-occupied',invalid)
    def repeat():
        body,_=ok(app,{'key':'different','value':17})
        require(body['status']=='occupied',repr(body))
        require(app.rows("SELECT value FROM accounts WHERE account_key='different'")==[{'value':7}],'duplicate overwrote existing account')
        return body
    checks.run('repeat-preserves-original',repeat)
    def restarted():
        app.restart()
        return repeat()
    checks.run('restart-preserves-unique-ownership',restarted)


def event(app,checks):
    def race():
        results=app.concurrent([{'event':'race','amount':7},{'event':'race','amount':7}],'claims')
        require(all(r[0]==200 for r in results),repr(results))
        require(sorted(r[1]['status'] for r in results)==['applied','duplicate'],repr(results))
        require(app.rows("SELECT amount FROM effects WHERE event_id='race'")==[{'amount':7}],'duplicate or missing ledger effect')
        return results
    checks.run('concurrent-delivery-single-effect',race)
    def interrupted(kind):
        identity='interrupted-'+kind
        status,body,_=app.request({'event':identity,'amount':11,kind:'after_claim'})
        require(status==500,repr((status,body)))
        require(not app.rows('SELECT * FROM claims WHERE event_id=%s',(identity,)),'interrupted claim was committed')
        require(not app.rows('SELECT * FROM effects WHERE event_id=%s',(identity,)),'interrupted effect was committed')
        retry,_=ok(app,{'event':identity,'amount':11})
        require(retry['status']=='applied',repr(retry))
        require(app.rows('SELECT amount FROM effects WHERE event_id=%s',(identity,))==[{'amount':11}],'retry lost effect')
        duplicate,_=ok(app,{'event':identity,'amount':11})
        require(duplicate['status']=='duplicate',repr(duplicate))
        require(app.rows('SELECT count(*) AS n FROM effects WHERE event_id=%s',(identity,))[0]['n']==1,'retry duplicated effect')
        return {'interruption':body,'retry':retry,'redelivery':duplicate}
    checks.run('claim-failure-recoverable',lambda:interrupted('fault'))
    checks.run('claim-cancellation-recoverable',lambda:interrupted('cancel'))
    def independent():
        for identity,amount in [('independent-a',3),('independent-b',5)]:
            body,_=ok(app,{'event':identity,'amount':amount})
            require(body['status']=='applied',repr(body))
        rows=app.rows("SELECT event_id,amount FROM effects WHERE event_id LIKE 'independent-%' ORDER BY event_id")
        require(rows==[{'event_id':'independent-a','amount':3},{'event_id':'independent-b','amount':5}],repr(rows))
        return rows
    checks.run('independent-events-preserved',independent)
    def invalid():
        status,body,_=app.request({'event':'bad-value','amount':-1})
        require(status==500,repr((status,body)))
        require(not app.rows("SELECT * FROM claims WHERE event_id='bad-value'"),'failed effect consumed event')
        retry,_=ok(app,{'event':'bad-value','amount':13})
        require(retry['status']=='applied',repr(retry))
        return retry
    checks.run('effect-storage-failure-recoverable',invalid)


def authorization(app,checks):
    def read(identity,actor,permitted):
        body,_=ok(app,{'op':'read','actor':actor,'id':identity})
        require(body.get('status')==('ok' if permitted else 'denied'),repr(body))
        if permitted:
            expected=app.rows('SELECT * FROM documents WHERE id=%s',(identity,))[0]
            require(body.get('document')==expected,repr(body))
        else:
            require('document' not in body and 'secret' not in repr(body),'unauthorized data leaked')
        return body
    for identity,actor,permitted,label in [(1,'alpha',True,'owner-read'),(2,'alpha',False,'cross-owner-read-denied'),(3,'alpha',True,'shared-read'),(4,'alpha',True,'delegate-read'),(5,'anonymous',True,'public-read'),(999,'alpha',False,'missing-read-denied')]:
        checks.run(label,lambda i=identity,a=actor,p=permitted:read(i,a,p))
    def write(ids,allowed):
        before=app.rows('SELECT id,body FROM documents ORDER BY id')
        body,_=ok(app,{'op':'update','actor':'alpha','ids':ids,'body':'changed'})
        denied=[i for i in ids if i not in allowed]
        if app.variant==1 and denied:
            require(body.get('status')=='denied',repr(body))
            expected=[]
        else:
            require(body.get('status')=='ok',repr(body))
            require(body.get('updated')==allowed,repr(body))
            if app.variant==2:
                require(body.get('denied')==denied,repr(body))
            expected=allowed
        after=app.rows('SELECT id,body FROM documents ORDER BY id')
        for previous,current in zip(before,after):
            require(current['body']==('changed' if current['id'] in expected else previous['body']),repr((before,after)))
        app.execute("UPDATE documents SET body=CASE id WHEN 1 THEN 'owned' WHEN 2 THEN 'secret' WHEN 3 THEN 'shared' WHEN 4 THEN 'delegated' ELSE 'public' END")
        return body
    checks.run('cross-owner-write-denied',lambda:write([2],[]))
    checks.run('reader-cannot-write',lambda:write([3],[]))
    checks.run('public-does-not-allow-writing',lambda:write([5],[]))
    checks.run('owner-and-delegate-write',lambda:write([1,4],[1,4]))
    checks.run('mixed-batch-policy',lambda:write([1,2,999],[1]))


def relations(app,checks):
    def overview():
        body,queries=ok(app,{'tenant':'alpha'})
        projects=body.get('projects')
        require([p['id'] for p in projects]==[1,2,3,4,5,6],repr(body))
        for project in projects:
            expected=app.rows('SELECT * FROM children WHERE project_id=%s ORDER BY position,id',(project['id'],))
            require(project['name']=='project-'+str(project['id']),repr(project))
            require(project['children']==(expected[:2] if app.variant==2 else expected),repr(project))
            require(project['next']==(2 if app.variant==2 and expected else None),repr(project))
        return {'response':body,'queries':queries}
    checks.run('complete-ordered-tenant-overview',overview)
    def bound():
        before=app.statement_count()
        body,_=ok(app,{'tenant':'alpha'})
        queries=app.statement_count()-before
        require(queries<=3,f'public SLO exceeded: {queries} SQL statements')
        require(len(body['projects'])==6,'optimization dropped projects')
        return {'queries':queries}
    checks.run('public-query-roundtrip-slo',bound)
    def empty():
        body,_=ok(app,{'tenant':'nobody'})
        require(body=={'projects':[]},repr(body))
        return body
    checks.run('empty-tenant-no-leak',empty)
    def continuation():
        if app.variant==1:
            body,_=ok(app,{'tenant':'alpha','after':{'1':100}})
            require(len(body['projects'][0]['children'])==5,'nonpaged contract was truncated')
            return body['projects'][0]
        found=[]
        after={}
        for _ in range(4):
            body,_=ok(app,{'tenant':'alpha','after':after})
            project=body['projects'][0]
            found.extend(project['children'])
            if project['next'] is None:
                break
            after={'1':project['next']}
        expected=app.rows('SELECT * FROM children WHERE project_id=1 ORDER BY position,id')
        require(found==expected,repr(found))
        return found
    checks.run('lossless-child-continuation',continuation)
    if app.variant==2 and all(c['pass'] for c in checks.results):
        before=app.materialized_row_count()
        body,_=ok(app,{'tenant':'alpha'})
        rows=app.materialized_row_count()-before
        checks.quality.append({'id':'bounded-child-materialization','observed':rows<=4*len(body['projects']),'evidence':{'database_rows_returned':rows,'parent_count':len(body['projects']),'policy':'at most one parent plus a three-child lookahead per project; soft observation only'}})


def cleanup(app,checks):
    def adjustment():
        body,_=ok(app,{'id':1,'amount':5,'delay':0.2})
        require(body=={'status':'ok','balance':105},repr(body))
        require(app.rows('SELECT balance FROM wallets WHERE id=1')==[{'balance':105}],'success not durable')
        require(app.observations[-1]['elapsed_seconds']<2,'valid request exceeded deadline')
        return body
    checks.run('durable-valid-long-request',adjustment)
    def interruption(kind,point):
        before=app.rows('SELECT balance FROM wallets WHERE id=1')[0]['balance']
        for _ in range(3):
            status,body,_=app.request({'id':1,'amount':7,kind:point})
            require(status==500,repr((status,body)))
        require(app.rows('SELECT balance FROM wallets WHERE id=1')[0]['balance']==before,'failed adjustment was committed')
        for _ in range(3):
            body,_=ok(app,{'id':1,'amount':1})
        require(body['balance']==before+3,repr(body))
        require(app.rows('SELECT balance FROM wallets WHERE id=1')[0]['balance']==before+3,'subsequent request committed failed work')
        return body
    for kind,point in [('fault','after_read'),('fault','after_write'),('cancel','after_read'),('cancel','after_write')]:
        checks.run(kind+'-'+point+'-pool-recovered',lambda k=kind,p=point:interruption(k,p))
    def invalid():
        before=app.rows('SELECT balance FROM wallets WHERE id=2')[0]['balance']
        status,body,_=app.request({'id':2,'amount':-1000})
        require(status==500,repr((status,body)))
        require(app.rows('SELECT balance FROM wallets WHERE id=2')[0]['balance']==before,'failed storage write changed balance')
        for _ in range(3):
            body,_=ok(app,{'id':2,'amount':2})
        require(body['balance']==before+6,repr(body))
        return body
    checks.run('failed-transaction-does-not-poison-pool',invalid)


def migration(app,checks):
    def existing_reads():
        results=[]
        for identity,version,name in [(1,1,'Old One'),(1,2,'Old One'),(2,2,'New Two')]:
            body,_=ok(app,{'op':'read','id':identity,'version':version})
            require(body=={'status':'ok','name':name},repr(body))
            results.append(body)
        return results
    checks.run('old-new-and-unbackfilled-reads',existing_reads)
    def old_caller():
        before=app.rows('SELECT * FROM profiles ORDER BY id')
        body,_=ok(app,{'op':'retire'})
        require(body=={'status':'blocked'},repr(body))
        require(app.rows('SELECT * FROM profiles ORDER BY id')==before,'blocked retirement changed data/schema')
        return body
    checks.run('active-nonweb-caller-blocks-retirement',old_caller)
    def dualwrite():
        body,_=ok(app,{'op':'update','id':1,'name':'Updated'})
        require(body=={'status':'ok'},repr(body))
        require(app.rows("SELECT 1 FROM information_schema.columns WHERE table_name='profiles' AND column_name='legacy_name'"),'legacy schema was destroyed before old callers retired')
        rows=app.rows('SELECT legacy_name,display_name FROM profiles WHERE id=1')
        require(rows==[{'legacy_name':'Updated','display_name':'Updated'}],repr(rows))
        app.execute("UPDATE profiles SET legacy_name='Old One',display_name=NULL WHERE id=1")
        return rows
    checks.run('legacy-new-write-compatibility',dualwrite)
    def rollback():
        app.execute('UPDATE consumers SET version=2 WHERE active')
        app.execute('UPDATE migration_settings SET rollback_required=true')
        before=app.rows('SELECT * FROM profiles ORDER BY id')
        body,_=ok(app,{'op':'retire'})
        require(body=={'status':'blocked'},repr(body))
        require(app.rows('SELECT * FROM profiles ORDER BY id')==before,'rollback promise lost schema/data')
        app.execute('UPDATE migration_settings SET rollback_required=false')
        return body
    checks.run('rollback-promise-blocks-retirement',rollback)
    def inventory_race():
        app.execute('UPDATE migration_settings SET rollback_required=false')
        app.execute('UPDATE consumers SET version=2')
        editor=psycopg.connect(app.admin.info.dsn,password=app.admin_password,autocommit=False)
        executor=ThreadPoolExecutor(max_workers=1)
        try:
            editor.execute("UPDATE consumers SET version=1 WHERE name='exporter'")
            future=executor.submit(app.request,{'op':'retire'})
            deadline=time.monotonic()+1.2
            observed_lock=False
            while not future.done():
                if app.rows("SELECT 1 FROM pg_stat_activity WHERE usename='app' AND wait_event_type='Lock'"):
                    observed_lock=True
                    break
                if time.monotonic()>deadline:
                    break
                time.sleep(0.01)
            editor.commit()
            status,body,_=future.result(timeout=4)
            require(observed_lock,'retirement did not wait for caller-inventory update')
            require(status==200 and body=={'status':'blocked'},repr((status,body)))
            require(app.rows("SELECT column_name FROM information_schema.columns WHERE table_name='profiles' AND column_name='legacy_name'"),'schema retired under concurrent old caller')
            return {'waited_for_inventory_lock':observed_lock,'response':body}
        finally:
            editor.rollback()
            editor.close()
            executor.shutdown(wait=True)
    checks.run('concurrent-inventory-change-protected',inventory_race)
    def retire():
        app.execute('UPDATE consumers SET version=2 WHERE active')
        app.execute('UPDATE migration_settings SET rollback_required=false')
        body,_=ok(app,{'op':'retire'})
        require(body=={'status':'retired'},repr(body))
        require(not app.rows("SELECT column_name FROM information_schema.columns WHERE table_name='profiles' AND column_name='legacy_name'"),'legacy schema never retired')
        rows=app.rows('SELECT id,display_name FROM profiles ORDER BY id')
        require(rows==[{'id':1,'display_name':'Old One'},{'id':2,'display_name':'New Two'}],repr(rows))
        repeat,_=ok(app,{'op':'retire'})
        require(repeat=={'status':'retired'},repr(repeat))
        old,_=ok(app,{'op':'read','id':1,'version':1})
        require(old=={'status':'retired'},repr(old))
        changed,_=ok(app,{'op':'update','id':1,'name':'Final'})
        current,_=ok(app,{'op':'read','id':1,'version':2})
        require(changed=={'status':'ok'} and current=={'status':'ok','name':'Final'},repr((changed,current)))
        return {'stored':rows,'repeat':repeat,'current':current}
    checks.run('safe-retirement-and-new-caller-continuity',retire)


EVALUATORS={name:globals()[name] for name in ('unique','event','authorization','relations','cleanup','migration')}


def evaluate(app):
    checks=Checks()
    EVALUATORS[app.family](app,checks)
    quality='observed' if checks.quality and all(c['observed'] for c in checks.quality) else ('not-observed' if checks.quality else 'not-run')
    return {'execution_health':'evaluated','semantic':'pass' if all(c['pass'] for c in checks.results) else 'fail','quality':quality,'checks':checks.results,'quality_checks':checks.quality}
