import sys,os,asyncio,json,secrets,ssl,re,time,contextvars,jwt,hashlib
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import dataclass
from urllib.parse import urlsplit,parse_qs
from http.cookies import SimpleCookie
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor/poppy02'))
import httpx,uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse,HTMLResponse,FileResponse,Response
from reactor import PluginManifest
from personal_agent_protocol import SessionClient,BrowserSessionClient,DeviceSignInClient
from personal_agent_protocol.company import CompanyConfig,build_company,company_app
from personal_agent_protocol.demo.kit import AgentIdentity,PersonalAgentHost,personal_agent_reactor
from personal_agent_protocol.reactor import URL_SAFETY_POLICIES,PublicUrlSafetyPolicy
from direct_network import local_addresses
from data import Memory
from company_context import CompanyContext
from recommendations import Explainer
from store import Store,page,CSS,E,WAIST_CATEGORIES
from catalog import BRANDS,PALETTE,MATERIALS
from product_art import product_svg
from browser import Browser
from model import Parser
from chat_routing import route,UNSUPPORTED
from memory_scope import request_expiry
CURRENT=contextvars.ContextVar('flow',default=None)
PORT=int(os.getenv('THREAD3_PORT','8543'));
if PORT not in (8543,8545):raise RuntimeError('Thread3 permits only isolated ports 8543 and 8545')
AGENT=f'https://atlas.localhost:{PORT}';ORIGIN=f'https://jacket.localhost:{PORT}'
AUTHORIZER_COOKIE='__Host-thread3_forme_authorizer'+('' if PORT==8543 else '_'+str(PORT))
def redact(value):
 if isinstance(value,dict):return {k:('[redacted]' if k.lower() in ('access_token','refresh_token','account_token','assertion','client_assertion','password','csrf','device_code','user_code','ticket','session_id','verification_uri_complete') else redact(v)) for k,v in value.items()}
 if isinstance(value,list):return [redact(v) for v in value]
 return value
class Clock:
 def now(self):return datetime.now(timezone.utc)
class Policy(PublicUrlSafetyPolicy):
 async def assert_safe(self,url):
  if urlsplit(url).port!=PORT:raise ValueError('Local port only')
  return await super().assert_safe(url)
class PolicyPlugin:
 def provide_contributions(self,c):c.contribute(URL_SAFETY_POLICIES,Policy(local_addresses,allow_private_networks=True),contribution_id='wardrobe-local',order=0)
@dataclass(frozen=True)
class Config(CompanyConfig):
 @property
 def base(self):return ORIGIN
class Network:
 resolve=staticmethod(local_addresses)
from watch_flow import WatchFlow,WatchMemory
from context_qa import ContextQA
from purchase_flow import PurchaseFlow
from card_context import CardContext
from agent_tools import AgentTools
from account_lifecycle import AccountLifecycle
class Flow(AccountLifecycle,WatchFlow,ContextQA,PurchaseFlow,CardContext,AgentTools):
 def __init__(self,app,customer):
  self.card_selections={};self.pending_adds=[];self.pending_add=None
  self.share_on_connect=False;self.pending_read=None;self.poll_cards=[];self.current_request_id=None
  self.principal=app.thread_accounts.by_profile(customer) if hasattr(app,'thread_accounts') else None
  self.app=app;self.customer=customer;self.trace=__import__('trace_page').TraceLog(environment=getattr(app,'trace_environment','unknown environment'));self.browser=Browser(ORIGIN,self.trace);self.lock=asyncio.Lock();self.started=None;self.options=[];self.option_offset=0;self.catalog_snapshot={};self.review=None;self.token=None;self.signurl=None;self.messages=[];self.pending_company_preferences={};self.category='';self.gender='men';self.department='';self.kind='';self.uncertain=False
  if self.principal and hasattr(app,'graph_saver'):
   recovered=app.graph_saver.latest_task(self.principal['id'])
   if recovered and recovered.get('status') in ('running','blocked','waiting_user','waiting_auth','uncertain'):
    from deep_runtime import safe
    self.agent_task=safe(recovered);self.agent_task['status']='recovery_required'
    self.trace.append({'kind':'agent recovery','status':'fresh review required; no tools replayed','request_id':recovered['id']})
 async def open(self):
  host=PersonalAgentHost(self.app.identity,Clock(),controlled_browser=self.browser)
  self.reactor=personal_agent_reactor(host,network=Network(),http_client=self.app.http,plugins=[self.app.policy]);self.who=dict(tenant_id='forme',pairwise_user_id=self.principal['pairwise'],issuer=ORIGIN)
  d,m,dest=await self.discover_company(self.reactor)
  self.token=await SessionClient(reactor=self.reactor,http_client=self.app.http).start(client_id=self.app.identity.client_id,token_endpoint=m['token_endpoint'],**self.who)
  self.token_received_at=time.time()
  self.app.flows[self.token.session_id]=self
  await self.browser.launch(storefront=dest,activation=d['web']['browser_session_endpoint']);await BrowserSessionClient(reactor=self.reactor).join(client_id=self.app.identity.client_id,pairwise_user_id=self.who['pairwise_user_id'],browser_session_endpoint=d['web']['browser_session_endpoint'],session_id=self.token.session_id,return_to=dest,company_domain='jacket.localhost')
  self.device=DeviceSignInClient(reactor=self.reactor,http_client=self.app.http);self.metadata=m
  self.discovery_pending=False
 async def discover_company(self,reactor):
  from personal_agent_protocol import DiscoveryClient
  discovered=await DiscoveryClient(reactor=reactor,http_client=self.app.http).discover(urlsplit(ORIGIN).netloc)
  d=discovered.document.model_dump(mode='json',exclude_none=True);m=discovered.oauth_metadata.model_dump(mode='json',exclude_none=True)
  if d['organization']['domain'].lower()!='jacket.localhost' or m['issuer']!=ORIGIN:raise ValueError('Company discovery mismatch')
  protocols=d.get('agent',{}).get('protocols',[])
  self.conversation_endpoint=next((p['endpoint'] for p in protocols if p.get('type')=='poppy'),None)
  if self.conversation_endpoint!=ORIGIN+'/poppy/conversations':raise ValueError('Unexpected conversation endpoint')
  dest=(await self.app.http.get(ORIGIN+'/storefront.json')).json()['url']
  if dest!=ORIGIN+'/shop' or d['web']['browser_session_endpoint']==dest:raise ValueError('Invalid storefront')
  self.trace.append(dict(kind='discovery',storefront=dest,activation=d['web']['browser_session_endpoint'],source='company storefront.json — application convention'))
  return d,m,dest
 async def rediscover_company(self):
  # A fresh metadata cache gives the new conversation real exchange records.
  # Keep the session reactor, authorization, and controlled browser (and bag).
  host=PersonalAgentHost(self.app.identity,Clock())
  reactor=personal_agent_reactor(host,network=Network(),http_client=self.app.http,plugins=[self.app.policy])
  await self.discover_company(reactor)
  self.discovery_pending=False
 async def signin(self):
  if self.signurl:
   prior=self.app.tickets.get(self.signurl.split('ticket=')[-1])
   if not prior or prior['expiry']<time.time() or (self.pending_read=='add' and not {'orders:read','orders:write'}<=set(prior['scopes'])):self.started=None;self.signurl=None
  if not self.started:
   scopes=('preferences:read','preferences:write') if self.pending_read=='save_preferences' else ('orders:read','orders:write') if self.pending_read=='add' else self.qa_scopes if self.pending_read=='qa' else ('availability:watch',) if self.pending_read in ('watch','watch_reconnect') else ('preferences:read',) if self.pending_read=='preferences' else ('orders:read',) if self.pending_read in ('orders','bag') else ('orders:read','orders:write','preferences:read','preferences:write')
   if self.pending_adds:scopes=tuple(sorted(set(scopes)|{'orders:read','orders:write'}))
   if self.token.signed_in:scopes=tuple(sorted(set(scopes)|set(self.token.scopes)))
   self.started=await self.device.begin(device_authorization_endpoint=self.metadata['device_authorization_endpoint'],token_endpoint=self.metadata['token_endpoint'],client_id=self.app.identity.client_id,session_id=self.token.session_id,scopes=scopes,**self.who)
   for link in (self.started.verification_uri,self.started.verification_uri_complete):
    if link and (urlsplit(link).scheme!='https' or not any(urlsplit(link).hostname==d.lower() or (urlsplit(link).hostname or '').endswith('.'+d.lower()) for d in [urlsplit(self.metadata['issuer']).hostname,*self.metadata['poppy_domains']])):raise ValueError('Untrusted company verification URL')
   ticket=self.started.user_code;self.app.tickets[ticket]=dict(flow=self,scopes=scopes,code=self.started.user_code,expiry=time.time()+600,csrf=secrets.token_urlsafe(32),done=False)
   self.signurl=self.started.verification_uri_complete
  return self.signurl
 async def poll(self):
  if not self.started:return await self.poll_watches()
  try:r=await self.device.poll(self.started.reference)
  except Exception as e:
   if getattr(e,'code','') in ('slow_down','authorization_pending','rate_limited'):return None
   self.started=None;self.signurl=None;return 'Sign-in expired. Say “sign in” to resume '+('your order history.' if self.pending_read=='orders' else 'your saved bag.')
  if r.token:
   if r.token.session_id!=self.token.session_id:raise ValueError('Session linkage failed')
   status=await self.browser.call('account_status')
   if not r.token.signed_in or not status.get('signed_in') or status.get('account_id')!=f'forme_customer_{self.customer:03}':raise ValueError('FORME authorization does not match this Thread customer.')
   self.app.company_links.bind(self.principal['id'],ORIGIN,status['account_id'],r.token.scopes)
   previous_account_token=getattr(self,'account_token_reference',None)
   self.token=r.token;self.account_token_reference=r.account_token_reference;self.token_received_at=time.time();self.started=None;self.signurl=None
   if previous_account_token and previous_account_token!=self.account_token_reference:await self.revoke_account_token(previous_account_token)
   self.trace.append(dict(kind='signin',status='complete',same_session=True,customer=self.customer))
   if self.pending_adds:
    message,self.poll_cards=await self.resume_add();return message
   if self.pending_read=='qa':
    self.pending_read=None
    message,self.poll_cards=await self.answer_question(self.pending_question);return message
   if self.pending_read=='watch':
    message,self.poll_cards=await self.resume_watch();return message
   if self.pending_read=='watch_reconnect':
    self.pending_read=None
    return await self.poll_watches() or 'FORME notifications reconnected.'
   if self.pending_read=='save_preferences':
    self.pending_read=None
    return await self.share_company_preferences() or 'FORME has not confirmed the preference update.'
   if self.pending_read=='preferences':
    self.pending_read=None
    message,self.poll_cards=await self.preference_status(True);return message
   if self.pending_read in ('bag','checkout'):
    pending=self.pending_read;self.pending_read=None
    message,self.poll_cards=await (self.show_bag() if pending=='bag' else self.begin_checkout());return message
   if self.pending_read=='orders':
    message,self.poll_cards=await self.order_history();return message
   context_message=await self.share_company_preferences() if self.share_on_connect else None
   if not (await self.browser.call('cart')).get('cart'):
    return context_message or 'Signed in with FORME.'
   snap=await self.browser.call('review');self.review=snap.get('review');self.poll_cards=self.commerce_cards(snap,'Review your order')
   return (context_message+' ' if context_message else '')+self.review_message()
 def commerce_cards(self,snap,title):
  # Only data extracted from the current verified storefront DOM; never search cards.
  if not snap.get('signed_in') or snap.get('error') or not snap.get('cart'):return []
  from urllib.parse import urlparse
  items=[]
  for row in snap['cart']:
   item=dict(row);image=item.get('image');url=urlparse(image or '')
   item['image']=image if image and url.scheme=='https' and url.netloc==urlparse(ORIGIN).netloc and url.path.startswith('/assets/') else None
   items.append(item)
  return [dict(type='commerce',reference=title,currency='USD',total_cents=(snap.get('review') or {}).get('total_cents',sum(i['price_cents']*i.get('quantity',1) for i in items)),items=items)]
 def review_message(self):return self.review['summary']+' Reply “I approve this order” to place it.' if self.review else 'Your bag is ready.'
 async def cancel_device_ticket(self,key):
  try:await self.app.shop.deny_device(key)
  except KeyError:pass # A consumed or expired device code already grants no further access.
  self.app.tickets.pop(key,None)
 async def clear_conversation(self):
  if hasattr(self,'deep_runner'):await self.deep_runner.cancel()
  self.agent_task=None
  await self.stop_watch_streams();self.pending_watch_consent=None;self.watch_transition=None
  self.qa_questions=[];self.last_read=None;self.pending_question=None;self.qa_scopes=();self.pending_add=None
  # Company changes go through its browser form; local chat state is never checkout authority.
  await self.reset_company_context()
  for key,ticket in list(self.app.tickets.items()):
   if ticket['flow'] is self:await self.cancel_device_ticket(key)
  self.card_selections={};self.pending_adds=[];self.pending_add=None
  self.pending_read=None;self.poll_cards=[];self.current_request_id=None;self.started=None;self.signurl=None;self.review=None;self.options=[];self.option_offset=0;self.catalog_snapshot={};self.category='';self.department='';self.kind='';self.pending_company_preferences={};self.messages=[];self.trace.clear()
  self.discovery_pending=bool(self.token)
 async def reset_company_context(self):
  if not getattr(self.app,'thread_auth',None) or not self.token:return
  try:
   for rid in self.app.thread_auth.reset_ids(self.customer):
    status=await self.browser.call('account_status')
    if status.get('signed_in') and status.get('account_id')!=f'forme_customer_{self.customer:03}':return
    if status.get('signed_in') and self.principal and not self.app.company_links.authorized(self.principal['id'],ORIGIN,status.get('account_id'),'preferences:write'):return
    snap=await self.browser.call('reset_context',request_id=rid)
    if snap.get('context_reset') and status.get('signed_in'):self.app.thread_auth.reset_done(self.customer,rid)
  except Exception:pass # Retain queued revocation; stale approval is still invalidated locally.
 async def share_company_preferences(self):
  await self.reset_company_context()
  pending=self.app.memory.pending_share(self.customer)
  if not pending:return None
  status=await self.browser.call('account_status')
  expected=f'forme_customer_{self.customer:03}'
  if not status.get('signed_in'):return None
  if status.get('account_id')!=expected:return 'Your FORME account does not match the selected Thread customer. Your shopping memory has not been shared.'
  if self.principal and (not self.app.company_links.authorized(self.principal['id'],ORIGIN,status.get('account_id'),'preferences:write') or 'preferences:write' not in self.token.scopes):return 'Connect this Thread identity to FORME through its sign-in before sharing preferences.'
  snap=await self.browser.call('context_update',preferences=pending.get('preferences',{}),intent=pending.get('intent',{}),update_id=pending['update_id'],metadata=pending['metadata'])
  if snap.get('error'):return snap['error']
  if not snap.get('context_saved'):return 'FORME has not confirmed your shopping memory update.'
  self.app.memory.shared(self.customer,pending['update_id']);self.pending_company_preferences={}
  if self.review:await self.browser.call('order_status')
  return 'FORME saved your shared shopping preferences and current request separately.'
 async def identity_status(self,company=False):
  profile=self.app.memory.get(self.customer)
  intro=f'Thread: customer {self.customer} — {profile["name"]}. '+(f'You’re signed in as {self.principal["email"]}.' if self.principal else 'No authenticated Thread principal is available in this internal flow.')
  if not company:return intro,[]
  if not self.token:return intro+' FORME: not signed in in this Thread session; no store browser session is open.',[]
  try:
   status=await self.browser.call('account_status')
   if self.review:await self.browser.call('order_status')
  except Exception:return intro+' FORME: I could not verify the store sign-in state. I won’t infer it from the selected customer.',[]
  account=status.get('account_id')
  if status.get('account_status')=='signed_in' and account:
   link=self.app.company_links.get(self.principal['id'],ORIGIN) if self.principal else None
   association=' This account is linked to your Thread identity.' if link and link['status']=='active' and link['account']==account else ' No active verified link to this Thread identity is recorded.'
   return intro+f' FORME: verified signed in as {account} in the controlled store browser.'+association,[]
  suffix=' The store browser session expired; your Thread preferences are still saved.' if status.get('account_status')=='expired' else ''
  return intro+' FORME: verified not signed in in the controlled store browser.'+suffix,[]
 async def order_history(self):
  self.pending_read='orders'
  if not self.token:await self.open()
  try:status=await self.browser.call('account_status')
  except Exception:return 'I couldn’t verify FORME right now. Ask for your orders again to retry.',[]
  if status.get('account_status')=='expired':
   await self.browser.close();self.app.flows.pop(self.token.session_id,None);self.token=None;await self.open();status=await self.browser.call('account_status')
  account=status.get('account_id')
  if status.get('signed_in') and account!=f'forme_customer_{self.customer:03}':return 'The FORME account does not match your Thread login. I won’t read its orders.',[]
  if not status.get('signed_in') or not self.principal or not self.app.company_links.authorized(self.principal['id'],ORIGIN,account,'orders:read'):
   await self.signin();return 'Sign in with FORME to read your previous orders. I’ll show them here after authorization; no order will be placed.',[]
  try:
   snap=await self.browser.call('orders')
   if snap.get('error') or snap.get('orders_account')!=account:return 'FORME could not verify access to your order history. No orders were changed.',[]
   self.pending_read=None
   rows=snap.get('orders',[])
   if not rows:return 'No previous orders were found for your signed-in FORME account. This is purchase history, separate from Thread’s Past chats.',[]
   count=snap.get('orders_count',len(rows));return f'Your FORME purchase history — {len(rows)}'+(f' most recent of {count}' if count>len(rows) else '')+(' order. ' if len(rows)==1 else ' orders. ')+'Dates and status are shown as recorded by FORME; payment and delivery tracking are not connected in this demo.',rows
  finally:
   if self.review:await self.browser.call('order_status')
 async def refresh_forme_preferences(self):
  self.company_preference_snapshot=None
  if not self.token or not self.principal:return None
  status=await self.browser.call('account_status');account=status.get('account_id')
  link=self.app.company_links.get(self.principal['id'],ORIGIN)
  if not status.get('signed_in') or not link or link['account']!=account or not any(self.app.company_links.authorized(self.principal['id'],ORIGIN,account,x) for x in ('preferences:read','preferences:write')):return None
  snap=await self.browser.call('context_read',request_id=self.current_request_id or None);payload=snap.get('preferences_json')
  if not isinstance(payload,dict) or payload.get('source')!='FORME' or not isinstance(payload.get('lasting_preferences'),dict) or snap.get('error'):return None
  self.company_preference_snapshot=payload
  self.trace.append({'kind':'company preference refresh','source':'FORME','revision':payload.get('revision'),'status':'complete'})
  return payload
 async def preference_status(self,company=False):
  if company:
   if not self.token:await self.open()
   try:
    status=await self.browser.call('account_status')
    if status.get('account_status')=='expired':
     await self.browser.close();self.app.flows.pop(self.token.session_id,None);self.token=None;await self.open()
    link=self.app.company_links.get(self.principal['id'],ORIGIN) if self.principal else None
    if status.get('signed_in') and link and status.get('account_id')!=link['account']:return 'I can’t verify a matching authorized FORME account for this Thread login.',[]
    payload=await self.refresh_forme_preferences()
    if payload is None:
     self.pending_read='preferences';await self.signin();return 'Sign in and connect your FORME account to read its saved preferences.',[]
    return json.dumps(payload,indent=2,ensure_ascii=False),[]
   except Exception:return 'I couldn’t verify FORME’s saved preferences right now. Your Thread preferences are unchanged.',[]
   finally:
    if self.review:await self.browser.call('order_status')
  p=self.app.memory.get(self.customer)
  from model import FIELDS
  payload={'source':'Thread','lasting_preferences':{k:p[k] for k in FIELDS if k in p},'temporary_constraints':None,'inferred_interests':{'status':'not_loaded','values':None}}
  rid=self.current_request_id or self.catalog_snapshot.get('filters',{}).get('request_id')
  db=self.app.memory.db
  if rid and db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='thread_shopping_intents'").fetchone():
   row=db.execute('SELECT data FROM thread_shopping_intents WHERE customer=?',(self.customer,)).fetchone();value=json.loads(row[0]) if row else {}
   if value.get('request_id')==rid and value.get('expires_at',0)>time.time() and value.get('current_request'):
    payload['temporary_constraints']={'scope':'request','request_id':rid,'expires_at':datetime.fromtimestamp(value['expires_at'],timezone.utc).isoformat(),'source':'Thread chat','values':{k:v for k,v in value['current_request'].items() if k in FIELDS}}
  return json.dumps(payload,indent=2,ensure_ascii=False),[]
 async def logout(self):
  await self.stop_watch_streams()
  await self.revoke_account_token()
  if self.principal:self.app.company_links.revoke(self.principal['id'],ORIGIN)
  if self.token:
   snap=await self.browser.call('logout')
   if snap.get('signed_in'):return 'FORME did not confirm sign-out. Please try again.',[]
   await self.browser.close()
   self.app.flows.pop(self.token.session_id,None)
  for key,ticket in list(self.app.tickets.items()):
   if ticket['flow'] is self:await self.cancel_device_ticket(key)
  self.pending_adds=[];self.pending_add=None;self.pending_read=None;self.poll_cards=[];self.token=None;self.started=None;self.signurl=None;self.review=None;self.options=[];self.catalog_snapshot={};self.pending_company_preferences={};self.uncertain=False
  return f'Signed out of FORME for this Thread flow. Customer {self.customer} remains selected; saved preferences and orders are unchanged.',[]
 async def connected_bag(self,checkout=False):
  if not self.token:await self.open()
  status=await self.browser.call('account_status')
  if status.get('account_status')=='expired':
   await self.browser.close();self.app.flows.pop(self.token.session_id,None);self.token=None;await self.open();status=await self.browser.call('account_status')
  account=status.get('account_id')
  if status.get('signed_in') and account!=f'forme_customer_{self.customer:03}':return None,'The FORME account does not match your Thread identity. Reconnect the matching account.'
  scope='orders:write' if checkout else 'orders:read'
  if not status.get('signed_in') or not self.app.company_links.authorized(self.principal['id'],ORIGIN,account,scope):
   self.pending_read='checkout' if checkout else 'bag';await self.signin()
   return None,'Sign in with FORME to '+('review checkout. I’ll ask for approval before placing the order.' if checkout else 'read your saved bag.')
  self.pending_read=None
  return await self.browser.call('cart'),None
 async def show_bag(self):
  snap,error=await self.connected_bag()
  if error:return error,[]
  if not isinstance(snap,dict) or snap.get('page')!='cart' or not snap.get('signed_in') or snap.get('error') or not isinstance(snap.get('cart'),list):return 'I couldn’t verify your FORME bag. Please try again. Nothing was changed.',[]
  self.last_read='bag'
  items=snap['cart']
  if not items:return 'Your FORME bag is empty.',[]
  lines=[f"{i['name']}, size {i['size']} × {i.get('quantity',1)}" for i in items]
  total=sum(i['price_cents']*i.get('quantity',1) for i in items)/100
  return 'Your FORME bag: '+ '; '.join(lines)+f'. Total USD {total:.2f}. Say “checkout” to review it.',self.commerce_cards(snap,'Your FORME bag')
 async def begin_checkout(self):
  if getattr(self,'pending_add',None):return await self.recover_pending_add()
  snap,error=await self.connected_bag(checkout=True)
  if error:return error,[]
  if not snap.get('cart'):return 'Your bag is empty. Ask me to find an item first.',[]
  snap=await self.browser.call('review');self.review=snap.get('review');return self.review_message(),self.commerce_cards(snap,'Review your order')
 async def chat(self,text):
  from conversation import conversational_reply
  if self.token and getattr(self,'discovery_pending',False) and not conversational_reply(text):
   try:await self.rediscover_company()
   except Exception:
    return 'I couldn’t verify FORME’s discovery information. Please try again; your bag is unchanged.',[]
  await self.ensure_current_token()
  self.watch_transition=None
  watch_reply=await self.resolve_watch_reply(text)
  if watch_reply is not None:
   self.agent_task={'status':'waiting_auth' if self.signurl else 'completed','watch_consent':getattr(self,'pending_watch_consent',None),'results':[]}
   return watch_reply
  self.pending_watch_consent=None
  new_item=self.unselected_add_search(text)
  if new_item:return await self.legacy_chat(new_item,forced_intent='shopping')
  from conversation import conversational_reply
  if conversational_reply(text) or not getattr(self.app.model,'key',None) or text.startswith(('select card ','add available item ')):
   return await self.legacy_chat(text)
  try:return await self.plan_and_execute(text)
  except Exception:
   self.trace.append({'kind':'agent tool plan','status':'unavailable','details':'redacted'})
   return 'I couldn’t complete that request safely. Please try again; no uncertain action will be retried automatically.',[]
 async def legacy_chat(self,text,forced_intent=None):
  from conversation import conversational_reply,without_greeting
  smalltalk=conversational_reply(text)
  if smalltalk:
   if smalltalk.startswith('Hello!') and not getattr(self,'greeted',False):
    self.greeted=True
    if self.principal and self.app.thread_accounts.by_profile(self.customer)['id']==self.principal['id']:
     profile=self.app.memory.get(self.customer)
     name=next((profile.get(k).strip() for k in ('preferred_name','display_name','name') if isinstance(profile.get(k),str) and profile[k].strip()),'')
     if name:smalltalk=smalltalk.replace('Hello!',f'Hello, {name[:100]}!',1)
   return smalltalk,[]
  text=without_greeting(text)
  command=text.strip().lower()
  if command in ('pending adds','show pending adds','show queued items'):
   return ('Waiting to add, one of each:\n'+self.queued_summary() if self.pending_adds else 'No items are waiting to be added.'),[]
  cancel=re.fullmatch(r'cancel queued item (\d+)',command)
  if command=='cancel add' or cancel:
   index=int(cancel[1])-1 if cancel else None
   if index is not None and not 0<=index<len(self.pending_adds):return 'Choose an item number from “show pending adds”.',[]
   jobs=self.cancel_queued_adds(index)
   if not self.pending_adds:
    self.pending_read=None;self.started=None;self.signurl=None
    for key,ticket in list(self.app.tickets.items()):
     if ticket['flow'] is self:await self.cancel_device_ticket(key)
   return 'Cancelled queued additions: '+(', '.join(j['name']+' size '+j['size'] for j in jobs) or 'none')+'. Nothing was purchased.',[]
  clarification=getattr(self,'card_clarification',[])
  if clarification:
   ordinal=re.fullmatch(r'(?:the )?(first|second|third)(?: one| shirt)?[.!]?',text.strip(),re.I)
   self.card_clarification=[]
   if ordinal:
    index=['first','second','third'].index(ordinal[1].lower())
    if index<len(clarification):return await self.select_card(clarification[index])
  if text.startswith('select card '):return await self.select_card(text.removeprefix('select card ').strip())
  historical=await self.historical_selection(text)
  if historical is not None:return historical
  if text.startswith('select product '):
   product=text.removeprefix('select product ').strip()
   index=next((i for i,x in enumerate(self.options) if x['id']==product),None)
   if index is None:return 'That selection is no longer in your current results. Please search again.',[]
   text=['the first one','the second one','the third one'][index]
  # Pending, explicit notification controls own their replies before generic QA.
  watch_reply=await self.watch_command(text)
  if watch_reply is not None:return watch_reply
  # Resolve a contextual color refinement only against current, unexpired results.
  if re.fullmatch(r'(?:show me |something in |in )?(?:another|a different|different|other) colou?r(?:s)?(?: please)?[.!]?',text.strip(),re.I):
   prior=self.catalog_snapshot.get('filters',{})
   if not self.options or not prior or int(prior.get('expires_at',0))<=time.time():return 'Which item would you like in another color? Please search for it first.',[]
   colors=sorted({x['color'] for x in self.options}|set(filter(None,prior.get('exclude_colors','').split(','))))
   text='exclude '+' and '.join(colors)
  # Correct a single adjacent-letter transposition in an explicit discovery request.
  # Do not reinterpret identity, memory, authorization or checkout messages.
  if re.match(r'^(?:show|find|browse|search for|recommend)(?: me)?\s',text.strip(),re.I) and not re.search(r'\b(my|preferences|profile|account|orders|cart|bag|basket|remember|save|update)\b',text,re.I):
   nouns={'shirts','shoes','trousers','jackets','shorts','dresses','skirts','sneakers','sweaters','blouses'}
   def correct_noun(m):
    word=m[0].lower()
    if word in nouns:return m[0]
    matches={word[:i]+word[i+1]+word[i]+word[i+2:] for i in range(len(word)-1)}&nouns
    return next(iter(matches)) if len(matches)==1 else m[0]
   text=re.sub(r'\b[A-Za-z]{5,12}\b',correct_noun,text)
  from color_constraints import parse_colors
  original_colors=parse_colors(text)
  if original_colors['conflict']:
   self.options=[];self.catalog_snapshot={}
   return 'You requested and excluded the same color. Which color should I use? I won’t show excluded items.',[]
  active_search=bool(self.catalog_snapshot.get('filters',{}).get('expires_at',0) and int(self.catalog_snapshot['filters']['expires_at'])>time.time())
  from chat_routing import catalog_discovery
  known=forced_intent or route(text,bool(self.options),active_search);combined=bool(re.search(r'\b(and|also|both|compare)\b',text,re.I))
  question=bool(re.match(r'^(?:what|who|which|when|where|why|how|do|does|did|have|has|is|are|can|could|would|tell me|remind me|summarize|describe|compare)\b',text.strip(),re.I) or '?' in text or known=='unknown')
  discovery=bool(re.search(r'\b(find|browse|shop|recommend|search for)\b',text,re.I)) or (known=='shopping' and bool(re.search(r'\b(show|display)\b',text,re.I)) and not re.search(r'\b(my|preferences|memory|recorded|size|account|orders)\b',text,re.I)) or (bool(re.search(r'\bred (shoes|sneakers|tie|necktie)\b',text,re.I)) and not re.search(r'\b(status|watch|notification|order|bought|purchase)\b',text,re.I))
  discovery=discovery or catalog_discovery(text) or forced_intent=='shopping'
  # A read question about existing cart contents must not become product discovery.
  if not catalog_discovery(text) and re.search(r'\b(bag|cart|basket)\b',text,re.I) and not re.search(r'\b(add|remove|delete|buy|checkout|purchase|find|recommend)\b',text,re.I):
   question=True;discovery=False
  if getattr(self.app.model,'key',None) and question and not discovery and known not in ('action','checkout','logout','bag') and (known in ('unknown','shopping') or combined):return await self.answer_question(text)
  trigger=re.search(r'\bred\s+(shoes?|sneakers?|ties?|neckties?)\b',text,re.I)
  if trigger and 'red' not in original_colors['exclude'] and not re.match(r'^(?:my|remember|save|i prefer|i like)\b',text.strip(),re.I):return await self.red_demo_search(text,'shoes' if trigger[1].lower().startswith(('shoe','sneaker')) else 'tie')
  original=text
  intent=forced_intent or route(original,bool(self.options),active_search)
  if intent=='identity':return await self.identity_status(bool(re.search(r'\bforme\b',original,re.I)))
  if intent=='bag':return await self.show_bag()
  if intent=='checkout':return await self.begin_checkout()
  if intent=='orders':return await self.order_history()
  if intent=='logout':return await self.logout()
  if intent=='unknown':
   if catalog_discovery(original):
    self.trace.append({'kind':'catalog request','status':'unsupported category','request':original})
    return 'FORME does not currently support that product category in its searchable catalog. I haven’t read or changed your bag.',[]
   return UNSUPPORTED,[]
  if text.lower().strip() in ('i approve this order','approve this order','confirm order') and not self.review:return 'Choose an item and review it before approving.',[]
  if intent in ('preferences','company_preferences'):return await self.preference_status(intent=='company_preferences')
  from constraints import extract,ConstraintError,matches,variant_size
  try:explicit_constraints=extract(original) if intent=='shopping' else {}
  except ConstraintError as e:
   self.options=[];return str(e),[]
  try:
   direct_selection=bool(self.options and re.fullmatch(r'(?:(?:choose|select|pick|take|i want|i.ll take) )?(?:the )?(?:first|second|third)(?: one| item| option)?[.!]?',original.strip(),re.I))
   if intent!='action' and not direct_selection:text=await self.app.model.parse(text,self.app.memory.get(self.customer))
   if not isinstance(text,str) or not text.strip() or len(text)>1000:return UNSUPPORTED,[]
   if intent!='action' and route(text,bool(self.options),active_search)!='shopping':return UNSUPPORTED,[]
   p,updates=self.app.memory.edit(self.customer,text,commit=False)
   if text!=original:
    _,explicit=self.app.memory.edit(self.customer,original,commit=False);updates.update(explicit);p.update(explicit)
   if original_colors['mentioned']:
    updates.pop('colors',None);updates.pop('excluded_colors',None)
    p['colors']=self.app.memory.get(self.customer)['colors']
    if original_colors['include']:updates['colors']=original_colors['include'];p['colors']=original_colors['include']
    if original_colors['exclude']:updates['excluded_colors']=original_colors['exclude'];p['excluded_colors']=sorted(set(self.app.memory.get(self.customer).get('excluded_colors',[]))|set(original_colors['exclude']))
   for field,key in [('budget','budget'),('min_price','budget_min'),('apparel_size','shirt_size'),('shoe_size','shoe_size'),('waist_size','waist')]:
    if field in explicit_constraints:
     p[key]=float(explicit_constraints[field]) if key in ('budget','budget_min') else explicit_constraints[field]
     if field!='min_price' or re.search(r'\b(between|range|at least|minimum|min|over|above|more than)\b',original,re.I):updates[key]=p[key]
   if 'budget' in explicit_constraints and 'min_price' not in explicit_constraints:p['budget_min']=0
   if p.get('budget_min',0)>p['budget']:return 'Those price bounds conflict. Please clarify the range.',[]
  except Exception:return UNSUPPORTED,[]
  category_intent=bool(re.search(r'\b(clothes|clothing|outfit|ties|tie|neckties?|shirts?|blouses?|tees?|t-shirts?|trousers?|pants|chinos?|jeans?|jackets?|knitwear|sweaters?|cardigans?|shorts|activewear|dress(?:es)?|skirts?|shoes?|sneakers?|runners?|loafers?|boots?|sandals?|heels?|footwear|kurta|haori|guayabera|barong|dashiki|kaftan|breton|fair.isle|poncho|espadrilles?|huaraches?|babouches?|jutti|geta|clogs?|yemeni)\b',original.lower()))
  explicit_preferences=bool(re.match(r'^(?:i usually |i wear |i prefer |i like |my |remember |save |update |shirt size|shoe size|waist |size system|budget |color |fit |material |quality |width |inseam |avoid |brand |occasion |style )',original.strip(),re.I))
  clauses=re.split(r'\bbut\b|[.;]',original.lower())
  lasting_clauses=[c for c in clauses if re.search(r'\b(my|i usually|i wear|i prefer|i like|always|usually|remember|save|update|favorite|favourite)\b',c) and not re.search(r'\b(tonight|today|this time|for this|only now)\b',c)]
  durable={}
  for key,value in updates.items():
   values=value if isinstance(value,list) else [str(value)]
   raw_support=any(any(str(v).lower() in c for v in values) for c in lasting_clauses)
   if key=='shirt_size':raw_support=raw_support or any(re.search(r'\b(?:extra small|small|medium|large|extra large)\b',c) for c in lasting_clauses)
   labeled=not hasattr(text,'lasting_fields') or key in text.lasting_fields
   if lasting_clauses and raw_support and labeled:durable[key]=value
  temporary={k:v for k,v in updates.items() if k not in durable}
  if forced_intent=='shopping':durable={};temporary=dict(updates);explicit_preferences=False
  request_id=secrets.token_hex(16);expires_at=request_expiry(original,p.get('timezone') or os.getenv('FORME_USER_TIMEZONE','America/Phoenix'))
  prior=self.catalog_snapshot.get('filters',{})
  refinement=bool(active_search and re.fullmatch(r'(?:under|up to|below) \$?\d+|between \$?\d+ and \$?\d+|(?:in )?(?:red|navy|white|black|olive|sand|blue|brown|rose|burgundy|sage)|(?:something |a bit |make it )?(?:cheaper|lighter|darker|more expensive)|(?:xs|s|m|l|xl|xxl)',original.strip(),re.I))
  refinement=refinement or bool(self.catalog_snapshot and original_colors['exclude'] and not category_intent)
  refinement=refinement or bool(prior and temporary and not durable and not category_intent and not re.search(r'\b(find|shop|new|another|different|instead)\b',original,re.I))
  if refinement and prior.get('request_id') and int(prior.get('expires_at',0))>time.time():request_id=prior['request_id'];expires_at=int(prior['expires_at'])
  else:refinement=False
  discovery=bool(re.search(r'\b(show|find|browse|shop|search|recommend|look for|looking for)\b',original,re.I)) or refinement or bool(self.options and not explicit_preferences)
  explicit_company=bool(re.search(r'\bforme\b',original,re.I))
  if updates and explicit_preferences and not discovery and not explicit_company:
   self.share_on_connect=False
   self.current_request_id=request_id
   self.app.memory.intent(self.customer,updates if lasting_clauses else durable,{} if lasting_clauses else temporary,request_id,expires_at)
   payload,_=await self.preference_status()
   return 'I’ve saved those preferences in Thread.\n'+payload,[]
  if intent=='shopping' and not category_intent and not self.department and not explicit_company:return UNSUPPORTED,[]
  if updates:
   self.current_request_id=request_id
   if forced_intent is None and re.match(r'^(?:remember|save|update) (?:at|with|for) forme\b',original.strip(),re.I):self.app.memory.queue_company_preferences(self.customer,updates,request_id,expires_at)
   else:self.app.memory.intent(self.customer,durable,temporary,request_id,expires_at)
   self.pending_company_preferences=self.app.memory.pending_share(self.customer).get('preferences',{})
  if text!=original:self.trace.append(dict(kind='language interpretation',command=text,applied_preferences=updates))
  low=text.lower().strip()
  if low in ('my preferences','what do you remember','preferences'):
   return 'I remember: '+', '.join(f'{k.replace("_"," ")}: {v}' for k,v in p.items() if k not in ('id','name'))+'. Tell me what to change.',[]
  explicit_company=bool(re.match(r'^(?:remember|save|update) (?:at|with|for) forme\b',original.strip(),re.I))
  if not self.token:await self.open()
  if discovery:self.share_on_connect=False


  if self.uncertain:
   snap=await self.browser.call('order_status')
   if snap.get('receipt'):self.uncertain=False;self.review=None;return snap['receipt'],self.commerce_cards(snap,'Order confirmed')
   return 'I’m checking the previous order. No second checkout will be submitted.',[]
  if explicit_company:
   self.share_on_connect=True
   if not updates:return 'Tell me specific values, for example: “remember at FORME shirt size M budget 150”.',[]
   self.pending_company_preferences=dict(self.app.memory.pending_share(self.customer).get('preferences',{}))
   if not self.token.signed_in:
    await self.signin();return 'Sign in with FORME to save only these explicitly shared preferences. Your other Thread memory stays private.',[]
   return await self.share_company_preferences(),[]
  if low in ('i approve this order','approve this order','confirm order'):
   if not self.review:return 'Choose an item and review it before approving.',[]
   if self.principal and not self.app.company_links.authorized(self.principal['id'],ORIGIN,f'forme_customer_{self.customer:03}','orders:write'):return 'Reconnect your FORME account before approving an order.',[]
   snap=await self.browser.call('snapshot')
   if snap.get('review')!=self.review or not snap.get('can_checkout'):return 'Please finish sign-in and review the current order first.',[]
   self.trace.append(dict(kind='approval',status='explicit chat approval',total_cents=self.review['total_cents']))
   self.uncertain=True
   snap=await self.browser.call('checkout',approved=True,review=self.review['id']);self.uncertain=False;self.review=None
   return snap.get('receipt') or snap.get('error') or 'Please review your order status.',self.commerce_cards(snap,'Order confirmed') if snap.get('receipt') else []
  if 'sign in' in low or 'signin' in low:
   if not self.browser.snapshot.get('cart') and not self.review and not self.app.memory.pending_share(self.customer) and not self.pending_read:return 'Choose an item first, then I’ll open the store sign-in.',[]
   await self.signin();return ('Sign in with FORME to read your order history.' if self.pending_read=='orders' else 'Sign in with FORME to continue. Your bag will be waiting if you close the window.'),[]
  chosen=None
  for n,word in enumerate(['first','second','third']):
   if word in low and len(self.options)>n:chosen=self.options[n]
  chosen=chosen or next((x for x in self.options if x['name'].lower() in low),None)
  if chosen:
   if chosen.get('card_id'):return await self.select_card(chosen['card_id'])
   request_filters=self.catalog_snapshot.get('filters',{})
   if request_filters.get('expires_at') and int(request_filters['expires_at'])<=time.time():return 'That search has expired. Tell me what you would like to find now.',[]
   size_key='shoe_size' if chosen['category']=='shoes' else 'waist_size' if chosen['category'] in WAIST_CATEGORIES else 'apparel_size'
   if not matches(chosen,request_filters):return 'That variant no longer meets your request. Please search again; nothing was added.',[]
   size=request_filters.get('size') or request_filters.get(size_key) or (p['shoe_size'] if chosen['category']=='shoes' else p['waist'] if chosen['category'] in WAIST_CATEGORIES else p['shirt_size'])
   return await self.add_selected(chosen['id'],size,chosen['name'])
  search=(original+' '+text).lower()
  if re.search(r"\bwomen(?:['’]s)?\b",search):self.gender='women'
  elif re.search(r"\bmen(?:['’]s)?\b",search):self.gender='men'
  if any(w in search for w in ('clothing','clothes','outfit')):self.category='';self.department='clothing';self.kind=''
  categories={'ties':['necktie','ties',' tie'],'shoes':['shoe','sneaker','runner','footwear','loafer','boot','sandal','heel'],'trousers':['trouser','pant','chino'],'shirts':['shirt'],'tees':['t-shirt','tee'],'jeans':['jean','denim pants'],'jackets':['jacket'],'blouses':['blouse'],'knitwear':['knit','sweater','cardigan'],'shorts':['shorts'],'activewear':['activewear','training top'],'dresses':['dress'],'skirts':['skirt']}
  for cat,words in categories.items():
   if any(w in search for w in words):self.category=cat;self.department='footwear' if cat=='shoes' else 'accessories' if cat=='ties' else 'clothing';self.kind=''
  if self.category=='shoes':
   for kind in ('sneakers','runners','loafers','boots','sandals','heels'):
    if kind[:-1] in search:self.kind=kind
  from global_catalog import FAMILIES,REGIONAL_SHOES,CLOTHING
  design=''
  for name in ('kurta','haori','guayabera','barong','dashiki','kaftan','breton','fair-isle','poncho',*REGIONAL_SHOES):
   if name.replace('-',' ') in search.replace('-',' '):
    design=name;self.kind=''
    if name in REGIONAL_SHOES:self.category='shoes';self.department='footwear';self.kind=name
    else:
     choices=[k for k,values in CLOTHING.items() if name in values]
     self.category=('blouses' if self.gender=='women' and 'blouses' in choices else choices[0]);self.department='clothing'
    break
  if self.gender=='women' and self.category=='shirts':self.category='blouses'
  if self.category=='shoes' and p['width']!='standard':return 'This collection currently stocks standard-width shoes. I remember your wide fit and won’t substitute a narrower pair.',[]
  if p['size_system']!='US':return 'This collection uses US sizes. Tell me your US shirt or shoe size and “size system US” before I choose a fit.',[]
  more=any(w in low for w in ('show more','next page','more options','next options'))
  if more:
   snap=self.catalog_snapshot
   if snap.get('filters',{}).get('expires_at') and int(snap['filters']['expires_at'])<=time.time():return 'That search has expired. Tell me what you would like to find now.',[]
   if self.option_offset+3<len(snap.get('products',[])):self.option_offset+=3
   elif snap.get('has_next'):snap=await self.browser.call('next');self.option_offset=0
   else:return 'You’ve reached the last page. Tell me what to refine.',[]
  else:
   filters=dict(preference_source='thread',request_id=request_id,expires_at=str(expires_at),explain='1',size_system=p['size_system'],width=p['width'],gender=self.gender,department=self.department,category=self.category,kind=self.kind,apparel_size=p['shirt_size'],waist_size=p['waist'],shoe_size=p['shoe_size'],budget=str(p['budget']),min_price=str(p.get('budget_min',0)),exclude_material=p['avoid'])
   if refinement:
    from recommendations import intent_filters
    filters.update(prior);filters.update(intent_filters(updates))
   if design:filters['design_style']=design
   elif p.get('design_style'):filters['prefer_design_style']=p['design_style']
   if re.search(r'\b(cheaper|least expensive|lowest price)\b',low):filters['sort']='price-low'
   for field in ('color','brand','material','quality','fit','style','occasion'):
    filters['prefer_'+field]=(p['colors'][0] if p['colors'] else '') if field=='color' else (p['brands'][0] if p['brands'] else '') if field=='brand' else p[field]
   from color_constraints import values
   color_request=original_colors if original_colors['mentioned'] else parse_colors(text)
   active_colors=values(filters.get('include_colors',''))|values(filters.get('color',''))
   excluded=((values(filters.get('exclude_colors',''))|(set(p.get('excluded_colors',[]))-active_colors)|(values(prior.get('exclude_colors','')) if refinement else set()))-set(color_request['include']))|set(color_request['exclude'])
   filters['exclude_colors']=','.join(sorted(excluded))
   if color_request['include']:
    filters['include_colors']=','.join(color_request['include'])
    if len(color_request['include'])==1:filters['color']=color_request['include'][0]
    else:filters.pop('color',None)
   if excluded:
    if filters.get('color') in excluded:filters.pop('color',None)
    if filters.get('prefer_color') in excluded:filters['prefer_color']=''
    if filters.get('include_colors'):
     allowed=values(filters['include_colors'])-excluded
     if not allowed and color_request['include']:
      self.options=[];self.catalog_snapshot={}
      return 'Those color requirements conflict with your exclusions. Please choose a different color.',[]
     filters['include_colors']=','.join(sorted(allowed))
   choices={'material':sorted({m for ms in MATERIALS.values() for m in ms}|{'leather','suede','vegan leather','nubuck'}),'brand':BRANDS+['Nike','Levi’s'],'fit':['regular','relaxed','slim'],'quality':['essential','premium','luxury'],'occasion':['everyday','work','running','evening','travel','weekend'],'style':['minimal','classic','sport','casual','modern']}
   for field,values in choices.items():
    for value in values:
     if re.search(r'\b'+re.escape(value.lower())+r'\b',low) and not re.search(r'avoid\s+'+re.escape(value.lower()),low):filters[field]=value
   filters.update({k:v for k,v in explicit_constraints.items() if k!='exclude_colors'})
   if 'budget' in explicit_constraints and 'min_price' not in explicit_constraints:filters['min_price']=prior.get('min_price','0') if refinement else '0'
   if float(filters.get('min_price') or 0)>float(filters.get('budget') or 100000):
    self.options=[];return 'That maximum is below your required minimum. Which price bound would you like to change?',[]
   if explicit_constraints.get('apparel_size'):filters.pop('size',None)
   # A current positive color overrides saved exclusions, never this request’s negatives.
   from color_constraints import values as color_values
   if explicit_constraints.get('include_colors'):
    filters['exclude_colors']=','.join(sorted((color_values(filters.get('exclude_colors',''))-color_values(explicit_constraints['include_colors']))|color_values(explicit_constraints.get('exclude_colors',''))))
   if filters.get('gender')=='women' and filters.get('category')=='shirts':filters['category']='blouses'
   if filters.get('category')=='ties':filters.update(department='accessories',gender='',apparel_size='',waist_size='',shoe_size='',size='')
   self.category=filters.get('category','');self.department=filters.get('department','');self.kind=filters.get('kind','')
   snap=await self.browser.call('filter',filters=filters);self.option_offset=0
  self.catalog_snapshot=snap
  products=snap.get('products',[])
  from color_constraints import values
  expected=snap.get('filters',{}) if more else filters
  included=values(expected.get('include_colors','')) or ({expected['color']} if expected.get('color') else set())
  excluded=values(expected.get('exclude_colors',''))
  if any((included and x.get('color') not in included) or x.get('color') in excluded for x in products):
   self.options=[];self.catalog_snapshot={}
   return 'The storefront returned items outside your requested colors. I won’t substitute them. Please try the search again.',[]
  if any(not matches(x,expected) for x in products):
   self.options=[];self.catalog_snapshot={}
   return 'The storefront returned variants that do not meet every requirement. I won’t substitute them. Please try the search again.',[]
  self.options=[dict(x,size=variant_size(x,expected)) for x in products[self.option_offset:self.option_offset+3]]
  if not products and expected.get('category')=='ties':return 'FORME’s public catalog currently has no ties matching this search. Your bag is unchanged. You can ask for a red tie to explore the separate demo restock option.',[]
  if not products:return await self.offer_watch(snap.get('filters',{}))
  self.trace.append(dict(kind='company recommendation explanations',sources=sorted({x.get('explanation_source') or 'none' for x in self.options}),items=[x['id'] for x in self.options]))
  cards=[self.remember_card(dict(x,image=ORIGIN+x['image'],url=ORIGIN+'/shop/product/'+x['id']),expected) for x in self.options]
  for option,card in zip(self.options,cards):option['card_id']=card['card_id']
  return ('I’ve saved those preferences in Thread. ' if durable else 'I’m using those details for this request. ' if temporary else '')+f'Here are {len(cards)} options from {snap.get("total",len(products))} matching styles in the {self.gender} collection, matching your current size, price and product requirements. Say “the first one”, “show more”, or tell me what to refine.',cards

class TracedEventStream(httpx.AsyncByteStream):
 def __init__(self,stream,trace,event):self.stream=stream;self.trace=trace;self.event=event;self.buffer='';self.events=[];self.decoder=__import__('codecs').getincrementaldecoder('utf-8')()
 async def __aiter__(self):
  async for chunk in self.stream:
   self.buffer+=self.decoder.decode(chunk)
   while '\n\n' in self.buffer:
    frame,self.buffer=self.buffer.split('\n\n',1)
    if any(line.startswith('data:') for line in frame.splitlines()):
     self.events.append(frame);self.trace.finish(self.event,{'headers':self.event['response']['headers'],'body':{'sse_frames':self.events}},status=200)
   yield chunk
 async def aclose(self):await self.stream.aclose()

class App:
 async def setup(self,memory_path=None):
  from isolation import fixture_paths
  memory_path,self.tls,self.fixture_directory=fixture_paths(memory_path)
  self.trace_environment='isolated synthetic fixture' if memory_path else 'local demo with synthetic commerce'
  self.model=Parser(trace_provider=lambda: CURRENT.get().trace if CURRENT.get() else None);self.memory=Memory(memory_path or ROOT/'memory.sqlite');self.flows={};self.clients={};self.tickets={};self.events=[];self.identity=AgentIdentity(domain=f'atlas.localhost:{PORT}',name='Thread3 personal stylist',extensions=());self.policy=(PluginManifest(name='wardrobe-policy',version='1'),PolicyPlugin())
  from checkpoints import DurableSaver
  self.graph_saver=DurableSaver(Path(memory_path).with_name(Path(memory_path).stem+'-graph.sqlite'))
  tls=self.tls
  self.pending_trace_requests={}
  async def request_hook(r):
   from trace_page import body,protocol_event
   r.extensions['trace_started']=time.monotonic();flow=CURRENT.get()
   if flow:r.extensions['trace_log']=flow.trace
   if flow and str(r.url).startswith(ORIGIN+'/oauth/') and r.method=='POST':
    key=hashlib.sha256(str(r.url).encode()+b'\0'+r.content).hexdigest();self.pending_trace_requests[key]=flow;r.extensions['trace_context_key']=key
   reverse=r.url.host=='atlas.localhost' and r.url.path in ('/agent.json','/jwks.json')
   if flow:r.extensions['trace_event']=flow.trace.begin(kind='http',direction='FORME → Thread → FORME' if reverse else 'Thread server → FORME → Thread server',endpoint=str(r.url),request={'method':r.method,'headers':dict(r.headers),'body':body(r.content,r.headers.get('content-type',''))},transport='actual HTTPS Poppy/client exchange',layer='Poppy protocol' if protocol_event({'kind':'http','endpoint':str(r.url)}) else 'Application HTTP exchange')
  async def response_hook(r):
   from trace_page import body
   flow=CURRENT.get();event=r.request.extensions.get('trace_event')
   if flow and event is not None:
    if r.headers.get('content-type','').startswith('text/event-stream'):
     flow.trace.finish(event,{'headers':dict(r.headers),'body':{'events':[]}},status=r.status_code)
     r.stream=TracedEventStream(r.stream,flow.trace,event);return
    await r.aread();flow.trace.finish(event,{'headers':dict(r.headers),'body':body(r.content,r.headers.get('content-type',''))},status=r.status_code,duration_ms=round((time.monotonic()-r.request.extensions['trace_started'])*1000,1))
  class TraceClient(httpx.AsyncClient):
   async def send(client,request,**kwargs):
    try:return await super(TraceClient,client).send(request,**kwargs)
    except BaseException as exc:
     event=request.extensions.get('trace_event');trace=request.extensions.get('trace_log')
     if event is not None and trace is not None:trace.finish(event,status='failed; no response',error_type=type(exc).__name__)
     raise
    finally:
     key=request.extensions.get('trace_context_key')
     if key:self.pending_trace_requests.pop(key,None)
  self.http=TraceClient(event_hooks={'request':[request_hook],'response':[response_hook]},verify=ssl.create_default_context(cafile=str(tls/'ca.pem')),trust_env=False,timeout=15)
  from availability_protocol import AvailabilityPlugin,AvailabilityService
  availability_plugin=AvailabilityPlugin(self,Path(memory_path).with_name(Path(memory_path).stem+'-conversations.sqlite') if memory_path else ROOT/'forme-conversations.sqlite')
  self.shop=build_company(Config(name='FORME',domain='jacket.localhost',scopes=('orders:read','orders:write','preferences:read','preferences:write','availability:watch','account:read','availability:read'),write_scopes=('orders:write','preferences:write','availability:watch'),custom_scopes={'account:read':'Read your FORME account facts','availability:read':'Read your existing availability watches','availability:watch':'Create, read and cancel consented availability watches','preferences:read':'Read your saved FORME preferences','orders:read':'Read your orders','orders:write':'Place orders after your approval','preferences:write':'Save preferences you explicitly share with FORME'},direct=False,operations=False,web=True),http_client=self.http,address_resolver=local_addresses,plugins=[self.policy,(PluginManifest(name='forme-availability',version='1'),availability_plugin)])
  self.shop=AvailabilityService(config=self.shop.config,reactor=self.shop.reactor);self.shop.app=self
  self.company_context=CompanyContext(Path(memory_path).with_name(Path(memory_path).stem+'-company.sqlite') if memory_path else ROOT/'forme_context.sqlite')
  from thread_auth import ThreadAuth
  from demo_identity import DemoAccounts,CompanyLinks
  identity_root=Path(memory_path).parent if memory_path else ROOT
  identity_prefix=Path(memory_path).stem+'-' if memory_path else ''
  self.thread_accounts=DemoAccounts(identity_root/(identity_prefix+'thread-identities.sqlite'),'thread')
  self.forme_accounts=DemoAccounts(identity_root/(identity_prefix+'forme-identities.sqlite'),'forme')
  self.forme_accounts.db.execute('CREATE TABLE IF NOT EXISTS authorization_logins(id TEXT PRIMARY KEY,account TEXT NOT NULL,expires REAL NOT NULL)');self.forme_accounts.db.commit()
  self.company_links=CompanyLinks(self.thread_accounts.db)
  self.thread_auth=ThreadAuth(self);self.watch_memory=WatchMemory(self.thread_accounts.db)
  self.protocol=company_app(self.shop);self.explainer=Explainer(self.model);self.store=Store(self.shop,self.memory,self.company_context,self.explainer,self.forme_accounts)
  from availability_webhook import AvailabilityWebhook
  self.webhook_enabled=True;self.webhook=AvailabilityWebhook(self,AGENT,ORIGIN);self.webhook.start()
 async def close(self):
  if hasattr(self,'webhook'):await self.webhook.close()
  flows=set(self.flows.values())
  for clients in self.clients.values():flows.update(clients.values())
  for flow in flows:
   await flow.stop_watch_streams()
   await flow.browser.close()
  for client in getattr(self,'graph_http_clients',[]):await client.aclose()
  await self.http.aclose()
  self.graph_saver.close()
  self.fixture_directory.cleanup()
 async def __call__(self,scope,receive,send):
  if scope['type']!='http':return
  r=Request(scope,receive);host=r.url.hostname;path=r.url.path;request_started=time.monotonic()
  flow=None
  if host=='jacket.localhost':
   if path=='/poppy/browser-session':
    raw=await r.body()
    try:
     assertion=parse_qs(raw.decode()).get('assertion',[''])[0];sid=jwt.decode(assertion,options={'verify_signature':False}).get('session_id');flow=self.flows.get(sid)
    except Exception:pass
    async def replay():return {'type':'http.request','body':raw,'more_body':False}
    receive=replay
   elif path=='/signin':flow=(self.tickets.get(r.query_params.get('ticket','')) or {}).get('flow')
   elif path.startswith('/shop'):
    session=await self.store.session(r);flow=self.flows.get(session.session_id) if session else None
  from trace_page import body
  exchange=None;chunks=[];response_meta={}
  if flow and host=='jacket.localhost' and not path.startswith('/assets'):
   CURRENT.set(flow)
   raw=await r.body()
   async def replay_body():return {'type':'http.request','body':raw,'more_body':False}
   receive=replay_body
   exchange=flow.trace.begin(kind='activation_capture' if path=='/poppy/browser-session' else 'http',direction='Controlled browser/sign-in popup → FORME → browser',endpoint=str(r.url),request={'method':r.method,'headers':dict(r.headers),'body':body(raw,r.headers.get('content-type',''))},method=r.method,path=path,transport='actual website handler execution; network transport not independently established by ASGI',layer='Poppy protocol' if path.startswith('/poppy') else 'Website HTTP exchange')
  async def observe(m):
   if m['type']=='http.response.start':
    if exchange is not None and path=='/poppy/browser-session':m={**m,'headers':[*m.get('headers',[]),(b'x-atlas-capture-id',exchange['correlation'].encode())]}
    h={k.lower():v for k,v in m.get('headers',[])};self.events.append(dict(kind='http',method=r.method,path=path,status=m['status'],cookie_issued=b'set-cookie' in h,cookie_present='cookie' in r.headers,origin=host));self.events=self.events[-300:]
    if exchange is not None:
     response_meta['status']=m['status'];response_meta['headers']=dict((k.decode(),v.decode()) for k,v in m.get('headers',[]))
     exchange['cookie_issued']=b'set-cookie' in h;exchange['cookie_present']='cookie' in r.headers
     if path=='/poppy/browser-session':exchange['assertion_validation']='accepted by company validator' if m['status']==303 else 'rejected by company validator'
   if m['type']=='http.response.body' and exchange is not None:
    chunks.append(m.get('body',b''))
    if not m.get('more_body',False):
     headers=response_meta.get('headers',{});code=response_meta.get('status')
     flow.trace.finish(exchange,{'headers':headers,'body':body(b''.join(chunks),headers.get('content-type',''))},status=code,duration_ms=round((time.monotonic()-request_started)*1000,1))
   await send(m)
  try:
   if path.startswith('/assets/photos/'):
    name=path.rsplit('/',1)[-1]
    allowed={p['image_url'] for p in self.store.products if '/assets/photos/' in p['image_url']}|{'/assets/photos/demo-red-shoes.png','/assets/photos/demo-red-tie.png'}
    response=FileResponse(ROOT/'assets/photos'/name,headers={'Cache-Control':'public, max-age=86400','X-Content-Type-Options':'nosniff'}) if path in allowed else HTMLResponse('',404)
   elif path.startswith('/assets/products/'):

    product=self.store.by_id.get(path.rsplit('/',1)[-1].removesuffix('.svg'))
    if product and path==product['image_url'] and 'design' in product:
     response=Response(product_svg(product['id'],product['category'],product['kind'],product['color'],product['material'],product['design'],product['gender']),media_type='image/svg+xml',headers={'Cache-Control':'public, max-age=86400','X-Content-Type-Options':'nosniff'})
    else:response=HTMLResponse('',404)
   elif path.startswith('/assets/'):

    name=path.split('/')[-1]
    response=HTMLResponse(CSS,media_type='text/css') if name=='store.css' else FileResponse(ROOT/'assets'/name) if name in ('shirt.jpg','tee.jpg','sneaker.jpg','shoes.jpg','trousers.jpg','jacket.jpg','logo.svg','store.js') else HTMLResponse('',404)
   elif host=='jacket.localhost':
    if path.startswith('/shop'):response=await self.store.handle(r)
    elif path=='/storefront.json':response=JSONResponse(dict(url=ORIGIN+'/shop'))
    elif path=='/signin':response=await self.signin(r)
    else:
     # Correlate only an exact in-flight request made by this app's HTTP client.
     # This is trace ownership, never identity or authorization evidence.
     raw=await r.body()
     key=hashlib.sha256(str(r.url).encode()+b'\0'+raw).hexdigest()
     owner=self.pending_trace_requests.get(key) if r.method=='POST' and path.startswith('/oauth/') else None
     async def protocol_body():return {'type':'http.request','body':raw,'more_body':False}
     token=CURRENT.set(owner) if owner else None
     try:
      if r.method=='GET' and path.startswith('/poppy/conversations/') and path.endswith('/events') and 'text/event-stream' in r.headers.get('accept',''):
       async def disconnected():
        while (await r.receive())['type']!='http.disconnect':pass
       serving=asyncio.create_task(self.protocol(scope,protocol_body,observe));watching=asyncio.create_task(disconnected())
       try:
        done,pending=await asyncio.wait((serving,watching),return_when=asyncio.FIRST_COMPLETED)
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)
        for task in done:await task
        return
       finally:
        for task in (serving,watching):
         if not task.done():task.cancel()
        await asyncio.gather(serving,watching,return_exceptions=True)
      return await self.protocol(scope,protocol_body,observe)
     finally:
      if token is not None:CURRENT.reset(token)
   elif host=='atlas.localhost':
    if path in ('/agent.json','/jwks.json'):return await self.identity.website()(scope,receive,observe)
    if path=='/extensions/forme-availability':response=await self.webhook.receive(r)
    else:response=await self.thread_auth.handle(r)
   else:response=HTMLResponse('Unknown host',421)
  except Exception as exc:
   print('Request failed:',type(exc).__name__,flush=True)
   response=JSONResponse(dict(error=str(exc) if isinstance(exc,ValueError) else 'This step could not finish. Your order was not retried.'),400)
  await response(scope,receive,observe)
 async def signin(self,r):
  from device_verification import verify
  return await verify(self,r,ORIGIN,AUTHORIZER_COOKIE)
async def main():
 app=App();await app.setup()
 try:await uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=PORT,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='warning')).serve()
 finally:await app.close()
if __name__=='__main__':asyncio.run(main())
