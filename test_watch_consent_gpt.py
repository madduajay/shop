import os,sys,asyncio,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
@pytest.mark.parametrize('first',['shoes','tie'])
@pytest.mark.asyncio
async def test_real_gpt_watch_consent(tmp_path,first):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Requires actual GPT configuration')
 app=App();await app.setup(tmp_path/'consent.sqlite');f=Flow(app,1);CURRENT.set(f);report=[]
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),log_level='critical',access_log=False));task=asyncio.create_task(server.serve())
 async def chat(q):
  r,c=await f.chat(q);report.append({'question':q,'reply':r,'status':getattr(f,'agent_task',{}).get('status'),'sign_in':bool(f.signurl)})
  assert 'not sure' not in r and 'repeated an earlier' not in r and r.count('Would you like')<=1,r
  return r
 try:
  while not server.started:await asyncio.sleep(.05)
  for index,(kind,affirmative) in enumerate([(first,'yes please'),('tie' if first=='shoes' else 'shoes','notify me')]):
   reply=await chat('show red '+kind);assert 'Would you like' in reply and f.agent_task['status']=='waiting_user' and not f.signurl
   offered=f.watch_rows()[-1]['consent'];assert all(w['consent']!=offered for w in [json.loads(r[0]) for r in app.store.availability.db.execute('select data from watches')])
   assert 'won’t notify' in await chat('no thanks');assert next(w for w in f.watch_rows() if w['consent']==offered)['status']=='cancelled'
   await chat('show red '+kind)
   if index==0:
    stale=f.watch_rows()[-1];stale['expires_at']=time.time()+2;app.watch_memory.save(1,stale)
    await chat('show red '+kind);assert f.watch_rows()[-1]['expires_at']>time.time()+590
    near=f.watch_rows()[-1];near['expires_at']=time.time()+2;app.watch_memory.save(1,near)
   before=app.model.calls
   reply=await chat(affirmative);assert app.model.calls==before # Resolve against exact pending offer, not a new ambiguous model plan.
   if index==0:
    assert f.signurl and f.agent_task['status']=='waiting_auth';url=f.signurl
    consented=f.watch_rows()[-1];assert consented['expires_at']>time.time()+590 and consented['offer_expires_at']<time.time()+3
    await chat('yes');assert f.signurl==url
    t=app.tickets[url.split('ticket=')[1]]
    await app.http.post(url,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
    await asyncio.sleep(5.2);reply=await f.poll();reply,_=await f.continue_agent_task(reply,[])
    assert f.agent_task['status']=='completed' and 'FORME will notify' in reply
    from trace_page import render
    posts=[e for e in f.trace if '/poppy/conversations' in e.get('endpoint','') and e.get('request',{}).get('method')=='POST']
    assert len(posts)>=2 and posts[-2]['status']==201 and posts[-1]['status']==202 and '/messages?' in posts[-1]['endpoint'] and posts[-1]['direction']=='Thread server → FORME → Thread server'
    rendered=render(f.trace,[]);assert '/poppy/conversations' in rendered and 'Send a consented availability message' in rendered and '<details open' not in rendered
   else:assert not f.signurl and 'FORME will notify' in reply
   w=f.watch_rows()[-1];assert w['status']=='active'
   count=app.store.availability.db.execute('select count(*) from watches').fetchone()[0]
   await chat('notify me');await chat('yes');assert app.store.availability.db.execute('select count(*) from watches').fetchone()[0]==count
   app.store.availability.now=lambda:time.time()+61
   for _ in range(50):
    if next(x for x in f.watch_rows() if x['consent']==w['consent'])['status']=='delivered':break
    await asyncio.sleep(.1)
   assert next(x for x in f.watch_rows() if x['consent']==w['consent'])['status']=='delivered'
   card=app.watch_memory.inbox(1)[-1];assert app.watch_memory.dismiss(1,card['event_id']) and card['event_id'] in app.watch_memory.dismissed(1)
   app.store.availability.now=time.time
  await chat('show red shoes');pending=f.watch_rows()[-1]['consent'];await chat('hello');reply=await chat('yes');assert 'name the item' in reply and next(w for w in f.watch_rows() if w['consent']==pending)['status']=='offered'
  assert not app.memory.orders() and app.model.actual and app.model.calls>0
 finally:
  Path('evidence/visibility-gpt-trace-'+first+'.json').write_text(json.dumps(list(f.trace),default=str,indent=2))
  Path('evidence/consent-gpt-'+first+'.json').write_text(json.dumps({'model':app.model.actual,'model_calls':app.model.calls,'turns':report},indent=2))
  await f.stop_watch_streams();await f.browser.close();await app.http.aclose();server.should_exit=True;await task
