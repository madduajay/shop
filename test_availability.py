import os,sys,json,time,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
from availability import Availability
from data import catalog
async def delivered(flow):
 for _ in range(60):
  result=await flow.poll()
  if result and 'Now available' in result:return result
  await asyncio.sleep(.1)
 raise AssertionError('No SSE availability delivery')

@pytest.mark.parametrize('kind,size,price',[('shoes','10',95),('tie','One size',45)])
def test_company_timer_persistence_isolation(tmp_path,kind,size,price):
 products=catalog();a=Availability(tmp_path/'watch.sqlite',products);clock=[1000];a.now=lambda:clock[0]
 c=a.candidate(dict(demo_trigger=kind,shoe_size='10',budget=100));assert c and c['size']==size and c['price_cents']==price*100
 assert c['template']['model_code'].startswith('DEMO-RED-') and c['template']['image_alt'].lower().startswith(('red','solid red'))
 assert c['template']['size_basis']==('US shoe' if kind=='shoes' else 'One size · regular length')
 one=a.subscribe('one','a'*32,c);assert a.subscribe('one','a'*32,c)['id']==one['id']
 clock[0]=1030;two=a.subscribe('two','b'*32,c);clock[0]=1059;a.tick();assert all(w['status']=='active' for w in a.rows('one'))
 clock[0]=1060;a.tick();ready=a.rows('one')[0];assert ready['status']=='ready' and a.rows('two')[0]['status']=='active'
 a.cancel('two','b'*32);assert a.rows('two')[0]['status']=='cancelled'
 event=ready['event_id'];a.tick();assert a.rows('one')[0]['event_id']==event
 b=Availability(tmp_path/'watch.sqlite',catalog());assert b.rows('one')[0]['event_id']==event
 assert b.rows('one')[0]['candidate']['product'].startswith('notify-')
 third=b.subscribe('one','c'*32,c);assert third['id']!=one['id'] and third['status']=='active'
 assert b.candidate(dict(demo_trigger=kind,budget=1)) is None
 assert b.candidate(dict(demo_trigger='shoes',shoe_size='99',budget=200)) is None
 clock[0]=100000;a.tick();assert a.rows('one')[0]['status']=='expired'

@pytest.mark.asyncio
async def test_watch_browser_flow(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'fixture.sqlite');flow=Flow(app,1);other=Flow(app,2)
 app.webhook_enabled=False # This journey verifies legacy SSE reconnect; webhook delivery has its own tests.
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  CURRENT.set(flow)
  for text in ['Red shoes','show me red shoes','find RED SHOES']:
   reply,_=await flow.chat(text);assert reply=='Red shoes are not available. Would you like FORME to notify you when they’re available?' and not flow.signurl
  assert len(flow.watch_rows())==1 and not app.store.availability.db.execute('SELECT * FROM watches').fetchall()
  await flow.chat('no');assert not flow.signurl
  await flow.chat('red shoes');auth_reply,_=await flow.chat('yes');assert auth_reply=='Authorize FORME to receive availability notifications. Sign in if needed.';assert flow.signurl and not app.store.availability.db.execute('SELECT * FROM watches').fetchall()
  old=flow.signurl;await flow.chat('cancel watch');assert (await app.http.get(old)).status_code==400
  await flow.chat('find red shoes');await flow.chat('yes');ticket=app.tickets[flow.signurl.split('ticket=')[1]]
  bad=await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer002@forme.local','password':'wardrobe'});assert 'Please check' in bad.text
  bad=await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wrong'});assert 'Please check' in bad.text and not app.store.availability.db.execute('SELECT * FROM watches').fetchall()
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await flow.poll();assert reply=='Red shoes are not available. FORME will notify you when they’re available.',reply
  before=app.store.availability.db.execute('SELECT count(*) FROM watches').fetchone()[0]
  assert (await flow.chat('yes'))[0]=='Red shoes are not available. FORME will notify you when they’re available.';assert (await flow.chat('red shoes'))[0]=='Red shoes are not available. FORME will notify you when they’re available.';assert app.store.availability.db.execute('SELECT count(*) FROM watches').fetchone()[0]==before
  await flow.logout();assert 'Reconnect' in await flow.poll()
  t=app.tickets[flow.signurl.split('ticket=')[1]]
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);assert 'reconnected' in await flow.poll()
  clock=time.time();app.store.availability.now=lambda:clock+61
  reply=await delivered(flow);assert 'Now available' in reply and len(flow.poll_cards)==1
  card=flow.poll_cards[0];assert card['color']=='red' and card['size']=='7' and 'shoes.png' in card['image']
  flow.poll_cards=[];assert await flow.poll() is None
  await other.open();denied=await other.browser.call('detail',product=card['product']);assert denied.get('error')
  assert 'unavailable' in (await other.chat('add available item '+card['event_id']))[0]
  reply,_=await flow.chat('add available item '+card['event_id']);assert flow.signurl and not flow.review
  t=app.tickets[flow.signurl.split('ticket=')[1]]
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await flow.poll();assert 'is in your bag' in reply,reply
  cart=(await flow.browser.call('cart'))['cart'];await flow.chat('add available item '+card['event_id']);assert (await flow.browser.call('cart'))['cart']==cart
  assert not app.memory.orders() and not flow.review
  reply,_=await flow.chat('find a red tie');assert reply=='Red tie is not available. Would you like FORME to notify you when it’s available?'
  reply,_=await flow.chat('yes');assert reply=='Red tie is not available. FORME will notify you when it’s available.' and not flow.signurl
  app.store.availability.now=lambda:clock+123;assert 'Now available' in await delivered(flow);assert flow.poll_cards[0]['size']=='One size'
  reply,_=await flow.chat('red shoes');assert 'not available' in reply # New scenario after delivery.
  assert 'promise' in (await flow.chat('red shoes size 99 under $100'))[0]
  await flow.chat('red shoes');await flow.chat('yes');await flow.logout();await flow.chat('cancel watch')
  assert any(w.get('cancel_remote_pending') for w in flow.watch_rows())
  await flow.open();flow.pending_read='watch_reconnect';await flow.signin()
  t=app.tickets[flow.signurl.split('ticket=')[1]]
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);await flow.poll()
  assert all(w['status']!='active' for w in flow.watch_rows())
  assert json.loads(app.store.availability.db.execute('SELECT data FROM watches ORDER BY rowid DESC LIMIT 1').fetchone()[0])['status']=='cancelled'
  await flow.chat('red tie');expired=flow.watch_rows()[-1];expired['expires_at']=0;app.watch_memory.save(1,expired)
  assert 'expired' in (await flow.chat('yes'))[0]
  tie=next(c for c in app.watch_memory.inbox(1) if 'Tie' in c['name'])
  await flow.chat('add available item '+tie['event_id']);assert flow.signurl and not app.memory.orders()
  t=app.tickets[flow.signurl.split('ticket=')[1]]
  consent_page=await app.http.get(flow.signurl);assert 'Confirm the requested access' in consent_page.text and 'name="password"' not in consent_page.text
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf']})
  await asyncio.sleep(5.2);assert 'is in your bag' in await flow.poll() and not flow.review
  assert 'approve' in (await flow.chat('checkout'))[0] and flow.review
  assert not app.memory.orders()
 finally:
  await flow.stop_watch_streams();await flow.browser.close();await other.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_restart_reconnect_inbox_and_expiry(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);path=tmp_path/'restart.sqlite';apps=[];servers=[];tasks=[];flows=[]
 async def start():
  app=App();await app.setup(path);apps.append(app)
  app.webhook_enabled=False # Persist/reconnect an SSE watch, rather than the default webhook transport.
  server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve());servers.append(server);tasks.append(task)
  for attempt in range(100):
   if server.started:break
   if task.done():await task
   await asyncio.sleep(.05)
  assert server.started,'Restart server did not start'
  flow=Flow(app,4);flows.append(flow);CURRENT.set(flow);return app,flow
 async def authorize(app,flow):
  t=app.tickets[flow.signurl.split('ticket=')[1]]
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer004@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);return await flow.poll()
 try:
  app,flow=await start();await flow.chat('Red shoes');await flow.chat('yes');assert 'FORME will notify you' in await authorize(app,flow)
  watch=flow.watch_rows()[-1]
  await flow.stop_watch_streams();await flow.browser.close();await app.http.aclose();servers[-1].should_exit=True;await asyncio.wait_for(tasks[-1],10)
  app,flow=await start();app.store.availability.now=lambda:time.time()+61
  assert 'Reconnect' in await flow.poll();assert flow.pending_read=='watch_reconnect'
  await authorize(app,flow);assert 'Now available' in await delivered(flow);card=flow.poll_cards[0];event=card['event_id']
  assert await flow.poll() is None and len(app.watch_memory.inbox(4))==1
  other=Flow(app,5);assert await other.poll() is None and other.token is None and not app.watch_memory.inbox(5)
  from watch_flow import WatchMemory
  import sqlite3
  reloaded=WatchMemory(sqlite3.connect(app.thread_accounts.db.execute('PRAGMA database_list').fetchone()[2]));assert reloaded.inbox(4)[0]['event_id']==event
  # Delivered messages survive a response loss/reload; event ID is the durable dedupe key.
  assert not reloaded.receive(4,card) and len(reloaded.inbox(4))==1
  card['expires_at']=time.time()-1;app.watch_memory.db.execute('UPDATE thread_availability_inbox SET data=? WHERE customer=? AND event=?',(json.dumps(card),4,event));app.watch_memory.db.commit()
  assert 'expired' in (await flow.chat('add available item '+event))[0]
  assert not app.memory.orders()
 finally:
  for flow in flows:await flow.stop_watch_streams();await flow.browser.close()
  for server in servers:server.should_exit=True
  for task in tasks:await task
  for app in apps:await app.http.aclose()

@pytest.mark.parametrize('text',['red shoes size 99','red shoes under $1','red shoes wide','red shoes size 42 EU','red shoes by Gucci','red shoes in suede','red tie under $5','red tie size 99','red tie extra long','red tie cotton'])
@pytest.mark.asyncio
async def test_impossible_red_constraints_no_offer(tmp_path,monkeypatch,text):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'constraints.sqlite');flow=Flow(app,1)
 # Exercise actual company candidate policy without starting network for this focused check.
 async def opened():flow.token=object()
 async def browser(action,**kw):return {'availability':{'candidate':app.store.availability.candidate(kw['filters'])}}
 flow.open=opened;flow.browser.call=browser
 try:
  reply,cards=await flow.chat(text);assert not cards and ('promise' in reply or 'supports' in reply),reply
  assert not flow.watch_rows() and not app.store.availability.db.execute('SELECT * FROM watches').fetchall()
 finally:await app.http.aclose()

@pytest.mark.parametrize('text,kind',[('Red shoes','shoes'),('RED SHOES','shoes'),('show me red shoes','shoes'),('find a pair of red shoes','shoes'),('red sneakers please','shoes'),('Red Tie','tie'),('RED TIE','tie'),('find a red tie','tie'),('show me red ties','tie'),('red necktie please','tie')])
@pytest.mark.asyncio
async def test_trigger_language_is_deterministic(tmp_path,monkeypatch,text,kind):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'trigger.sqlite');flow=Flow(app,1)
 async def no_model(*args):raise AssertionError('Demo trigger must not depend on model interpretation')
 app.model.parse=no_model
 async def opened():flow.token=object()
 async def browser(action,**kw):return {'availability':{'candidate':app.store.availability.candidate(kw['filters']),'offer':'fixture-offer'}}
 flow.open=opened;flow.browser.call=browser
 try:
  reply,_=await flow.chat(text);assert 'not available' in reply and flow.watch_rows()[-1]['filters']['demo_trigger']==kind and not flow.signurl
 finally:await app.http.aclose()


def test_unavailable_copy_has_no_scenario_disclaimers():
 source=(Path(__file__).parent/'watch_flow.py').read_text()
 for old in ('In this demo scenario','this local demo','about one minute','about 60 seconds','No order will be placed'):
  assert old not in source


def test_generic_watch_preserves_product_name():
 from watch_flow import availability_message
 watch={'filters':{},'candidate':{'name':'Linen Oxford Shirt'}}
 assert availability_message(watch)=='Linen Oxford Shirt is not available. Would you like FORME to notify you when it’s available?'
 assert availability_message(watch,True)=='Linen Oxford Shirt is not available. FORME will notify you when it’s available.'
