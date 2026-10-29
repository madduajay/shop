"""Thread-owned consent state and delivery inbox. Company state is read via browser."""
import json,secrets,time,re
class WatchMemory:
 def __init__(self,db):
  self.db=db;db.executescript('''CREATE TABLE IF NOT EXISTS thread_watches(customer INTEGER NOT NULL,consent TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS thread_availability_inbox(customer INTEGER NOT NULL,event TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(customer,event));
CREATE TABLE IF NOT EXISTS thread_notification_dismissals(customer INTEGER NOT NULL,event TEXT NOT NULL,dismissed_at REAL NOT NULL,PRIMARY KEY(customer,event));''');db.commit()
 def rows(self,customer):return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM thread_watches WHERE customer=? ORDER BY rowid',(customer,))]
 def save(self,c,w):self.db.execute('INSERT INTO thread_watches VALUES(?,?,?) ON CONFLICT(consent) DO UPDATE SET data=excluded.data',(c,w['consent'],json.dumps(w)));self.db.commit()
 def inbox(self,c):return [v for r in self.db.execute('SELECT data FROM thread_availability_inbox WHERE customer=? ORDER BY rowid',(c,)) if (v:=json.loads(r[0])).get('expires_at',0)>time.time()]
 def receive(self,c,card):
  with self.db:return self.db.execute('INSERT OR IGNORE INTO thread_availability_inbox VALUES(?,?,?)',(c,card['event_id'],json.dumps(card))).rowcount==1
 def dismissed(self,c):return [r[0] for r in self.db.execute('SELECT event FROM thread_notification_dismissals WHERE customer=?',(c,))]
 def dismiss(self,c,event):
  with self.db:
   if not self.db.execute('SELECT 1 FROM thread_availability_inbox WHERE customer=? AND event=?',(c,event)).fetchone():return False
   self.db.execute('INSERT OR IGNORE INTO thread_notification_dismissals VALUES(?,?,?)',(c,event,time.time()))
  return True
def availability_message(w,active=False):
 kind=w['filters'].get('demo_trigger')
 item,verb,pronoun=('Red shoes','are','they’re') if kind=='shoes' else ('Red tie','is','it’s') if kind=='tie' else (w['candidate']['name'],'is','it’s')
 notification=f'FORME will notify you when {pronoun} available.' if active else f'Would you like FORME to notify you when {pronoun} available?'
 return f'{item} {verb} not available. {notification}'

from availability_client import AvailabilityClient
class WatchFlow(AvailabilityClient):
 def watch_boundary(self,w):
  self.pending_watch_consent=w['consent']
  self.watch_transition={'consent':w['consent'],'phase':{'offered':'waiting_user','consented':'waiting_auth','active':'completed'}.get(w['status'],'completed')}
 async def resolve_watch_reply(self,text):
  q=' '.join(text.lower().strip().rstrip('.!').split())
  yes=q in ('yes','yes please','yes, please','yes notify me','yes, notify me','notify me','please notify me','yes please notify me','yes, please notify me','yes do that','yes, do that','please let me know','yes please let me know','let me know when available')
  no=q in ('no','no thanks','no, thanks','no thank you','decline','do not notify me',"don't notify me",'don’t notify me')
  if not (yes or no):return None
  consent=getattr(self,'pending_watch_consent',None)
  w=next((w for w in self.watch_rows() if w['consent']==consent),None)
  if not w:return ('Please tell me which item you want an availability notification for.' if yes and 'notify' in q else 'What would you like me to do? Please name the item or action.' if yes else 'Okay.'),[]
  if no:
   if w['status']=='active':return await self.watch_command('cancel watch',consent=consent)
   w['status']='cancelled';self.app.watch_memory.save(self.customer,w);self.pending_watch_consent=None
   if self.pending_read=='watch':
    for key,t in list(self.app.tickets.items()):
     if t['flow'] is self:await self.cancel_device_ticket(key)
    self.started=None;self.signurl=None;self.pending_read=None
   return 'Okay, I won’t notify you about '+w['candidate']['name']+'.',[]
  if w['expires_at']<=time.time():return 'That notification offer expired. Please search again.',[]
  if w['status']=='consented' and self.signurl:return 'Authorize FORME to activate the notification for '+w['candidate']['name']+'.',[]
  return await self.watch_command('notify me',consent=consent)

 def watch_rows(self):return self.app.watch_memory.rows(self.customer) if hasattr(self.app,'watch_memory') else []
 async def offer_watch(self,filters):
  for old in self.watch_rows():
   if old['status'] in ('consented','active') and old['expires_at']>time.time() and old['filters']==filters:
    self.watch_boundary(old)
    return (availability_message(old,True) if old['status']=='active' else availability_message(old) if old['status']=='offered' else 'Authorize FORME to receive availability notifications.'),[]
  snap=await self.browser.call('availability_offer',filters=filters) or {}
  candidate=(snap.get('availability') or {}).get('candidate')
  if not candidate:return 'No in-stock items match those filters. I can’t promise a matching restock within the supported catalog. Try another size, color, or budget.',[]
  reusable=next((old for old in self.watch_rows() if old['status']=='offered' and old['filters']==filters),None)
  w={'consent':reusable['consent'] if reusable else secrets.token_hex(16),'status':'offered','candidate':candidate,'filters':filters,'expires_at':time.time()+600,'offer':snap['availability']['offer']}
  for old in self.watch_rows():
   if old['status']=='offered':old['status']='cancelled';self.app.watch_memory.save(self.customer,old)
  self.app.watch_memory.save(self.customer,w)
  self.watch_boundary(w)
  return availability_message(w),[]
 async def watch_command(self,text,consent=None):
  q=' '.join(text.lower().strip().rstrip('.!').split());rows=self.watch_rows();live=[w for w in rows if w['status'] in ('offered','consented','active') and (consent is None or w['consent']==consent)]
  if q in ('no','no thanks','decline','cancel notification','cancel availability watch','cancel watch','cancel notifications'):
   if not live:return 'There is no active availability watch to cancel.',[]
   for w in live:
    if w['status']=='active':
     w['cancel_remote_pending']=True
     w['status']='cancelled';self.app.watch_memory.save(self.customer,w)
     if self.token and await self.watch_authorized():
      await self.watch_message(w,'cancel');w['cancel_remote_pending']=False
    w['status']='cancelled';self.app.watch_memory.save(self.customer,w)
   if self.pending_read in ('watch','watch_reconnect'):
    for key,t in list(self.app.tickets.items()):
     if t['flow'] is self:await self.cancel_device_ticket(key)
    self.started=None;self.signurl=None;self.pending_read=None
   return 'Availability notifications cancelled. No order was placed.',[]
  if q in ('yes','yes please','notify me','yes notify me','enable notification'):
   offered=[w for w in live if w['status']=='offered']
   if not offered:
    if any(w['status']=='consented' for w in live):return await self.resume_watch()
    return (availability_message(next(w for w in reversed(live) if w['status']=='active'),True) if any(w['status']=='active' for w in live) else 'Finish FORME authorization to activate your notification.' if live else 'Ask for an unavailable item to check notification options.'),[]
   w=offered[-1]
   if self.signurl and self.pending_read=='watch' and getattr(self,'authorizing_watch_consent',w['consent'])!=w['consent']:return 'Finish or cancel the existing FORME notification authorization first.',[]
   if time.time()>w['expires_at']:w['status']='expired';self.app.watch_memory.save(self.customer,w);return 'That notification offer expired. Please search again.',[]
   w['status']='consented';w['consented_at']=time.time();w['offer_expires_at']=w['expires_at'];w['expires_at']=w['consented_at']+600;self.authorizing_watch_consent=w['consent'];self.app.watch_memory.save(self.customer,w);self.watch_boundary(w);return await self.resume_watch()
  if q in ('my watches','notification status','availability status'):
   return ('You have '+str(sum(w['status']=='active' for w in live))+' active availability watches. Say “cancel watch” to stop notifications.'),[]
  m=re.fullmatch(r'add available item ([a-f0-9]{32})',q)
  if m:return await self.add_notification_item(m[1])
  return None
 async def watch_authorized(self):
  if not self.token or not self.principal:return False
  status=await self.browser.call('account_status');account=status.get('account_id')
  return bool(status.get('signed_in') and account==f'forme_customer_{self.customer:03}' and self.app.company_links.authorized(self.principal['id'],self.browser.origin,account,'availability:watch') and 'availability:watch' in self.token.scopes)
 async def resume_watch(self):
  pending=[w for w in self.watch_rows() if w['status']=='consented' and w['expires_at']>time.time() and (not getattr(self,'authorizing_watch_consent',None) or w['consent']==self.authorizing_watch_consent)]
  if not pending:
   expired=[w for w in self.watch_rows() if w['status']=='consented' and w['expires_at']<=time.time() and (not getattr(self,'authorizing_watch_consent',None) or w['consent']==self.authorizing_watch_consent)]
   for w in expired:w['status']='expired';self.app.watch_memory.save(self.customer,w)
   self.pending_read=None;self.pending_watch_consent=None
   return ('Your notification consent expired while signing in. Please search for the item again and confirm a new notification.' if expired else 'There is no notification awaiting authorization. Search for an item to request one.'),[]
  w=pending[-1];self.pending_read='watch'
  if not self.token:await self.open()
  if not await self.watch_authorized():
   await self.signin();return 'Authorize FORME to receive availability notifications. Sign in if needed.',[]
  existing=await self.watch_message(w)
  if not existing:return 'FORME could not activate the watch. No order was placed; retry by saying “yes”.',[]
  w.update(status='active',watch_id=existing['id'],expires_at=existing['expires_at']);self.app.watch_memory.save(self.customer,w);self.pending_read=None
  self.ensure_watch_stream(w);self.watch_boundary(w)
  return availability_message(w,True),[]
 async def poll_watches(self):
  await self.ensure_current_token()
  notice=getattr(self,'watch_recovery_notice',None)
  if notice:self.watch_recovery_notice=None;return notice
  cards=getattr(self,'watch_deliveries',[]);self.watch_deliveries=[]
  if cards:self.poll_cards=cards;return 'Now available at FORME — your matching demo restock is ready. Add it to your bag if you’d like; this notification does not place an order.'
  active=[w for w in self.watch_rows() if w['status']=='active' and w['expires_at']>time.time() and w.get('delivery')!='thread-forme-webhook-v1']
  cancellations=[w for w in self.watch_rows() if w.get('cancel_remote_pending')]
  if not active and not cancellations:return None
  if not self.token:
   self.pending_read='watch_reconnect';await self.open();await self.signin();return 'Reconnect FORME to receive your saved availability notifications. Your watch survived the restart; no order was placed.'
  if any(w.get('reconnect_required') for w in active) or not self.token.signed_in or 'availability:watch' not in self.token.scopes:
   self.pending_read='watch_reconnect';await self.signin()
   for w in active:w.pop('reconnect_required',None);self.app.watch_memory.save(self.customer,w)
   return 'Reconnect FORME to resume availability notifications.'
  for w in cancellations:
   await self.watch_message(w,'cancel');w['cancel_remote_pending']=False;self.app.watch_memory.save(self.customer,w)
  for w in active:
   if not w.get('conversation_id'):
    remote=await self.watch_message(w)
    if not remote:continue
   self.ensure_watch_stream(w)
  return None
 async def add_notification_item(self,event_id,authorized=False):
  card=next((c for c in self.app.watch_memory.inbox(self.customer) if c['event_id']==event_id),None)
  if not card or card['expires_at']<=time.time():return 'That notification is unavailable or expired. Please search again.',[]
  if card.get('added'):return 'This notification item was already added or is awaiting a bag check. Say “checkout” to review your bag.',[]
  if not self.token:await self.open()
  if not authorized:return await self.add_selected(card['product'],card['size'],card['name'],event_id)
  detail=await self.browser.call('detail',product=card['product'])
  item=next((p for p in detail.get('products',[]) if p['id']==card['product']),None)
  if not item or item['price_cents']!=card['price_cents'] or item['color']!=card['color'] or not any(v['size']==card['size'] and v['stock']>0 for v in item['sizes']):return 'That notification’s exact variant or price changed. Nothing was added. Search again to review the current item.',[]
  # Reserve once before the browser mutation; an interrupted add is not replayed.
  prior=json.dumps(card);card['added']=True
  reserved=self.app.watch_memory.db.execute('UPDATE thread_availability_inbox SET data=? WHERE customer=? AND event=? AND data=?',(json.dumps(card),self.customer,event_id,prior)).rowcount;self.app.watch_memory.db.commit()
  if not reserved:return 'This notification item was already added or is awaiting a bag check.',[]
  self._add_in_flight=True
  snap=await self.browser.call('add',product=card['product'],size=card['size'],add_id=event_id,expected_price=card['price_cents']);self.review=None
  return snap.get('error') or f'{card["name"]}, size {card["size"]}, is in your bag. Say “checkout” when you’re ready.',[]

 async def red_demo_search(self,text,kind):
  p,updates=self.app.memory.edit(self.customer,text,commit=False)
  # The deterministic trigger does not let a model discard incompatible attributes.
  filters={'demo_trigger':kind,'shoe_size':p['shoe_size'],'size_system':p['size_system'],'width':p['width'],'budget':p['budget'],'min_price':p.get('budget_min',0),'exclude_material':p.get('avoid','none'),'exclude_colors':','.join(p.get('excluded_colors',[]))}
  for field in ('material','fit','quality','occasion','style'):
   if field in updates:filters[field]=updates[field]
  if updates.get('brands'):filters['brand']=updates['brands'][0]
  if re.search(r'\b(vegan|suede|cotton|linen|wool|silk|leather)\b',text,re.I):filters['material']=re.search(r'\b(vegan|suede|cotton|linen|wool|silk|leather)\b',text,re.I)[1].lower()
  size=re.search(r'\bsize\s+(\d+(?:\.\d+)?)',text,re.I)
  if size and kind=='shoes':filters['shoe_size']=size[1]
  if size and kind=='tie':return 'This demo tie is One size (regular length); I can’t promise a numeric tie size.',[]
  if kind=='shoes' and re.search(r'\b(boots?|heels?|sandals?|loafers?)\b',text,re.I):return 'This demo supports red leather court sneakers only.',[]
  brand=re.search(r'\b(?:brand|by)\s+([A-Za-z’]+)',text,re.I)
  if brand:filters['brand']=brand[1]
  for field,values in {'fit':['slim','relaxed'],'quality':['luxury','essential']}.items():
   for value in values:
    if re.search(r'\b'+value+r'\b',text,re.I):filters[field]=value
  if re.search(r'\b(wide|extra wide)\b',text,re.I):filters['width']='wide'
  if re.search(r'\b(UK|EU)\b',text,re.I):filters['size_system']=re.search(r'\b(UK|EU)\b',text,re.I)[1].upper()
  limit=re.search(r'\b(?:below|no more than|less than)\s*\$?(\d+)',text,re.I)
  if limit:filters['budget']=int(limit[1])
  if kind=='shoes' and re.search(r'\b(running|runners?|formal|wedding)\b',text,re.I):return 'This demo supports casual red leather court sneakers only; I can’t promise that occasion or style.',[]
  if kind=='tie' and re.search(r'\b(skinny|bow|extra long|short|cotton|wool)\b',text,re.I):return 'This demo supports a regular-length red silk necktie only. I can’t promise the requested variant.',[]
  from constraints import extract,ConstraintError
  try:required=extract(text)
  except ConstraintError as e:return str(e),[]
  filters.update(required)
  if 'budget' in required and 'min_price' not in required:filters['min_price']='0'
  if required.get('include_colors'):
   from color_constraints import values
   filters['exclude_colors']=','.join(sorted((values(filters.get('exclude_colors',''))-values(required['include_colors']))|values(required.get('exclude_colors',''))))
  if not self.token:await self.open()
  return await self.offer_watch(filters)
