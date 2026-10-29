import os,sys,json,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx,uvicorn
from app import App,Flow,CURRENT,ORIGIN
from test_commerce import login,add
QUERIES=['show me what is on the baf','show me what is on the bag','what have I got in my basket?','show the shirts in my cart','could you check what I already put in there?','how much is that altogether?','lemme see whats inside the shopping basket','is my basket empty?']
@pytest.mark.asyncio
async def test_semantic_bag_tool_and_contract(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'m.sqlite');f=Flow(app,1);app.model.key='fixture';seen=[]
 async def planner(instructions,payload,tools):
  assert 'read_forme_bag' in [t['name'] for t in tools];seen.append(payload)
  return [{'name':'read_forme_bag','arguments':'{}'}]
 app.model.context_tools=planner
 async def bag():f.last_read='bag';return 'VERIFIED BAG',[]
 f.show_bag=bag
 try:
  for q in QUERIES:assert (await f.answer_question(q))[0]=='VERIFIED BAG'
  assert seen[-1]['last_read']=='bag' and seen[-1]['previous_questions']
  for args in ['{"customer":2}','{"checkout":true}','null']:
   async def bad(*a):return [{'name':'read_forme_bag','arguments':args}]
   app.model.context_tools=bad;assert 'couldn’t complete' in (await f.answer_question(QUERIES[0]))[0]
  assert not app.memory.orders()
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_bag_does_not_claim_unverified_empty(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'m.sqlite');f=Flow(app,1)
 try:
  for snap in ({'cart':[],'page':'login'},{'cart':[],'page':'cart','error':'Sign in'}, {'page':'cart'}, {'page':'cart','cart':[],'signed_in':False}):
   async def connected():return snap,None
   f.connected_bag=connected;assert 'couldn’t verify' in (await f.show_bag())[0]
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_semantic_bag_browser_recovery_isolation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'m.sqlite');app.model.key='fixture';before=[app.memory.get(i) for i in range(1,101)]
 async def planner(*a):return [{'name':'read_forme_bag','arguments':'{}'}]
 app.model.context_tools=planner
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve());flows=[]
 async def authorize(f):
  t=app.tickets[f.signurl.split('ticket=')[1]];assert set(t['scopes'])=={'orders:read'}
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':f'customer{f.customer:03}@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await f.poll();assert f.pending_read is None and f.signurl is None;assert await f.poll() is None;return reply
 try:
  while not server.started:await asyncio.sleep(.05)
  async with httpx.AsyncClient(verify=app.http._transport._pool._ssl_context,base_url=ORIGIN,trust_env=False) as direct:
   await login(direct);await add(direct,'tee','L')
   original=app.store.commerce.cart('account:forme_customer_001')['lines']
   for n in (1,2,1):
    f=Flow(app,n);flows.append(f);CURRENT.set(f)
    reply,_=await f.answer_question(QUERIES[0]);assert 'Sign in with FORME' in reply and f.pending_read=='bag'
    reply=await authorize(f)
    assert ('Essential Crew Tee' in reply) if n==1 else ('bag is empty' in reply)
    for q in QUERIES:
     reply,_=await f.answer_question(q);assert ('Essential Crew Tee' in reply and '32.00' in reply) if n==1 else ('bag is empty' in reply)
    assert not f.review and not getattr(f,'pending_add',None)
   assert app.store.commerce.cart('account:forme_customer_001')['lines']==original
   assert before==[app.memory.get(i) for i in range(1,101)] and not app.memory.orders()
 finally:
  for f in flows:await f.browser.close()
  await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_bag_identity_guard(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'m.sqlite');f=Flow(app,1);f.token=object();calls=[]
 async def browser(action,**kwargs):
  calls.append(action);assert action=='account_status';return {'signed_in':True,'account_id':'forme_customer_002'}
 f.browser.call=browser
 try:
  reply,_=await f.show_bag();assert 'does not match' in reply and calls==['account_status'] and not f.signurl
 finally:await app.http.aclose()
