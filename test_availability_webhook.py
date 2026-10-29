import os,asyncio,time,json
from pathlib import Path
os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
from availability_webhook import EXT,canonical,AvailabilityWebhook
from starlette.responses import JSONResponse
@pytest.mark.asyncio
async def test_real_webhook_delivery_and_security(tmp_path):
 app=App();await app.setup(tmp_path/'webhook.sqlite');await app.webhook.close();f=Flow(app,1);CURRENT.set(f);outage=False
 async def endpoint(scope,receive,send):
  if outage and scope.get('path')=='/extensions/forme-availability':return await JSONResponse({'error':'temporary_outage'},503)(scope,receive,send)
  return await app(scope,receive,send)
 server=uvicorn.Server(uvicorn.Config(endpoint,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  reply,_=await f.chat('show red tie');assert 'Would you like' in reply,reply
  await f.chat('notify me');assert f.signurl
  t=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);await f.poll();w=f.watch_rows()[-1]
  assert w['status']=='active' and w['delivery']==EXT and not getattr(f,'watch_streams',{})
  def remote():return json.loads(app.store.availability.db.execute('SELECT data FROM watches WHERE consent=?',(w['consent'],)).fetchone()[0])
  conv=await app.shop._conversation(w['conversation_id']);reg={'extension':EXT,'url':app.webhook.url,'consent':w['consent']}
  for url in ['http://atlas.localhost:8545/extensions/forme-availability',app.webhook.url+'?x=1',app.webhook.url+'/',ORIGIN+'/shop','https://evil.example/hook','https://127.0.0.1:8545/extensions/forme-availability','https://atlas.localhost:8443/extensions/forme-availability']:
   with pytest.raises(ValueError):app.webhook.register(conv,dict(reg,url=url))
  app.store.availability.now=lambda:time.time()+61
  outage=True;await app.webhook.tick();r=remote();assert r['webhook_attempts']==1 and not r.get('webhook_delivered') and not app.watch_memory.inbox(1)
  next_attempt=r['next_attempt'];await app.webhook.tick();assert remote()['webhook_attempts']==1
  app.webhook=AvailabilityWebhook(app,app.webhook.agent,ORIGIN);outage=False
  await asyncio.sleep(max(0,next_attempt-time.time())+.05);await app.webhook.tick()
  assert remote()['webhook_delivered'] and len(app.watch_memory.inbox(1))==1 and not app.watch_memory.inbox(2)
  raw=canonical(app.webhook.event(remote()))
  async def post(raw,proof):return await app.http.post(app.webhook.url,content=raw,headers={'Authorization':'Bearer '+proof,'Content-Type':'application/json'})
  proof=app.webhook.assertion(raw);assert (await post(raw,proof)).json()['duplicate'];assert (await post(raw,proof)).status_code==409
  for overrides in [{'iss':'https://evil.example'},{'aud':ORIGIN},{'iat':int(time.time())-120,'exp':int(time.time())-60}]:assert (await post(raw,app.webhook.assertion(raw,**overrides))).status_code==401
  assert (await post(raw+b' ',app.webhook.assertion(raw))).status_code==401
  assert (await post(raw,'invalid')).status_code==401
  for field,value in [('account','forme_customer_002'),('event_id','0'*32)]:
   bad=json.loads(raw);bad[field]=value;other=canonical(bad);assert (await post(other,app.webhook.assertion(other))).status_code==403
  assert len(app.watch_memory.inbox(1))==1
  app.store.availability.now=time.time
  await f.chat('red shoes');await f.chat('notify me');assert f.watch_rows()[-1]['status']=='active'
  await f.chat('cancel watch');app.store.availability.now=lambda:time.time()+61;await app.webhook.tick()
  assert len(app.watch_memory.inbox(1))==1 and f.watch_rows()[-1]['status']=='cancelled'
  assert not app.memory.orders() and not app.store.commerce.cart('account:forme_customer_001')['lines']
  exchanges=[e for e in f.trace if '/poppy/conversations' in e.get('endpoint','')]
  assert any('thread_webhook' in json.dumps(e.get('request')) and e['status']==201 for e in exchanges)
  assert any('/messages?' in e.get('endpoint','') and e['status']==202 for e in exchanges)
  assert not any('/events' in e.get('endpoint','') for e in exchanges)
  hooks=[json.loads(row[0]) for row in app.watch_memory.db.execute('SELECT data FROM webhook_traces')]
  assert [e['status'] for e in hooks]==[503,200]
  from trace_page import render
  html=render(exchanges+hooks,[]);assert 'Custom extension' in html and 'FORME → Thread' in html and 'fixed callback' in html
  Path('evidence/custom-webhook.json').write_text(json.dumps({'registration':exchanges,'webhooks':hooks,'model_calls':app.model.calls,'no_sse':True,'no_orders':True,'isolated_inbox':True},indent=2))
 finally:
  await app.webhook.close();await f.stop_watch_streams();await f.browser.close();await app.http.aclose();server.should_exit=True;await task
