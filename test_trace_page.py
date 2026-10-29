import json,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx
from app import App,AGENT
from test_thread_auth import login
from trace_page import safe_events,TraceLog,render

def test_collapsed_payloads_and_recorded_participants():
 trace=TraceLog();event=trace.begin(kind='http',direction='Thread server → FORME → Thread server',endpoint='/oauth/token',request={'method':'POST'})
 trace.finish(event,{'status':200})
 page=render(trace,[])
 assert 'Thread server → FORME' in page and 'FORME → Thread server · reply to this request' in page
 assert page.count('class="payload"')==2 and ' open' not in page
 assert 'Caller and recipient not captured' in render([{'kind':'http','path':'/oauth/token'}],[])
 trace=TraceLog();event=trace.begin(kind='http',direction='FORME → Thread',endpoint='/poppy/mcp',request={});trace.finish(event,{})
 assert 'FORME → Thread' in render(trace,[]) and 'Thread → FORME · reply to this request' in render(trace,[])

def test_comprehensive_redaction_and_safe_rendering():
 secret='SECRET-MUST-NOT-APPEAR'
 events=TraceLog();events.append({'kind':'http','path':'/oauth/token?secret='+secret,'request_body':{k:secret for k in ['authorization','password','assertion','cookie','private_key','access_token','refresh_token','name','email','customer','custom']},'response_headers':{'Set-Cookie':secret},'status':401,'duration_ms':12,'action':'<script>alert(1)</script>'})
 output=render(events,[]);assert secret not in output and '<script>' not in output and '&lt;script&gt;' in output and 'Poppy protocol' in output and 'duration_ms' in output and 'timestamp' in output
 assert 'A quiet start' in render([],[])
 b=TraceLog();e=b.begin(kind='browser',direction='agent → browser',endpoint='filter',request={'action':'filter'},transport='actual browser operation');b.finish(e,{'products':[]});assert 'Browser</div>' in render(b,[],channel='browser') and '<summary>Response' in render(b,[],channel='browser')
 assert 'api.openai.com' not in render([{'kind':'model','endpoint':'https://api.openai.com/v1/responses'}],[])
 assert '/shop?foo=bar' not in render([{'kind':'http','endpoint':'https://shop.test/shop?foo=bar'}],[])
 assert '/oauth/device' in render([{'kind':'http','path':'/oauth/device'}],[])
 page=render([{'kind':'http','path':'/oauth/token'}],[]);assert page.count('class="payload"')==2 and '<details open' not in page and 'Caller and recipient not captured' in page

@pytest.mark.asyncio
async def test_trace_auth_archive_clear_and_navigation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'trace.sqlite');transport=httpx.ASGITransport(app=app)
 try:
  async with httpx.AsyncClient(transport=transport,base_url=AGENT) as a,httpx.AsyncClient(transport=transport,base_url=AGENT) as b,httpx.AsyncClient(transport=transport,base_url=AGENT) as anon:
   assert (await anon.get('/traces')).headers['location']=='/login'
   ha=await login(a,1);hb=await login(b,2);await a.post('/api/state',headers=ha,json={})
   flow=next(iter(app.clients.values()))[1];flow.trace.append({'kind':'http','path':'/poppy/browser-session','tool':'thread_user_context','status':'complete'})
   from types import SimpleNamespace
   flow.token=SimpleNamespace(signed_in=True);flow.signurl='/signin?fixture'
   state=(await a.post('/api/state',headers=ha,json={})).json();assert state['signin_label']=='Review FORME permissions'
   flow.token=SimpleNamespace(signed_in=False)
   assert (await a.post('/api/state',headers=ha,json={})).json()['signin_label']=='Sign in with FORME'
   flow.token=None;flow.signurl=None
   page=await a.get('/traces');assert 'thread_user_context' in page.text and page.headers['cache-control']=='no-store'
   assert 'thread_user_context' not in (await b.get('/traces?customer=1')).text
   home=(await a.get('/')).text;assert 'href="/traces" target="_blank"' in home and 'id="traces"' not in home
   cleared=(await a.post('/api/clear',headers=ha,json={'confirm':True})).json();url='/traces?archive='+cleared['archive']
   assert 'thread_user_context' in (await a.get(url)).text
   assert (await b.get(url)).status_code==404
   assert 'A quiet start' in (await a.get('/traces')).text
   assert (await a.get('/traces?archive=guessed')).status_code==404
 finally:await app.http.aclose()

def test_complete_payload_pairing_provenance_and_secret_masking():
 extra=safe_events([{'key':{'kty':'oct','k':'PRIVATE-MATERIAL'},'echo':'PRIVATE-MATERIAL','html':'<body data-csrf="HTML-TOKEN">HTML-TOKEN</body>','url':'https://someone:PASS@shop.test/path'}])
 assert all(v not in json.dumps(extra) for v in ['PRIVATE-MATERIAL','HTML-TOKEN','someone:PASS'])
 trace=TraceLog(environment='isolated synthetic fixture')
 event=trace.begin(kind='http',direction='test client → website',endpoint='https://shop.test/poppy/browser-session?ticket=URL-CREDENTIAL',request={'headers':{'Authorization':'Bearer RAW-CREDENTIAL','Cookie':'secret-cookie'},'body':{'password':'PW-CREDENTIAL','name':'Alex Example','email':'alex@example.test','address':'12 Example Lane','colors':['blue'],'rows':list(range(150))}},transport='injected mock transport')
 trace.finish(event,{'status':200,'html':"<input value='HIDDEN-CREDENTIAL' name='csrf'><p>PW-CREDENTIAL RAW-CREDENTIAL</p>",'record':{'name':'Alex Example','price':95}},status=200)
 encoded=json.dumps(trace)
 for secret in ['RAW-CREDENTIAL','PW-CREDENTIAL','secret-cookie','HIDDEN-CREDENTIAL','URL-CREDENTIAL']:assert secret not in encoded
 assert 'Alex Example' in encoded and 'alex@example.test' in encoded and '12 Example Lane' in encoded
 assert event['request']['body']['rows']==list(range(150)) and event['response_at'] and event['correlation']
 page=render(trace,[]);assert '<summary>Request' in page and '<summary>Response' in page and 'injected mock transport' in page
 missing=trace.begin(kind='http',direction='outbound',endpoint='/oauth/token',request={'query':'hello'});trace.finish(missing,status='failed; no response',error_type='TimeoutError')
 page=render(trace,[]);assert 'No response captured' in page and 'TimeoutError' in page
 assert 'Historical capture' in render([{'kind':'http','path':'/poppy/browser-session','request_body':'[values omitted]'}],[])
 trace.append({'kind':'approval','status':'explicit approval'});assert 'explicit approval' not in render(trace,[])

@pytest.mark.asyncio
async def test_model_trace_mock_and_failed_attempt():
 from model import Parser
 trace=TraceLog(environment='isolated synthetic fixture')
 def respond(request):return httpx.Response(200,json={'model':'fixture','output':[]})
 parser=Parser(transport=httpx.MockTransport(respond),trace_provider=lambda:trace);parser.key='FAKE-KEY-SECRET'
 async with httpx.AsyncClient(transport=parser.transport) as c:
  await parser._post(c,'https://api.openai.com/v1/responses',headers={'Authorization':'Bearer '+parser.key},json={'input':'show me a red tie'})
 assert trace[0]['provenance']=='injected test transport; may be mocked'
 assert trace[0]['response']['body']['model']=='fixture' and 'FAKE-KEY-SECRET' not in json.dumps(trace)
 def timeout(request):raise httpx.ConnectTimeout('never log credential exception text')
 async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as c:
  with pytest.raises(httpx.ConnectTimeout):await parser._post(c,'https://api.openai.com/v1/responses',json={'input':'hello'})
 assert trace[-1]['status']=='failed; no response' and trace[-1]['response'] is None

@pytest.mark.parametrize('event,expected',[
 ({'kind':'http','endpoint':'/oauth/device','capture_version':2,'request':{},'response':{'body':{}},'status':200},('Request user authorization','HTTP 200')),
 ({'kind':'http','endpoint':'/poppy/browser-session','capture_version':2,'request':{},'response':{},'status':303,'cookie_issued':True,'assertion_validation':'accepted by company validator'},('signed assertion','issued its cookie')),
 ({'kind':'http','endpoint':'/poppy/browser-session','capture_version':2,'request':{},'response':{},'status':400},('signed assertion','did not succeed')),
 ({'kind':'http','endpoint':'/oauth/token','capture_version':2,'request':{},'response':None,'status':'awaiting response'},('session token','Awaiting a response')),
 ({'kind':'http','endpoint':'/oauth/token','capture_version':2,'request':{},'response':None,'status':'failed; no response'},('session token','attempt failed')),
 ({'kind':'http','path':'/oauth/token'},('payload was not captured','outcome is unknown')),
 ({'kind':'browser','endpoint':'add','capture_version':2,'request':{'action':'add'},'response':{'result':{'cart':[]}},'status':'complete'},('Request adding','0 line item')),
 ({'kind':'browser','endpoint':'add','capture_version':2,'request':{'action':'add'},'response':{'result':{'error':'Denied'}},'status':'complete'},('Request adding','success is not confirmed')),
 ({'kind':'browser','endpoint':'account_status','capture_version':2,'request':{'action':'account_status'},'response':{'result':{'signed_in':True}}},('sign-in state','reports signed in')),
 ({'kind':'browser','action':'unknown_action'},('recorded browser command','outcome is unknown')),
])
def test_visible_grounded_descriptions(event,expected):
 from trace_page import descriptions
 request,response=descriptions(event);assert expected[0] in request and expected[1] in response
 from html.parser import HTMLParser
 class Summaries(HTMLParser):
  def __init__(self):super().__init__();self.active=False;self.text=''
  def handle_starttag(self,tag,attrs):
   if tag=='summary':self.active=True
   if tag=='details':assert 'open' not in dict(attrs)
  def handle_endtag(self,tag):
   if tag=='summary':self.active=False
  def handle_data(self,data):
   if self.active:self.text+=data
 parser=Summaries();parser.feed(render([event],[],channel='browser' if event.get('kind')=='browser' else 'poppy'));assert request in parser.text and response in parser.text


def test_exclusive_channel_filter_and_empty_states():
 events=[{'kind':'http','path':'/oauth/token','request_body':'poppy-request','response_body':'poppy-response'}, {'kind':'browser','action':'cart','request_body':'browser-request','response_body':'browser-response'}, {'kind':'model','endpoint':'internal-model'}, {'kind':'http','path':'/shop','request_body':'application-only'}]
 for channel,yes,no in [('poppy','poppy','browser'),('browser','browser','poppy')]:
  page=render(events,[],channel=channel)
  assert yes+'-request' in page and yes+'-response' in page
  assert no+'-request' not in page and no+'-response' not in page
  assert 'internal-model' not in page and 'application-only' not in page
  assert '<option value="'+channel+'" selected>' in page
  assert '<details open' not in page and 'data-live="true"' in page
  assert 'No '+channel.title()+' messages' in render([],[],channel=channel)
 assert render(events,[])==render(events,[],channel='invalid')
 archived=render(events,[{'id':'owned','created':0}],active='owned',channel='browser')
 assert 'data-live="false"' in archived and '&amp;channel=browser' in archived and 'name="archive" value="owned"' in archived


def test_pending_token_poll_is_not_described_as_auth_failure():
 from trace_page import descriptions
 for error,expected in [('authorization_pending','waiting for your sign-in approval'),('slow_down','slow down'),('expired_token','expired'),('invalid_grant','did not succeed')]:
  event={'kind':'http','endpoint':'/oauth/token','capture_version':2,'request':{},'response':{'body':{'error':error}},'status':400}
  assert expected in descriptions(event)[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('fail_refresh', [False, True])
async def test_discovery_after_clear_is_fetched_and_visible_without_reconnecting(tmp_path,monkeypatch,fail_refresh):
 from app import CURRENT,ORIGIN,BrowserSessionClient
 from browser import Browser
 import direct_network
 async def dns(host):return ['127.0.0.1']
 async def no_browser(*args,**kwargs):return {}
 monkeypatch.setattr(direct_network,'resolve_addresses',dns)
 monkeypatch.setattr(Browser,'launch',no_browser)
 monkeypatch.setattr(Browser,'call',no_browser)
 monkeypatch.setattr(Browser,'close',no_browser)
 monkeypatch.setattr(BrowserSessionClient,'join',no_browser)
 app=App();await app.setup(tmp_path/'discovery.sqlite')
 transport=httpx.ASGITransport(app=app);requests=[];unavailable=False
 async def route(request):
  requests.append(request.url.path)
  if unavailable and request.url.path=='/.well-known/poppy.json':
   return httpx.Response(503,json={'error':'fixture unavailable'})
  return await transport.handle_async_request(request)
 await app.http._transport.aclose();app.http._transport=httpx.MockTransport(route)
 context=CURRENT.set(None)
 try:
  async with httpx.AsyncClient(transport=transport,base_url=AGENT) as ui,httpx.AsyncClient(transport=transport,base_url=AGENT) as other:
   headers=await login(ui);other_headers=await login(other,2)
   await ui.post('/api/state',headers=headers,json={})
   flow=next(v[1] for v in app.clients.values() if 1 in v)
   CURRENT.set(flow);await flow.open()
   session=flow.token;reactor=flow.reactor;browser=flow.browser
   assert requests.count('/.well-known/poppy.json')==1
   assert '/.well-known/poppy.json' in (await ui.get('/traces')).text
   archive=(await ui.post('/api/clear',headers=headers,json={'confirm':True})).json()['archive']
   assert not flow.trace
   assert '/.well-known/poppy.json' in (await ui.get('/traces?archive='+archive)).text
   # A greeting stays local and clearing does not synthesize old exchanges.
   await ui.post('/api/chat',headers=headers,json={'text':'hello'})
   assert requests.count('/.well-known/poppy.json')==1
   unavailable=fail_refresh
   reply=await ui.post('/api/chat',headers=headers,json={'text':'show pending adds'})
   if fail_refresh:
    assert 'couldn’t verify' in reply.json()['reply'] and flow.discovery_pending
    assert any(e.get('status')==503 for e in flow.trace)
    unavailable=False
    await ui.post('/api/chat',headers=headers,json={'text':'show pending adds'})
   assert requests.count('/.well-known/poppy.json')==(3 if fail_refresh else 2)
   assert requests.count('/.well-known/oauth-authorization-server')==2
   assert requests.count('/oauth/token')==1
   assert not flow.discovery_pending
   assert flow.token is session and flow.reactor is reactor and flow.browser is browser
   entries=(await ui.post('/api/trace',headers=headers,json={})).json()['events']
   discovery=[e for e in entries if e.get('endpoint')==ORIGIN+'/.well-known/poppy.json' and e.get('status')==200]
   assert len(discovery)==1 and discovery[0]['request']['method']=='GET'
   assert discovery[0]['response']['body']['organization']['domain']=='jacket.localhost'
   assert '/.well-known/poppy.json' in (await ui.get('/traces')).text
   assert '/.well-known/poppy.json' not in (await other.get('/traces')).text
   assert not (await other.post('/api/trace',headers=other_headers,json={})).json()['events']
   await ui.post('/api/chat',headers=headers,json={'text':'show pending adds'})
   assert requests.count('/.well-known/poppy.json')==(3 if fail_refresh else 2)
   assert not app.memory.orders()
 finally:
  CURRENT.reset(context);await app.close()
