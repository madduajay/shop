"""Actual GPT + browser regression: product identity survives later search and auth."""
import os,sys,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
@pytest.mark.asyncio
async def test_harbor_not_dashiki_through_browser(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Actual GPT regression requires authorized model configuration')
 app=App();await app.setup(tmp_path/'identity.sqlite');f=Flow(app,1);CURRENT.set(f)
 before=[app.memory.get(i) for i in range(1,101)]
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  reply,cards=await f.chat('show me blue kurta shirts size L relaxed fit under $100')
  all_cards=list(cards)
  for _ in range(5):
   if any(c['id']=='m-shirts-021' for c in all_cards):break
   _,cards=await f.chat('show more');all_cards+=cards
  harbor=next(c for c in all_cards if c['id']=='m-shirts-021');assert harbor['name']=='Harbor Kurta-inspired Tunic' and harbor['size']=='L'
  _,dashikis=await f.chat('show me burgundy dashiki shirts size L relaxed fit under $100')
  field=next(c for c in dashikis if c['id']=='m-shirts-018');assert field['name']=='Field Dashiki-inspired Top' and field['card_id']!=harbor['card_id']
  await f.chat('show me shoes size 7')
  await f.chat('select card '+harbor['card_id'])
  assert f.pending_add['product']==harbor['id'] and f.pending_add['size']=='L'
  old_url=f.signurl;app.tickets[old_url.split('ticket=')[1]]['expiry']=0
  reply,_=await f.chat('select card '+harbor['card_id']);assert 'Sign in with FORME' in reply and f.signurl!=old_url
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  assert set(ticket['scopes'])=={'orders:read','orders:write'}
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply,_=await f.chat('checkout');assert 'Harbor Kurta-inspired Tunic, size L, is in your bag' in reply
  expected=[{'id':'m-shirts-021','size':'L','quantity':1}]
  assert app.store.commerce.cart('account:forme_customer_001')['lines']==expected
  snap=await f.browser.call('snapshot');assert [(x['id'],x['size'],x['quantity']) for x in snap['cart']]==[('m-shirts-021','L',1)]
  assert snap['cart'][0]['name']=='Harbor Kurta-inspired Tunic · blue'
  await f.chat('select card '+harbor['card_id']);assert app.store.commerce.cart('account:forme_customer_001')['lines']==expected
  other=Flow(app,2);assert 'not available' in (await other.chat('select card '+harbor['card_id']))[0]
  assert app.store.commerce.cart('account:forme_customer_002')['lines']==[]
  assert before==[app.memory.get(i) for i in range(1,101)] and not app.memory.orders()
  assert not f.review and not f.pending_add
  assert app.model.actual;print('Actual GPT:',app.model.actual,'calls:',app.model.calls,'selected/submitted/cart/display all m-shirts-021 L; m-shirts-018 absent')
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_signed_in_read_grant_add_upgrade_and_reuse(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Actual GPT regression requires authorized model configuration')
 app=App();await app.setup(tmp_path/'upgrade.sqlite');f=Flow(app,1);CURRENT.set(f)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 async def approve():
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2)
 try:
  while not server.started:await asyncio.sleep(.05)
  await f.show_bag();assert set(app.tickets[f.signurl.split('ticket=')[1]]['scopes'])=={'orders:read'}
  await approve();await f.poll();assert f.token.signed_in
  _,cards=await f.chat('show me blue kurta shirts size L relaxed fit under $100');c=cards[0]
  reply,_=await f.select_card(c['card_id']);assert 'already signed in' in reply and f.signin_label=='Review FORME permissions'
  ticket=app.tickets[f.signurl.split('ticket=')[1]];assert set(ticket['scopes'])=={'orders:read','orders:write'}
  before_url=f.signurl;reply,_=await f.select_card(c['card_id']);assert 'Review FORME permissions' in reply and f.signurl==before_url
  await approve()
  reply,_=await f.select_card(c['card_id']);assert 'is in your bag' in reply
  assert app.store.commerce.cart('account:forme_customer_001')['lines']==[{'id':c['id'],'size':'L','quantity':1}]
  assert 'already added once' in (await f.select_card(c['card_id']))[0]
  # Valid write authorization is reused for a distinct selection without a new grant.
  other=cards[1];reply,_=await f.select_card(other['card_id']);assert 'is in your bag' in reply and not f.signurl
  assert not app.memory.orders() and not f.review
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_replaced_pending_harbor_can_add_after_loafer_authorization(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Actual GPT regression requires authorized model configuration')
 app=App();await app.setup(tmp_path/'replaced.sqlite');f=Flow(app,1);CURRENT.set(f)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  _,cards=await f.chat('show me blue kurta shirts size L relaxed fit under $100')
  for _ in range(5):
   if any(c['id']=='m-shirts-021' for c in cards):break
   _,cards=await f.chat('show more')
  harbor=next(c for c in cards if c['id']=='m-shirts-021')
  await f.select_card(harbor['card_id']);assert f.pending_add['product']==harbor['id']
  reply,shoes=await f.chat('show me brown shoes size 9 regular fit under $100');assert shoes,reply
  loafer=next(c for c in shoes if c['id']=='m-loafers-001')
  await f.select_card(loafer['card_id']);assert [j['product'] for j in f.pending_adds]==[harbor['id'],loafer['id']]
  assert f.card_selections[harbor['card_id']]['state']=='pending'
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await f.poll();assert 'Birch Penny Loafer, size 9' in reply
  assert len(app.store.commerce.cart('account:forme_customer_001')['lines'])==2
  reply,_=await f.select_card(harbor['card_id']);assert 'already added once' in reply and not f.signurl
  lines=app.store.commerce.cart('account:forme_customer_001')['lines'];assert {(x['id'],x['size'],x['quantity']) for x in lines}=={('m-shirts-021','L',1),('m-loafers-001','9',1)}
  assert 'already added once' in (await f.select_card(harbor['card_id']))[0]
  assert not app.memory.orders()
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task
