"""Thread's authenticated Poppy availability conversation and event receiver."""
import asyncio,time
from personal_agent_protocol.conversations import ConversationClient
from personal_agent_protocol.transport import DpopHttpClient
from personal_agent_protocol.models import Message,ConversationEvent
class AvailabilityClient:
 def conversation_client(self):return ConversationClient(transport=DpopHttpClient(reactor=self.reactor,http_client=self.app.http))
 async def watch_message(self,w,action='subscribe'):
  endpoint=self.conversation_endpoint
  message=Message(id=('subscribe_' if action=='subscribe' else 'cancel_')+w['consent'],sender='agent',text='Notify me when this item is available.' if action=='subscribe' else 'Cancel my availability watch.',data={'forme_availability':{'action':action,'consent':w['consent'],'filters':w['filters']}})
  client=self.conversation_client()
  # Preserve the original endpoint for pre-migration embedded-message retries.
  legacy=bool(w.get('conversation_id') and not w.get('separate_watch_message'))
  if not w.get('conversation_id'):
   w['separate_watch_message']=True;self.app.watch_memory.save(self.customer,w)
   from availability_webhook import EXT
   if getattr(self.app,'webhook_enabled',True):w['delivery']=EXT;self.app.watch_memory.save(self.customer,w)
   registration={'thread_webhook':{'extension':EXT,'url':self.app.webhook.url,'consent':w['consent']}} if w.get('delivery')==EXT else None
   introduction=Message(id='availability_intro_'+w['consent'],sender='agent',text='Can you help arrange an availability notification for an item the user has selected?',data=registration)
   opened=await client.start(endpoint,introduction,token=self.token,**self.who,wait=0)
   w['conversation_id']=opened.conversation_id;self.app.watch_memory.save(self.customer,w)
  if legacy and action=='subscribe':
   result=await client.start(endpoint,message,token=self.token,**self.who,wait=0)
  else:
   result=await client.send(endpoint,w['conversation_id'],message,token=self.token,**self.who,wait=0)
  w['conversation_id']=result.conversation_id
  self.app.watch_memory.save(self.customer,w)
  for event in getattr(result,'events',[]):
   if event.message and event.message.role=='company':
    data=(event.message.data or {}).get('forme_availability',{})
    if data.get('action')=='subscribed':return data['watch']
    if data.get('action')=='cancelled':return {'cancelled':True}
  return None
 async def stop_watch_streams(self):
  tasks=list(getattr(self,'watch_streams',{}).values())
  for task in tasks:task.cancel()
  if tasks:await asyncio.gather(*tasks,return_exceptions=True)
  self.watch_streams={}
 def ensure_watch_stream(self,w):
  if w.get('delivery')=='thread-forme-webhook-v1':return
  if not hasattr(self,'watch_streams'):self.watch_streams={}
  old=self.watch_streams.get(w['consent'])
  if old and not old.done():return
  if w.get('retry_after',0)>time.time():return
  self.watch_streams[w['consent']]=asyncio.create_task(self.receive_watch(w['consent']))
 async def watch_events(self,w):
  client=self.conversation_client()
  args=dict(token=self.token,**self.who)
  try:
   async for event in client.stream(self.conversation_endpoint,w['conversation_id'],last_event_id=w.get('cursor'),max_reconnects=5,**args):yield event
  except Exception as exc:
   if getattr(exc,'code','')!='sse_unsupported':raise
   async for event in client.events(self.conversation_endpoint,w['conversation_id'],cursor=w.get('cursor'),**args):yield event
 async def receive_watch(self,consent):
  w=next(x for x in self.watch_rows() if x['consent']==consent)
  try:
   async for event in self.watch_events(w):
    if not isinstance(event,ConversationEvent):continue # Never act on text deltas.
    w=next(x for x in self.watch_rows() if x['consent']==consent)
    if w['status']!='active' or w['expires_at']<=time.time():return
    if event.type=='message' and event.message and event.message.role=='company':
     data=(event.message.data or {}).get('forme_availability',{});remote=data.get('watch',{})
     if data.get('action')=='available' and remote.get('consent')==consent and remote.get('id')==w.get('watch_id') and remote.get('expires_at',0)>time.time():
      c=remote['candidate'];card=dict(type='availability',event_id=remote['event_id'],watch_id=remote['id'],name=c['name'],product=c['product'],size=c['size'],color=c['color'],price_cents=c['price_cents'],image=self.browser.origin+c['image'],available_at=remote['available_at'],expires_at=remote['expires_at'])
      if self.app.watch_memory.receive(self.customer,card):
       self.watch_deliveries=getattr(self,'watch_deliveries',[])+[card]
      w['status']='delivered'
    # Persist only after handling; replay after a crash is harmless via inbox unique key.
    w['cursor']=event.id;self.app.watch_memory.save(self.customer,w)
    if w['status']=='delivered':return
  except asyncio.CancelledError:raise
  except Exception as exc:
   w=next(x for x in self.watch_rows() if x['consent']==consent)
   w['retry_after']=time.time()+max(15,getattr(exc,'retry_after',0) or 0);w['delivery_error']=getattr(exc,'code',type(exc).__name__)
   if w['delivery_error']=='cursor_expired':
    w.pop('cursor',None);w['retry_after']=time.time();self.watch_recovery_notice='Some earlier notification history is no longer available. Reconnecting from the retained history.'
   if w['delivery_error'] in ('invalid_token','sign_in_required','insufficient_scope'):w['reconnect_required']=True;self.app.watch_memory.save(self.customer,w)
   self.app.watch_memory.save(self.customer,w)
   self.trace.append({'kind':'availability stream recovery','status':'paused; retry after backoff','error_type':type(exc).__name__})
