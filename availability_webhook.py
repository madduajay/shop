"""Custom Thread/FORMe webhook v1. Not part of Poppy or A2A.
Pinned local destination and existing TLS signing key; no new credentials.
"""
import asyncio,contextvars,hashlib,json,secrets,time,jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.responses import JSONResponse
EXT='thread-forme-webhook-v1'
PATH='/extensions/forme-availability'
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
class AvailabilityWebhook:
 def __init__(self,app,agent,company):
  self.app=app;self.agent=agent;self.company=company;self.url=agent+PATH;self.task=None;self.lock=asyncio.Lock()
  self.key=serialization.load_pem_private_key((app.tls/'key.pem').read_bytes(),password=None)
  self.public=x509.load_pem_x509_certificate((app.tls/'cert.pem').read_bytes()).public_key()
  self.algorithm='RS256' if isinstance(self.key,rsa.RSAPrivateKey) else 'ES256'
  self.db=app.store.availability.db
  self.db.execute('CREATE TABLE IF NOT EXISTS webhook_registrations(conversation TEXT PRIMARY KEY,data TEXT NOT NULL)');self.db.commit()
  db=app.watch_memory.db
  db.executescript('''CREATE TABLE IF NOT EXISTS webhook_receipts(event TEXT PRIMARY KEY,digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS webhook_proofs(jti TEXT PRIMARY KEY,expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS webhook_traces(customer INTEGER NOT NULL,data TEXT NOT NULL);''');db.commit()
 def register(self,conv,data):
  if not isinstance(data,dict) or set(data)!={'extension','url','consent'} or data['extension']!=EXT or data['url']!=self.url or conv.owner[0]!=self.app.identity.client_id:raise ValueError('Invalid custom callback destination or owner')
  row=self.app.watch_memory.db.execute('SELECT customer,data FROM thread_watches WHERE consent=?',(data['consent'],)).fetchone()
  if not row:raise ValueError('Unknown callback consent')
  w=json.loads(row[1]);principal=self.app.thread_accounts.by_profile(row[0])
  if principal['pairwise']!=conv.owner[1] or w['status'] not in ('consented','active') or w['expires_at']<=time.time():raise ValueError('Callback ownership or consent mismatch')
  registration=dict(data,owner=list(conv.owner))
  old=self.db.execute('SELECT data FROM webhook_registrations WHERE conversation=?',(conv.conversation_id,)).fetchone()
  if old and json.loads(old[0])!=registration:raise ValueError('Callback registration conflict')
  with self.db:self.db.execute('INSERT OR IGNORE INTO webhook_registrations VALUES(?,?)',(conv.conversation_id,json.dumps(registration)))
 def registration(self,conversation,consent):
  row=self.db.execute('SELECT data FROM webhook_registrations WHERE conversation=?',(conversation,)).fetchone()
  if not row:return None
  r=json.loads(row[0])
  if r['consent']!=consent or r['url']!=self.url:raise ValueError('Callback binding mismatch')
  return r
 def start(self):
  if not self.task or self.task.done():self.task=asyncio.create_task(self.run(),context=contextvars.Context())
 async def run(self):
  while not self.app.http.is_closed:
   try:await self.tick()
   except asyncio.CancelledError:raise
   except Exception:pass # Retry from durable rows; never lose an event on a worker failure.
   await asyncio.sleep(.5)
 async def close(self):
  if self.task:self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
 def local(self,consent):
  row=self.app.watch_memory.db.execute('SELECT customer,data FROM thread_watches WHERE consent=?',(consent,)).fetchone()
  return (row[0],json.loads(row[1])) if row else (None,None)
 def allowed(self,remote,customer,w):
  if not w or w.get('delivery')!=EXT or w['status'] not in ('active','delivered') or w['expires_at']<=time.time():return False
  principal=self.app.thread_accounts.by_profile(customer);owner=json.loads(remote['owner'])
  return owner==[self.app.identity.client_id,principal['pairwise'],f'forme_customer_{customer:03}'] and self.app.company_links.authorized(principal['id'],self.company,owner[2],'availability:watch') and w.get('watch_id')==remote['id'] and w.get('conversation_id')==remote.get('conversation_id')
 def event(self,w):
  c=w['candidate'];owner=json.loads(w['owner'])
  return {'extension':EXT,'event_id':w['event_id'],'consent':w['consent'],'watch_id':w['id'],'conversation_id':w['conversation_id'],'subject':owner[1],'account':owner[2],'expires_at':w['expires_at'],'available_at':w['available_at'],'candidate':{k:c[k] for k in ('product','name','size','color','price_cents','image')}}
 def assertion(self,raw,**overrides):
  now=int(time.time());claims=dict(iss=self.company,aud=self.url,iat=now,exp=now+60,jti=secrets.token_hex(16),method='POST',body_sha256=hashlib.sha256(raw).hexdigest());claims.update(overrides)
  return jwt.encode(claims,self.key,algorithm=self.algorithm,headers={'typ':EXT})
 async def tick(self):
  async with self.lock:
   self.app.store.availability.tick()
   for (value,) in self.db.execute('SELECT data FROM watches').fetchall():
    w=json.loads(value)
    if w.get('delivery')!=EXT or w['status']!='ready' or w.get('webhook_delivered') or w.get('next_attempt',0)>time.time():continue
    customer,local=self.local(w['consent'])
    if not self.allowed(w,customer,local):continue
    raw=canonical(self.event(w));proof=self.assertion(raw)
    # Destination is a constant, never a URL taken from an event or model output.
    from trace_page import TraceLog
    trace=TraceLog();entry=trace.begin(kind='http',direction='FORME → Thread → FORME',endpoint=self.url,request={'method':'POST','headers':{'Authorization':'Bearer '+proof,'Content-Type':'application/json'},'body':json.loads(raw)},transport='actual HTTPS custom webhook delivery',layer='Custom extension (not standard Poppy or A2A)')
    try:
     r=await self.app.http.post(self.url,content=raw,headers={'Authorization':'Bearer '+proof,'Content-Type':'application/json'},follow_redirects=False,timeout=5)
     from trace_page import body
     trace.finish(entry,{'headers':dict(r.headers),'body':body(r.content,r.headers.get('content-type',''))},status=r.status_code)
     ok=r.status_code==200
    except Exception as exc:trace.finish(entry,status='failed; no response',error_type=type(exc).__name__);ok=False
    # Re-read to preserve a cancellation that occurred during the HTTP await.
    latest=json.loads(self.db.execute('SELECT data FROM watches WHERE id=?',(w['id'],)).fetchone()[0])
    latest['webhook_attempts']=latest.get('webhook_attempts',0)+1
    if ok:latest['webhook_delivered']=True
    else:latest['next_attempt']=time.time()+min(300,2**min(latest['webhook_attempts'],8))
    self.app.store.availability.save(latest)
    with self.app.watch_memory.db:self.app.watch_memory.db.execute('INSERT INTO webhook_traces VALUES(?,?)',(customer,json.dumps(entry)))
 async def receive(self,r):
  if r.method!='POST':return JSONResponse({'error':'method_not_allowed'},405)
  raw=await r.body()
  if len(raw)>16000:return JSONResponse({'error':'payload_too_large'},413)
  try:
   proof=r.headers.get('authorization','')
   if not proof.startswith('Bearer '):raise ValueError()
   token=proof[7:];header=jwt.get_unverified_header(token)
   if header.get('typ')!=EXT:raise ValueError()
   claims=jwt.decode(token,self.public,algorithms=[self.algorithm],audience=self.url,issuer=self.company,options={'require':['iss','aud','iat','exp','jti','method','body_sha256']})
   now=int(time.time())
   if type(claims['iat']) is not int or type(claims['exp']) is not int or not 0<claims['exp']-claims['iat']<=60 or claims['iat']>now or claims['method']!='POST' or claims['body_sha256']!=hashlib.sha256(raw).hexdigest() or not isinstance(claims['jti'],str) or len(claims['jti'])!=32:raise ValueError()
  except Exception:return JSONResponse({'error':'invalid_webhook_authentication'},401)
  try:
   data=json.loads(raw);customer,w=self.local(data['consent'])
   remote_row=self.db.execute('SELECT data FROM watches WHERE id=?',(data['watch_id'],)).fetchone()
   remote=json.loads(remote_row[0]) if remote_row else None
   if not remote or remote['status']!='ready' or not self.allowed(remote,customer,w) or data!=self.event(remote) or data['expires_at']<=time.time():raise ValueError()
   c=data['candidate']
   if not c['image'].startswith('/assets/photos/') or '..' in c['image'] or '?' in c['image']:raise ValueError()
   card=dict(type='availability',event_id=data['event_id'],watch_id=data['watch_id'],name=c['name'],product=c['product'],size=c['size'],color=c['color'],price_cents=c['price_cents'],image=self.company+c['image'],available_at=data['available_at'],expires_at=data['expires_at'])
  except Exception:return JSONResponse({'error':'invalid_or_cancelled_webhook_binding'},403)
  db=self.app.watch_memory.db;digest=hashlib.sha256(raw).hexdigest()
  with db:
   db.execute('DELETE FROM webhook_proofs WHERE expires<?',(now,))
   if not db.execute('INSERT OR IGNORE INTO webhook_proofs VALUES(?,?)',(claims['jti'],claims['exp'])).rowcount:return JSONResponse({'error':'replayed_webhook_proof'},409)
   previous=db.execute('SELECT digest FROM webhook_receipts WHERE event=?',(data['event_id'],)).fetchone()
   if previous:
    if previous[0]!=digest:return JSONResponse({'error':'event_conflict'},409)
    return JSONResponse({'accepted':True,'duplicate':True})
   db.execute('INSERT INTO webhook_receipts VALUES(?,?)',(data['event_id'],digest))
   db.execute('INSERT OR IGNORE INTO thread_availability_inbox VALUES(?,?,?)',(customer,data['event_id'],json.dumps(card)))
   w['status']='delivered';db.execute('UPDATE thread_watches SET data=? WHERE consent=?',(json.dumps(w),w['consent']))
  for flow in set(self.app.flows.values()):
   if flow.customer==customer:flow.watch_deliveries=getattr(flow,'watch_deliveries',[])+[card]
  return JSONResponse({'accepted':True,'duplicate':False})
