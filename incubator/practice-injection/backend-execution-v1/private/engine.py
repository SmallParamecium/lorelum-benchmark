"""Isolated Docker application runner. No private files enter candidate containers."""
import contextlib
import json
import pathlib
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

import psycopg
from psycopg.rows import dict_row

POSTGRES = 'postgres:17.6@sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929'
IMAGE = 'backend-execution-python:v1'
ROOT = pathlib.Path(__file__).resolve().parent.parent


def docker(*args, timeout=60):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'docker {args[0]} failed: {result.stderr.strip()}')
    return result.stdout.strip()


def bound_port(container, port):
    return int(docker('port', container, str(port)).split(':')[-1])


class Application:
    def __init__(self, family, variant, source, schema, seed):
        self.family, self.variant = family, variant
        self.prefix = 'backend-' + uuid.uuid4().hex[:12]
        self.network = self.prefix + '-net'
        self.db_name = self.prefix + '-db'
        self.app_name = self.prefix + '-app'
        self.ingress_name = self.prefix + '-ingress'
        self.admin_password = secrets.token_hex(16)
        self.app_password = secrets.token_hex(16)
        self.directory = pathlib.Path(tempfile.mkdtemp(prefix='backend-public-'))
        self.admin = None
        self.resources = []
        self.observations = []
        try:
            public = ROOT/'tasks'/f'{family}-{variant}'/'public'/'starter'
            shutil.copyfile(public/'server.py', self.directory/'server.py')
            (self.directory/'app.py').write_text(source, encoding='utf-8')
            docker('network','create','--internal',self.network)
            self.resources.append(('network',self.network))
            docker('run','-d','--name',self.db_name,'--network',self.network,'--network-alias','database','--env','POSTGRES_USER=admin','--env','POSTGRES_PASSWORD='+self.admin_password,POSTGRES,'postgres','-c','shared_preload_libraries=pg_stat_statements','-c','pg_stat_statements.track=all')
            self.resources.append(('container',self.db_name))
            ingress_source=(ROOT/'private'/'ingress.py').read_text(encoding='utf-8')
            docker('run','-d','--name',self.ingress_name,'--network','bridge','--publish','127.0.0.1::5432','--publish','127.0.0.1::8080','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python',IMAGE,'-u','-c',ingress_source)
            self.resources.append(('container',self.ingress_name))
            docker('network','connect',self.network,self.ingress_name)
            deadline=time.monotonic()+30
            while True:
                try:
                    self.admin=psycopg.connect(host='127.0.0.1',port=bound_port(self.ingress_name,5432),dbname='admin',user='admin',password=self.admin_password,autocommit=True,row_factory=dict_row,connect_timeout=2)
                    break
                except psycopg.OperationalError:
                    if time.monotonic()>deadline:
                        raise
                    time.sleep(0.1)
            self.admin.execute("CREATE ROLE app LOGIN PASSWORD %s".replace('%s',"'"+self.app_password+"'"))
            self.admin.execute('CREATE DATABASE backend OWNER app')
            self.admin.execute('REVOKE CONNECT ON DATABASE admin FROM PUBLIC')
            self.admin.execute('REVOKE CONNECT ON DATABASE postgres FROM PUBLIC')
            self.admin.execute('REVOKE CONNECT ON DATABASE template1 FROM PUBLIC')
            port=bound_port(self.ingress_name,5432)
            self.admin.close()
            self.admin=psycopg.connect(host='127.0.0.1',port=port,dbname='backend',user='admin',password=self.admin_password,autocommit=True,row_factory=dict_row)
            self.admin.execute('CREATE EXTENSION pg_stat_statements')
            self.admin.execute('SET ROLE app')
            self.admin.execute(schema)
            if seed:
                self.admin.execute(seed)
            self.admin.execute('RESET ROLE')
            dsn=f'host=database dbname=backend user=app password={self.app_password} application_name=backend_candidate connect_timeout=2 options=-cstatement_timeout=1800'
            docker('run','-d','--name',self.app_name,'--network',self.network,'--network-alias','application','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=8m','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1','--mount',f'type=bind,source={self.directory},target=/work,readonly','--env','DATABASE_URL='+dsn,IMAGE)
            self.resources.append(('container',self.app_name))
            self.url=f'http://127.0.0.1:{bound_port(self.ingress_name,8080)}/'
            deadline=time.monotonic()+15
            while True:
                try:
                    urllib.request.urlopen(self.url,timeout=1)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code==501:
                        break
                    raise
                except (urllib.error.URLError,TimeoutError,ConnectionResetError):
                    if time.monotonic()>deadline:
                        raise RuntimeError('application startup failed: '+docker('logs',self.app_name))
                    time.sleep(0.1)
        except BaseException:
            self.close()
            raise

    def request(self, payload):
        request=urllib.request.Request(self.url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        start=time.monotonic()
        try:
            with urllib.request.urlopen(request,timeout=3) as response:
                status=response.status
                body=json.load(response)
        except urllib.error.HTTPError as exc:
            status=exc.code
            body=json.loads(exc.read())
        observed={'request':payload,'http':status,'body':body,'elapsed_seconds':time.monotonic()-start}
        self.observations.append(observed)
        return status,body['result'],body['queries']

    def rows(self, query, args=()):
        return self.admin.execute(query,args or None).fetchall()

    def execute(self, query, args=()):
        self.admin.execute(query,args or None)

    def statement_count(self):
        return int(self.rows("SELECT COALESCE(sum(calls),0) AS n FROM pg_stat_statements WHERE userid=(SELECT oid FROM pg_roles WHERE rolname='app')")[0]['n'])

    def materialized_row_count(self):
        return int(self.rows("SELECT COALESCE(sum(rows),0) AS n FROM pg_stat_statements WHERE userid=(SELECT oid FROM pg_roles WHERE rolname='app')")[0]['n'])

    def restart(self):
        docker('restart',self.app_name)
        deadline=time.monotonic()+10
        while True:
            try:
                urllib.request.urlopen(self.url,timeout=1)
            except urllib.error.HTTPError as exc:
                if exc.code==501:
                    return
                raise
            except (urllib.error.URLError,TimeoutError,ConnectionResetError):
                if time.monotonic()>deadline:
                    raise RuntimeError('application did not recover after restart')
                time.sleep(0.1)

    def concurrent(self, requests, table):
        """Block INSERT triggers until both sessions reached the same write window."""
        from concurrent.futures import ThreadPoolExecutor
        self.execute('CREATE OR REPLACE FUNCTION insertion_gate() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock(77119); RETURN NEW; END $$')
        self.execute(f'CREATE TRIGGER insertion_gate BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION insertion_gate()')
        self.execute('SELECT pg_advisory_lock(77119)')
        executor=ThreadPoolExecutor(max_workers=len(requests))
        futures=[executor.submit(self.request,r) for r in requests]
        try:
            deadline=time.monotonic()+1.2
            while True:
                waiting=self.rows("SELECT count(*) AS n FROM pg_stat_activity WHERE usename='app' AND wait_event='advisory'")[0]['n']
                if waiting==len(requests):
                    break
                if time.monotonic()>deadline:
                    raise AssertionError('concurrency barrier did not observe every insert session')
                time.sleep(0.01)
        finally:
            self.execute('SELECT pg_advisory_unlock(77119)')
        try:
            return [future.result(timeout=4) for future in futures]
        finally:
            executor.shutdown(wait=True)
            self.execute(f'DROP TRIGGER insertion_gate ON {table}')

    def isolation_probe(self):
        probe="""import os,socket,psycopg,json,pathlib
checks={}
checks['mounts_only_public']=sorted(p.name for p in pathlib.Path('/work').iterdir())==['__pycache__','app.py','server.py'] if pathlib.Path('/work/__pycache__').exists() else sorted(p.name for p in pathlib.Path('/work').iterdir())==['app.py','server.py']
checks['host_canary_unavailable']=not pathlib.Path('/host/private-canary').exists() and not pathlib.Path('E:/loerlum-benchmark').exists()
checks['private_absent']=not pathlib.Path('/work/private').exists() and not pathlib.Path('/work/../private').exists()
try:
 psycopg.connect(os.environ['DATABASE_URL']+' dbname=postgres',connect_timeout=1)
 checks['admin_database_denied']=False
except psycopg.Error:
 checks['admin_database_denied']=True
try:
 s=socket.create_connection(('1.1.1.1',443),timeout=0.3);s.close();checks['external_network_denied']=False
except OSError:
 checks['external_network_denied']=True
print(json.dumps(checks))
"""
        return json.loads(docker('exec',self.app_name,'python','-c',probe))

    def close(self):
        if self.admin:
            self.admin.close()
            self.admin=None
        for kind,name in reversed(self.resources):
            with contextlib.suppress(Exception):
                docker('rm','-f',name) if kind=='container' else docker('network','rm',name)
        self.resources=[]
        shutil.rmtree(self.directory,ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()
