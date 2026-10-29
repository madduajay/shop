"""FORME availability data carried by standard Poppy messages and SSE (§7).
Only conversation/idempotency records persist here; credentials remain ephemeral.
"""
import asyncio,contextvars,json,sqlite3,secrets,time
from datetime import datetime,timezone
from dataclasses import replace
from contextlib import contextmanager
from urllib.parse import urlsplit
from personal_agent_protocol.company import CompanyService,CompanyResponse,Reply,MemoryCompanyStore,StoredRecord,COMPANY_AGENTS,COMPANY_STORES
from personal_agent_protocol.company.service import _RefusedError
from personal_agent_protocol.company.store import CONVERSATION,MESSAGE_ID,StoredConversation

class ConversationStore:
 def __init__(self,path):
  self.memory=MemoryCompanyStore();self.db=sqlite3.connect(path);self.transaction_active=False;self.request_lock=asyncio.Lock()
  self.db.execute('CREATE TABLE IF NOT EXISTS records(kind TEXT,key TEXT,value TEXT,version TEXT,expires TEXT,PRIMARY KEY(kind,key))');self.db.commit()
 @contextmanager
 def write(self):
  if self.transaction_active:yield
  else:
   with self.db:yield
 @contextmanager
 def transaction(self):
  self.db.execute("BEGIN IMMEDIATE");self.transaction_active=True
  try:
   yield
   self.db.commit()
  except BaseException:
   self.db.rollback();raise
  finally:self.transaction_active=False
 def keys(self,k):
  if not self.durable(k):return self.memory.keys(k)
  return [r[0] for r in self.db.execute('SELECT key FROM records WHERE kind=?',(k,))]
 def durable(self,k):return k in (CONVERSATION,MESSAGE_ID)
 async def get(self,k,key):
  if not self.durable(k):return await self.memory.get(k,key)
  row=self.db.execute('SELECT value,version,expires FROM records WHERE kind=? AND key=?',(k,key)).fetchone()
  if not row:return None
  expiry=datetime.fromisoformat(row[2]) if row[2] else None
  if expiry and datetime.now(timezone.utc)>=expiry:await self.delete(k,key);return None
  return StoredRecord(json.loads(row[0]),row[1],expiry)
 async def put(self,k,key,value,*,expires_at=None):
  if not self.durable(k):return await self.memory.put(k,key,value,expires_at=expires_at)
  with self.write():self.db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?)',(k,key,json.dumps(value),secrets.token_hex(16),expires_at.isoformat() if expires_at else None))
 async def create(self,k,key,value,*,expires_at=None):
  if not self.durable(k):return await self.memory.create(k,key,value,expires_at=expires_at)
  await self.get(k,key)
  with self.write():return self.db.execute('INSERT OR IGNORE INTO records VALUES(?,?,?,?,?)',(k,key,json.dumps(value),secrets.token_hex(16),expires_at.isoformat() if expires_at else None)).rowcount==1
 async def replace(self,k,key,version,value,*,expires_at=None):
  if not self.durable(k):return await self.memory.replace(k,key,version,value,expires_at=expires_at)
  if not await self.get(k,key):return False
  with self.write():return self.db.execute('UPDATE records SET value=?,version=?,expires=? WHERE kind=? AND key=? AND version=?',(json.dumps(value),secrets.token_hex(16),expires_at.isoformat() if expires_at else None,k,key,version)).rowcount==1
 async def delete(self,k,key):
  if not self.durable(k):return await self.memory.delete(k,key)
  with self.write():self.db.execute('DELETE FROM records WHERE kind=? AND key=?',(k,key))
 async def take(self,k,key):
  if not self.durable(k):return await self.memory.take(k,key)
  record=await self.get(k,key)
  if record:await self.delete(k,key);return record.value
  return None

class AvailabilityAgent:
 def __init__(self,app):self.app=app
 async def respond(self,turn):
  if not turn.account_id:return [Reply(text='Please sign in to FORME to request an availability watch.'),Reply(authorization=('sign_in_required','availability:watch'))]
  if 'availability:watch' not in turn.scopes:return [Reply(text='Please authorize availability notifications to continue.'),Reply(authorization=('insufficient_scope','availability:watch'))]
  data=turn.data or {};action=data.get('forme_availability',{});consent=action.get('consent','')
  if not action:
   registration=data.get('thread_webhook')
   if registration is not None:
    conv=await self.app.shop._conversation(turn.conversation_id)
    self.app.webhook.register(conv,registration)
    return [Reply(text='Custom Thread/FORMe webhook registered. Send the consented item requirements to activate the watch. This delivery extension is not standard Poppy or A2A.')]
   return [Reply(text='Yes. Send the selected item requirements and the user’s notification consent to request a watch. No watch has been created yet.')]
  if not isinstance(consent,str) or len(consent)!=32 or any(c not in '0123456789abcdef' for c in consent):return [Reply(text='A valid consent identifier is required.')]
  conv=await self.app.shop._conversation(turn.conversation_id)
  owner=json.dumps([*conv.owner,turn.account_id]);availability=self.app.store.availability
  if action.get('action')=='cancel':
   availability.cancel(owner,consent);return [Reply(text='Availability watch cancelled.',data={'forme_availability':{'action':'cancelled','consent':consent}})]
  if action.get('action')!='subscribe':return [Reply(text='This conversation supports consented availability watches.')]
  existing=next((w for w in availability.rows(owner) if w['consent']==consent),None)
  candidate=availability.candidate(action.get('filters',{}))
  if not existing and not candidate:return [Reply(text='No supported restock matches those requirements.')]
  try:w=existing or availability.subscribe(owner,consent,candidate)
  except ValueError as exc:return [Reply(text=str(exc))]
  w['conversation_id']=turn.conversation_id
  registration=self.app.webhook.registration(turn.conversation_id,consent)
  if registration:w['delivery']=registration['extension']
  availability.save(w)
  return [Reply(text='FORME will notify you when this item is available.',data={'forme_availability':{'action':'subscribed','watch':{k:v for k,v in w.items() if k!='owner'}}})]

class AvailabilityPlugin:
 def __init__(self,app,path):self.agent=AvailabilityAgent(app);self.store=ConversationStore(path)
 def provide_contributions(self,c):
  c.contribute(COMPANY_AGENTS,self.agent,contribution_id='forme-availability-agent',order=0)
  c.contribute(COMPANY_STORES,self.store,contribution_id='forme-conversations',order=0)

class AvailabilityService(CompanyService):
 async def handle(self,request):
  store=self.store
  if urlsplit(request.url).path.startswith('/poppy/conversations') and isinstance(store,ConversationStore):
   # One local dispatcher: receipts, history and exact responses commit together.
   # Availability effects in their separate database are consent-idempotent, so a
   # retry after rollback recovers an effect committed just before a crash.
   async with store.request_lock:
    with store.transaction():return await super().handle(request)
  return await super().handle(request)
 caller_session=contextvars.ContextVar('availability_caller',default=None)
 async def _device(self,request):
  response=await super()._device(request)
  # A company chooses its verification URL; return the same protected page Thread opens.
  body=dict(response.body);body['verification_uri']=self.config.base+'/signin'
  body['verification_uri_complete']=body['verification_uri']+'?ticket='+body['user_code']
  return replace(response,body=body)

 async def _caller(self,request):
  result=await super()._caller(request)
  self.caller_session.set((result[1],request.headers.get('authorization','').partition(' ')[2]));return result
 async def _owned(self,conversation_id,session):
  conversation=await super()._owned(conversation_id,session)
  if conversation.account_id and 'availability:watch' not in session.scopes:raise _RefusedError(403,'insufficient_scope',scope='availability:watch')
  if conversation.account_id and conversation.status!='closed':
   await self.publish_ready(conversation)
   conversation=await self._conversation(conversation_id)
  return conversation
 async def publish_ready(self,conversation):
  availability=self.app.store.availability;availability.tick()
  owner=json.dumps([*conversation.owner,conversation.account_id])
  for w in availability.rows(owner):
   if w.get('conversation_id')!=conversation.conversation_id or w['status']!='ready' or w.get('delivery')=='thread-forme-webhook-v1':continue
   event=self._event(type='message',message={'id':'restock_'+w['event_id'],'sender':'agent','role':'company','text':w['candidate']['name']+' is now available at FORME.','data':{'forme_availability':{'action':'available','watch':{k:v for k,v in w.items() if k!='owner'}}}})
   def append(current):
    if current.status=='closed' or any(e.payload.get('message',{}).get('id')=='restock_'+w['event_id'] for e in current.events):return current
    return replace(current,events=(*current.events,event))
   await self._change(CONVERSATION,conversation.conversation_id,StoredConversation.from_json,append)
 def _stream(self,conversation,last_event_id):
  self._after(conversation,last_event_id) # validate cursor before starting HTTP response
  session,credential=self.caller_session.get()
  async def frames():
   cursor=last_event_id;started=time.monotonic()
   while time.monotonic()-started<30:
    live=await self._token_session(credential)
    if not live or self._now()>=live.expires_at or (conversation.account_id and (live.account_id!=conversation.account_id or 'availability:watch' not in live.scopes)):return
    current=await self._conversation(conversation.conversation_id)
    if current.status!='closed':await self.publish_ready(current)
    current=await self._conversation(conversation.conversation_id)
    for event in self._after(current,cursor):
     yield f'id: {event.id}\ndata: {json.dumps(event.payload)}\n\n'.encode();cursor=event.id
    if current.status=='closed':return
    watches=[w for w in self.app.store.availability.rows(json.dumps([*current.owner,current.account_id])) if w.get('conversation_id')==current.conversation_id]
    if watches and all(w['status']!='active' for w in watches):return
    yield b': heartbeat\n\n'
    await asyncio.sleep(1)
  return CompanyResponse(200,headers={'Content-Type':'text/event-stream','Cache-Control':'no-store'},stream=frames())
