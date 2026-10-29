"""Single-process durable protocol boundary tests; no live database or network."""
import asyncio,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from app import App
from personal_agent_protocol.company import CompanyRequest
from types import SimpleNamespace

async def harness(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'fixture.sqlite')
 session=SimpleNamespace(client_id='https://independent.example/agent.json',pairwise_user_id='user_random_fixture',account_id='forme_customer_001',scopes=('availability:watch',))
 async def caller(request):return None,session
 app.shop._caller=caller # These tests isolate durable dispatch after authentication.
 async def supports(_):return False
 app.shop._supports_operations=supports
 req=CompanyRequest('POST',app.shop.config.conversations_endpoint+'?wait=0',{},json.dumps({'message':{'id':'msg_repeat','sender':'agent','text':'Watch','data':{'forme_availability':{'action':'subscribe','consent':'a'*32,'filters':{'demo_trigger':'tie'}}}}}).encode())
 return app,req
@pytest.mark.asyncio
async def test_concurrent_identical_requests_return_exact_original(tmp_path,monkeypatch):
 app,req=await harness(tmp_path,monkeypatch)
 from personal_agent_protocol.company import COMPANY_AGENTS
 from personal_agent_protocol.reactor import first_contribution
 agent=first_contribution(app.shop.reactor,COMPANY_AGENTS,'agent');original=agent.respond;calls=0
 async def delayed(turn):
  nonlocal calls
  calls+=1;await asyncio.sleep(.03);return await original(turn)
 agent.respond=delayed
 try:
  responses=await asyncio.gather(*(app.shop.handle(req) for _ in range(12)))
  assert all(r.status==201 and r.body==responses[0].body for r in responses)
  assert responses[0].body['status']=='idle'
  assert calls==1
  assert app.store.availability.db.execute('select count(*) from watches').fetchone()[0]==1
 finally:await app.http.aclose()
@pytest.mark.asyncio
@pytest.mark.parametrize('point',['after_claim','after_effect'])
async def test_interrupted_acceptance_retries_without_orphan_or_duplicate(tmp_path,monkeypatch,point):
 app,req=await harness(tmp_path,monkeypatch)
 from personal_agent_protocol.company.store import CONVERSATION
 if point=='after_claim':
  original=app.shop.store.put
  async def fail(k,*args,**kwargs):
   if k==CONVERSATION:raise RuntimeError('simulated crash after receipt claim')
   return await original(k,*args,**kwargs)
  app.shop.store.put=fail
 else:
  from personal_agent_protocol.company import COMPANY_AGENTS
  from personal_agent_protocol.reactor import first_contribution
  agent=first_contribution(app.shop.reactor,COMPANY_AGENTS,'agent');original=agent.respond
  async def fail(turn):
   await original(turn);raise RuntimeError('simulated crash after idempotent company effect')
  agent.respond=fail
 try:
  with pytest.raises(RuntimeError):await app.shop.handle(req)
  if point=='after_claim':app.shop.store.put=original
  else:agent.respond=original
  response=await app.shop.handle(req)
  assert response.status==201 and response.body['status']=='idle'
  assert app.store.availability.db.execute('select count(*) from watches').fetchone()[0]==1
  assert (await app.shop.handle(req)).body==response.body
 finally:await app.http.aclose()
@pytest.mark.asyncio
async def test_committed_response_survives_connection_reopen(tmp_path,monkeypatch):
 app,req=await harness(tmp_path,monkeypatch)
 try:
  response=await app.shop.handle(req)
  import sqlite3
  store=app.shop.store;path=store.db.execute('pragma database_list').fetchone()[2];store.db.close();store.db=sqlite3.connect(path)
  replay=await app.shop.handle(req)
  assert replay.status==response.status and replay.body==response.body
  assert app.store.availability.db.execute('select count(*) from watches').fetchone()[0]==1
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_task_cancellation_rolls_back_acceptance(tmp_path,monkeypatch):
 app,req=await harness(tmp_path,monkeypatch)
 from personal_agent_protocol.company import COMPANY_AGENTS
 from personal_agent_protocol.reactor import first_contribution
 agent=first_contribution(app.shop.reactor,COMPANY_AGENTS,'agent');original=agent.respond;entered=asyncio.Event()
 async def blocked(turn):entered.set();await asyncio.Event().wait()
 agent.respond=blocked
 try:
  task=asyncio.create_task(app.shop.handle(req));await entered.wait();task.cancel()
  with pytest.raises(asyncio.CancelledError):await task
  agent.respond=original
  response=await app.shop.handle(req);assert response.status==201 and response.body['status']=='idle'
 finally:await app.http.aclose()
