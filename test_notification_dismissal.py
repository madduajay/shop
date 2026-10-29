import os,sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx
from app import App,AGENT
from test_thread_auth import login
from watch_flow import WatchMemory

def card(event):return {'type':'availability','event_id':event,'name':'Red Silk Classic Tie','expires_at':time.time()+3600}
@pytest.mark.asyncio
async def test_dismiss_persistence_isolation_history_and_future(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'fixture.sqlite');w=app.watch_memory;a_id='a'*32;b_id='b'*32
 for c in (1,2):w.receive(c,card(a_id))
 profiles=[app.memory.get(i) for i in range(1,101)];orders=app.memory.orders()
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as a,httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as b:
  ha=await login(a,1);hb=await login(b,2)
  await a.post('/api/state',headers=ha,json={});flow=next(iter(app.clients.values()))[1];flow.messages=[{'role':'assistant','text':'Restock','cards':[card(a_id)]}];flow.trace.append({'kind':'proof','message':'unchanged'});history=json.dumps(flow.messages);trace=json.dumps(flow.trace)
  assert (await a.post('/api/notifications/dismiss',headers=ha,json={'event_id':a_id,'customer':2})).status_code==403
  assert (await a.post('/api/notifications/dismiss',json={'event_id':a_id})).status_code==403
  assert (await a.post('/api/notifications/dismiss',headers=ha,json={'event_id':b_id})).status_code==404
  for _ in range(2):assert (await a.post('/api/notifications/dismiss',headers=ha,json={'event_id':a_id})).status_code==200
  for endpoint in ('state','poll'):
   result=(await a.post('/api/'+endpoint,headers=ha,json={})).json();assert not result['notifications'];assert result['dismissed_notifications']==[a_id]
  assert not (await a.post('/api/state',headers=ha,json={})).json()['messages'][0]['cards']
  assert (await b.post('/api/state',headers=hb,json={})).json()['notifications'][0]['event_id']==a_id
  assert json.dumps(flow.messages)==history and json.dumps(flow.trace)==trace
  assert not w.receive(1,card(a_id));assert w.receive(1,card(b_id))
  assert [c['event_id'] for c in (await a.post('/api/state',headers=ha,json={})).json()['notifications']]==[b_id]
  assert WatchMemory(w.db).dismissed(1)==[a_id] and WatchMemory(w.db).dismissed(2)==[]
  import sqlite3
  reopened=sqlite3.connect(w.db.execute('PRAGMA database_list').fetchone()[2]);assert WatchMemory(reopened).dismissed(1)==[a_id];reopened.close()
  assert profiles==[app.memory.get(i) for i in range(1,101)] and orders==app.memory.orders()
 await app.http.aclose()
