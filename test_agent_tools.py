import os,sys,asyncio,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
from agent_tools import tools

@pytest.mark.asyncio
async def test_actual_agent_journey(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Actual GPT required')
 app=App();await app.setup(tmp_path/'agent.sqlite');f=Flow(app,1);CURRENT.set(f);report=[]
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),log_level='critical'));task=asyncio.create_task(server.serve())
 async def chat(q):
  reply,cards=await f.chat(q);report.append({'question':q,'reply':reply,'card_types':[x.get('type','product') for x in cards],'task_status':getattr(f,'agent_task',{}).get('status')});Path('evidence/commerce-images/journey-progress.json').write_text(json.dumps(report,indent=2));return reply,cards
 try:
  while not server.started:await asyncio.sleep(.05)
  assert 'Alex Morgan' in (await chat('hello'))[0]
  assert 'Alex Morgan' in (await chat('who am I'))[0]
  await chat('Remember my shirt size is L')
  assert app.memory.get(1)['shirt_size']=='L'
  reply,_=await chat('What shirt size do you remember for me?');assert 'L' in reply
  reply,cards=await chat('Find white shirts in size L');assert len(cards)>1 and not f.signurl
  await chat('Add the first shirt to my bag');local,_=await chat('What is my name?');assert 'Alex Morgan' in local and f.agent_task['status']=='completed';await chat('Also add the second shirt to my bag');assert len(f.pending_adds)==2
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);resumed=await f.poll();await f.continue_agent_task(resumed,f.poll_cards);assert f.agent_task['status']=='completed';assert len(app.store.commerce.cart('account:forme_customer_001')['lines'])==2
  reply,bag=await chat('What have I got in my bag?');assert len(bag[0]['items'])==2 and all(x['image'] for x in bag[0]['items'])
  item=bag[0]['items'][0]
  reply,updated=await chat('Change the quantity of '+item['name']+' size '+item['size']+' in my bag to 2');assert updated and next(x['quantity'] for x in updated[0]['items'] if x['id']==item['id'])==2,(reply,updated)
  reply,review=await chat('Let me review the order before buying');assert f.review and review and 'approve' in reply.lower()
  await chat('thanks');assert not app.memory.orders()
  await chat('I approve this order');assert len(app.memory.orders())==1
  await chat('I approve this order');assert len(app.memory.orders())==1
  combined,_=await chat('Tell me my name and saved shirt size, and what remains in my FORME bag');assert 'Alex Morgan' in combined and 'L' in combined and 'empty' in combined.lower();assert f.agent_task['status']=='completed'
  status,_=await chat('Are any restock alerts running?');assert '0 active' in status
  no_match,none=await chat('Show me ties under $50');assert not none and 'no ties' in no_match
  other=Flow(app,2);assert 'Alex Morgan' not in (await other.chat('hello'))[0]
  assert not app.store.commerce.cart('account:forme_customer_002')['lines']
  print('Actual GPT calls',app.model.calls)
 finally:
  Path('evidence/commerce-images/agent-trace.json').write_text(json.dumps(list(f.trace),default=str,indent=2))
  Path('evidence/commerce-images/agent-journey.json').write_text(json.dumps(report,indent=2))
  await f.browser.close();await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
async def test_confirmation_cannot_be_forged(tmp_path,monkeypatch):
 from graph_fixtures import ScriptModel,plan,call
 app=App();await app.setup(tmp_path/'forged.sqlite');f=Flow(app,1);app.model.key='fixture-only'
 app.deep_model=ScriptModel(script=[plan('purchase'),call('confirm_checkout')])
 try:
  reply,cards=await f.chat('thanks');assert 'welcome' in reply
  reply,cards=await f.chat('I might buy it tomorrow');assert 'Nothing was purchased' in reply and not app.memory.orders()
  assert len({x['name'] for x in tools()})==len(tools())
 finally:
  await app.http.aclose()
  if hasattr(app,'graph_saver'):app.graph_saver.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['complete','repeat','failure'])
async def test_loop_evidence_and_no_progress(tmp_path,monkeypatch,mode):
 from graph_fixtures import ScriptModel,plan,call,finish
 app=App();await app.setup(tmp_path/(mode+'.sqlite'));f=Flow(app,1);executed=[]
 script=[plan(),call('read_thread_user_data'),call('read_thread_user_data')]
 script += [call('read_thread_user_data')] if mode=='repeat' else [finish(status='unavailable' if mode=='failure' else 'satisfied')]
 app.deep_model=ScriptModel(script=script)
 async def execute(text,calls):
  executed.append(calls)
  if mode=='failure':raise ValueError('fixture failure')
  return 'Verified fixture identity.',[]
 f.execute_tool_calls=execute
 try:
  reply,_=await f.plan_and_execute('who am I');assert len(executed)==1
  assert f.agent_task['skills']['identity-preferences']['version']=='1.0.0'
  assert f.agent_task['status']=={'complete':'completed','repeat':'paused_after_duplicate','failure':'incomplete'}[mode]
  assert 'Verified fixture identity.' in reply if mode!='failure' else 'not retried' in reply
  assert f.agent_task['results'] and not app.memory.orders()
  assert any(x.get('kind')=='Deep Agents business tool' for x in f.trace)
 finally:
  await app.http.aclose()
  if hasattr(app,'graph_saver'):app.graph_saver.close()

@pytest.mark.asyncio
async def test_preference_update_is_verified_and_concise(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'concise.sqlite');f=Flow(app,1)
 try:
  reply,cards=await f.save_tool_preferences({'source':'Thread','updates':[{'field':'shirt_size','value':'L'}]})
  assert reply=='Saved in Thread — shirt size: L.' and not cards
  assert app.memory.get(1)['shirt_size']=='L'
 finally:await app.http.aclose()
