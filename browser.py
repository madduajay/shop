import asyncio,json,shutil,time,os
from pathlib import Path
class Browser:
 def __init__(self,origin,trace):self.origin=origin;self.trace=trace;self.process=None;self.seq=0
 async def call(self,action,**kw):
  start=time.monotonic();self.seq+=1;seq=self.seq
  request=dict(id=seq,action=action,**kw)
  event=self.trace.begin(kind='browser',direction='Thread → controlled Chrome → Thread',endpoint=action,request=request,transport='actual browser/UI operation over local process',layer='Browser operation',action=action) if hasattr(self.trace,'begin') else None
  try:
   self.process.stdin.write((json.dumps(request)+'\n').encode());await self.process.stdin.drain()
   async with asyncio.timeout(45):
    while True:
     raw=await self.process.stdout.readline()
     if not raw:raise ConnectionError('Browser process ended before response')
     data=json.loads(raw)
     if data['id']==seq:break
   for wire in data.pop('activation_exchanges',[]):
    capture_id=next((v for k,v in wire['response']['headers'].items() if k.lower()=='x-atlas-capture-id'),None)
    server_capture=next((x for x in self.trace if x.get('kind')=='activation_capture' and x.get('correlation')==capture_id),None)
    if server_capture is not None and server_capture.get('response') is not None:
     wire['response']['body']=server_capture['response']['body'];wire['response']['body_capture']='Actual company response bytes, correlated with Chrome response via X-Atlas-Capture-ID.'
     self.trace.remove(server_capture)
    e=self.trace.begin(kind='http',direction='Thread-controlled browser → FORME → Thread-controlled browser',endpoint=wire['endpoint'],request=wire['request'],transport='actual Chrome Network.requestWillBeSent / Network.responseReceivedExtraInfo before redirect',layer='Poppy protocol',network_request_id=wire['network_request_id'])
    if server_capture is not None:e['assertion_validation']=server_capture.get('assertion_validation')
    e['request_at']=wire['request_at'];e['timestamp']=wire['request_at']
    self.trace.finish(e,wire['response'],status=wire['status']);e['response_at']=wire['response_at']
    e['cookie_issued']=any(k.lower()=='set-cookie' for k in wire['response']['headers'])
    from datetime import datetime
    e['duration_ms']=round((datetime.fromisoformat(wire['response_at'].replace('Z','+00:00'))-datetime.fromisoformat(wire['request_at'].replace('Z','+00:00'))).total_seconds()*1000,1)
   captured=data
   if action=='screenshot' and isinstance(data.get('result'),dict) and 'data' in data['result']:
    # Screenshot pixels are binary evidence, not application text to scan/render.
    captured={**data,'result':{**data['result'],'data':{'capture':'Binary screenshot body not decoded','encoding':'base64','encoded_characters':len(data['result']['data'])}}}
   if event is not None:self.trace.finish(event,captured,'failed' if 'error' in data else 'complete',duration_ms=round((time.monotonic()-start)*1000,1))
   if 'error' in data:raise ValueError('The controlled browser could not complete this step. Your order was not retried.')
   self.snapshot=data['result'];return self.snapshot
  except BaseException as exc:
   if event is not None and event['response'] is None:self.trace.finish(event,status='failed; no response',error_type=type(exc).__name__,duration_ms=round((time.monotonic()-start)*1000,1))
   raise
 async def launch(self,storefront=None,activation=None):
  chrome=os.getenv('THREAD3_CHROME') or next((p for p in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',shutil.which('google-chrome'),shutil.which('chromium'),shutil.which('chromium-browser')) if p and Path(p).is_file()),None)
  if not chrome:raise RuntimeError('Chrome/Chromium is required; configure THREAD3_CHROME')
  child_env={k:v for k,v in os.environ.items() if k!='OPENAI_API_KEY'}
  self.process=await asyncio.create_subprocess_exec(shutil.which('node'),str(Path(__file__).with_suffix('.cjs')),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=None,limit=8*1024*1024,env=child_env)
  await self.call('launch',origin=self.origin,chrome=chrome)
  await self.call('configure',storefront=storefront or self.origin+'/shop',activation=activation or self.origin+'/poppy/browser-session')
 async def post(self,endpoint,fields):await self.call('join',endpoint=endpoint,fields={k:v.get_secret_value() for k,v in fields.items()})
 async def close(self):
  if self.process:
   await self.call('close');self.process.stdin.close();await self.process.wait();self.process=None
