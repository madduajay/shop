import os,sys,time,secrets,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx
from app import App,Flow,AGENT,ORIGIN
from chat_routing import route,UNSUPPORTED
from test_thread_auth import login
@pytest.mark.parametrize('q',['do you know my preferences','what do you remember about me','my sizes','my sizes/preferences','what are my preferences','do you remember my sizes','show me my preferences','what is my shirt size','what have you saved about me','my preferences'])
def test_preference_question_routes(q):assert route(q,True)=='preferences'
@pytest.mark.parametrize('q',['do you know the user logged in','who am I',"who’s signed in","who's signed in",'who is logged in','can you tell me who is signed in','do you know the customer signed in','do you know the logged in user'])
def test_identity_question_routes(q):assert route(q,True)=='identity'
@pytest.mark.asyncio
async def test_status_queries_isolation_temporary_clear_and_expiry(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'status.sqlite')
 async def forbidden(*args):raise AssertionError('Status must not invoke model')
 app.model.parse=forbidden
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as a,httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=AGENT) as b:
   for phrase in ['do you know my preferences','do you know the user logged in']:assert (await a.post('/api/chat',json={'text':phrase})).status_code==401
   ah=await login(a,1);bh=await login(b,2)
   profile=app.memory.get(2);profile.update(shirt_size='XXL',colors=['rose']);app.memory.save(profile)
   before=[app.memory.get(i) for i in range(1,101)]
   async def ask(c,h,q):
    r=await c.post('/api/chat',headers=h,json={'text':q});assert r.status_code==200;v=r.json();assert v['cards']==[];return v['reply']
   reply=await ask(a,ah,'do you know my preferences');assert json.loads(reply)['source']=='Thread' and json.loads(reply)['lasting_preferences']['shirt_size']=='M' and 'rose' not in reply
   assert json.loads(await ask(b,bh,'what do you remember about me'))['lasting_preferences']['shirt_size']=='XXL'
   identity=await ask(a,ah,'do you know the user logged in');assert 'customer001@thread.local' in identity and 'FORME' not in identity
   f=next(flows[1] for flows in app.clients.values() if 1 in flows);rid=secrets.token_hex(16);f.current_request_id=rid;app.memory.intent(1,{}, {'colors':['blue'],'budget':100},rid,int(time.time())+100)
   pending=app.memory.pending_share(1)
   reply=await ask(a,ah,'my sizes/preferences');assert json.loads(reply)['temporary_constraints']['values']['colors']==['blue'] and json.loads(reply)['lasting_preferences']['budget']==180
   assert app.memory.pending_share(1)==pending
   now=time.time()
   with monkeypatch.context() as clock:
    clock.setattr(time,'time',lambda:now+101)
    assert json.loads(await ask(a,ah,'my preferences'))['temporary_constraints'] is None
   f.current_request_id='e'*32;assert json.loads(await ask(a,ah,'my preferences'))['temporary_constraints'] is None;f.current_request_id=rid
   await a.post('/api/clear',headers=ah,json={'confirm':True});reply=await ask(a,ah,'do you know my preferences');assert json.loads(reply)['temporary_constraints'] is None and json.loads(reply)['lasting_preferences']['shirt_size']=='M'
   assert await ask(a,ah,'what is the weather')==UNSUPPORTED
   assert [app.memory.get(i) for i in range(1,101)]==before and not app.memory.orders() and f.token is None
   app.thread_auth.db.execute('UPDATE thread_sessions SET expires=0 WHERE customer=1');app.thread_auth.db.commit()
   assert (await a.post('/api/chat',headers=ah,json={'text':'do you know the user logged in'})).status_code==401
   assert 'XXL' in await ask(b,bh,'my preferences')
 finally:await app.http.aclose()
@pytest.mark.asyncio
async def test_empty_preferences_and_authorized_company_browser_read(tmp_path,monkeypatch):
 from types import SimpleNamespace
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'read.sqlite')
 try:
  flow=Flow(app,1);app.memory.save({'id':1,'name':'Fixture Person'})
  assert json.loads((await flow.chat('do you know my preferences'))[0])['lasting_preferences']=={}
  class Browser:
   def __init__(self):self.calls=[];self.account='forme_customer_001';self.signed=True
   async def call(self,action,**kw):
    self.calls.append(action)
    if action=='account_status':return {'signed_in':self.signed,'account_status':'signed_in' if self.signed else 'expired','account_id':self.account}
    if action=='context_read':return {'preferences_json':{'source':'FORME','lasting_preferences':{'shirt_size':'L','material':'linen'},'temporary_constraints':None,'inferred_interests':{'status':'loaded','values':{}}}}
    return {}
  flow.browser=Browser();flow.token=SimpleNamespace(signed_in=True)
  async def signin():flow.signurl='fixture-reconnect'
  flow.signin=signin
  assert 'Sign in' in (await flow.chat('what does FORME remember about me'))[0] and 'context_read' not in flow.browser.calls
  app.company_links.bind(flow.principal['id'],ORIGIN,'forme_customer_001',('preferences:write',))
  assert json.loads((await flow.chat('my preferences at FORME'))[0])['lasting_preferences']['shirt_size']=='L'
  identity=(await flow.chat('who is logged in to FORME'))[0];assert 'linked to your Thread identity' in identity
  flow.browser.account='forme_customer_002';flow.browser.calls=[]
  assert 'can’t verify' in (await flow.chat('what does FORME remember about me'))[0] and 'context_read' not in flow.browser.calls
  flow.browser.signed=False;assert 'expired' in (await flow.chat("who is signed in to FORME"))[0]
 finally:await app.http.aclose()

@pytest.mark.parametrize('q',['can you show me my previous orders?','my orders','order history','what did I buy','what have I bought','show my orders','show me my past purchases','my purchase history'])
def test_order_queries(q):assert route(q)=='orders'

@pytest.mark.asyncio
async def test_company_order_history_owned_records_only(tmp_path,monkeypatch):
 from types import SimpleNamespace
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'orders.sqlite')
 active=SimpleNamespace(session_id='history-read',signed_in=True,account_id='forme_customer_001',scopes=('orders:read',))
 async def session(r):return active
 app.store.session=session
 product=app.store.by_id['oxford'];item=dict(product,size='M',quantity=2)
 records=[dict(review_id='history-a',reference='FM-OWN',customer='usr_forme_customer_001',items=[item],total=11800,fictional=True),dict(review_id='history-b',reference='FM-NEW',account_id='forme_customer_001',items=[item],total=11800,created_at='2026-10-19T12:00:00+00:00',status='Confirmed',currency='USD',fictional=True),dict(review_id='history-c',reference='FM-PRIVATE',account_id='forme_customer_002',items=[item],total=11800,fictional=True)]
 app.store.orders={r['review_id']:r for r in records}
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as c:
   page=await c.get('/shop/orders?customer=2');assert page.status_code==200 and 'FM-OWN' in page.text and 'FM-NEW' in page.text and 'FM-PRIVATE' not in page.text
   assert 'Date not recorded' in page.text and 'data-status="Recorded"' in page.text and '2026-10-19' in page.text and 'data-quantity="2"' in page.text
   active.account_id='forme_customer_003';page=await c.get('/shop/orders');assert 'No orders found' in page.text and 'FM-OWN' not in page.text
   active.scopes=();assert (await c.get('/shop/orders')).status_code==403
   active.signed_in=False;assert (await c.get('/shop/orders')).status_code==401
   assert list(app.store.orders.values())==records and not app.memory.orders()
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_empty_order_reply_and_clear_cancels_pending_read(tmp_path,monkeypatch):
 from types import SimpleNamespace
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'empty-orders.sqlite');flow=Flow(app,1)
 try:
  flow.token=SimpleNamespace(signed_in=True)
  app.company_links.bind(flow.principal['id'],ORIGIN,'forme_customer_001',('orders:read',))
  class Browser:
   async def call(self,action,**kw):
    if action=='account_status':return {'signed_in':True,'account_id':'forme_customer_001'}
    assert action=='orders';return {'orders_account':'forme_customer_001','orders':[],'orders_count':0}
  flow.browser=Browser();reply,cards=await flow.chat('can you show me my previous orders?')
  assert 'No previous orders' in reply and 'Past chats' in reply and cards==[] and flow.pending_read is None
  flow.token=None;flow.pending_read='orders';await flow.clear_conversation();assert flow.pending_read is None and not app.memory.orders()
 finally:await app.http.aclose()

@pytest.mark.parametrize('q',['show my preferences','can you display preferences in json format','show my preferences as JSON','my preferences in JSON','can you display my preferences in JSON format'])
def test_json_preference_phrases(q):assert route(q)=='preferences'

def test_company_json_phrase():assert route('show FORME preferences in JSON')=='company_preferences'

@pytest.mark.asyncio
async def test_json_payload_allowlist_and_text_values(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'json.sqlite')
 try:
  profile=app.memory.get(1);profile.update(password='fixture-do-not-expose',internal_id='fixture-private',colors=['</code><img src=x onerror=alert(1)>']);app.memory.save(profile)
  reply,cards=await Flow(app,1).chat('can you display preferences in json format');payload=json.loads(reply)
  assert payload['source']=='Thread' and payload['temporary_constraints'] is None and payload['inferred_interests']=={'status':'not_loaded','values':None}
  assert 'password' not in reply and 'internal_id' not in reply and 'fixture-do-not-expose' not in reply
  assert payload['lasting_preferences']['colors']==profile['colors'] and '\n  "source"' in reply and cards==[]
 finally:await app.http.aclose()

@pytest.mark.parametrize('linked',[False,True])
@pytest.mark.asyncio
async def test_preferences_and_identity_are_strictly_local(tmp_path,monkeypatch,linked):
 from types import SimpleNamespace
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'local.sqlite');flow=Flow(app,1)
 async def forbidden(*args,**kwargs):raise AssertionError('Local preference operation contacted FORME')
 flow.open=forbidden;flow.signin=forbidden;flow.browser.call=forbidden
 if linked:flow.token=SimpleNamespace(signed_in=True,scopes=('preferences:write',))
 before=[app.memory.get(i) for i in range(2,101)]
 try:
  for phrase,key,value in [('I usually wear medium','shirt_size','M'),('I prefer linen','material','linen'),('my shoe size is 10','shoe_size','10'),('remember my budget is 150','budget',150)]:
   reply,cards=await flow.chat(phrase);assert 'saved those preferences in Thread' in reply and not cards
   assert json.loads(reply.split('\n',1)[1])['lasting_preferences'][key]==value
   assert app.memory.get(1)[key]==value
  assert 'FORME' not in (await flow.chat('who am I'))[0]
  assert json.loads((await flow.chat('my preferences'))[0])['source']=='Thread'
  assert [app.memory.get(i) for i in range(2,101)]==before and flow.signurl is None
  assert (await flow.chat('tell me a joke'))[0]==UNSUPPORTED
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_private_preferences_read_only_login_resume(tmp_path,monkeypatch):
 import asyncio,uvicorn
 from app import CURRENT
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'private.sqlite');flow=Flow(app,3)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  CURRENT.set(flow)
  reply,_=await flow.chat('show my FORME preferences');assert 'Sign in' in reply and flow.pending_read=='preferences'
  t=app.tickets[flow.signurl.split('ticket=')[1]];assert t['scopes']==('preferences:read',)
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer003@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);payload=json.loads(await flow.poll());assert payload['source']=='FORME' and payload['lasting_preferences']=={} and payload['temporary_constraints'] is None
  assert set(flow.token.scopes)=={'preferences:read'} and app.company_context.get('forme_customer_003')['preferences']=={}
  assert not (await flow.browser.call('context_update',preferences={'budget':1})).get('context_saved')
  assert app.company_context.get('forme_customer_003')['preferences']=={}
  app.company_links.revoke(flow.principal['id'],ORIGIN)
  assert 'Sign in' in (await flow.chat('show my FORME preferences'))[0]
  assert not app.memory.orders()
 finally:
  await flow.browser.close();await app.http.aclose();server.should_exit=True;await task
