"""Single-boundary mutations with their required behavioral rejection checks."""
from implementations import source


def replace_once(text, old, new):
    if text.count(old)!=1:
        raise ValueError('mutation anchor is not unique: '+repr(old))
    return text.replace(old,new,1)


def mutations(family,variant):
    correct=source(family,variant,1)
    result=[]
    def add(name,old,new,expected):
        result.append((name,replace_once(correct,old,new),expected))
    if family=='unique':
        add('missing-database-uniqueness',"    sql(c, 'CREATE UNIQUE INDEX IF NOT EXISTS account_key_unique ON accounts(account_key)')",'    pass','concurrent-key-ownership')
        add('storage-error-misclassified','except UniqueViolation:','except Exception:','storage-error-not-occupied')
        add('all-keys-denied',"    with pool.connection() as c:\n        try:","    return {'status':'occupied'}\n    with pool.connection() as c:\n        try:",'different-keys-create-durably')
        if variant==2:
            add('normalization-omitted',"key = r['key'].strip().lower() if NORMALIZE else r['key']","key = r['key']",'concurrent-key-ownership')
    elif family=='event':
        # Removing the single transaction scope recreates the acknowledged-claim crash window.
        broken=source(family,variant,0)
        result.append(('claim-committed-before-effect',broken,'claim-failure-recoverable'))
        add('effect-omitted',"            sql(c, 'INSERT INTO effects(event_id,amount) VALUES (%s,%s)', (r['event'],r['amount']))",'            pass','independent-events-preserved')
        add('deduplication-removed',"ON CONFLICT DO NOTHING RETURNING event_id","RETURNING event_id",'concurrent-delivery-single-effect')
        add('fault-swallowed',"            checkpoint(r, 'after_claim')","            if 'cancel' in r:\n                checkpoint(r, 'after_claim')",'claim-failure-recoverable')
        add('cancellation-swallowed',"            checkpoint(r, 'after_claim')","            if 'fault' in r:\n                checkpoint(r, 'after_claim')",'claim-cancellation-recoverable')
    elif family=='authorization':
        add('target-check-removed',"return row and (row['owner']==actor or (actor in row['writers']) or (not write and (row['is_public'] or actor in row['readers'])))",'return bool(row)','cross-owner-read-denied')
        add('reader-write-escalation',"(not write and (row['is_public'] or actor in row['readers']))","(row['is_public'] or actor in row['readers'])",'reader-cannot-write')
        add('delegation-removed',"(actor in row['writers'])",'False','owner-and-delegate-write')
        add('public-read-removed',"row['is_public'] or actor in row['readers']","actor in row['readers']",'public-read')
        add('shared-read-removed',"row['is_public'] or actor in row['readers']","row['is_public']",'shared-read')
        add('write-effect-omitted',"        sql(c,'UPDATE documents SET body=%s WHERE id=ANY(%s)',(r['body'],accepted))",'        pass','owner-and-delegate-write')
        add('wrong-batch-semantics','if ATOMIC and denied:','if not ATOMIC and denied:','mixed-batch-policy')
    elif family=='relations':
        result.append(('row-at-a-time-queries',source(family,variant,0),'public-query-roundtrip-slo'))
        add('children-truncated',"page=children[:2] if PAGED else children","page=children[:1]",'complete-ordered-tenant-overview')
        add('empty-project-dropped',"for p in parents]}","for p in parents if grouped[p['id']]]}",'complete-ordered-tenant-overview')
        add('tenant-filter-removed',"WHERE tenant=%s ORDER BY id',(r['tenant'],)","WHERE %s::text IS NOT NULL ORDER BY id',(r['tenant'],)",'complete-ordered-tenant-overview')
        if variant==2:
            add('continuation-lost',"'next':page[-1]['position'] if more else None","'next':None",'lossless-child-continuation')
            add('unbounded-child-materialization','        if PAGED:','        if False:','quality:bounded-child-materialization')
    elif family=='cleanup':
        result.append(('connection-leak',source(family,1,0),'fault-after_read-pool-recovered'))
        equivalent=source(family,variant,2)
        result.append(('rollback-omitted',replace_once(equivalent,'            c.rollback()','            pass'),'fault-after_write-pool-recovered'))
        add('write-omitted',"        sql(c,'UPDATE wallets SET balance=balance+%s WHERE id=%s',(r['amount'],r['id']))",'        pass','durable-valid-long-request')
        add('fault-swallowed',"        checkpoint(r,'after_read')","        if 'cancel' in r:\n            checkpoint(r,'after_read')",'fault-after_read-pool-recovered')
        add('cancellation-swallowed',"        checkpoint(r,'after_write')","        if 'fault' in r:\n            checkpoint(r,'after_write')",'cancel-after_write-pool-recovered')
    elif family=='migration':
        add('nonweb-callers-ignored',"SELECT 1 FROM consumers WHERE active AND version=1","SELECT 1 FROM consumers WHERE name=chr(119)||chr(101)||chr(98) AND active AND version=1",'active-nonweb-caller-blocks-retirement')
        add('rollback-promise-ignored','if old or rollback:','if old:','rollback-promise-blocks-retirement')
        add('inventory-lock-omitted',"        sql(c,'LOCK TABLE consumers, migration_settings IN SHARE MODE')",'        pass','concurrent-inventory-change-protected')
        add('backfill-omitted',"        sql(c,'UPDATE profiles SET display_name=COALESCE(display_name,legacy_name)')",'        pass','safe-retirement-and-new-caller-continuity')
        add('new-data-overwritten','SET display_name=COALESCE(display_name,legacy_name)','SET display_name=legacy_name','safe-retirement-and-new-caller-continuity')
        add('retirement-permanently-blocked','if old or rollback:','if True:','safe-retirement-and-new-caller-continuity')
        add('dualwrite-omitted',"SET legacy_name=%s,display_name=%s WHERE id=%s',(r['name'],r['name'],r['id'])","SET display_name=%s WHERE id=%s',(r['name'],r['id'])",'legacy-new-write-compatibility')
        add('fallback-omitted',"('COALESCE(display_name,legacy_name)' if old else 'display_name')","'display_name'",'old-new-and-unbackfilled-reads')
    for _,code,_ in result:
        compile(code,'mutation','exec')
    return result
