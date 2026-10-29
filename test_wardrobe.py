import os,sys,asyncio,tempfile,time,secrets
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,jwt,httpx,uvicorn
from app import App,Flow,ORIGIN,AGENT,CURRENT
from data import Memory,catalog
from store import filtered
@pytest.mark.parametrize('customer',range(1,101))
def test_memory_isolation_and_persistence(tmp_path,customer):
 m=Memory(tmp_path/'memory.sqlite');before=[m.get(i) for i in range(1,101)];m.edit(customer,'shirt size XL waist 34 shoe size 10 budget 130 color black fit relaxed material linen occasion travel style classic quality luxury width wide inseam 32')
 n=Memory(tmp_path/'memory.sqlite');assert n.get(customer)['shirt_size']=='XL';assert n.get(customer)['waist']=='34';assert n.get(customer)['shoe_size']=='10'
 for i in range(1,101):
  if i!=customer:assert n.get(i)==before[i-1]
def test_filters():
 products=catalog()
 for p in products:
  size=next(s for s,n in p['stock'].items() if n)
  result=filtered(products,dict(category=p['category'],size=size,color=p['color'],brand=p['brand'],material=p['material'],fit=p['fit'],budget=str(p['price']/100)))
  assert p in result
  assert all(x['stock'].get(size,0)>0 and x['price']<=p['price'] for x in result)
@pytest.mark.asyncio
async def test_actual_browser_and_assertions(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'fixture.sqlite')
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'))
 task=asyncio.create_task(server.serve());flow=Flow(app,1)
 try:
  for _ in range(100):
   if server.started:break
   await asyncio.sleep(.05)
  CURRENT.set(flow);await flow.open()
  discovery=(await app.http.get(ORIGIN+'/.well-known/poppy.json')).json();assert 'preferences:write' in discovery['auth']['custom_scopes']
  assert flow.browser.snapshot['page']=='catalog'
  dimensions=await flow.browser.call('viewport',width=390,height=844);assert dimensions['width']==390 and dimensions['content']<=390
  import base64
  shot=await flow.browser.call('screenshot');(Path(__file__).parent/'evidence'/'store-mobile.png').write_bytes(base64.b64decode(shot['data']))
  await flow.browser.call('viewport',width=1200,height=1150)
  empty=await flow.chat('my preferences');assert __import__('json').loads(empty[0])['source']=='Thread'
  assert any(e.get('cookie_issued') and e['status']==303 for e in flow.trace)
  assert any(e.get('cookie_present') and e['path']=='/shop' for e in flow.trace)
  now=int(time.time());base=dict(iss=app.identity.client_id,sub=flow.who['pairwise_user_id'],aud=ORIGIN+'/poppy/browser-session',session_id=flow.token.session_id,return_to=ORIGIN+'/shop',iat=now,exp=now+50,jti=secrets.token_urlsafe(24))
  def sign(claims,typ='poppy-browser+jwt',key=None):return jwt.encode(claims,key or app.identity.private_key,algorithm='ES256',headers={'typ':typ,'kid':app.identity.kid})
  good=sign(base);r=await app.http.post(base['aud'],data={'assertion':good});assert r.status_code==303
  cookie=r.headers['set-cookie'];assert all(x in cookie for x in ('Secure','HttpOnly','SameSite=Lax','Path=/'));assert 'Domain=' not in cookie
  r=await app.http.post(base['aud'],data={'assertion':good});assert r.status_code==400 and 'set-cookie' not in r.headers
  for update in [dict(aud=AGENT),dict(sub='usr_wrong'),dict(session_id='ses_wrong'),dict(exp=now-1),dict(exp=now+61),dict(return_to='https://example.com/'),dict(return_to=ORIGIN+'@example.com/')]:
   r=await app.http.post(base['aud'],data={'assertion':sign(dict(base,jti=secrets.token_urlsafe(24),**update))});assert r.status_code==400 and 'set-cookie' not in r.headers
  from cryptography.hazmat.primitives.asymmetric import ec
  for assertion in [sign(dict(base,jti=secrets.token_urlsafe(24)),typ='poppy-session+jwt'),sign(dict(base,jti=secrets.token_urlsafe(24)),key=ec.generate_private_key(ec.SECP256R1()))]:
   r=await app.http.post(base['aud'],data={'assertion':assertion});assert r.status_code==400
  await flow.browser.call('catalog')
  first_ids={p['id'] for p in flow.browser.snapshot['products']}
  next_page=await flow.browser.call('next');assert first_ids.isdisjoint({p['id'] for p in next_page['products']}) and next_page['total']==1000
  msg,cards=await flow.chat("find women's dresses");assert all(c['explanation'] and c['explanation_source']=='deterministic' for c in cards);assert cards and all(c['gender']=='women' and c['category']=='dresses' for c in cards)
  shot=await flow.browser.call('screenshot');(Path(__file__).parent/'evidence'/'photo-women-clothing.png').write_bytes(base64.b64decode(shot['data']))
  msg,cards=await flow.chat('find men shoes');assert cards and all(c['gender']=='men' and c['category']=='shoes' for c in cards)
  shot=await flow.browser.call('screenshot');(Path(__file__).parent/'evidence'/'photo-men-shoes.png').write_bytes(base64.b64decode(shot['data']))
  snap=await flow.browser.call('filter',filters={'gender':'women','department':'footwear','kind':'heels'})
  assert snap['products'] and all(x['gender']=='women' for x in snap['products'])
  shot=await flow.browser.call('screenshot');(Path(__file__).parent/'evidence'/'photo-women-shoes.png').write_bytes(base64.b64decode(shot['data']))
  msg,cards=await flow.chat('find men shirts under $100');assert cards
  shot=await flow.browser.call('screenshot');(Path(__file__).parent/'evidence'/'photo-men-clothing.png').write_bytes(base64.b64decode(shot['data']))
  first_options={c['id'] for c in cards};msg,more=await flow.chat('show more');assert more and first_options.isdisjoint({c['id'] for c in more})
  model_parse=app.model.parse
  async def forbid_selection_parse(*args):raise AssertionError('Ordinal selection must not invoke GPT')
  app.model.parse=forbid_selection_parse
  msg,_=await flow.chat('the first one');app.model.parse=model_parse;assert 'Sign in with FORME' in msg and flow.signurl and not app.store.orders
  assert not flow.browser.snapshot.get('cart');assert flow.signurl
  assert (await flow.chat('I approve this order'))[0].startswith('Choose')
  t=app.tickets[flow.signurl.split('ticket=')[1]]
  # Closing a popup produces no authorization mutation; a resumed link retains its cart.
  before=flow.browser.snapshot['cart'];assert not flow.token.signed_in
  assert await flow.signin()==flow.signurl
  old_url=flow.signurl;t['expiry']=time.time()-1
  expired=await app.http.get(old_url);assert expired.status_code==400
  # Explicit broader fixture grant for later memory-sharing checks; add-only least scopes are tested separately.
  flow.pending_read=None
  assert await flow.signin()!=old_url
  t=app.tickets[flow.signurl.split('ticket=')[1]]
  wrong=await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer002@forme.local','password':'wardrobe'});assert 'Please check' in wrong.text and not t['done']
  ok=await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'});assert ok.status_code==200 and t['done']
  await asyncio.sleep(5.2);msg=await flow.poll();assert not flow.review and flow.token.signed_in and 'is in your bag' in msg
  await flow.poll();assert len((await flow.browser.call('cart'))['cart'])==1
  msg,_=await flow.chat('checkout');assert flow.review and 'approve' in msg and 'Example Lane' in msg
  assert app.company_links.get(flow.principal['id'],ORIGIN)['account']=='forme_customer_001' and flow.principal['id']!='forme_customer_001'
  assert not before and len(flow.browser.snapshot['cart'])==1
  empty=(await flow.chat('show my FORME preferences'))[0];assert __import__('json').loads(empty)['lasting_preferences']=={}
  delivery=app.store.commerce.address('forme_customer_001');delivery['address']+=' · revised fixture'
  app.forme_accounts.db.execute('UPDATE delivery_addresses SET data=? WHERE account=?',(__import__('json').dumps(delivery),'forme_customer_001'));app.forme_accounts.db.commit()
  denied,_=await flow.chat('I approve this order');assert 'Delivery details changed' in denied and not app.store.orders
  await flow.chat('checkout')
  msg,_=await flow.chat('I approve this order');assert 'Order FM-' in msg and len(app.store.orders)==1
  assert next(iter(app.store.orders.values()))['delivery']==delivery
  await flow.chat('I approve this order');assert len(app.store.orders)==1
  receipt=await flow.browser.call('order_status');assert receipt['receipt']
  # Explicit company preferences cross the actual browser form, after authentication.
  from company_context import CompanyContext
  assert app.company_context.get('forme_customer_001')['preferences']=={}
  msg,_=await flow.chat('remember at FORME shirt size L budget 140')
  assert 'FORME saved' in msg
  assert any(e.get('path')=='/shop/context' and e.get('method')=='POST' and e.get('request',{}).get('body',{}).get('preferences') and e['request']['body']['preferences']!=['[values omitted]'] for e in flow.trace)
  company=app.company_context.get('forme_customer_001')
  assert {k:v['value'] for k,v in company['preferences'].items()}=={'shirt_size':'L','budget':140}
  status,cards=await flow.chat('who is logged in to FORME');assert flow.principal['email'] in status and 'linked to your Thread identity' in status and not cards
  remembered,cards=await flow.chat('what does FORME remember about me');assert __import__('json').loads(remembered)['source']=='FORME' and __import__('json').loads(remembered)['lasting_preferences']['budget']==140 and not cards
  assert app.company_context.get('forme_customer_001')==company
  await flow.chat('find shirts under $70')
  company=app.company_context.get('forme_customer_001')
  assert company['preferences']['budget']['value']==140 and company['recent_constraints']['budget']=='69.99'
  reopened=CompanyContext(app.company_context.path)
  assert reopened.get('forme_customer_001')==company;reopened.db.close()
  other=Flow(app,2);await other.open();assert not other.browser.snapshot['signed_in'] and not other.browser.snapshot['cart']
  assert app.company_context.get('forme_customer_002') is None
  denied=await other.browser.call('context_update',preferences={'budget':30});assert denied['error']
  assert app.company_context.get('forme_customer_002') is None
  # Saving before sign-in stages only explicit values, not Thread's whole profile.
  msg,_=await other.chat('remember at FORME shoe size 10')
  assert other.signurl and app.company_context.get('forme_customer_002') is None
  old_signin=other.signurl
  app.memory.intent(2,{}, {'colors':['blue']})
  app.thread_auth.forget_temporary(other);await other.clear_conversation()
  assert app.memory.pending_share(2)['preferences']=={'shoe_size':'10'} and app.memory.pending_share(2)['intent']=={}
  assert (await app.http.get(old_signin)).status_code==400
  await other.signin()
  ticket=app.tickets[other.signurl.split('ticket=')[1]]
  await app.http.post(other.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer002@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);assert 'FORME saved' in await other.poll()
  assert {k:v['value'] for k,v in app.company_context.get('forme_customer_002')['preferences'].items()}=={'shoe_size':'10'}
  assert app.company_context.get('forme_customer_001')==company
  # Company explanation batching sees only the signed-in company's record.
  from types import SimpleNamespace
  batches=[]
  async def grounded(instructions,payload,schema,name,max_tokens):
   batches.append(payload)
   return {'items':[{'id':r['id'],'reason_ids':list(r['facts'])[:2]} for r in payload['selected_items']]}
  app.explainer.client=SimpleNamespace(key='test-only',actual='fixture-model',structured=grounded)
  msg,cards=await other.chat('find men shirts under $80')
  assert cards and all(c['explanation_source']=='gpt-grounded' and len(c['explanation'].split())<=25 for c in cards)
  assert batches[-1]['stored_FORME_preferences']=={} # Thread searches do not use FORME memory
  assert batches[-1]['current_received_preferences']['budget']=='79.99'
  assert all('account_id' not in str(b) and 'customer001' not in str(b) for b in batches)
  await other.browser.call('viewport',width=1200,height=1500)
  shot=await other.browser.call('screenshot');(Path(__file__).parent/'evidence'/'forme-explanations.png').write_bytes(base64.b64decode(shot['data']))
  trace_before=list(other.trace)
  await other.chat('my shirt size XL')
  assert app.memory.get(2)['shirt_size']=='XL' and other.trace==trace_before
  assert app.memory.pending_share(2)
  await other.chat('find shirts under $55')
  assert 'shirt_size' not in app.company_context.get('forme_customer_002')['preferences']
  assert app.memory.pending_share(2) # Thread edits are not automatically copied to FORME
  assert 'budget' not in app.company_context.get('forme_customer_002')['preferences']
  assert app.memory.get(2)['budget']==180
  # Actual controlled-browser requests use stored temporary context only for this request.
  rid='b'*32;expiry=int(time.time())+600
  await other.browser.call('context_update',preferences={},intent={'colors':['blue'],'budget':140},update_id='c'*32,metadata={'preference_scope':'lasting','intent_scope':'request','source':'thread_chat','request_id':rid,'expires_at':expiry})
  other.current_request_id=rid
  private=__import__('json').loads((await other.chat('show my FORME preferences'))[0])
  assert private['source']=='FORME' and private['temporary_constraints']['values']['colors']==['blue']
  snap=await other.browser.call('filter',filters={'request_id':rid,'category':'shirts','explain':'1'})
  assert snap['filters']['color']=='blue' and snap['filters']['budget']=='140' and int(snap['filters']['expires_at'])<=expiry
  assert batches[-1]['current_received_preferences']['color']=='blue'
  snap=await other.browser.call('filter',filters={'request_id':rid,'category':'shirts','color':'white','budget':'100'})
  assert snap['filters']['color']=='white' and snap['filters']['budget']=='100'
  snap=await other.browser.call('filter',filters={'request_id':'d'*32,'category':'shirts'})
  assert not snap['filters'].get('color') and not snap['filters'].get('budget')
  # Expire only this fixture envelope, without changing the protocol clock.
  import json
  db=app.company_context.db;row=json.loads(db.execute('SELECT data FROM shared_shopping_intents WHERE account_id=?',('forme_customer_002',)).fetchone()[0]);row['expires_at']=int(time.time())-1
  db.execute('UPDATE shared_shopping_intents SET data=? WHERE account_id=?',(json.dumps(row),'forme_customer_002'));db.commit()
  snap=await other.browser.call('filter',filters={'request_id':rid,'category':'shirts'})
  assert not snap['filters'].get('color') and not snap['filters'].get('budget')
  assert __import__('json').loads((await other.chat('show my FORME preferences'))[0])['temporary_constraints'] is None
  await other.chat('find blue shirts under $140');old=other.catalog_snapshot['filters'];assert other.options
  await other.chat('under $100');new=other.catalog_snapshot['filters']
  assert new['request_id']==old['request_id'] and new['color']=='blue' and new['budget']=='99.99' and new['expires_at']==old['expires_at']
  assert app.company_context.shared_intent('forme_customer_002',new['request_id']) is None # Current constraints travel in the browser filter, not shared memory
  await other.chat('material cotton');assert other.catalog_snapshot['filters']['request_id']==old['request_id'] and other.catalog_snapshot['filters']['color']=='blue' and other.catalog_snapshot['filters']['budget']=='99.99' and other.catalog_snapshot['filters']['material']=='cotton'
  await other.chat('find shirts under $150');assert other.catalog_snapshot['filters']['request_id']!=old['request_id'] and not other.catalog_snapshot['filters'].get('color')
  assert any(e['kind']=='checkout_started' for e in app.company_context.history('forme_customer_001'))
  # Clear preserves the company bag and durable preferences, but invalidates review and request context.
  await other.browser.call('detail',product='oxford');await other.browser.call('add',product='oxford',size='XL')
  reviewed=await other.browser.call('review');other.review=reviewed['review'];old_review=other.review['id'];bag=(await other.browser.call('cart'))['cart'];company_before=app.company_context.get('forme_customer_002')['preferences'];rid=other.catalog_snapshot['filters']['request_id']
  app.thread_auth.forget_temporary(other);await other.clear_conversation()
  assert not other.trace
  assert (await other.browser.call('cart'))['cart']==bag and app.store.states[other.token.session_id]['review'] is None
  assert app.company_context.shared_intent('forme_customer_002',rid) is None and app.company_context.get('forme_customer_002')['preferences']==company_before
  assert not app.thread_auth.reset_ids(2) and not other.review and not other.options
  assert (await other.chat('I approve this order'))[0].startswith('Choose') and len(app.store.orders)==1
  status,cards=await other.chat('who is logged in to FORME')
  assert 'forme_customer_002' in status and 'verified signed in' in status and not cards
  status,_=await flow.chat('who is the current logged in user at FORME');assert 'forme_customer_001' in status and 'customer 1' in status
  before_logout=app.memory.get(2)
  reply,_=await other.chat('log out of FORME');assert 'Signed out' in reply
  status,cards=await other.chat('am I logged in to FORME');assert 'not signed in' in status and 'customer 2' in status and not cards
  assert app.memory.get(2)==before_logout
  assert app.company_links.get(other.principal['id'],ORIGIN)['status']=='revoked'
  # The other customer's sign-in survives logout of account 002.
  status,_=await flow.chat('who am I at FORME');assert 'forme_customer_001' in status
  await other.browser.close()
  import datetime
  old_now=app.shop._now;app.shop._now=lambda:old_now()+datetime.timedelta(hours=2)
  expired=await flow.browser.call('order_status');assert expired.get('error') and not expired['signed_in']
  status,cards=await flow.chat('am I logged in to FORME');assert 'expired' in status and 'not signed in' in status and not cards
  app.shop._now=old_now
  encoded=str(flow.trace);assert 'eyJ' not in encoded and 'wardrobe' not in encoded
 finally:
  await flow.browser.close();await app.http.aclose();server.should_exit=True;await task

def test_natural_size_and_price_range(tmp_path):
 m=Memory(tmp_path/'prefs.sqlite');p,u=m.edit(1,'My shirt size is L, shoe size is 10, between $40 and $100')
 assert p['shirt_size']=='L' and p['shoe_size']=='10' and p['budget_min']==40 and p['budget']==100

@pytest.mark.asyncio
async def test_wide_shoe_preference_never_substitutes_narrow(tmp_path):
 from types import SimpleNamespace
 class NoModel:
  async def parse(self,text,prefs):return text
 app=SimpleNamespace(memory=Memory(tmp_path/'wide.sqlite'),model=NoModel());flow=Flow(app,1);flow.token=SimpleNamespace(signed_in=False)
 reply,cards=await flow.chat('Find shoes width wide')
 assert not cards and 'won’t substitute' in reply and app.memory.get(1)['width']=='standard' and app.memory.pending_share(1)['intent']['width']=='wide'

@pytest.mark.asyncio
async def test_model_receives_only_current_message(monkeypatch):
 from model import Parser
 monkeypatch.setenv('OPENAI_API_KEY','fixture-only-key')
 def response(request):
  import json
  body=json.loads(request.content);assert json.loads(body['input'])=={'message':'find shoes under $180'}
  return httpx.Response(200,json={'model':'gpt-4.1-mini-2025-04-14','output':[{'content':[{'type':'output_text','text':'{"command":"find shoes budget 180","lasting_fields":[],"temporary_fields":["budget"]}'}]}]})
 parser=Parser(httpx.MockTransport(response));out=await parser.parse('find shoes under $180',{'name':'unrelated private context','colors':['black'],'brands':['Form & Field']})
 assert out=='find shoes budget 180' and parser.calls==1

def test_expanded_catalog_counts_and_legacy():
 from collections import Counter
 from data import legacy_catalog
 products=catalog();assert len(products)==len({p['id'] for p in products})==1000
 assert Counter((p['gender'],p['department']) for p in products)=={('men','clothing'):400,('women','clothing'):400,('men','footwear'):100,('women','footwear'):100}
 by_id={p['id']:p for p in products}
 for old in legacy_catalog():
  for k,v in old.items():assert by_id[old['id']][k]==v
 for gender in ('men','women'):
  for department in ('clothing','footwear'):
   rows=filtered(products,dict(gender=gender,department=department));assert all(p['gender']==gender and p['department']==department for p in rows)
 generated=[p for p in products if 'design' in p]
 assert len({p['design_style'] for p in generated})==38
 assert len({p['region'] for p in generated})>=15
 assert all(any(n==0 for n in p['stock'].values()) or all(n>0 for n in p['stock'].values()) for p in products)

@pytest.mark.asyncio
async def test_public_routes_images_pagination_guest_bag(tmp_path,monkeypatch):
 import re
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'routes.sqlite')
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as c:
   home=await c.get('/shop');assert home.status_code==200 and 'set-cookie' not in home.headers
   assert home.text.count('data-product=')==24 and 'data-result-count="1000"' in home.text
   first=set(re.findall('data-product="([^"]+)"',home.text));second=await c.get('/shop?page=2');assert first.isdisjoint(set(re.findall('data-product="([^"]+)"',second.text)))
   for dept,count in [('clothing',800),('footwear',200)]:
    r=await c.get('/shop',params={'department':dept});assert r.status_code==200 and f'data-result-count="{count}"' in r.text
   for gender,count in [('men',400),('women',400)]:
    r=await c.get('/shop',params={'gender':gender,'department':'clothing'});assert f'data-result-count="{count}"' in r.text
   for p in app.store.products:
    image=await c.get(p['image_url']);assert image.status_code==200 and image.content
    if 'design' in p:assert image.headers['content-type'].startswith('image/jpeg') and image.content.startswith(b'\xff\xd8') and p['photo_color'] in p['image_note'].lower()
   assert (await c.get('/assets/products/not-real.svg')).status_code==404
   bag=await c.get('/shop/cart');assert bag.status_code==200 and 'Your bag is empty' in bag.text
   assert '__Host-thread3_forme_guest' in bag.headers['set-cookie'] and '__Host-thread3_poppy_session' not in bag.headers['set-cookie']
   detail=await c.get('/shop/product/w-dresses-002');csrf=re.search('name="csrf" value="([^"]+)"',detail.text)[1]
   add=await c.post('/shop/cart',headers={'Origin':ORIGIN},data={'csrf':csrf,'product':'w-dresses-002','size':'M'});assert add.status_code==303
   bag=await c.get('/shop/cart');assert 'data-cart-item' in bag.text
   assert (await c.post('/shop/checkout',headers={'Origin':ORIGIN},data={'csrf':csrf,'approved':'yes'})).status_code==401
   assert not app.store.orders
   assert (await c.post('/shop/clear',headers={'Origin':ORIGIN},data={'csrf':csrf})).status_code==303
   assert 'Your bag is empty' in (await c.get('/shop/cart')).text
 finally:await app.http.aclose()

def test_photo_coverage_and_preserved_catalog():
 import json
 from collections import Counter
 import subprocess,re
 root=Path(__file__).parent;products=catalog();before=json.loads((root/'evidence/before-photo-catalog.json').read_text())
 for prior,current in zip(before,products):
  # Regional merchandising may evolve; existing identifiers, prices and variants remain stable.
  for key in ('id','price','stock','gender','department'):assert prior[key]==current[key]
 photos=[p for p in products if 'design' in p]
 assert len(photos)==992 and len({p['image_url'] for p in photos})==38
 from global_catalog import FAMILIES
 for p in photos:
  assert p['image_url'].endswith(p['design_style']+'.jpg')
  assert p['color']==p['photo_color']==FAMILIES[p['design_style']][0]
  assert p['material']==FAMILIES[p['design_style']][1]
 for url in {p['image_url'] for p in photos}:
  path=root/url.lstrip('/');assert path.read_bytes().startswith(b'\xff\xd8')
  info=subprocess.check_output(['sips','-g','pixelWidth','-g','pixelHeight',str(path)],text=True)
  assert all(int(n)>=1000 for n in re.findall(r'pixel(?:Width|Height): (\d+)',info))

def test_company_context_100_accounts_restart_and_validation(tmp_path):
 from company_context import CompanyContext
 path=tmp_path/'company.sqlite';company=CompanyContext(path)
 assert company.db.execute('select count(*) from customer_context').fetchone()[0]==0
 for i in range(1,101):company.update(f'account-{i}',{'budget':i+100,'shirt_size':'M'})
 company.update('account-42',{'shirt_size':'L'})
 company.observe_filters('account-42',{'budget':'20','q':'secret must never be stored','account_id':'account-1','prefer_color':'navy','access_token':'secret'},catalog())
 company.db.close();company=CompanyContext(path)
 for i in range(1,101):
  row=company.get(f'account-{i}');assert row['preferences']['budget']['value']==i+100
  assert row['preferences']['shirt_size']['value']==('L' if i==42 else 'M')
  assert row['preferences']['budget']['source']=='explicit_storefront_preference_form' and row['preferences']['budget']['updated_at']
 assert company.get('account-42')['recent_constraints']=={'budget':'20','prefer_color':'navy'}
 before=company.get('account-42')
 for bad in ({'account_id':'account-1'},{'password':'secret'},{'budget':True},{'colors':['secret']},{'budget_min':9000}):
  with pytest.raises(ValueError):company.update('account-42',bad)
 assert company.get('account-42')==before
 company.db.close()

@pytest.mark.asyncio
async def test_company_context_authorization_and_account_binding(tmp_path,monkeypatch):
 from types import SimpleNamespace
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'identity.sqlite')
 active=SimpleNamespace(session_id='session-a',signed_in=True,account_id='stable-account-a',scopes=('preferences:write',))
 async def session(request):return active
 monkeypatch.setattr(app.store,'session',session)
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as c:
   import re,json
   r=await c.get('/shop/context');csrf=re.search('name="csrf" value="([^"]+)"',r.text)[1]
   form={'csrf':csrf,'preferences':json.dumps({'budget':200})}
   assert (await c.post('/shop/context',data=form,headers={'Origin':'https://wrong.localhost'})).status_code==403
   assert (await c.post('/shop/context',data=dict(form,csrf='wrong'),headers={'Origin':ORIGIN})).status_code==403
   assert (await c.post('/shop/context',data=dict(form,account_id='stable-account-b'),headers={'Origin':ORIGIN})).status_code==400
   assert (await c.post('/shop/context',data=form,headers={'Origin':ORIGIN})).status_code==303
   active=SimpleNamespace(session_id='new-session-a',signed_in=True,account_id='stable-account-a',scopes=('preferences:write',))
   assert 'budget: 200' in (await c.get('/shop/context')).text
   active=SimpleNamespace(session_id='session-b',signed_in=True,account_id='stable-account-b',scopes=())
   r=await c.get('/shop/context');assert 'budget: 200' not in r.text
   csrf=app.store.states['session-b']['csrf']
   assert (await c.post('/shop/context',data=dict(form,csrf=csrf),headers={'Origin':ORIGIN})).status_code==403
   assert app.company_context.get('stable-account-b')['preferences']=={}
   active=None
   assert (await c.get('/shop/context')).status_code==401
   assert app.company_context.get('stable-account-a')['preferences']['budget']['value']==200
 finally:await app.http.aclose()

def test_company_precedence_and_deterministic_eligibility():
 from recommendations import effective_filters,evidence
 saved={'budget':50,'budget_min':30,'shirt_size':'M','colors':['navy'],'material':'cotton','width':'wide'}
 current={'budget':'100','min_price':'0','color':'white','apparel_size':'L','width':'standard','category':'shirts'}
 f=effective_filters(current,saved)
 assert f['budget']=='100' and f['min_price']=='0' and f['apparel_size']=='L' and f['color']=='white' and f['prefer_material']=='cotton'
 rows=filtered(catalog(),f);assert rows and all(p['color']=='white' and p['stock']['L']>0 and p['price']<=10000 for p in rows)
 e=evidence(rows[0],current,saved,f);assert 'precedence' in e['required'] and 'saved 50' in e['facts']['precedence']
 assert effective_filters({},saved)['budget']=='50'
 assert not filtered(catalog(),effective_filters({'category':'shoes'},{'width':'wide'}))
 assert not filtered(catalog(),effective_filters({'category':'shoes'},{'size_system':'UK','shoe_size':'10'}))
 assert saved['budget']==50

@pytest.mark.asyncio
@pytest.mark.parametrize('bad',['ids','duplicate','extra','invented','missing_tradeoff','failure','valid'])
async def test_company_explanation_validation_and_fallback(bad):
 from recommendations import Explainer,effective_filters
 from types import SimpleNamespace
 p=catalog()[0];saved={'budget':20,'colors':['black']};current={'budget':'100','color':'white','apparel_size':'M'};seen=[]
 async def structured(instructions,payload,schema,name,max_tokens):
  seen.append(payload)
  if bad=='failure':raise TimeoutError()
  r=payload['selected_items'][0];ids=list(r['facts'])[:2]
  item={'id':r['id'],'reason_ids':ids}
  if bad=='ids':item['id']='another-product'
  if bad=='duplicate':ids.append(ids[0])
  if bad=='extra':item['price']=1
  if bad=='invented':ids.append('perfect_fit_guaranteed')
  if bad=='missing_tradeoff':item['reason_ids']=[]
  return {'items':[item]}
 client=SimpleNamespace(key='fixture',actual='fixture-model',structured=structured);ex=Explainer(client)
 result=await ex.explain([p],current,saved,effective_filters(current,saved));row=result[p['id']]
 assert row['source']==('gpt-grounded' if bad=='valid' else 'deterministic')
 assert len(row['text'].split())<=25 and 'saved 20' not in row['text'] and 'perfect' not in row['text'] and row['text'].endswith('.')
 assert seen[0]['stored_FORME_preferences']==saved and seen[0]['current_received_preferences']==current
 assert list(result)==[p['id']]

@pytest.mark.asyncio
async def test_shared_gpt_explanation_transport(monkeypatch):
 import json
 from model import Parser
 from recommendations import Explainer
 monkeypatch.setenv('OPENAI_API_KEY','fixture-key-never-returned')
 def respond(request):
  b=json.loads(request.content);assert b['store'] is False and b['text']['format']['name']=='forme_recommendation_reasons'
  payload=json.loads(b['input']);assert set(payload)=={'current_received_preferences','stored_FORME_preferences','effective_preferences','observed_behavior','selected_items'}
  r=payload['selected_items'][0]
  return httpx.Response(200,json={'model':'fixture-gpt','output':[{'content':[{'type':'output_text','text':json.dumps({'items':[{'id':r['id'],'reason_ids':['catalog']}]})}]}]})
 client=Parser(httpx.MockTransport(respond));ex=Explainer(client);p=catalog()[0]
 out=await ex.explain([p],{}, {},{});assert out[p['id']]['source']=='gpt-grounded' and ex.actual=='fixture-gpt'
 assert 'fixture-key' not in str(out)

def test_token_search_and_dependent_facets():
 from catalog_search import facet_options,FILTER_FIELDS
 products=catalog()
 blue=filtered(products,{'q':'blue shirt'});assert blue and all(p['color']=='blue' and p['category'] in ('shirts','blouses') for p in blue)
 assert filtered(products,{'q':'Japanese sandals'})
 for f in ({},{'gender':'women'},{'department':'footwear'},{'category':'shirts','color':'blue'},{'material':'linen','budget':'100'},{'category':'shirts','kind':'geta'}):
  options=facet_options(products,f,filtered)
  for key,counts in options.items():
   for value,count in counts.items():
    scope={**f,key:value}
    expected=filtered(products,scope)
    assert count==len(expected),(f,key,value,count,len(expected))
    assert count>0 or f.get(key)==value or (key,value) in (('category','ties'),('department','accessories'))
 zero=facet_options(products,{'category':'shirts','kind':'geta'},filtered)
 assert zero['category']['shirts']==0 and zero['kind']['geta']==0

@pytest.mark.asyncio
async def test_headless_filter_control_matrix(tmp_path,monkeypatch):
 import json,base64
 from urllib.parse import urlparse,parse_qs
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'matrix.sqlite')
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'))
 task=asyncio.create_task(server.serve());flow=Flow(app,1);report=[]
 async def capture(name):
  shot=await flow.browser.call('screenshot');(Path(__file__).parent/'evidence'/name).write_bytes(base64.b64decode(shot['data']))
 try:
  while not server.started:await asyncio.sleep(.05)
  await flow.open();await flow.browser.call('viewport',width=1360,height=1100)
  cases={'exclude_colors':'white','q':'blue shirt','gender':'women','department':'footwear','category':'shirts','kind':'geta','size':'M','color':'blue','brand':'Morrow','material':'linen','fit':'relaxed','quality':'premium','occasion':'work','style':'classic','region':'Japan','design_style':'kurta','sort':'price-high','min_price':'100','budget':'70'}
  layout=await flow.browser.call('catalog_layout');assert set(layout['controls'])==set(cases) and layout['pager_gap']>=40
  for name,value in cases.items():
   await flow.browser.call('reset_filters')
   snap=await flow.browser.call('edit_filter',name=name,value=value,expect_navigation=True)
   expected=filtered(app.store.products,{name:value})
   assert snap['total']==len(expected)>0,(name,snap['total'],len(expected))
   assert [p['id'] for p in snap['products']]==[p['id'] for p in expected[:24]],name
   assert snap['filters'][name]==value and parse_qs(urlparse(snap['url']).query)[name]==[value]
   assert all(p['color']==p['photo_color'] for p in snap['products'])
   report.append({'control':name,'value':value,'matches':snap['total'],'url_matches':True,'image_color_matches':True})
   if name=='q':await capture('global-blue-shirt.png')
   if name=='region':await capture('global-japan.png')
  for values in [{'gender':'women','department':'clothing','color':'blue'},{'gender':'women','department':'footwear','kind':'jutti'},{'category':'shirts','kind':'geta'},{'q':'no-such-catalog-item'},{'category':'shoes','size':'XXL'}]:
   snap=await flow.browser.call('filter',filters=values);expected=filtered(app.store.products,values)
   assert snap['total']==len(expected)
   assert all(snap['filters'][key]==value for key,value in values.items())
   if not expected:
    assert snap['page']=='catalog' and not snap['products']
    await capture('global-empty.png')
   else:await capture('global-footwear.png')
   report.append({'combination':values,'matches':snap['total']})
  reset=await flow.browser.call('reset_filters');assert reset['total']==1000 and all(not reset['filters'][k] for k in cases if k!='sort')
  first=[p['id'] for p in reset['products']];second=await flow.browser.call('next');assert not set(first)&{p['id'] for p in second['products']}
  prior=await flow.browser.call('previous');assert first==[p['id'] for p in prior['products']]
  await flow.browser.call('filter',filters={'department':'footwear'});await capture('global-footwear.png')
  await flow.browser.call('scroll_catalog_end');await capture('global-pagination.png')
  mobile=await flow.browser.call('viewport',width=390,height=844);assert mobile['content']<=390
  await flow.browser.call('filter',filters={'q':'blue shirt'});await capture('global-mobile.png')
  layout=await flow.browser.call('catalog_layout');assert not layout['mobile_filters_open'] and layout['pager_gap']>=40
  (Path(__file__).parent/'evidence/filter-matrix.json').write_text(json.dumps({'controls':report,'pagination':True,'reset':True,'mobile':layout},indent=2))
 finally:await flow.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.parametrize('question',['who is the current logged in user','who am I','which customer is selected','am I logged in','who is logged in to FORME','which user is active','current customer','what is my login status','am I signed in','who is the active user'])
@pytest.mark.asyncio
async def test_identity_queries_do_not_parse_or_browse(tmp_path,question):
 from types import SimpleNamespace
 class NoModel:
  async def parse(self,*args):raise AssertionError('Identity must not go to GPT')
 app=SimpleNamespace(memory=Memory(tmp_path/'identity.sqlite'),model=NoModel());flow=Flow(app,73);before=app.memory.get(73)
 reply,cards=await flow.chat(question)
 assert 'customer 73' in reply and before['name'] in reply and not cards
 assert flow.token is None and flow.trace==[] and app.memory.get(73)==before

@pytest.mark.parametrize('question',['what is the weather','hello','tell me a joke','who is the president','42','why is the sky blue?'])
@pytest.mark.asyncio
async def test_unknown_requests_never_default_to_shirts(tmp_path,question):
 from types import SimpleNamespace
 class NoModel:
  async def parse(self,*args):raise AssertionError('Unknown request must not go to GPT')
 app=SimpleNamespace(memory=Memory(tmp_path/'unknown.sqlite'),model=NoModel());flow=Flow(app,1)
 reply,cards=await flow.chat(question)
 assert (reply.startswith('Hello!') if question=='hello' else reply=='Sorry i am not sure how to handle this request') and not cards and flow.token is None

def test_material_exclusion_includes_blends():
 rows=filtered(catalog(),{'exclude_material':'wool'});assert rows and all('wool' not in p['material'].split() for p in rows)

@pytest.mark.parametrize('result',[None,{},[],42,'','unrecognized command','sign in','I approve this order'])
@pytest.mark.asyncio
async def test_malformed_parser_has_no_side_effects(tmp_path,result):
 from types import SimpleNamespace
 class BrokenParser:
  async def parse(self,*args):return result
 app=SimpleNamespace(memory=Memory(tmp_path/'bad-parser.sqlite'),model=BrokenParser());flow=Flow(app,1);before=app.memory.get(1)
 reply,cards=await flow.chat('find blue shirts')
 assert reply=='Sorry i am not sure how to handle this request' and not cards
 assert app.memory.get(1)==before and flow.token is None and not flow.trace

@pytest.mark.asyncio
async def test_failed_parser_has_no_side_effects(tmp_path):
 from types import SimpleNamespace
 class FailedParser:
  async def parse(self,*args):raise TimeoutError('Language provider failed')
 app=SimpleNamespace(memory=Memory(tmp_path/'failure.sqlite'),model=FailedParser());flow=Flow(app,1);before=app.memory.get(1)
 reply,cards=await flow.chat('my shirt size L find white shirts')
 assert reply=='Sorry i am not sure how to handle this request' and not cards and app.memory.get(1)==before and flow.token is None

@pytest.mark.asyncio
async def test_invalid_original_range_does_not_commit_model_updates(tmp_path):
 from types import SimpleNamespace
 class BadRangeParser:
  async def parse(self,*args):return 'shirt size L budget 150'
 app=SimpleNamespace(memory=Memory(tmp_path/'range.sqlite'),model=BadRangeParser());flow=Flow(app,1);before=app.memory.get(1)
 reply,cards=await flow.chat('find shirts between $100 and $40')
 assert 'price bounds conflict' in reply and not cards and app.memory.get(1)==before

@pytest.mark.parametrize('utterance',['blue','under $70','the first one','cheaper','show more','next page','L'])
def test_clear_short_refinements_remain_shopping(utterance):
 from chat_routing import route
 assert route(utterance,has_options=True)=='shopping'

@pytest.mark.parametrize('utterance',['shirts','find shoes','women clothing','kurta','Japanese sandals','my shirt size L','remember at FORME budget 150'])
def test_clear_shopping_remains_recognized(utterance):
 from chat_routing import route
 assert route(utterance)=='shopping'

@pytest.mark.asyncio
async def test_no_initial_category_fallback_or_unsupported_mutation(tmp_path):
 from types import SimpleNamespace
 class PlainParser:
  async def parse(self,text,*args):return text
 app=SimpleNamespace(memory=Memory(tmp_path/'no-default.sqlite'),model=PlainParser());flow=Flow(app,1);before=app.memory.get(1)
 reply,cards=await flow.chat('find hats budget 100')
 assert reply=='Sorry i am not sure how to handle this request' and not cards
 assert not flow.category and not flow.department and flow.token is None and app.memory.get(1)==before
 reply,cards=await flow.chat('my budget 150')
 assert 'saved those preferences' in reply and not cards and flow.token is None and app.memory.get(1)['budget']==150
