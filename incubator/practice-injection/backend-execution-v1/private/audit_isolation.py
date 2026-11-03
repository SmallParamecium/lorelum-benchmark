"""Executable cross-attempt and real-canary isolation audit; no model calls."""
import argparse
import hashlib
import json
import pathlib
import secrets
import tempfile

from definitions import SCHEMAS
from implementations import source
from engine import Application, docker, bound_port


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite isolation evidence')
    canary=pathlib.Path(tempfile.gettempdir())/('backend-private-canary-'+secrets.token_hex(8))
    marker=secrets.token_hex(32)
    canary.write_text(marker,encoding='utf-8')
    try:
        with Application('unique',1,source('unique',1,1),SCHEMAS['unique'],'') as first, Application('unique',2,source('unique',2,1),SCHEMAS['unique'],'') as second:
            peer=json.loads(docker('inspect',second.db_name))[0]
            peer_ip=peer['NetworkSettings']['Networks'][second.network]['IPAddress']
            peer_host_port=bound_port(second.ingress_name,5432)
            probe='''import pathlib,socket,json,os,psycopg
checks={}
checks['real_host_canary_unreadable']=not pathlib.Path('/work/../'+CANARY).exists() and not pathlib.Path(HOST_CANARY).exists()
checks['docker_socket_absent']=not pathlib.Path('/var/run/docker.sock').exists() and 'DOCKER_HOST' not in os.environ
checks['admin_credentials_absent']='POSTGRES_PASSWORD' not in os.environ and 'admin' not in os.environ['DATABASE_URL']
for label,host,port in [('peer_database_network_denied',PEER_IP,5432),('peer_host_ingress_denied','host.docker.internal',PEER_PORT)]:
 try:
  connection=socket.create_connection((host,port),timeout=0.4);connection.close();checks[label]=False
 except OSError:
  checks[label]=True
try:
 with psycopg.connect(os.environ['DATABASE_URL']) as c:
  c.execute('SELECT rolpassword FROM pg_authid').fetchall()
 checks['credential_catalog_denied']=False
except psycopg.errors.InsufficientPrivilege:
 checks['credential_catalog_denied']=True
print(json.dumps(checks))
'''
            prelude='CANARY='+repr(canary.name)+'\nHOST_CANARY='+repr(str(canary))+'\nPEER_IP='+repr(peer_ip)+'\nPEER_PORT='+repr(peer_host_port)+'\n'
            checks=json.loads(docker('exec',first.app_name,'python','-c',prelude+probe))
            checks.update(first.isolation_probe())
            mounts=json.loads(docker('inspect',first.app_name))[0]['Mounts']
            checks['only_public_readonly_mount']=len(mounts)==1 and mounts[0]['Destination']=='/work' and not mounts[0]['RW'] and pathlib.Path(mounts[0]['Source']).name==first.directory.name
            report={'kind':'isolation-audit-not-effectiveness','model_calls':0,'canary_existed_on_host':canary.read_text()==marker,'canary_sha256':hashlib.sha256(marker.encode()).hexdigest(),'checks':checks,'passed':all(checks.values())}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as output:
            json.dump(report,output,indent=2)
        print(json.dumps(report,indent=2))
        return 0 if report['passed'] else 1
    finally:
        canary.unlink(missing_ok=True)


if __name__=='__main__':
    raise SystemExit(main())
