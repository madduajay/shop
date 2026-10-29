import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest
from app import App,Flow,ORIGIN

@pytest.mark.asyncio
async def test_company_addresses_are_isolated_and_preserved(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);path=tmp_path/'address.sqlite';app=App();await app.setup(path)
 addresses=[app.store.commerce.address(f'forme_customer_{i:03}') for i in range(1,101)]
 assert len({x['address'] for x in addresses})==100 and all(x['synthetic'] for x in addresses)
 assert all('address' not in app.memory.get(i) for i in range(1,101))
 owned=dict(addresses[0],address='Previously entered demo address');app.forme_accounts.db.execute('UPDATE delivery_addresses SET data=? WHERE account=?',(json.dumps(owned),'forme_customer_001'));app.forme_accounts.db.commit();await app.http.aclose()
 again=App();await again.setup(path)
 try:assert again.store.commerce.address('forme_customer_001')==owned and again.store.commerce.address('forme_customer_002')==addresses[1]
 finally:await again.http.aclose()

@pytest.mark.asyncio
async def test_pending_add_cancel_resume_duplicate_and_mismatch(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'pending.sqlite');f=Flow(app,1);f.token=object();calls=[];signed=False;account='forme_customer_001'
 class Browser:
  origin=ORIGIN
  async def call(self,action,**kw):
   calls.append(action)
   return {'signed_in':signed,'account_id':account} if action=='account_status' else {}
 f.browser=Browser()
 async def signin():f.signurl='fixture';return f.signurl
 f.signin=signin
 try:
  answer,_=await f.add_selected('oxford','M','Oxford');assert 'Sign in' in answer and 'add' not in calls
  await f.chat('cancel add');signed=True;app.company_links.bind(f.principal['id'],ORIGIN,account,('orders:write',))
  await f.resume_add();assert 'add' not in calls
  signed=False;await f.add_selected('oxford','M','Oxford');signed=True
  await f.resume_add();await f.resume_add();assert calls.count('add')==1 and not f.review and not app.memory.orders()
  account='forme_customer_002';answer,_=await f.add_selected('oxford','M','Oxford');assert 'does not match' in answer and calls.count('add')==1
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_fresh_flow_bag_reconnect_is_read_only_and_checkout_requires_review(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'reconnect.sqlite');f=Flow(app,1);calls=[];signed=False;account='forme_customer_001'
 class Browser:
  origin=ORIGIN
  async def call(self,action,**kw):
   calls.append(action)
   if action=='account_status':return {'signed_in':signed,'account_id':account}
   if action=='cart':return {'page':'cart','signed_in':signed,'cart':[{'name':'Saved shirt','size':'L','quantity':2,'price_cents':5000}]}
   if action=='review':return {'review':{'summary':'Two saved shirts, USD 100.00'}}
 f.browser=Browser()
 async def opened():calls.append('open');f.token=object()
 async def signin():calls.append('signin');f.signurl='fixture'
 f.open=opened;f.signin=signin
 try:
  answer,_=await f.chat('what is in my bag?');assert 'Sign in' in answer and f.pending_read=='bag' and calls==['open','account_status','signin']
  signed=True;app.company_links.bind(f.principal['id'],ORIGIN,account,('orders:read','orders:write'))
  answer,_=await f.chat('show my bag');assert 'Saved shirt, size L × 2' in answer and 'USD 100.00' in answer and 'review' not in calls and not f.review
  answer,_=await f.chat('checkout');assert 'I approve this order' in answer and calls.count('review')==1 and not app.memory.orders()
  account='forme_customer_002';calls.clear();answer,_=await f.show_bag();assert 'does not match' in answer and calls==['account_status']
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_pending_read_only_grant_is_replaced_for_add(tmp_path,monkeypatch):
 from types import SimpleNamespace
 import time
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'grant.sqlite');f=Flow(app,1)
 f.token=SimpleNamespace(signed_in=True,scopes=('orders:read',),session_id='fixture')
 f.pending_read='add';f.started=SimpleNamespace(reference='old');f.signurl=ORIGIN+'/signin?ticket=old'
 app.tickets['old']={'expiry':time.time()+600,'scopes':('orders:read',)}
 f.metadata={'issuer':ORIGIN,'poppy_domains':['jacket.localhost'],'device_authorization_endpoint':ORIGIN+'/oauth/device_authorization','token_endpoint':ORIGIN+'/oauth/token'};f.who={};calls=[]
 class Device:
  async def begin(self,**kw):calls.append(kw);return SimpleNamespace(user_code='fixture',reference='new',verification_uri=ORIGIN+'/signin',verification_uri_complete=ORIGIN+'/signin?ticket=fixture')
 f.device=Device()
 try:
  await f.signin();assert f.started.reference=='new' and f.signurl!=ORIGIN+'/signin?ticket=old'
  assert len(calls)==1 and set(calls[0]['scopes'])=={'orders:read','orders:write'}
  await f.signin();assert len(calls)==1
 finally:await app.http.aclose()
