import os,sys,asyncio,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT
from trace_page import render

@pytest.mark.asyncio
async def test_actual_cold_fetch_warm_cache_and_trace_ownership(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'identity-trace.sqlite')
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve());flows=[]
 try:
  while not server.started:await asyncio.sleep(.05)
  cold=Flow(app,1);flows.append(cold);CURRENT.set(cold);await cold.open()
  reads=[x for x in cold.trace if x.get('kind')=='http' and x.get('endpoint','').endswith(('/agent.json','/jwks.json'))]
  assert [x['endpoint'].split('/')[-1] for x in reads]==['agent.json','jwks.json']
  for x in reads:
   assert x['direction']=='FORME → Thread → FORME' and x['request']['method']=='GET' and x['status']==200
   assert x['response']['body'] and x['response_at'] and x['provenance']=='actual HTTPS Poppy/client exchange'
  assert reads[0]['response']['body']['jwks_uri'].endswith('/jwks.json')
  assert all('d' not in k for k in reads[1]['response']['body']['keys'])
  assert 'Fetch Thread’s client metadata' in render(cold.trace,[]) and 'Fetch Thread’s public signing keys' in render(cold.trace,[])
  assert '/agent.json' not in render(reads,[],channel='browser')
  assert 'FORME → Thread' in render(reads,[]) and '<details open' not in render(reads,[])
  network_before=len([e for e in app.events if e['path'] in ('/agent.json','/jwks.json')])
  warm=Flow(app,2);flows.append(warm);CURRENT.set(warm);await warm.open()
  assert not [x for x in warm.trace if x.get('endpoint','').endswith(('/agent.json','/jwks.json'))]
  network_after=len([e for e in app.events if e['path'] in ('/agent.json','/jwks.json')]);assert network_after==network_before==2
  assert not app.pending_trace_requests and not app.memory.orders()
  Path('evidence/identity-trace.json').write_text(json.dumps({'cold_fetches':reads,'cold_network_fetch_count':network_before,'warm_network_fetch_count':network_after-network_before,'warm_identity_trace_count':0,'customer_isolation':True},indent=2))
 finally:
  for f in flows:await f.browser.close()
  await app.http.aclose();server.should_exit=True;await task

@pytest.mark.asyncio
@pytest.mark.parametrize('failed_path',['/agent.json','/jwks.json'])
async def test_actual_reverse_fetch_failure_is_captured(tmp_path,monkeypatch,failed_path):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'failure.sqlite')
 original=type(app.identity).website
 def website(identity):
  real=original(identity)
  async def serve(scope,receive,send):
   if scope['path']==failed_path:
    from starlette.responses import JSONResponse
    return await JSONResponse({'error':'fixture_unavailable'},status_code=503)(scope,receive,send)
   return await real(scope,receive,send)
  return serve
 monkeypatch.setattr(type(app.identity),'website',website)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve());f=Flow(app,1);CURRENT.set(f)
 try:
  while not server.started:await asyncio.sleep(.05)
  with pytest.raises(Exception):await f.open()
  reads=[x for x in f.trace if x.get('endpoint','').endswith(failed_path)]
  assert len(reads)==1
  event=reads[0];assert event['direction']=='FORME → Thread → FORME' and event['status']==503
  assert event['response']['body']=={'error':'fixture_unavailable'} and event['response_at']
  poppy=render([event],[]);assert failed_path in poppy and 'HTTP 503; the request did not succeed' in poppy
  assert failed_path not in render([event],[],channel='browser') and '<details open' not in poppy
  assert not app.pending_trace_requests and not f.token and not app.memory.orders()
 finally:
  await f.browser.close();await app.http.aclose();server.should_exit=True;await task
