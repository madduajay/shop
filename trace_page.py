"""Account-scoped exchange records, with authentication secrets removed before storage."""
import html,json,re,secrets,time
from urllib.parse import parse_qs,urlsplit,unquote
from datetime import datetime,timezone
MASK='[authentication secret masked]'
SECRET=re.compile(r'^(?:authorization|proxy.authorization|cookie|set.cookie|password|passwd|api.?key|access_token|refresh_token|id_token|client_secret|private_key|assertion|signature|csrf|csrf_token|ticket|device_code|user_code|code|session_id|session_cookie|encrypted_content|secret)$',re.I)
PROTOCOL_PATHS={'/agent.json','/jwks.json','/.well-known/poppy.json','/.well-known/oauth-authorization-server','/oauth/token','/oauth/device','/oauth/revoke','/poppy/browser-session','/poppy/mcp'}
def protocol_event(x):
 if x.get('layer')=='Custom extension (not standard Poppy or A2A)':return True
 return x.get('kind')=='http' and (urlsplit(x.get('endpoint') or x.get('path','')).path in PROTOCOL_PATHS or urlsplit(x.get('endpoint') or x.get('path','')).path.startswith('/poppy/conversations'))
def now():return datetime.now(timezone.utc).isoformat()
def sensitive(key):return bool(SECRET.fullmatch(str(key)))
def collect(value,known):
 if isinstance(value,dict):
  for k,v in value.items():
   if sensitive(k) or (value.get('kty') in ('RSA','EC','OKP','oct') and k in ('d','p','q','dp','dq','qi','k')):
    for item in (v if isinstance(v,list) else [v]):
     if isinstance(item,str) and item and item!=MASK:
      known.add(item)
      if item.lower().startswith('bearer '):known.add(item[7:])
   collect(v,known)
 elif isinstance(value,(list,tuple)):
  for v in value:collect(v,known)

def payload(value,key='',known=None):
 known=set() if known is None else known
 collect(value,known)
 if str(key).lower() in ('set-cookie','set_cookie') and isinstance(value,str):
  return '\n'.join(re.sub(r'^(\s*[^=;]+)=([^;]*)',lambda m:m[1]+'='+MASK,line) if '=' in line else MASK for line in value.splitlines())
 if sensitive(key):
  if isinstance(value,str) and value and value!=MASK:known.add(value)
  return MASK
 if isinstance(value,dict):
  # Discover all secrets before scrubbing echoes in unrelated fields.
  for k,v in value.items():
   if sensitive(k) and isinstance(v,str) and v and v!=MASK:known.add(v)
  if value.get('kty') in ('RSA','EC','OKP','oct'):
   value={k:MASK if k in ('d','p','q','dp','dq','qi','k') else v for k,v in value.items()}
  return {k:payload(v,k,known) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [payload(v,'',known) for v in value]
 if not isinstance(value,str):return value
 # Structured JSON embedded in model inputs and browser form fields stays complete.
 if value.lstrip().startswith(('{','[')):
  try:return json.dumps(payload(json.loads(value),'',known),ensure_ascii=False)
  except (ValueError,TypeError):pass
 # Secrets embedded in HTML inputs, independent of attribute order.
 def field(m):
  tag=m[0];attrs=dict((x[0].lower(),html.unescape(x[2])) for x in re.findall(r'([\w:-]+)\s*=\s*([\"\'])(.*?)\2',tag,re.S))
  if sensitive(attrs.get('name','')) or attrs.get('type')=='password':
   if attrs.get('value'):known.add(attrs['value'])
   return re.sub(r'(\bvalue\s*=\s*)([\"\'])(.*?)\2',lambda x:x[1]+x[2]+MASK+x[2],tag,flags=re.I|re.S)
  return tag
 value=re.sub(r'<input\b[^>]*>',field,value,flags=re.I|re.S)
 def embedded(m):
  known.add(html.unescape(unquote(m[2])));return m[1]+MASK
 value=re.sub(r'(https?://)([^/\s@]+)@',lambda m:m[1]+MASK+'@',value,flags=re.I)
 value=re.sub(r'((?:data-)?(?:csrf(?:_token)?|access_token|client_secret)\s*=\s*[\"\'])([^\"\']+)',embedded,value,flags=re.I)
 # URL/query strings, JSON-like assignments, and credential-shaped free text.
 value=re.sub(r'([?&](?:access_token|refresh_token|id_token|assertion|ticket|code|csrf|api_key|session_id|secret|password)=)([^&#\s\"\'<>]+)',lambda m:m[1]+MASK,value,flags=re.I)
 value=re.sub(r'((?:[\"\']|\b)(?:password|api_key|access_token|refresh_token|client_secret|csrf|ticket|assertion)(?:[\"\'])?\s*[:=]\s*)([\"\'])(.*?)\2',lambda m:m[1]+m[2]+MASK+m[2],value,flags=re.I|re.S)
 value=re.sub(r'\bBearer\s+[A-Za-z0-9._~+/=-]+','Bearer '+MASK,value,flags=re.I)
 value=re.sub(r'\bsk-[A-Za-z0-9_-]{8,}|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',MASK,value)
 for secret in sorted(known,key=len,reverse=True):
  if secret!=MASK:value=value.replace(secret,MASK).replace(html.escape(secret,quote=True),MASK)
 return value

def body(raw,content_type=''):
 if not raw:return ''
 if isinstance(raw,bytes):
  try:raw=raw.decode('utf-8')
  except UnicodeDecodeError:return {'capture':'Binary body not decoded','bytes':len(raw)}
 if 'json' in content_type:
  try:return json.loads(raw)
  except ValueError:pass
 if 'x-www-form-urlencoded' in content_type:return parse_qs(raw,keep_blank_values=True)
 return raw

def safe_events(events):
 known=set();collect(events,known)
 return [payload(dict(x),known=known) for x in events]
class TraceLog(list):
 def __init__(self,*args,environment='local demo with synthetic commerce'):
  super().__init__(*args);self.environment=environment;self._secrets=set()
 def append(self,event):
  event=dict(event);event.setdefault('timestamp',now());event.setdefault('layer','Poppy protocol' if event.get('kind')=='http' and ('poppy' in event.get('path','') or '.well-known' in event.get('path','')) else 'Application-specific')
  event.setdefault('provenance','internal event; no transport exchange recorded');event.setdefault('environment',self.environment)
  super().append(payload(event,known=self._secrets))
 def begin(self,*,kind,direction,endpoint,request,transport='actual transport',layer='Application-specific',**metadata):
  self.append(dict(kind=kind,direction=direction,endpoint=endpoint,request=request,response=None,request_at=now(),response_at=None,correlation=secrets.token_hex(12),capture_version=2,status='awaiting response',provenance=transport,layer=layer,**metadata));return self[-1]
 def finish(self,event,response=None,status='complete',**metadata):
  if event is None:return
  event.update(payload(dict(response=response,response_at=now() if response is not None else None,status=status,**metadata),known=self._secrets))
  # A response may disclose a credential also echoed earlier in the request.
  event.update(payload(event,known=self._secrets))

def participants(event):
 # Use the recorded route, never the endpoint hostname to guess an initiator.
 route=event.get('direction','')
 parts=[p.strip() for p in route.split('→')]
 if len(parts) not in (2,3) or not all(parts):return None
 return parts[0],parts[1],parts[2] if len(parts)==3 else parts[0]

def descriptions(event):
 """Deterministic explanations of recorded facts, never inferred intent or success."""
 request=event.get('request');response=event.get('response')
 if event.get('capture_version')!=2:
  request=event.get('request_body');response=event.get('response_body')
 browser=event.get('kind')=='browser'
 operation=(request.get('action') if isinstance(request,dict) else None) or event.get('action') or event.get('endpoint')
 browser_requests={'launch':'Start the controlled browser.','configure':'Set the storefront and browser activation destinations.','join':'Submit the signed browser-session assertion.','filter':'Browse products using the requested filters.','catalog':'Open the product catalog.','next':'Open the next product page.','detail':'Open the requested product details.','account_status':'Check the storefront’s current sign-in state.','availability_offer':'Check availability for the requested item.','availability_subscribe':'Request the consented availability notification.','availability_events':'Check for availability updates.','availability_cancel':'Request cancellation of the availability watch.','add':'Request adding the selected item to the bag.','cart':'Read the current bag.','review':'Request an order review.','checkout':'Submit the approved simulated checkout.','order_status':'Check the storefront’s order status.','close':'Close the controlled browser.','screenshot':'Capture the current browser view.','viewport':'Set the browser viewport.'}
 path=urlsplit(event.get('endpoint') or event.get('path','')).path
 protocol_requests={'/agent.json':'Fetch Thread’s client metadata (CIMD) for identity verification.','/jwks.json':'Fetch Thread’s public signing keys (JWKS) for signature verification.','/.well-known/poppy.json':'Read the company’s Poppy capabilities.','/.well-known/oauth-authorization-server':'Read the company’s authorization endpoints.','/oauth/token':'Request a session token or authorization update.','/oauth/device':'Request user authorization for the listed permissions.','/oauth/revoke':'Request revocation of the supplied authorization.','/poppy/browser-session':'Submit a signed assertion to activate a browser session.','/poppy/mcp':'Send the recorded protocol tool request.'}
 requested=browser_requests.get(operation,'Issue the recorded browser command.') if browser else protocol_requests.get(path,'Send the recorded protocol request.')
 if path.startswith('/poppy/conversations'):
  requested='Open the authenticated FORME event stream.' if path.endswith('/events') else 'Start a conversation with FORME using the first message.' if path.endswith('/conversations') else 'Send a consented availability message to FORME.'
  if path.endswith('/conversations') and 'thread_webhook' in json.dumps(request):requested+=' Register Thread’s fixed callback URL in the initial message (custom extension, not standard Poppy or A2A).'
 if path=='/extensions/forme-availability':requested='FORME posts the signed, consent-bound availability event to Thread (custom webhook extension, not standard Poppy or A2A).'
 if request is None:requested+=' Request payload was not captured.'
 status=event.get('status')
 if response is None:
  outcome='Awaiting a response.' if status=='awaiting response' else 'The attempt failed; no response was captured.' if 'failed' in str(status).lower() else 'No response was captured; outcome is unknown.'
  return requested,outcome
 if not isinstance(response,dict):return requested,'Historical response recorded; detailed outcome is not established.'
 if browser:
  result=response.get('result')
  if response.get('error') or (isinstance(result,dict) and result.get('error')):return requested,'The browser reported an error; success is not confirmed.'
  if status=='failed':return requested,'The recorded browser operation failed.'
  if not isinstance(result,dict):return requested,'A browser response was captured; no detailed result was recorded.'
  if operation=='account_status' and isinstance(result.get('signed_in'),bool):return requested,'The storefront reports signed in.' if result['signed_in'] else 'The storefront reports not signed in.'
  if operation in ('cart','add') and isinstance(result.get('cart'),list):return requested,f'The observed bag contains {len(result["cart"])} line item(s).'
  if operation=='filter' and isinstance(result.get('products'),list):return requested,f'The browser observed {len(result["products"])} products on this page.'
  if result.get('receipt'):return requested,'The browser observed a receipt for the simulated order.'
  return requested,'The browser returned the recorded result.'
 code=status if isinstance(status,int) else response.get('status')
 body=response.get('body')
 if path.endswith('/events') and path.startswith('/poppy/conversations') and code==200:
  count=len(body.get('sse_frames',[])) if isinstance(body,dict) else 0
  return requested,f'FORME opened the authenticated stream; {count} event frame(s) received.'
 if path=='/oauth/token' and isinstance(body,dict):
  pending={'authorization_pending':'FORME is waiting for your sign-in approval; this device-authorization poll returned HTTP 400.','slow_down':'FORME asked the client to slow down device-authorization polling.','expired_token':'The device-authorization code expired; sign in again to continue.','access_denied':'The device-authorization request was denied.'}
  if body.get('error') in pending:return requested,pending[body['error']]
 if isinstance(code,int) and code>=400:return requested,f'The endpoint returned HTTP {code}; the request did not succeed.'
 if isinstance(body,dict) and body.get('error'):return requested,'The endpoint returned an error; success is not confirmed.'
 if path=='/poppy/browser-session' and code==303 and event.get('cookie_issued') and (event.get('assertion_validation')=='accepted by company validator' or 'Chrome Network' in event.get('provenance','')):return requested,'The website accepted the assertion, issued its cookie and redirected the browser.'
 if path=='/oauth/token' and isinstance(body,dict) and isinstance(body.get('signed_in'),bool):return requested,'The token response reports signed in.' if body['signed_in'] else 'The token response reports an unsigned-in session.'
 return requested,f'The endpoint returned HTTP {code}; see the recorded response.' if isinstance(code,int) else 'A response was captured; its status was not recorded.'

def render(events,archives,active=None,channel="poppy"):
 channel=channel if channel in ("poppy","browser") else "poppy"
 e=html.escape;links='<a href="/traces?channel='+channel+'">Current conversation</a>'+''.join('<a href="/traces?archive='+e(x['id'],quote=True)+'&amp;channel='+channel+'">'+datetime.fromtimestamp(x['created'],timezone.utc).strftime('%d %b %Y · %H:%M UTC')+'</a>' for x in archives)
 entries=[]
 for i,x in enumerate(safe_events(events)):
  if not (x.get('kind')=='browser' if channel=='browser' else protocol_event(x)):continue
  paired=x.get('capture_version')==2
  provenance=x.get('provenance','Historical record · transport provenance not captured')
  category='Browser' if x.get('kind')=='browser' else 'Custom extension' if x.get('layer')=='Custom extension (not standard Poppy or A2A)' else 'Poppy'
  actors=participants(x)
  request_direction=(actors[0]+' → '+actors[1]) if actors else 'Caller and recipient not captured'
  response_direction=(actors[1]+' → '+actors[2]+' · reply to this request') if actors else 'Reply direction not captured'
  if paired and x.get('response') is None:response_direction='No response captured'
  request_description,response_description=descriptions(x)
  def panel(label,value,missing):
   direction=request_direction if label=='Request' else response_direction
   description=request_description if label=='Request' else response_description
   return '<details class="payload"><summary>'+label+'<small>'+e(direction)+'</small><span class="description">'+e(description)+'</span></summary><pre>'+e(json.dumps(value,indent=2,ensure_ascii=False) if value is not None else missing)+'</pre></details>'
  title=x.get('endpoint') or x.get('tool') or x.get('action') or x.get('path') or x.get('kind','Activity')
  if x.get('kind')=='http' and isinstance(x.get('request'),dict) and x['request'].get('method'):title=x['request']['method']+' '+title
  meta={k:v for k,v in x.items() if k not in ('request','response','request_body','response_body','request_headers','response_headers')}
  if paired:
   request=x.get('request');response=x.get('response')
   panels='<div class="pair">'+''.join(panel(label,v,missing) for label,v,missing in [('Request',request,'Request payload not captured.'),('Response',response,'No response captured. Request may be pending, failed, or interrupted; see status.')])+'</div>'
  else:
   panels='<p class="note">'+('Internal event, not a request/response exchange.' if x.get('provenance','').startswith('internal') else 'Historical capture: full payloads and transport provenance were not recorded. Existing omissions cannot be recovered.')+'</p>'
   panels+='<div class="pair">'+''.join(panel(label,x.get(key),'Not captured in this historical record.') for label,key in [('Request','request_body'),('Response','response_body')])+'</div>'
  entries.append('<article class="event" data-event="'+e(str(x.get('correlation',i)),quote=True)+'"><div class="eyebrow">'+category+'</div><div>'+e(str(title))+'<small>'+e(str(provenance))+' · '+e(str(x.get('status','recorded')))+'</small></div>'+panels+'<details><summary>Exchange metadata</summary><pre class="metadata">'+e(json.dumps(meta,indent=2,ensure_ascii=False))+'</pre></details></article>')
 content=''.join(entries) or '<div class="empty"><h2>A quiet start.</h2><p>No '+channel.title()+' messages in this conversation yet.</p></div>'
 controls='<form method="get" action="/traces" id="trace-filter"><label for="channel">Messages</label> <select name="channel" id="channel">'+''.join('<option value="'+v+'"'+(' selected' if channel==v else '')+'>'+v.title()+'</option>' for v in ('poppy','browser'))+'</select>'+('<input type="hidden" name="archive" value="'+e(active,quote=True)+'">' if active else '')+' <button type="submit">Show</button></form>'
 return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Behind the conversation · Thread</title><style>*{box-sizing:border-box}body{margin:0;background:#f8f7f3;color:#27382d;font:15px/1.6 Arial}header,main{max-width:1400px;margin:auto;padding:28px 24px}header{display:flex;justify-content:space-between;border-bottom:1px solid #dedfd5}a{color:inherit;text-underline-offset:4px}header b{font:28px Georgia}h1{font:42px/1.15 Georgia;margin:18px 0}h2{font:24px Georgia}.eyebrow{text-transform:uppercase;letter-spacing:2px;font-size:11px;color:#747d6c}nav{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0}nav a{font-size:12px;border:1px solid #d7dccf;border-radius:18px;padding:6px 12px;text-decoration:none}.event,.empty{background:white;border:1px solid #e0e3d9;border-radius:12px;margin:12px 0;padding:18px}summary{cursor:pointer;overflow-wrap:anywhere}small{display:block;color:#727d6e}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.7 monospace;max-height:650px;overflow:auto}.metadata{background:#f5f6f0;padding:14px}.pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px}.pair .payload{min-width:0;border-top:1px solid #ddd;padding:14px 0}.payload summary{font:22px Georgia}.payload summary small{font:12px/1.6 Arial;margin-top:6px}.pair{margin:18px 0}.payload .description{display:block;font:13px/1.5 Arial;margin-top:8px;color:#344a3d}select,button{font:inherit;color:inherit;background:white;border:1px solid #d7dccf;border-radius:8px;padding:7px 12px}#trace-filter{margin-bottom:20px}.note{color:#727d6e;font-size:13px}@media(max-width:700px){.pair{grid-template-columns:1fr}h1{font-size:32px}header,main{padding:22px 16px}}</style><header><b>thread ✳</b><a href="/">← Back to chat</a></header><main><div class="eyebrow">A little transparency</div><h1>Behind the conversation</h1><p>'''+('Archived conversation · read-only.' if active else 'Current conversation · updates automatically.')+'''</p><p class="note">Choose Poppy protocol exchanges or Browser actions. Expand Request or Response to inspect its payload. Directions identify the caller, recipient and reply to the same request. Browser requests are commands and responses are observed results, not invented HTTP traffic. Model calls and internal processing are excluded. Actual transport does not mean a real purchase: commerce data is synthetic. Captured application payloads are complete except authentication secrets; binary bodies are identified explicitly. Historical missing payloads are labeled explicitly.</p><nav>'''+links+'</nav>'+controls+'<section id="events" data-live="'+('false' if active else 'true')+'">'+content+'</section></main><script src="/trace-filter.js" defer></script></html>'
