import os,sys,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN

@pytest.mark.asyncio
async def test_earlier_card_variant_auth_dedup_stock_price_and_isolation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'cards.sqlite');f=Flow(app,1);CURRENT.set(f)
 before=[app.memory.get(i) for i in range(1,101)]
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  _,shirts=await f.chat('show me white shirts size L');assert len(shirts)==3
  selected=shirts[0];key=selected['card_id'];assert selected['size']=='L'
  _,shoes=await f.chat('show me shoes size 7');assert shoes and all(x['size']=='7' for x in shoes)
  assert (await f.chat('add that shirt'))[0].startswith('Which one')
  other=Flow(app,2);assert 'not available' in (await other.chat('select card '+key))[0]
  # Original expiry does not erase the card; all variant facts are revalidated.
  f.card_selections[key]['requirements']['expires_at']='1'
  reply,_=await f.chat('select card '+key);assert f.pending_add['size']=='L' and f.pending_add['card_id']==key and f.signurl
  assert 'Sign in with FORME' in (await f.chat('select card '+key))[0]
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await f.poll();assert 'size L, is in your bag' in reply,reply
  expected=[{'id':selected['id'],'size':'L','quantity':1}]
  assert app.store.commerce.cart('account:forme_customer_001')['lines']==expected
  assert 'already added once' in (await f.chat('select card '+key))[0]
  await f.resume_add();assert app.store.commerce.cart('account:forme_customer_001')['lines']==expected
  # The same browser form id cannot increase quantity, including transport retries.
  await f.browser.call('add',product=selected['id'],size='L',add_id=key,expected_price=selected['price_cents'])
  assert app.store.commerce.cart('account:forme_customer_001')['lines']==expected
  second=shirts[1];item=app.store.by_id[second['id']];old=item['stock']['L'];item['stock']['L']=0
  assert 'Nothing was added' in (await f.chat('select card '+second['card_id']))[0]
  item['stock']['L']=old;item['price']+=100
  assert 'price has changed' in (await f.chat('select card '+second['card_id']))[0]
  assert app.store.commerce.cart('account:forme_customer_001')['lines']==expected
  assert app.store.commerce.cart('account:forme_customer_002')['lines']==[]
  assert [app.memory.get(i) for i in range(1,101)]==before and not app.memory.orders()
  # Clearing invalidates old actions; the archive UI is read-only.
  await f.clear_conversation();assert 'not available' in (await f.chat('select card '+key))[0]
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task
