"""Offline validation only: no sockets, browser, or remote service."""
import json,time
from types import SimpleNamespace
import pytest
from app import App,ORIGIN,AGENT
from availability_webhook import canonical,EXT
from starlette.requests import Request
@pytest.mark.asyncio
async def test_offline_webhook_auth_binding_replay_and_cancel(tmp_path,monkeypatch):
 from availability_webhook import AvailabilityWebhook
 monkeypatch.setattr(AvailabilityWebhook,'start',lambda self:None)
 app=App();await app.setup(tmp_path/'offline.sqlite');h=app.webhook
 try:
  p=app.thread_accounts.by_profile(1);consent='a'*32;conv=SimpleNamespace(owner=(app.identity.client_id,p['pairwise']),conversation_id='conv')
  local=dict(consent=consent,status='consented',expires_at=time.time()+600,delivery=EXT)
  app.watch_memory.save(1,local);reg=dict(extension=EXT,url=h.url,consent=consent)
  h.register(conv,reg);h.register(conv,reg)
  for url in ['http://atlas.localhost/extensions/forme-availability',h.url+'?q=1',h.url+'/',ORIGIN+'/shop','https://evil.example/hook','https://127.0.0.1/extensions/forme-availability']:
   with pytest.raises(ValueError):h.register(conv,dict(reg,url=url))
  with pytest.raises(ValueError):h.register(SimpleNamespace(owner=('https://evil.example/agent.json',p['pairwise']),conversation_id='bad'),reg)
  with pytest.raises(ValueError):h.register(SimpleNamespace(owner=(app.identity.client_id,'wrong-customer'),conversation_id='bad'),reg)
  candidate=app.store.availability.demo_candidate({'demo_trigger':'tie'})
  remote=app.store.availability.subscribe(json.dumps([*conv.owner,'forme_customer_001']),consent,candidate)
  remote.update(delivery=EXT,conversation_id='conv',due_at=time.time()-1);app.store.availability.save(remote);app.store.availability.tick()
  remote=json.loads(h.db.execute('SELECT data FROM watches').fetchone()[0]);local.update(status='active',watch_id=remote['id'],conversation_id='conv',expires_at=remote['expires_at']);app.watch_memory.save(1,local)
  app.company_links.bind(p['id'],ORIGIN,'forme_customer_001',['availability:watch'])
  raw=canonical(h.event(remote))
  async def receive(raw,proof):
   async def body():return {'type':'http.request','body':raw,'more_body':False}
   req=Request({'type':'http','method':'POST','path':'/extensions/forme-availability','headers':[(b'authorization',('Bearer '+proof).encode())]},body)
   return await h.receive(req)
  for overrides in [{'iss':'wrong'},{'aud':'wrong'},{'iat':int(time.time())-120,'exp':int(time.time())-60},{'exp':int(time.time())+120}]:assert (await receive(raw,h.assertion(raw,**overrides))).status_code==401
  assert (await receive(raw+b' ',h.assertion(raw))).status_code==401
  assert (await receive(raw,'invalid')).status_code==401
  for key,value in [('account','forme_customer_002'),('subject','other'),('event_id','b'*32),('watch_id','b'*32)]:
   value=canonical(dict(json.loads(raw),**{key:value}));assert (await receive(value,h.assertion(value))).status_code==403
  proof=h.assertion(raw);assert (await receive(raw,proof)).status_code==200
  assert (await receive(raw,proof)).status_code==409
  assert json.loads((await receive(raw,h.assertion(raw))).body)['duplicate']
  assert len(app.watch_memory.inbox(1))==1 and not app.watch_memory.inbox(2)
  local['status']='cancelled';app.watch_memory.save(1,local)
  assert (await receive(raw,h.assertion(raw))).status_code==403
  assert len(app.watch_memory.inbox(1))==1
 finally:await app.http.aclose()
