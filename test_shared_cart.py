import os,sys,asyncio,re,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx,uvicorn
from app import App,Flow,ORIGIN,CURRENT
from test_commerce import login,add,csrf

@pytest.mark.asyncio
async def test_headless_and_direct_share_account_cart(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);db=tmp_path/'shared.sqlite';app=App();await app.setup(db);flow=Flow(app,1)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  async with httpx.AsyncClient(verify=app.http._transport._pool._ssl_context,base_url=ORIGIN,trust_env=False) as direct,httpx.AsyncClient(verify=app.http._transport._pool._ssl_context,base_url=ORIGIN,trust_env=False) as other:
   await login(direct);await add(direct,'tee','XS')
   CURRENT.set(flow);reply,_=await flow.add_selected('m-shirts-010','L','Cliff Guayabera-inspired Shirt');assert flow.signurl
   t=app.tickets[flow.signurl.split('ticket=')[1]]
   await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
   await asyncio.sleep(5.2);assert 'is in your bag' in await flow.poll()
   bag=await direct.get('/shop/cart');assert 'Cliff Guayabera-inspired Shirt' in bag.text and 'value="L" selected' in bag.text
   shared=app.store.commerce.cart('account:forme_customer_001');assert shared['lines']==[{'id':'tee','size':'XS','quantity':1},{'id':'m-shirts-010','size':'L','quantity':1}]
   assert len((await flow.browser.call('cart'))['cart'])==2
   revision=shared['revision'];fields={'csrf':csrf(bag),'product':'m-shirts-010','old_size':'L','size':'M','quantity':'2','cart_revision':str(revision)}
   assert (await direct.post('/shop/cart/update',headers={'Origin':ORIGIN},data=fields)).status_code==303
   state=await flow.browser.call('cart');assert any(x['size']=='M' and x['quantity']==2 for x in state['cart'])
   assert (await direct.post('/shop/cart/update',headers={'Origin':ORIGIN},data=fields)).status_code==409
   # Parallel sessions add distinct variants without replacing each other's lines.
   await asyncio.gather(add(direct,'oxford','L'),flow.add_selected('tee','L','Essential Crew Tee'))
   assert len(app.store.commerce.cart('account:forme_customer_001')['lines'])==4
   page=await direct.get('/shop/product/oxford');add_id=re.search('name="add_id" value="([^"]+)"',page.text)[1]
   payload={'csrf':csrf(page),'product':'oxford','size':'M','quantity':'1','add_id':add_id}
   for _ in range(2):assert (await direct.post('/shop/cart',headers={'Origin':ORIGIN},data=payload)).status_code==303
   rows=app.store.commerce.cart('account:forme_customer_001')['lines'];assert next(x['quantity'] for x in rows if x['id']=='oxford' and x['size']=='M')==1
   await login(other,2);assert 'Your bag is empty' in (await other.get('/shop/cart')).text
   fresh=App();await fresh.setup(db)
   try:assert fresh.store.commerce.cart('account:forme_customer_001')['lines']==rows
   finally:await fresh.http.aclose()
   assert not app.memory.orders()
   (Path(__file__).parent/'evidence/shared-cart-verification.json').write_text(json.dumps({'headless_to_direct':True,'direct_to_headless':True,'size_quantity':True,'parallel_changes':True,'stale_form_rejected':True,'duplicate_add_rejected':True,'account_isolation':True,'restart_persistence':True,'orders_created':0,'fixture_only':True},indent=2))
 finally:await flow.browser.close();await app.http.aclose();server.should_exit=True;await task
