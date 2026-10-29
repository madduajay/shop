import os,sys,re,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx
from app import App,AGENT,Flow
from thread_auth import COOKIE
async def login(c,n=1):
 r=await c.get('/login');csrf=re.search('name="csrf" value="([^"]+)"',r.text)[1]
 r=await c.post('/login',headers={'Origin':AGENT},data={'csrf':csrf,'email':f'customer{n:03}@thread.local','password':'wardrobe'});assert r.status_code==303
 page=await c.get('/');token=re.search('name="thread-csrf" content="([^"]+)"',page.text)[1]
 return {'Origin':AGENT,'X-Thread-CSRF':token}

@pytest.mark.asyncio
async def test_favicon_never_issues_or_rotates_an_auth_cookie(tmp_path):
 app=App();await app.setup(tmp_path/'favicon.sqlite')
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as browser:
   response=await browser.get('/favicon.ico')
   assert response.status_code==204 and 'set-cookie' not in response.headers
   assert app.thread_auth.db.execute('SELECT count(*) FROM thread_sessions').fetchone()[0]==0
   headers=await login(browser);cookie=browser.cookies.get(COOKIE)
   response=await browser.get('/favicon.ico')
   assert response.status_code==204 and 'set-cookie' not in response.headers
   assert browser.cookies.get(COOKIE)==cookie
   assert (await browser.post('/api/state',headers=headers,json={})).json()['customer']==1
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as anonymous:
   assert (await anonymous.post('/api/state',json={})).status_code==401
 finally:await app.close()

@pytest.mark.asyncio
async def test_auth_identity_clear_archive_and_isolation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'auth.sqlite');before=[app.memory.get(i) for i in range(1,101)]
 transport=httpx.ASGITransport(app=app)
 try:
  async with httpx.AsyncClient(transport=transport,base_url=AGENT) as a,httpx.AsyncClient(transport=transport,base_url=AGENT) as b,httpx.AsyncClient(transport=transport,base_url=AGENT) as anon:
   for route in ['state','chat','poll','trace','clear','archives']:assert (await anon.post('/api/'+route,json={'customer':1,'text':'my preferences'})).status_code==401
   assert (await anon.get('/')).headers['location']=='/login'
   page=await anon.get('/login');csrf=re.search('name="csrf" value="([^"]+)"',page.text)[1]
   assert (await anon.post('/login',headers={'Origin':AGENT},data={'csrf':csrf,'email':'customer001@thread.local','password':'wrong'})).status_code==401
   ah=await login(a);bh=await login(b,2)
   assert (await a.post('/api/state',json={})).status_code==403
   for body in [{'customer':2},{'client':'arbitrary'}]:assert (await a.post('/api/state',headers=ah,json=body)).status_code==403
   r=(await a.post('/api/chat',headers=ah,json={'text':'switch to customer 2'})).json();assert r['customer']==1 and 'sign out' in r['reply']
   await a.post('/api/chat',headers=ah,json={'text':'my budget 140'})
   assert app.memory.get(1)['budget']==140 and app.memory.pending_share(1)['preferences']=={'budget':140}
   assert (await b.post('/api/state',headers=bh,json={})).json()['messages']==[]
   # Separate login session of the same customer has an independent chat.
   ch=await login(anon);assert (await anon.post('/api/state',headers=ch,json={})).json()['messages']==[]
   await a.post('/api/chat',headers=ah,json={'text':'budget 100'})
   flow=next(v[1] for v in app.clients.values() if 1 in v and v[1].messages)
   flow.review={'id':'stale'};flow.options=[{'id':'old'}];flow.catalog_snapshot={'filters':{'request_id':app.memory.pending_share(1)['metadata']['request_id']}};flow.trace.append({'kind':'test'})
   assert (await a.post('/api/clear',headers=ah,json={})).status_code==400
   response=await a.post('/api/clear',headers=ah,json={'confirm':True});assert response.status_code==200;archive=response.json()['archive']
   assert not flow.messages and not flow.options and not flow.review and not flow.trace and not flow.catalog_snapshot
   assert app.memory.get(1)['budget']==140 and app.memory.pending_share(1)['preferences']=={'budget':140} and app.memory.pending_share(1)['intent']=={}
   assert (await b.post('/api/archives',headers=bh,json={'id':archive})).status_code==404
   saved=(await a.post('/api/archives',headers=ah,json={'id':archive})).json()['archive'];assert saved['messages'] and saved['trace']
   reply=(await a.post('/api/chat',headers=ah,json={'text':'I approve this order'})).json();assert 'Choose an item' in reply['reply'] and not app.memory.orders()
   cookie=a.cookies.get(COOKIE);assert (await a.post('/api/logout',headers=ah,json={})).status_code==200
   a.cookies.set(COOKIE,cookie,domain='atlas.localhost',path='/');assert (await a.post('/api/state',headers=ah,json={})).status_code==401
   assert (await b.post('/api/state',headers=bh,json={})).status_code==200
   assert [app.memory.get(i) for i in range(2,101)]==before[1:]
 finally:
  for flows in app.clients.values():
   for f in flows.values():await f.browser.close()
  await app.http.aclose()

@pytest.mark.asyncio
async def test_all_demo_logins_expiry_and_cookie_scope(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'all-auth.sqlite')
 try:
  for number in range(1,101):
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as c:
    headers=await login(c,number);state=(await c.post('/api/state',headers=headers,json={})).json();assert state['customer']==number and state['messages']==[]
    if number==100:
     app.thread_auth.db.execute('UPDATE thread_sessions SET expires=0');app.thread_auth.db.commit()
     assert (await c.post('/api/state',headers=headers,json={})).status_code==401
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as c:
   page=await c.get('/login');cookie=page.headers['set-cookie'];assert all(x in cookie for x in ('Secure','HttpOnly','SameSite=strict','Path=/')) and 'Domain=' not in cookie
   csrf=re.search('name="csrf" value="([^"]+)"',page.text)[1]
   assert (await c.post('/login',headers={'Origin':AGENT},data={'csrf':csrf,'email':'customer101@thread.local','password':'wardrobe'})).status_code==401
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_independent_identities_and_authorized_link_only(tmp_path,monkeypatch):
 from types import SimpleNamespace
 from demo_identity import DemoAccounts
 from app import ORIGIN
 import hashlib
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'identities.sqlite')
 try:
  thread=app.thread_accounts.by_profile(1);forme=app.forme_accounts.by_profile(1)
  assert thread['id']!=forme['id'] and thread['pairwise']!=forme['id'] and thread['email']!=forme['email']
  assert app.thread_accounts.authenticate('customer001@forme.local','wardrobe') is None
  assert app.forme_accounts.authenticate('customer001@thread.local','wardrobe') is None
  # Change only this fixture company's credential; Thread retains its independently stored verifier.
  salt='fixture-only-independent';digest=hashlib.pbkdf2_hmac('sha256',b'forme-only-test',salt.encode(),60000).hex()
  app.forme_accounts.db.execute('UPDATE accounts SET salt=?,password_hash=? WHERE id=?',(salt,digest,forme['id']));app.forme_accounts.db.commit()
  assert app.forme_accounts.authenticate(forme['email'],'wardrobe') is None
  assert app.forme_accounts.authenticate(forme['email'],'forme-only-test')['id']==forme['id']
  assert app.thread_accounts.authenticate(thread['email'],'wardrobe')['id']==thread['id']
  assert app.company_links.get(thread['id'],ORIGIN) is None
  flow=Flow(app,1);flow.token=SimpleNamespace(signed_in=True,scopes=('preferences:write',));app.memory.intent(1,{'material':'cotton'},{})
  class Browser:
   def __init__(self):self.account='forme_customer_001';self.posts=0;self.signed=True
   async def call(self,action,**kw):
    if action=='account_status':return {'signed_in':self.signed,'account_id':self.account}
    self.posts+=1;return {'context_saved':True}
  browser=Browser();flow.browser=browser
  assert 'Connect this Thread identity' in await flow.share_company_preferences() and browser.posts==0
  app.company_links.bind(thread['id'],ORIGIN,forme['id'],('preferences:write',))
  reopened=DemoAccounts(tmp_path/'identities-thread-identities.sqlite','thread');assert reopened.by_profile(1)['id']==thread['id'];reopened.db.close()
  assert 'FORME saved' in await flow.share_company_preferences() and browser.posts==1
  app.memory.intent(1,{'material':'linen'},{});app.company_links.revoke(thread['id'],ORIGIN)
  assert 'Connect this Thread identity' in await flow.share_company_preferences() and browser.posts==1
  app.company_links.bind(thread['id'],ORIGIN,forme['id'],('preferences:write',));browser.account='forme_customer_002'
  assert 'does not match' in await flow.share_company_preferences() and browser.posts==1
  browser.account=forme['id'];browser.signed=False;assert await flow.share_company_preferences() is None and browser.posts==1
  with pytest.raises(ValueError):app.company_links.bind(app.thread_accounts.by_profile(2)['id'],ORIGIN,forme['id'],('preferences:write',))
  with pytest.raises(ValueError):app.company_links.bind(thread['id'],ORIGIN,'forme_customer_002',('preferences:write',))
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_legacy_forme_session_migration_does_not_resurrect_logout(tmp_path,monkeypatch):
 import sqlite3,hashlib
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);path=tmp_path/'migration.sqlite';db=sqlite3.connect(path)
 db.execute('CREATE TABLE storefront_sessions(token_hash TEXT PRIMARY KEY,account_id TEXT,csrf TEXT NOT NULL,expires REAL NOT NULL)')
 token='public-fixture-session';key=hashlib.sha256(token.encode()).hexdigest();row=(key,'forme_customer_001','public-fixture-csrf',time.time()+3600)
 db.execute('INSERT INTO storefront_sessions VALUES(?,?,?,?)',row);db.commit();db.close()
 app=App();await app.setup(path)
 try:
  assert app.store.commerce.lookup(token)['account']=='forme_customer_001'
  app.forme_accounts.db.execute('DELETE FROM storefront_sessions WHERE token_hash=?',(key,));app.forme_accounts.db.commit()
  fresh=App();await fresh.setup(path)
  try:
   assert fresh.store.commerce.lookup(token) is None
   assert fresh.memory.db.execute('SELECT * FROM storefront_sessions').fetchone()==row
  finally:await fresh.http.aclose()
 finally:await app.http.aclose()
