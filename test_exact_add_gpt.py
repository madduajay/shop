import os,sys,asyncio,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN
@pytest.mark.asyncio
async def test_actual_gpt_exact_selection(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Real GPT required')
 app=App();await app.setup(tmp_path/'exact.sqlite');f=Flow(app,1);CURRENT.set(f);report=[]
 original_plan=f.plan_and_execute
 async def diagnostic(*a,**kw):
  try:return await original_plan(*a,**kw)
  except Exception:
   import traceback
   Path('evidence/exact-add-plan-error.txt').write_text(traceback.format_exc());raise
 f.plan_and_execute=diagnostic
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),log_level='critical'));task=asyncio.create_task(server.serve())
 async def chat(q):
  r,c=await f.chat(q);report.append({'request':q,'reply':r,'cards':[x.get('name') for x in c]});return r,c
 try:
  while not server.started:await asyncio.sleep(.05)
  _,prior=await chat('show me black shoes size 9');assert prior
  before=app.store.commerce.cart('account:forme_customer_001')['lines']
  r,c=await chat('add red shoes to cart');assert 'not available' in r and 'notify' in r
  assert not f.pending_adds and not f.signurl and app.store.commerce.cart('account:forme_customer_001')['lines']==before
  assert not any(e.get('kind')=='browser' and e.get('action')=='add' for e in f.trace)
  _,shirts=await chat('show me white shirts size L');assert shirts;earlier=shirts[0]
  _,shoes=await chat('Find black shoes in US shoe size 9');assert shoes,report
  r,_=await chat('Add '+earlier['name']+' size L to my bag');assert f.signurl and f.pending_adds[0]['product']==earlier['id'] and f.pending_adds[0]['size']=='L'
  t=app.tickets[f.signurl.split('ticket=')[1]];await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);await f.poll();await f.resume_add();await f.poll()
  lines=app.store.commerce.cart('account:forme_customer_001')['lines'];assert lines==[{'id':earlier['id'],'size':'L','quantity':1}]
  # Explicit UI selection retains exact stored variant and is deduplicated.
  await chat('select card '+shoes[0]['card_id']);await chat('select card '+shoes[0]['card_id'])
  lines=app.store.commerce.cart('account:forme_customer_001')['lines'];assert len(lines)==2 and all(x['quantity']==1 for x in lines)
  assert not app.memory.orders()
  Path('evidence/exact-add-gpt.json').write_text(json.dumps({'journey':report,'bag':lines,'orders':0,'model_calls':app.model.calls},indent=2))
 finally:
  Path('evidence/exact-add-gpt-progress.json').write_text(json.dumps(report,indent=2))
  await f.stop_watch_streams();await f.browser.close();await app.http.aclose();server.should_exit=True;await task
@pytest.mark.asyncio
async def test_model_cannot_substitute_stale_variant(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'guard.sqlite');f=Flow(app,1)
 c=f.remember_card({'id':'black-shoe','name':'Black Sandal','category':'shoes','color':'black','size':'9','price_cents':1000},{})
 async def forbidden(*a,**kw):raise AssertionError('Mismatched selection reached mutation')
 f.select_card=forbidden
 try:
  for text in ['add red shoes to cart','add Black Sandal size 10','What is the price of Black Sandal?']:
   r,_=await f.execute_tool_calls(text,[{'name':'add_to_bag','arguments':json.dumps({'card_id':c['card_id']})}]);assert 'Nothing was added' in r and not f.pending_adds
 finally:await app.http.aclose()
