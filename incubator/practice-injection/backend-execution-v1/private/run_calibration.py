"""Offline calibration entry point; never invokes an LLM or creates formal records."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import hashlib
import json
import pathlib
import platform
import sys

from definitions import SCHEMAS
from implementations import FAMILIES, source
from mutations import mutations
from evaluator import evaluate, seed
from engine import Application, ROOT, IMAGE, POSTGRES, docker


def attempt(family,variant,name,code,expected):
    compile(code,f'{family}-{variant}-{name}','exec')
    record={'task':f'{family}-{variant}','implementation':name,'source_sha256':hashlib.sha256(code.encode()).hexdigest(),'expected':expected}
    try:
        with Application(family,variant,code,SCHEMAS[family],seed(family,variant)) as app:
            record['isolation']=app.isolation_probe()
            record['observations']=app.observations
            record['outcome']=evaluate(app)
        outcome=record['outcome']
        failed={c['id'] for c in outcome['checks'] if not c['pass']}
        if expected=='pass':
            matched=outcome['semantic']=='pass'
        elif expected=='fail':
            matched=outcome['semantic']=='fail'
        elif expected.startswith('quality:'):
            matched=outcome['semantic']=='pass' and any(c['id']==expected.split(':',1)[1] and not c['observed'] for c in outcome.get('quality_checks',[]))
        else:
            matched=expected in failed
        record['calibration_pass']=matched and all(record['isolation'].values())
    except Exception as exc:
        record['outcome']={'execution_health':'execution-failed','semantic':'not-run','quality':'not-run','reason':type(exc).__name__+': '+str(exc)}
        record['calibration_pass']=False
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family',choices=list(FAMILIES))
    parser.add_argument('--workers',type=int,default=2,choices=(1,2))
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite existing calibration evidence')
    jobs=[]
    for family in ([args.family] if args.family else FAMILIES):
        for variant in (1,2):
            for index,name,expected in [(0,'starter','fail'),(1,'reference','pass'),(2,'equivalent','pass')]:
                jobs.append((family,variant,name,source(family,variant,index),expected))
            for name,code,expected in mutations(family,variant):
                jobs.append((family,variant,'mutation-'+name,code,expected))
    for family,variant,name,code,_ in jobs:
        compile(code,f'{family}-{variant}-{name}','exec')
    sources={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(ROOT.rglob('*')) if path.is_file() and '__pycache__' not in str(path) and path.suffix in ('.py','.sql','.md','.json')}
    report={'kind':'offline-calibration-not-effectiveness','revision':'backend-execution-v1','created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_calls':0,'python':platform.python_version(),'postgres_image':POSTGRES,'candidate_image':docker('image','inspect',IMAGE,'--format','{{.Id}}'),'source_sha256':sources,'planned':len(jobs),'results':[]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        pending=[executor.submit(attempt,*job) for job in jobs]
        for future in as_completed(pending):
            record=future.result()
            report['results'].append(record)
            print(json.dumps({'task':record['task'],'implementation':record['implementation'],'calibration_pass':record['calibration_pass'],'semantic':record['outcome']['semantic']},ensure_ascii=False),flush=True)
    report['passed']=sum(r['calibration_pass'] for r in report['results'])
    report['complete']=len(report['results'])==report['planned']
    with args.output.open('x',encoding='utf-8') as destination:
        json.dump(report,destination,ensure_ascii=False,indent=2)
    print(json.dumps({'planned':report['planned'],'passed':report['passed'],'output':str(args.output)}),flush=True)
    return 0 if report['complete'] and report['passed']==report['planned'] else 1


if __name__=='__main__':
    sys.exit(main())
