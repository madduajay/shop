import asyncio,json,os,traceback
from pathlib import Path
os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT
from trace_page import safe_events,payload

@pytest.mark.asyncio
@pytest.mark.parametrize('attempt',range(3))
async def test_category_switch_diagnosis(tmp_path,attempt):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Actual GPT required')
 app=App();await app.setup(tmp_path/'diagnosis.sqlite');f=Flow(app,1);CURRENT.set(f);report=[];errors=[]
 original=f.plan_and_execute
 async def diagnose(*args,**kwargs):
  try:return await original(*args,**kwargs)
  except Exception as exc:
   errors.append({'type':type(exc).__name__,'error':str(exc),'stack':traceback.format_exc()});raise
 f.plan_and_execute=diagnose
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  for q in ['show me black shoes size 9','add red shoes to cart','show me white shirts size L','Find black shoes in US shoe size 9']:
   reply,cards=await f.chat(q);report.append({'request':q,'reply':reply,'cards':[c.get('name') for c in cards]})
  assert not app.store.commerce.cart('account:forme_customer_001')['lines']
  assert not f.pending_adds and not f.signurl and not app.memory.orders()
  assert not errors,errors
  assert report[-1]['cards'],report
 finally:
  Path(f'evidence/planner-diagnosis-{attempt}.json').write_text(json.dumps(payload({'journey':report,'errors':errors,'task':f.agent_task,'trace':safe_events(f.trace)}),indent=2))
  await f.stop_watch_streams();await f.browser.close();await app.http.aclose();server.should_exit=True;await task
