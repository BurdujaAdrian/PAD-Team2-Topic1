import json,subprocess,time,urllib.request,urllib.error,sys
import argparse
parser = argparse.ArgumentParser(description="Creates demo data, stops/restarts one Redis node and the primary DB in a standalone compose.cluster.yaml deployment. Do not use on a production cluster.")
parser.add_argument("service", choices=["zombie", "resource"])
parser.add_argument("project", help="Docker Compose project name, e.g. resource-check")
args = parser.parse_args()
slug=args.service; project=args.project
def docker(*args):return subprocess.check_output(['docker',*args],text=True,stderr=subprocess.DEVNULL).strip()
def sql(i,q):return docker('exec',f'{project}-db-{i}-1','sh','-c', 'PGPASSWORD="$POSTGRESQL_POSTGRES_PASSWORD" psql -h 127.0.0.1 -U postgres -d "$POSTGRESQL_DATABASE" -Atc "$1"', 'query',q)
def wait(fn,timeout=100):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   v=fn()
   if v:return v
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('Condition timed out')
def base(i):return 'http://'+docker('port',f'{project}-api-{i}','8080/tcp')
def request(i,method,path,data=None,expected=200):
 req=urllib.request.Request(base(i)+path,method=method,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
 try:r=urllib.request.urlopen(req,timeout=15)
 except urllib.error.HTTPError as e:r=e
 body=r.read().decode()
 if r.status!=expected:raise RuntimeError(f'{method} {path}: {r.status} {body}')
 return (json.loads(body) if body else None,dict(r.headers))
for i in [1,2]:wait(lambda:request(i,'GET','/api/status'))
path='/api/zombies/types' if slug=='zombie' else '/api/resource-nodes'
body={'name':'Resilience demo','category':'tourist','health':100,'speed':2,'attack_strength':5,'perception_radius':10,'abilities':[]} if slug=='zombie' else {'node_id':'resilience-'+str(time.time_ns()),'resource_type':'wood','quantity':50,'max_capacity':50}
created,_=request(1,'POST',path,body,201);id=created['zombie_type_id' if slug=='zombie' else 'node_id'];url=path+'/'+id
_,h=request(1,'GET',url);assert h['X-Cache']=='MISS',h
_,h=request(2,'GET',url);assert h['X-Cache']=='HIT',h
print(slug,'PASS two API replicas share cached data',flush=True)
owner=h['X-Cache-Shard'].split(':')[0];cache=f'{project}-{owner}-1'
docker('stop',cache)
try:
 _,h=request(2,'GET',url);assert h['X-Cache']=='MISS',h
 if slug=='zombie':body['health']=150
 else:body['quantity']=45
 request(1,'PUT',url,body)
 result,_=request(2,'GET',url);assert result['health' if slug=='zombie' else 'quantity']==(150 if slug=='zombie' else 45)
finally:docker('start',cache)
result,_=request(1,'GET',url);assert result['health' if slug=='zombie' else 'quantity']==(150 if slug=='zombie' else 45)
print(slug,'PASS Redis outage, mutation and recovery do not expose stale data',flush=True)
transaction='resilience-'+str(time.time_ns());player=transaction
if slug=='resource':
 request(1,'POST','/api/resource-transactions',{'action_id':transaction,'player_id':player,'node_id':id,'resource_type':'wood','quantity':20})
 request(1,'GET',f'/api/players/{player}/resources')
 request(2,'GET',f'/api/players/{player}/resources')
 request(1,'POST','/api/resource-transactions/prepare',{'transaction_id':transaction,'player_id':player,'reason':'crafting','items':[{'resource_type':'wood','quantity':5}]})
primary=next(i for i in [1,2,3] if sql(i,'SELECT pg_is_in_recovery()')=='f')
wait(lambda: sql(primary,'SELECT count(*) FROM pg_stat_replication')=='2')
print(slug,'Stopping primary',primary,flush=True);docker('stop',f'{project}-db-{primary}-1')
try:
 wait(lambda:request(1,'GET',url),120)
 if slug=='resource':
  result,_=request(2,'POST',f'/api/resource-transactions/{transaction}/commit');assert result['remaining']['wood']==15,result
  result2,_=request(1,'POST',f'/api/resource-transactions/{transaction}/commit');assert result2==result
  balances,_=request(1,'GET',f'/api/players/{player}/resources')
  assert next(x['quantity'] for x in balances['resources'] if x['resource_type']=='wood')==15
  print(slug,'PASS prepared reservation survives primary failover; commit retry deducts once',flush=True)
 else:
  body['health']=175;request(2,'PUT',url,body)
  result,_=request(1,'GET',url);assert result['health']==175
 print(slug,'PASS writes resume through the promoted primary',flush=True)
finally:docker('start',f'{project}-db-{primary}-1')
wait(lambda:sql(primary,'SELECT pg_is_in_recovery()')=='t',150)
wait(lambda:sum(sql(i,'SELECT pg_is_in_recovery()')=='f' for i in [1,2,3])==1)
leader=wait(lambda:next(i for i in [1,2,3] if sql(i,'SELECT pg_is_in_recovery()')=='f'))
wait(lambda:sql(leader,"SELECT count(*) FROM pg_stat_replication WHERE sync_state='quorum'")=='2')
assert sql(leader,'SHOW synchronous_standby_names')=='ANY 1 (*)'
print(slug,'PASS old primary rejoins; exactly one primary with two synchronous candidates',flush=True)
