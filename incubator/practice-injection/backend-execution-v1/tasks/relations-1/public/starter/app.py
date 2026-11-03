from server import pool, sql, checkpoint
PAGED = False

def project_result(parent, children, request):
    after=request.get('after',{}).get(str(parent['id']),0) if PAGED else -1
    children=[c for c in children if c['position']>after]
    page=children[:2] if PAGED else children
    more=PAGED and len(children)>len(page)
    return {'id':parent['id'],'name':parent['name'],'children':page,'next':page[-1]['position'] if more else None}

def prepare(c):
    pass

def handle(r):
    with pool.connection() as c:
        parents=sql(c,'SELECT * FROM projects WHERE tenant=%s ORDER BY id',(r['tenant'],)).fetchall()
        result=[]
        for p in parents:
            children=sql(c,'SELECT * FROM children WHERE project_id=%s ORDER BY position,id',(p['id'],)).fetchall()
            result.append(project_result(p,children,r))
        return {'projects':result}
