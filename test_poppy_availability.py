import os,sys,asyncio,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
@pytest.mark.asyncio
async def test_real_messages_stream_and_browser_activation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'fixture.sqlite');app.webhook_enabled=False;flow=Flow(app,1) # Standard SSE remains supported alongside the custom extension.
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='error'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  CURRENT.set(flow);await flow.chat('red tie')
  activation=[x for x in flow.trace if x.get('endpoint','').endswith('/poppy/browser-session')]
  assert len(activation)==1,activation
  a=activation[0];assert a['status']==303 and 'Chrome Network' in a['provenance']
  headers={k.lower():v for k,v in a['response']['headers'].items()}
  assert headers['location'] in ('/shop',ORIGIN+'/shop')
  cookie=headers['set-cookie'];assert all(x in cookie.lower() for x in ('secure','httponly','samesite=','path=/','masked'))
  await flow.execute_tool_calls('get me a red tie',[{'name':'availability_notifications','arguments':json.dumps({'action':'subscribe','event_id':''})}])
  assert not flow.signurl and flow.watch_rows()[-1]['status']=='offered'
  await flow.chat('notify me');ticket=app.tickets[flow.signurl.split('ticket=')[1]]
  await app.http.post(flow.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await flow.poll();assert 'FORME will notify' in reply,reply
  watch=flow.watch_rows()[-1];assert watch.get('conversation_id')
  assert len(app.store.availability.db.execute('SELECT * FROM watches').fetchall())==1
  replay=await flow.watch_message(watch);assert replay['id']==watch['watch_id']
  original_conversation=watch['conversation_id'];watch.pop('conversation_id');app.watch_memory.save(1,watch)
  replay=await flow.watch_message(watch);assert replay['id']==watch['watch_id'] and watch['conversation_id']==original_conversation
  assert app.store.availability.db.execute('SELECT count(*) FROM watches').fetchone()[0]==1
  app.store.availability.now=lambda:time.time()+61
  for _ in range(40):
   if app.watch_memory.inbox(1):break
   await asyncio.sleep(.1)
  cards=app.watch_memory.inbox(1);assert len(cards)==1 and not app.watch_memory.inbox(2)
  assert 'Now available' in await flow.poll()
  await flow.stop_watch_streams();watch=flow.watch_rows()[-1];watch['status']='active';watch.pop('cursor',None);app.watch_memory.save(1,watch);flow.ensure_watch_stream(watch)
  await asyncio.sleep(1.2);assert len(app.watch_memory.inbox(1))==1 and not getattr(flow,'watch_deliveries',[])
  assert app.watch_memory.dismiss(1,cards[0]['event_id']) and not app.watch_memory.dismiss(2,cards[0]['event_id'])
  assert not any(x.get('endpoint') in ('availability_events','availability_subscribe') for x in flow.trace)
  messages=[x for x in flow.trace if '/poppy/conversations' in x.get('endpoint','')]
  assert any(x['status']==201 and '/conversations?' in x['endpoint'] for x in messages) and any(x['status']==202 and '/messages?' in x['endpoint'] for x in messages) and any('sse_frames' in x.get('response',{}).get('body',{}) for x in messages)
  # Another customer cannot read this conversation, even with its own valid watch grant.
  other=Flow(app,2);CURRENT.set(other);await other.chat('red tie');await other.chat('notify me')
  t=app.tickets[other.signurl.split('ticket=')[1]]
  await app.http.post(other.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer002@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);await other.poll()
  with pytest.raises(Exception):
   stream=other.conversation_client().stream(ORIGIN+'/poppy/conversations',watch['conversation_id'],token=other.token,**other.who,max_reconnects=0)
   await anext(stream)
  assert any(x.get('status')==404 for x in other.trace if watch['conversation_id'] in x.get('endpoint',''))
  await other.chat('cancel watch');await other.stop_watch_streams();await other.browser.close();CURRENT.set(flow)
  await flow.chat('red shoes');await flow.chat('notify me');cancelled=flow.watch_rows()[-1]
  await flow.chat('cancel watch');await flow.stop_watch_streams()
  remote=[json.loads(r[0]) for r in app.store.availability.db.execute('SELECT data FROM watches')]
  assert next(w for w in remote if w['consent']==cancelled['consent'])['status']=='cancelled'
  assert not app.memory.orders()
  with pytest.raises(ValueError):await flow.browser.call('join',endpoint=ORIGIN+'/poppy/browser-session',fields={'assertion':'invalid-fixture-assertion'})
  failure=[x for x in flow.trace if x.get('endpoint','').endswith('/poppy/browser-session')][-1]
  assert failure['status']==400 and not any(k.lower()=='set-cookie' for k in failure['response']['headers'])
  Path('evidence/poppy-availability.json').write_text(json.dumps({'activation':activation,'messages':messages,'delivery_without_browser_poll':True,'isolated_inbox':True,'duplicate_suppressed':True,'orders':0},indent=2))
 finally:
  await flow.stop_watch_streams();await flow.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_durable_conversations_without_credentials(tmp_path):
 from availability_protocol import ConversationStore
 from personal_agent_protocol.company.store import CONVERSATION,SESSION,MESSAGE_ID
 path=tmp_path/'conversations.sqlite';first=ConversationStore(path)
 assert await first.create(CONVERSATION,'c',{'owner':['a','u']})
 assert not await first.create(CONVERSATION,'c',{})
 original=await first.get(CONVERSATION,'c')
 assert not await first.replace(CONVERSATION,'c','wrong',{})
 assert await first.replace(CONVERSATION,'c',original.version,{'owner':['a','u'],'events':[1]})
 await first.put(SESSION,'secret',{'credential':'fixture-secret'})
 await first.put(MESSAGE_ID,'m',{'digest':'same-content'})
 restored=ConversationStore(path)
 assert (await restored.get(CONVERSATION,'c')).value['events']==[1]
 assert (await restored.get(MESSAGE_ID,'m')).value['digest']=='same-content'
 assert await restored.get(SESSION,'secret') is None
 assert b'fixture-secret' not in path.read_bytes()
 assert await restored.take(MESSAGE_ID,'m')=={'digest':'same-content'}
 assert await restored.take(MESSAGE_ID,'m') is None
