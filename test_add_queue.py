import os,sys,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
from chat_routing import route,catalog_discovery

@pytest.mark.parametrize('q',['show me ties','show me tie','show me neckties','find ties','show me shirts','show me shoes'])
def test_catalog_routes(q):
 assert route(q)=='shopping' and catalog_discovery(q)
 assert not catalog_discovery('show me my bag')

@pytest.mark.asyncio
async def test_catalog_tool_preserves_unsupported_discovery_without_private_reads(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'unsupported-tool.sqlite');f=Flow(app,1);app.model.key='fixture-only';f.last_read='bag'
 async def forbidden(*a,**kw):raise AssertionError('Unsupported catalog discovery must not read private data or browse')
 f.answer_question=forbidden;f.show_bag=forbidden;f.open=forbidden
 try:
  for text in ['show me bags','find me a cummerbund','I need a cravat','could you show me brooches']:
   reply,cards=await f.execute_tool_calls(text,[{'name':'catalog_search','arguments':'{}'}])
   assert 'does not currently support that product category' in reply and not cards
  assert not app.memory.orders() and not f.signurl
 finally:await app.close()

@pytest.mark.asyncio
async def test_queue_and_catalog_with_actual_gpt(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Requires actual GPT configuration')
 app=App();await app.setup(tmp_path/'queue.sqlite');f=Flow(app,1);CURRENT.set(f)
 before=[app.memory.get(i) for i in range(1,101)]
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 async def search(q,category):
  mark=len(f.trace);reply,cards=await f.chat(q)
  assert f.catalog_snapshot['filters']['category']==category,(q,reply)
  assert 'bag is empty' not in reply.lower()
  assert not any(e.get('tool')=='read_forme_bag' or e.get('action') in ('cart','review','checkout') for e in f.trace[mark:]),q
  return reply,cards
 try:
  while not server.started:await asyncio.sleep(.05)
  f.last_read='bag';f.qa_questions=['what is in my bag'];f.pending_read='checkout'
  reply,_=await search('show me ties','ties');assert 'public catalog currently has no ties' in reply
  await search('under $80','ties')
  _,shirts=await search('show me white shirts size L','shirts')
  await f.select_card(shirts[0]['card_id']);await f.select_card(shirts[1]['card_id'])
  _,shoes=await search('show me shoes size 7','shoes');await f.select_card(shoes[0]['card_id'])
  # Stocked tie exists only in this synthetic fixture, never added to the live catalog.
  tie=app.store.availability.demo_candidate({'demo_trigger':'tie'})['template'];tie['stock']={'One size':5};app.store.products.append(tie);app.store.by_id[tie['id']]=tie
  _,ties=await search('show me ties','ties');assert len(ties)==1 and ties[0]['size']=='One size'
  await f.select_card(ties[0]['card_id']);assert len(f.pending_adds)==4
  await f.select_card(shirts[0]['card_id']);assert len(f.pending_adds)==4
  reply,_=await f.chat('cancel queued item 3');assert shoes[0]['name'] in reply and len(f.pending_adds)==3
  await f.select_card(shoes[0]['card_id']);assert len(f.pending_adds)==4
  assert '× 1' in (await f.chat('show pending adds'))[0]
  other=Flow(app,2);assert 'not available' in (await other.select_card(shirts[0]['card_id']))[0]
  old=f.signurl;app.tickets[old.split('ticket=')[1]]['expiry']=0
  await f.select_card(shirts[0]['card_id']);assert f.signurl!=old and len(f.pending_adds)==4
  bad=app.store.by_id[shirts[1]['id']];price=bad['price'];bad['price']+=100
  ticket=app.tickets[f.signurl.split('ticket=')[1]];assert set(ticket['scopes'])=={'orders:read','orders:write'}
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await f.poll();assert 'price has changed' in reply and shoes[0]['name'] in reply and ties[0]['name'] in reply
  expected=[(shirts[0]['id'],'L'),(ties[0]['id'],'One size'),(shoes[0]['id'],'7')]
  lines=app.store.commerce.cart('account:forme_customer_001')['lines'];assert [(x['id'],x['size']) for x in lines]==expected and all(x['quantity']==1 for x in lines)
  assert not f.pending_adds and not f.pending_add
  bad['price']=price;reply,_=await f.select_card(shirts[1]['card_id']);assert 'is in your bag' in reply
  await f.resume_add();await f.select_card(shirts[0]['card_id']);assert len(app.store.commerce.cart('account:forme_customer_001')['lines'])==4
  await search('show me ties','ties');await search('under $80','ties');await search('show me shirts size L','shirts');await search('show me shoes size 7','shoes')
  reply,_=await f.chat('show my bag');assert 'Your FORME bag' in reply
  assert not app.store.commerce.cart('account:forme_customer_002')['lines']
  assert before==[app.memory.get(i) for i in range(1,101)] and not app.memory.orders() and not f.review
  print('Actual GPT queue/search calls',app.model.calls,'model',app.model.actual)
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_search_after_empty_checkout_with_actual_gpt(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Requires actual GPT configuration')
 app=App();await app.setup(tmp_path/'empty.sqlite');f=Flow(app,1);CURRENT.set(f)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  await f.chat('checkout');ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await f.poll();assert 'bag is empty' in reply
  f.last_read='bag';f.qa_questions=['show my bag']
  for query,category in [('show me ties','ties'),('show me a necktie','ties'),('under $50','ties'),('show me shirts size L','shirts'),('show me shoes size 7','shoes')]:
   mark=len(f.trace);reply,cards=await f.chat(query)
   assert f.catalog_snapshot['filters']['category']==category,(query,reply)
   assert 'bag is empty' not in reply and not any(e.get('tool')=='read_forme_bag' for e in f.trace[mark:])
  for query in ('show me bags','find me a cummerbund','I need a cravat','could you show me brooches'):
   mark=len(f.trace);reply,_=await f.chat(query);assert 'does not currently support that product category' in reply
   assert not any(e.get('tool')=='read_forme_bag' for e in f.trace[mark:])
  reply,_=await f.chat('show me my bag');assert 'bag is empty' in reply
  assert not app.memory.orders() and not f.review and not app.store.commerce.cart('account:forme_customer_001')['lines']
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_unfamiliar_products_never_fall_back_to_bag(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'routing.sqlite');f=Flow(app,1);app.model.key='fixture';f.last_read='bag'
 async def forbidden(*a,**kw):raise AssertionError('Catalog discovery must not ask a context/bag tool')
 f.answer_question=forbidden;f.show_bag=forbidden
 try:
  for text in ['show me bags','show me a new bag','find me a cummerbund','I need a cravat','I am looking for cufflinks','could you show me brooches','do you sell fascinators']:
   reply,cards=await f.legacy_chat(text);assert 'does not currently support that product category' in reply,(text,reply)
  from chat_routing import bag_read_intent
  assert bag_read_intent('show me my bag') and not bag_read_intent('show me bags','bag')
  assert bag_read_intent('how much is that altogether?','bag')
  assert not bag_read_intent('show me ties','bag')
 finally:await app.http.aclose()
