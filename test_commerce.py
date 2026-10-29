import os,sys,re,json,time,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx
from app import App,ORIGIN,Flow
from data import Memory,catalog
from company_context import CompanyContext
from recommendations import effective_filters,evidence

def csrf(r):return re.search(r'name="csrf" value="([^"]+)"',r.text)[1]
async def login(client,number=1):
 r=await client.get('/shop/login?return_to=/shop/cart')
 r=await client.post('/shop/login',headers={'Origin':ORIGIN},data={'csrf':csrf(r),'email':f'customer{number:03}@forme.local','password':'wardrobe','return_to':'/shop/cart'})
 assert r.status_code==303 and '__Host-thread3_forme_account=' in r.headers['set-cookie'];return r
async def add(client,product='oxford',size='M',quantity=1):
 page=await client.get('/shop/product/'+product)
 return await client.post('/shop/cart',headers={'Origin':ORIGIN},data={'csrf':csrf(page),'product':product,'size':size,'quantity':quantity})

@pytest.mark.asyncio
async def test_direct_cart_checkout_persistence_and_isolation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'direct.sqlite');original=[app.memory.get(i) for i in range(1,101)]
 transport=httpx.ASGITransport(app=app)
 try:
  async with httpx.AsyncClient(transport=transport,base_url=ORIGIN) as a,httpx.AsyncClient(transport=transport,base_url=ORIGIN) as b:
   assert (await add(a,quantity=2)).status_code==303
   assert (await add(a,'m-shirts-008','L',1)).status_code==303
   assert app.company_context.get('forme_customer_001') is None
   guest=await a.get('/shop/checkout');assert 'Sign in to checkout' in guest.text
   assert (await a.post('/shop/checkout',headers={'Origin':ORIGIN},data={'csrf':csrf(await a.get('/shop/product/oxford')),'approved':'yes'})).status_code==401
   await login(a);bag=await a.get('/shop/cart');assert bag.text.count('data-cart-item')==2 and 'data-quantity="2"' in bag.text
   owner='account:forme_customer_001';assert len(app.store.commerce.cart(owner)['lines'])==2
   assert [e['kind'] for e in app.company_context.history('forme_customer_001')]==['cart_associated']
   await login(b,2);assert 'Your bag is empty' in (await b.get('/shop/cart')).text
   token=csrf(bag)
   for values in [{'quantity':'0'},{'quantity':'11'},{'quantity':'1.5'},{'size':'UNKNOWN'}]:
    fields={'csrf':token,'product':'oxford','old_size':'M','size':'M','quantity':'2'}|values
    assert (await a.post('/shop/cart/update',headers={'Origin':ORIGIN},data=fields)).status_code==409
   assert (await a.post('/shop/cart/update',headers={'Origin':'https://evil.localhost'},data={'csrf':token})).status_code==403
   assert (await a.post('/shop/cart/update',headers={'Origin':ORIGIN},data={'csrf':'wrong'})).status_code==403
   r=await a.post('/shop/cart/update',headers={'Origin':ORIGIN},data={'csrf':token,'product':'oxford','old_size':'M','size':'L','quantity':'3'});assert r.status_code==303
   bag=await a.get('/shop/cart');assert 'data-quantity="3"' in bag.text
   assert (await a.post('/shop/cart/remove',headers={'Origin':ORIGIN},data={'csrf':csrf(bag),'product':'m-shirts-008','old_size':'L'})).status_code==303
   assert (await add(a,'m-shirts-008','L',1)).status_code==303
   # Price is recomputed from catalog; no form price is trusted.
   shipping=await a.get('/shop/checkout');assert 'Where should it go?' in shipping.text
   fields={'csrf':csrf(shipping),'name':'Test Shopper','email':'test@example.test','address':'123 Example Lane','city':'Test City','postal':'12345','country':'US','price':'1'}
   invalid=await a.post('/shop/shipping',headers={'Origin':ORIGIN},data=fields|{'email':'invalid'});assert invalid.status_code==400
   review=await a.post('/shop/shipping',headers={'Origin':ORIGIN},data=fields);assert review.status_code==303
   url=review.headers['location'];review=await a.get(url);rid=re.search('data-review="([^"]+)"',review.text)[1]
   assert not app.store.orders
   assert not any(e['kind']=='purchase_completed' for e in app.company_context.history('forme_customer_001'))
   assert (await b.get(url)).status_code==404
   # Edits invalidate a prior review.
   assert (await add(a,'oxford','L',1)).status_code==303
   assert (await a.post('/shop/checkout',headers={'Origin':ORIGIN},data={'csrf':csrf(review),'review':rid,'approved':'yes'})).status_code==409
   shipping=await a.get('/shop/checkout');review=await a.post('/shop/shipping',headers={'Origin':ORIGIN},data=fields|{'csrf':csrf(shipping)})
   review=await a.get(review.headers['location']);rid=re.search('data-review="([^"]+)"',review.text)[1];total=int(re.search(r'data-total="(\d+)"',review.text)[1]);confirm={'csrf':csrf(review),'review':rid,'approved':'yes','total':'1'}
   assert (await a.post('/shop/checkout',headers={'Origin':ORIGIN},data=confirm|{'approved':'no'})).status_code==409
   done=await a.post('/shop/checkout',headers={'Origin':ORIGIN},data=confirm);assert done.status_code==303
   receipt=await a.get(done.headers['location']);assert 'Your order is confirmed' in receipt.text and 'No payment has been collected' in receipt.text
   assert len(app.store.orders)==1 and app.store.orders[rid]['total']==total and total>1
   assert app.store.commerce.cart(owner)['lines']==[]
   for _ in range(2):assert (await a.post('/shop/checkout',headers={'Origin':ORIGIN},data=confirm)).status_code==200
   assert len(app.store.orders)==1
   history=app.company_context.history('forme_customer_001');assert sum(e['kind']=='purchase_completed' for e in history)==1
   assert all(word not in json.dumps(history) for word in ('Test Shopper','test@example.test','123 Example Lane','password','csrf'))
   assert (await b.get('/shop/receipt?review='+rid)).status_code==404 and app.company_context.history('forme_customer_002')==[]
   assert [app.memory.get(i) for i in range(1,101)]==original
   assert (await add(a,'oxford','M',1)).status_code==303
   account=await a.get('/shop/account');assert (await a.post('/shop/logout',headers={'Origin':ORIGIN},data={'csrf':csrf(account)})).status_code==303
   assert 'Your bag is empty' in (await a.get('/shop/cart')).text
   await login(a);assert 'data-cart-item' in (await a.get('/shop/cart')).text
   # Durable cart and order reconstruct in a fresh application instance.
   fresh=App();await fresh.setup(tmp_path/'direct.sqlite')
   assert fresh.store.commerce.cart(owner)['lines']==app.store.commerce.cart(owner)['lines']
   assert len(fresh.store.orders)==1 and len(fresh.company_context.history('forme_customer_001'))==len(app.company_context.history('forme_customer_001'))
   await fresh.http.aclose()
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_authenticated_filter_memory_and_explicit_remember(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'filters.sqlite')
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as c:
   await login(c)
   r=await c.get('/shop?color=blue&budget=100');assert 'Remember selected preferences' in r.text
   assert app.company_context.get('forme_customer_001')['preferences']=={}
   form=re.search(r'<form class="remember-filter".*?</form>',r.text)[0]
   import html
   values={k:html.unescape(v) for k,v in re.findall('name="([^"]+)" value="([^"]*)"',form)}
   assert (await c.post('/shop/preferences',headers={'Origin':ORIGIN},data=values)).status_code==303
   assert app.company_context.get('forme_customer_001')['preferences']['colors']['value']==['blue']
   await c.get('/shop?color=white&budget=70')
   assert app.company_context.get('forme_customer_001')['preferences']['budget']['value']==100
   history=app.company_context.history('forme_customer_001');assert history[0]['payload']['filters']['color']=='white' and history[0]['payload']['scope']=='request'
   expired=await c.get('/shop?color=white&request_id='+'a'*32+'&expires_at='+str(int(time.time())-1));assert 'previous search expired' in expired.text and 'data-result-count="1000"' not in expired.text # saved budget remains
 finally:await app.http.aclose()

def test_behavior_isolated_bounded_inferred_and_idempotent(tmp_path):
 c=CompanyContext(tmp_path/'context.sqlite');products=catalog();p=products[0];item={'id':p['id'],'size':'M','quantity':1}
 for n in range(1,101):c.activity(f'forme_customer_{n:03}','cart_add',products,items=[item])
 c.update('forme_customer_001',{'colors':['navy'],'budget':150})
 assert c.activity('forme_customer_001','purchase_completed',products,items=[item],event_id='order1')
 assert not c.activity('forme_customer_001','purchase_completed',products,items=[item],event_id='order1')
 before=c.get('forme_customer_001');behavior=c.behavior('forme_customer_001');assert behavior['activity_counts']['purchase_completed']==1
 assert 'purchase_completed' not in c.behavior('forme_customer_002')['activity_counts']
 inferred=effective_filters({}, {},behavior);assert inferred['prefer_color']=='white'
 explicit=effective_filters({}, {'colors':['navy']},behavior);assert explicit['prefer_color']=='navy'
 current=effective_filters({'color':'blue'}, {'colors':['navy']},behavior);assert current['color']=='blue'
 facts=evidence(p,{}, {},inferred,behavior);assert 'inferred' in facts['facts']['behavior'] and 'not preferences' in facts['facts']['behavior']
 c.activity('forme_customer_001','checkout_started',products,items=[item]);assert c.behavior('forme_customer_001')['activity_counts']['purchase_completed']==1
 for _ in range(220):c.activity('forme_customer_001','cart_update',products,items=[item])
 assert len(c.history('forme_customer_001'))==200 and not c.activity('forme_customer_001','purchase_completed',products,items=[item],event_id='order1')
 assert c.get('forme_customer_001')['preferences']==before['preferences']
 reopened=CompanyContext(c.path);assert reopened.history('forme_customer_002')==c.history('forme_customer_002')

@pytest.mark.asyncio
async def test_dual_memory_deferral_scope_identity_and_restart(tmp_path):
 from types import SimpleNamespace
 from model import ParsedCommand
 class Model:
  async def parse(self,text,prefs):
   if 'usually' in text:return ParsedCommand('shirt size M',['shirt_size'],[])
   if 'Remember' in text:return ParsedCommand('material cotton',['material'],[])
   return ParsedCommand('find blue shirts budget 100',[],['colors','budget'])
 memory=Memory(tmp_path/'thread.sqlite');app=SimpleNamespace(memory=memory,model=Model());flow=Flow(app,1)
 # Prevent browser operations while checking the staged signed-out memory itself.
 async def opened():flow.token=SimpleNamespace(signed_in=False)
 flow.open=opened
 class Browser:
  def __init__(self):self.sent=[];self.account='forme_customer_002';self.signed=True
  async def call(self,action,**kw):
   if action=='account_status':return {'signed_in':self.signed,'account_id':self.account}
   if action=='context_update':self.sent.append(kw);return {'context_saved':True}
   if action=='filter':return {'products':[],'total':0}
  snapshot={}
 flow.browser=Browser();before=memory.get(1)
 reply,_=await flow.chat('I usually wear medium')
 assert memory.get(1)['shirt_size']=='M' and memory.pending_share(1)['preferences']=={'shirt_size':'M'}
 await flow.chat('Remember I prefer cotton')
 pending=memory.pending_share(1);assert pending['preferences']=={'shirt_size':'M','material':'cotton'}
 await flow.chat('Find a blue shirt for tonight under $100')
 pending=memory.pending_share(1);assert pending['intent']['colors']==['blue'] and pending['intent']['budget']==99.99
 assert memory.get(1)['colors']==before['colors'] and memory.get(1)['budget']==before['budget']
 assert pending['metadata']['intent_scope']=='request' and pending['metadata']['request_id'] and pending['metadata']['expires_at']>time.time()
 assert memory.pending_share(2)=={} and not flow.browser.sent
 reopened=Memory(tmp_path/'thread.sqlite');assert reopened.pending_share(1)==pending
 denied=await flow.share_company_preferences();assert 'does not match' in denied and not flow.browser.sent and memory.pending_share(1)
 flow.browser.signed=False;assert await flow.share_company_preferences() is None and memory.pending_share(1)
 flow.browser.signed=True;flow.browser.account='forme_customer_001'
 assert 'FORME saved' in await flow.share_company_preferences();assert len(flow.browser.sent)==1 and memory.pending_share(1)=={}
 assert await flow.share_company_preferences() is None and len(flow.browser.sent)==1
 assert flow.browser.sent[0]['preferences']==pending['preferences'] and flow.browser.sent[0]['intent']==pending['intent']


def test_scope_validation_expiry_and_request_binding(tmp_path,monkeypatch):
 from memory_scope import request_expiry
 c=CompanyContext(tmp_path/'scoped.sqlite');now=int(time.time());rid='a'*32;uid='b'*32
 metadata={'preference_scope':'lasting','intent_scope':'request','source':'thread_chat','expires_at':now+60,'request_id':rid}
 c.accept_shared('account1',{'material':'cotton'},{'colors':['blue'],'budget':100},uid,metadata)
 assert c.get('account1')['preferences']['material']['scope']=='lasting'
 assert c.shared_intent('account1',rid)['current_request']['colors']==['blue']
 assert c.shared_intent('account1','c'*32) is None and c.shared_intent('account2',rid) is None and c.shared_intent('account1') is None
 before=c.get('account1');c.accept_shared('account1',{'material':'cotton'},{'colors':['blue'],'budget':100},uid,metadata);assert c.get('account1')==before
 for bad in [metadata|{'intent_scope':'lasting'},metadata|{'preference_scope':'temporary'},metadata|{'expires_at':now-1},metadata|{'source':'unknown'},metadata|{'request_id':'wrong'}]:
  with pytest.raises(ValueError):c.accept_shared('account1',{'material':'silk'},{},'d'*32,bad)
 assert c.get('account1')==before
 monkeypatch.setattr(time,'time',lambda:now+61)
 assert c.shared_intent('account1',rid) is None and c.get('account1')['preferences']['material']['value']=='cotton'
 assert not c.shared_intent('account1','another-request')
 # Time phrases follow the supplied timezone, not UTC midnight.
 from datetime import datetime
 from zoneinfo import ZoneInfo
 fixed=datetime(2026,10,17,15,0,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp();monkeypatch.setattr(time,'time',lambda:fixed)
 expected=datetime(2026,10,18,0,0,tzinfo=ZoneInfo('America/Los_Angeles')).timestamp()
 assert request_expiry('for tonight','America/Los_Angeles')==expected
 assert request_expiry('blue shirt',None)==int(fixed)+3600
 assert request_expiry('for 2 hours',None)==int(fixed)+7200


def test_expired_search_history_not_used_for_ranking(tmp_path,monkeypatch):
 c=CompanyContext(tmp_path/'expiry.sqlite');products=catalog();now=int(time.time())
 for color in ['blue','white','blue','white','blue']:
  c.activity('account1','filters_selected',products,filters={'color':color,'request_id':__import__('secrets').token_hex(16),'expires_at':str(now+60)})
 assert c.behavior('account1')['inferred_interests']=={} # Temporary filters never become cross-request tastes
 monkeypatch.setattr(time,'time',lambda:now+61)
 assert c.history('account1') and c.behavior('account1')['inferred_interests']=={}

@pytest.mark.asyncio
@pytest.mark.parametrize('labels',[{'lasting_fields':['material'],'temporary_fields':['material']},{'lasting_fields':'material','temporary_fields':[]},{'lasting_fields':['unknown'],'temporary_fields':[]}])
async def test_malformed_gpt_scope_never_promotes_memory(tmp_path,monkeypatch,labels):
 from model import Parser
 from types import SimpleNamespace
 monkeypatch.setenv('OPENAI_API_KEY','fixture-only')
 def respond(r):return httpx.Response(200,json={'model':'fixture','output':[{'content':[{'type':'output_text','text':json.dumps({'command':'material silk'}|labels)}]}]})
 memory=Memory(tmp_path/'bad-scope.sqlite');flow=Flow(SimpleNamespace(memory=memory,model=Parser(httpx.MockTransport(respond))),1);before=memory.get(1)
 reply,cards=await flow.legacy_chat('Remember I prefer silk');assert reply=='Sorry i am not sure how to handle this request' and not cards and memory.get(1)==before and not memory.pending_share(1)

def test_pending_temporary_expiry_and_lasting_retention(tmp_path,monkeypatch):
 m=Memory(tmp_path/'pending.sqlite');now=int(time.time())
 m.intent(1,{'material':'cotton'},{'colors':['blue']},'a'*32,now+60)
 m.intent(2,{}, {'budget':100},'b'*32,now+60)
 monkeypatch.setattr(time,'time',lambda:now+61)
 assert m.pending_share(1)['preferences']=={'material':'cotton'} and m.pending_share(1)['intent']=={}
 assert m.pending_share(2)=={} and m.get(1)['material']=='cotton'

@pytest.mark.asyncio
async def test_request_size_used_for_selection_without_changing_saved_size(tmp_path):
 from types import SimpleNamespace
 class Model:
  async def parse(self,text,prefs):return text
 app=SimpleNamespace(memory=Memory(tmp_path/'fit.sqlite'),model=Model());flow=Flow(app,1);flow.token=SimpleNamespace(signed_in=False);flow.options=[{'id':'oxford','name':'Oxford','category':'shirts','price_cents':5900,'sizes':[{'size':'XL','stock':3}]}]
 flow.department='clothing';flow.catalog_snapshot={'filters':{'apparel_size':'XL','expires_at':str(int(time.time())+60)}}
 calls=[]
 class Browser:
  async def call(self,action,**kw):
   calls.append((action,kw));return {'signed_in':False}
 flow.browser=Browser()
 async def signin():return 'synthetic-sign-in'
 flow.signin=signin
 async def selection(product,size,name):calls.append(('add',{'size':size}));return 'Pending selection',[]
 flow.add_selected=selection
 await flow.chat('the first one');assert next(v for k,v in calls if k=='add')['size']=='XL' and app.memory.get(1)['shirt_size']=='M'
 flow.catalog_snapshot['filters']['expires_at']=str(int(time.time())-1);calls.clear()
 reply,_=await flow.chat('the first one');assert 'expired' in reply and not calls

@pytest.mark.asyncio
async def test_direct_stock_return_allowlist_and_session_expiry(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'security.sqlite')
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as c:
   assert (await c.get('/shop/login?return_to=https://evil.example/')).status_code==400
   app.store.by_id['oxford']['stock']['M']=2
   assert (await add(c,quantity=3)).status_code==409
   await login(c)
   assert (await add(c,quantity=2)).status_code==303
   app.store.commerce.authdb.execute('UPDATE storefront_sessions SET expires=0 WHERE account_id IS NOT NULL');app.store.commerce.authdb.commit()
   r=await c.get('/shop/checkout');assert r.status_code in (200,303) and 'Where should it go?' not in r.text
   assert len(app.memory.orders())==0
   assert len(app.store.commerce.cart('account:forme_customer_001')['lines'])==1
 finally:await app.http.aclose()

def test_phoenix_midnight_and_tomorrow(monkeypatch):
 from datetime import datetime
 from zoneinfo import ZoneInfo
 from memory_scope import request_expiry
 zone=ZoneInfo('America/Phoenix')
 for day,hour,minute in [(17,23,59),(18,0,1)]:
  now=datetime(2026,10,day,hour,minute,tzinfo=zone);monkeypatch.setattr(time,'time',lambda:now.timestamp())
  assert request_expiry('tonight')==datetime(2026,10,day+1,tzinfo=zone).timestamp()
  assert request_expiry('tomorrow')==datetime(2026,10,day+2,tzinfo=zone).timestamp()
  assert request_expiry('shirts')==int(now.timestamp())+3600

def test_request_context_precedence_and_no_filter_inference(tmp_path):
 from recommendations import request_context
 c=CompanyContext(tmp_path/'temporary.sqlite');products=catalog();rid='a'*32
 for color in ['blue','white']*5:c.activity('a','filters_selected',products,filters={'color':color,'request_id':rid,'expires_at':str(int(time.time())+3600)})
 assert c.history('a') and c.behavior('a')['inferred_interests']=={}
 envelope={'current_request':{'colors':['blue'],'budget':140,'budget_min':40,'shirt_size':'M'}}
 f=request_context({'color':'white','budget':'100','request_id':rid,'apparel_size':''},envelope)
 assert f['color']=='white' and f['budget']=='100' and 'min_price' not in f and f['apparel_size']=='M'
 assert request_context({'category':'shirts'},None)=={'category':'shirts'}
 c.activity('a','cart_add',products,items=[{'id':'oxford','size':'M'}]);assert c.behavior('a')['inferred_interests']['color']['value']=='white'
