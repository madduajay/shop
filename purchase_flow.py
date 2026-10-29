"""Conversation-owned ordered add queue; all mutations use storefront browser forms."""
import secrets
class PurchaseFlow:
 def sync_add_queue(self):
  self.pending_add=self.pending_adds[0] if self.pending_adds else None
  if not self.pending_add and self.pending_read=='add':self.pending_read=None
 def queued_summary(self):
  return '\n'.join(f"{i+1}. {j['name']}, size {j['size']} × 1" for i,j in enumerate(self.pending_adds))
 def cancel_queued_adds(self,index=None):
  jobs=list(self.pending_adds) if index is None else self.pending_adds[index:index+1]
  for j in jobs:
   self.pending_adds.remove(j)
   if j.get('card_id') in self.card_selections:self.card_selections[j['card_id']]['state']='ready'
  self.sync_add_queue()
  return jobs
 async def recover_pending_add(self,card_id=None):
  if not self.pending_adds:return 'No items are waiting to be added. Choose a card to add it.',[]
  self.pending_read='add'
  if self.started:
   reply=await self.poll()
   if not self.pending_adds:
    cards=self.poll_cards;self.poll_cards=[]
    return reply or 'Your queued selections were processed. Check your bag.',cards
  return await self.resume_add()
 async def add_selected(self,product,size,name,event_id=None,requirements=None,card_id=None,quoted_price=None):
  key=card_id or event_id
  if not any((key and (j.get('card_id') or j.get('event_id'))==key) for j in self.pending_adds):
   requirements=dict(requirements if requirements is not None else {} if event_id else self.catalog_snapshot.get('filters',{}))
   self.pending_adds.append(dict(product=product,size=size,name=name,event_id=event_id,requirements=requirements,card_id=card_id,quoted_price=quoted_price,quantity=1,add_id=key or secrets.token_hex(16)))
   if card_id:self.card_selections[card_id]['state']='pending'
  self.sync_add_queue()
  return await self.resume_add()
 async def resume_add(self):
  if not self.pending_adds:return 'Signed in with FORME. No item is pending.',[]
  reports=[]
  while self.pending_adds:
   job=self.pending_adds[0]
   try:
    reply,_=await self._add_one(**job)
    if self._add_waiting:
     count=len(self.pending_adds)
     if count>1:reply+=f'\n{count} selections are queued, one of each:\n'+self.queued_summary()+'\nOne authorization will resume all of them. Say “cancel add” to cancel all, or “cancel queued item 2” to cancel one.'
     return '\n'.join(reports+[reply]),[]
   except Exception:
    uncertain=getattr(self,'_add_in_flight',False)
    if job.get('card_id') in self.card_selections:self.card_selections[job['card_id']]['state']='uncertain' if uncertain else 'ready'
    reply=('Could not confirm this add. Check your bag before retrying.' if uncertain else 'Could not validate this item. Nothing was submitted; choose its card to retry.')
   if job.get('card_id') in self.card_selections and self.card_selections[job['card_id']]['state']=='pending':self.card_selections[job['card_id']]['state']='ready'
   self.pending_adds.pop(0);self.sync_add_queue()
   reports.append(reply if reply.startswith(job['name']) else f"{job['name']}, size {job['size']}: {reply}")
   self.trace.append({'kind':'queued add result','product':job['product'],'size':job['size'],'quantity':job['quantity'],'message':reply})
  return '\n'.join(reports),[]
 async def _add_one(self,product,size,name,event_id=None,requirements=None,card_id=None,quoted_price=None,add_id=None,quantity=1):
  import time
  self._add_waiting=False;self._add_in_flight=False
  if quantity!=1:return 'Queued cards add one unit each. Use your bag controls to change quantities.',[]
  from constraints import matches,variant_size
  requirements=requirements if requirements is not None else dict(self.catalog_snapshot.get('filters',{}))
  if requirements.get('expires_at') and int(requirements['expires_at'])<=time.time():return 'That search expired. Please search again before adding.',[]
  if not self.token:await self.open()
  status=await self.browser.call('account_status')
  if status.get('account_status')=='expired':
   await self.browser.close();self.app.flows.pop(self.token.session_id,None);self.token=None;await self.open();status=await self.browser.call('account_status')
  account=status.get('account_id')
  if status.get('signed_in') and account!=f'forme_customer_{self.customer:03}':return 'FORME’s account does not match your Thread identity. I won’t add this item.',[]
  authorized=status.get('signed_in') and self.app.company_links.authorized(self.principal['id'],self.browser.origin,account,'orders:write')
  if not authorized:
   self.signin_label='Review FORME permissions' if status.get('signed_in') else 'Sign in with FORME'
   self._add_waiting=True
   self.pending_read='add';await self.signin()
   if status.get('signed_in'):
    return f'You’re already signed in to FORME. Choose “Review FORME permissions” to authorize adding {name}, size {size}, to your bag. I’ll resume this selection once after you authorize it. Nothing will be purchased. Say “cancel add” to cancel.',[]
   return f'Sign in with FORME to add {name}, size {size}, to your bag. I’ll resume this selection once. Nothing will be purchased. Say “cancel add” to cancel.',[]
  self.signin_label=None
  if event_id:return await self.add_notification_item(event_id,authorized=True)
  detail=await self.browser.call('detail',product=product)
  if requirements:
   chosen=next((p for p in detail.get('products',[]) if p['id']==product),None)
   if not chosen or not matches(chosen,requirements) or variant_size(chosen,requirements)!=size:
    if card_id:self.card_selections[card_id]['state']='ready'
    return 'That exact variant no longer meets your request or is unavailable. Nothing was added. Would you like to search again?',[]
  if quoted_price is not None and (not chosen or chosen['price_cents']!=quoted_price):
   if card_id:self.card_selections[card_id]['state']='ready'
   return 'The price has changed since that card was shown. Nothing was added. Please search again to review the current price.',[]
  if card_id:self.card_selections[card_id]['state']='uncertain'
  self._add_in_flight=True
  snap=await self.browser.call('add',product=product,size=size,add_id=add_id or card_id,**({'expected_price':quoted_price} if quoted_price is not None else {}));self.review=None
  if card_id:
   if snap.get('error'):self.card_selections[card_id]['state']='ready'
   elif any(x.get('id')==product and x.get('size')==size for x in snap.get('cart',[])):self.card_selections[card_id]['state']='added'
   else:return 'I could not confirm that add. Please check your bag; I won’t submit it again automatically.',[]
  return snap.get('error') or f'{name}, size {size}, is in your bag. Keep browsing, or say “checkout” when you’re ready.',[]
