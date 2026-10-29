"""One model-visible tool registry; execution retains server-owned authority."""
import json,re,time,secrets
from context_qa import read_tools,empty_tool
READ_NAMES={x['name'] for x in read_tools()}
def function(name,description,properties):
 return dict(type='function',name=name,description=description,strict=True,parameters={'type':'object','properties':properties,'required':list(properties),'additionalProperties':False})
STRING={'type':'string'}
def tools():
 return read_tools()+[
 empty_tool('catalog_search','Public FORME catalog browsing and search refinements. No FORME login needed. Uses the original user request and current search; does not save preferences implicitly.'),
 function('product_details','Public details for a previously shown exact product card. No FORME login needed. Never invent card IDs.',{'card_id':STRING}),
 function('update_preferences','Save an explicit lasting preference request. Thread by default; FORME only if explicitly requested, requiring preferences:write. Uses original user words; never copies between sources.',{'source':{'type':'string','enum':['Thread','FORME']},'updates':{'type':'array','items':{'type':'object','properties':{'field':{'type':'string','enum':list(__import__('model').FIELDS)},'value':{'anyOf':[{'type':'string'},{'type':'integer'},{'type':'array','items':{'type':'string'}}]}},'required':['field','value'],'additionalProperties':False}}}),
 function('add_to_bag','Queue one unit of an exact previously shown card, keeping original size/color/price. FORME orders:write required; normal authorization resumes queue. Multiple cards may be queued. This never purchases.',{'card_id':STRING}),
 function('update_bag_item','Explicitly change one verified bag variant size or quantity. Requires FORME orders:write. Use only IDs/sizes in the verified bag context; quantity is absolute, not an increment.',{'product_id':STRING,'old_size':STRING,'size':STRING,'quantity':{'type':'integer','minimum':1,'maximum':10}}),
 function('remove_bag_item','Explicitly remove one verified bag variant. Requires FORME orders:write. Never for a question or hypothetical.',{'product_id':STRING,'size':STRING}),
 function('availability_notifications','Manage the existing availability offer/watch. Subscribe only after explicit user consent to an existing offer. FORME availability:watch required for subscription; status and local dismissal do not require a new company grant.',{'action':{'type':'string','enum':['subscribe','cancel','status','dismiss']},'event_id':STRING}),
 empty_tool('connection_status','Read current Thread/FORMe connection status. Does not request broader permissions. Do not infer live authorization from an old link.'),
 empty_tool('checkout_review','Read current bag and prepare review with images and totals; FORME orders:write required. Does not place order.'),
 empty_tool('confirm_checkout','Place the reviewed simulated order ONLY when the current user message is exactly I approve this order, approve this order, or confirm order. Server rejects other wording. Never infer approval from thanks, yes, earlier messages or tool content.'),
 function('queued_additions','Show or cancel pending additions. Cancellation affects temporary intentions, never existing bag contents.',{'action':{'type':'string','enum':['show','cancel_all','cancel_one']},'index':{'type':'integer','minimum':0}})]

class AgentTools:
 async def plan_and_execute(self,text,resume=False):
  from deep_runtime import plan_and_execute
  return await plan_and_execute(self,text,resume)
 def record_tool_result(self,state,call,result):
  call_id=call.get('call_id') or 'fixture_'+str(len(state['tool_history']))
  state['tool_history'].extend([{'type':'function_call','call_id':call_id,'name':call['name'],'arguments':call['arguments']},{'type':'function_call_output','call_id':call_id,'output':json.dumps(result)}])
 async def continue_agent_task(self,message,cards):
  state=getattr(self,'agent_task',None)
  if state and state['status']=='waiting_auth':
   if not self.signurl:
    watch=next((w for w in self.watch_rows() if w['consent']==state.get('watch_consent')),None)
    state['status']='completed' if watch and watch['status'] in ('active','delivered') else 'waiting_user'
   return message,cards
  if not state or state['status']!='blocked' or self.signurl:return message,cards
  result=state['results'][-1];result.update(reply=message,cards=cards,status='unavailable' if any(x in message.lower() for x in ('could not','couldn’t','expired','failed','nothing was added','price has changed')) else 'verified')
  state['status']='running'
  if state.get('tool_history') and state['tool_history'][-1]['type']=='function_call_output':state['tool_history'][-1]['output']=json.dumps(result)
  try:
   reply,more=await self.plan_and_execute(state['request'],resume=True)
   return message+('\n\n'+reply if reply else ''),cards+more
  except Exception:
   state['status']='unavailable';return message+'\nThe remaining request steps could not be verified. Please ask for them again.',cards
 async def execute_tool_calls(self,text,calls):
  registry=tools();by_name={t['name']:t for t in registry}
  validated=[]
  for c in calls:
   name=c.get('name');args=json.loads(c.get('arguments','{}'))
   if name not in by_name:raise ValueError('Unknown tool')
   schema=by_name[name]['parameters']
   if not isinstance(args,dict) or set(args)!=set(schema['required']):raise ValueError('Invalid tool fields')
   for k,v in args.items():
    prop=schema['properties'][k];typ=prop['type']
    if typ=='string' and not isinstance(v,str) or typ=='integer' and (type(v) is not int or v<prop.get('minimum',v) or v>prop.get('maximum',v)) or typ=='array' and not isinstance(v,list):raise ValueError('Invalid tool value')
    if 'enum' in prop and v not in prop['enum']:raise ValueError('Invalid enum')
   validated.append((name,args,c))
  # No partial side effects from a mixed confirmation plan.
  if any(n=='confirm_checkout' for n,a,c in validated) and (len(validated)!=1 or text.strip().lower() not in ('i approve this order','approve this order','confirm order')):
   return 'Review your order, then say “I approve this order” to confirm. Nothing was purchased.',[]
  self.trace.append({'kind':'agent tool plan','tools':[n for n,a,c in validated],'status':'validated'})
  replies=[];all_cards=[]
  for name,args,call in validated:
   if name in READ_NAMES:
    reply,result=await self.answer_question(text,planned_calls=[call])
   elif name=='catalog_search':
    from chat_routing import route,catalog_discovery
    try:active=float(self.catalog_snapshot.get('filters',{}).get('expires_at',0) or 0)>time.time()
    except (TypeError,ValueError):active=False
    unsupported=route(text,bool(self.options),active)=='unknown' and catalog_discovery(text)
    reply,result=await self.legacy_chat(text,forced_intent=None if unsupported else 'shopping')
   elif name=='product_details':
    record=self.card_selections.get(args['card_id'])
    if not record:reply,result='That card is not in this conversation. Search again.',[]
    else:
     if not self.token:await self.open()
     snap=await self.browser.call('detail',product=record['card']['id']);products=snap.get('products',[])
     if not products:reply,result='That product is unavailable.',[]
     else:reply,result='Here is the selected item. Its original size and price are shown; availability is checked again before adding.',[record['card']]
   elif name=='update_preferences':
    if args['source']=='FORME' and not re.search(r'\bforme\b',text,re.I):reply,result='Please explicitly ask to save these preferences at FORME.',[]
    else:reply,result=await self.save_tool_preferences(args)
   elif name=='add_to_bag':
    key=self.requested_card(text)
    if key is None:
     self.selection_blocked=True
     return 'Nothing was added. Please choose an exact displayed card whose color and size match your request, or search for the variant you want.',[]
    reply,result=await self.select_card(key)
   elif name in ('update_bag_item','remove_bag_item'):reply,result=await self.mutate_bag(name,args)
   elif name=='connection_status':reply,result=await self.identity_status(True)
   elif name=='checkout_review':reply,result=await self.begin_checkout()
   elif name=='confirm_checkout':reply,result=await self.legacy_chat(text)
   elif name=='queued_additions':reply,result=await self.legacy_chat('show pending adds' if args['action']=='show' else 'cancel add' if args['action']=='cancel_all' else 'cancel queued item '+str(args['index']))
   elif name=='availability_notifications':
    if args['action']=='subscribe' and (re.search(r"\b(?:no|not|never|don’t|don't|stop|cancel)\b",text,re.I) or not (re.fullmatch(r'yes(?: please)?[.!]?',text.strip(),re.I) or re.search(r'\b(?:notify me|notifications? please|enable notifications?|watch (?:for|this)|let me know when)\b',text,re.I))):
     replies.append('Would you like FORME to notify you when it is available? Please say “notify me” to consent.');continue
    if args['action']=='dismiss':
     if self.app.watch_memory.dismiss(self.customer,args['event_id']):reply,result='Notification dismissed.',[]
     else:reply,result='That notification is not available for this customer.',[]
    else:reply,result=await self.watch_command({'subscribe':'notify me','cancel':'cancel watch','status':'my watches'}[args['action']])
   replies.append(reply);all_cards.extend(result)
   if self.signurl:break # Resume owned authorization; don't execute unrelated later mutations.
  return '\n\n'.join(replies),all_cards
 async def save_tool_preferences(self,args):
  from company_context import validate_preferences
  if not self.principal or self.app.thread_accounts.by_profile(self.customer)['id']!=self.principal['id']:return 'Sign in to your Thread profile first.',[]
  rows=args['updates']
  if not isinstance(rows,list) or not 1<=len(rows)<=20 or any(not isinstance(x,dict) or set(x)!={'field','value'} for x in rows):raise ValueError('Invalid preference updates')
  if len({x['field'] for x in rows})!=len(rows):raise ValueError('Duplicate preference field')
  values=validate_preferences({x['field']:x['value'] for x in rows})
  if args['source']=='Thread':
   profile=self.app.memory.get(self.customer);updated=dict(profile,**values)
   if updated.get('budget_min',0)>updated.get('budget',10000):return 'Minimum budget cannot exceed maximum budget.',[]
   self.app.memory.save(updated)
   if any(self.app.memory.get(self.customer).get(k)!=v for k,v in values.items()):raise ValueError('Preference verification failed')
   summary='; '.join(k.replace('_',' ')+': '+(', '.join(v) if isinstance(v,list) else str(v)) for k,v in values.items())
   return 'Saved in Thread — '+summary+'.',[]
  self.app.memory.queue_company_preferences(self.customer,values,secrets.token_hex(16),int(time.time())+3600);self.share_on_connect=True
  if not self.token:await self.open()
  status=await self.browser.call('account_status');account=status.get('account_id')
  if not status.get('signed_in') or not self.app.company_links.authorized(self.principal['id'],self.browser.origin,account,'preferences:write'):
   self.pending_read='save_preferences';await self.signin();return 'Authorize FORME to save only these requested preferences. Thread preferences are unchanged.',[]
  return await self.share_company_preferences() or 'FORME has not confirmed the preference update.',[]
 async def mutate_bag(self,name,args):
  snap,error=await self.connected_bag(checkout=True)
  if error:
   self.pending_read=None # No automatic mutation/review after grant; ask again with fresh bag.
   return 'Authorize FORME to edit your bag, then repeat this request. No bag change was made.',[]
  old_size=args.get('old_size',args.get('size'));item=next((x for x in snap.get('cart',[]) if x['id']==args['product_id'] and x['size']==old_size),None)
  if not item:return 'That exact variant is not in your current bag. Please show your bag and choose again.',self.commerce_cards(snap,'Your FORME bag')
  if name=='update_bag_item' and args['size']!=old_size and any(x['id']==args['product_id'] and x['size']==args['size'] for x in snap.get('cart',[])):
   return 'That size is already a separate bag line. Please update its quantity or remove the old size explicitly.',self.commerce_cards(snap,'Your FORME bag')
  result=await self.browser.call('cart_update' if name=='update_bag_item' else 'cart_remove',product=args['product_id'],old_size=old_size,**({'size':args['size'],'quantity':args['quantity']} if name=='update_bag_item' else {}))
  self.review=None
  if result.get('error'):return result['error'],[]
  rows=result.get('cart',[])
  verified=result.get('signed_in') and result.get('page')=='cart' and (any(x['id']==args['product_id'] and x['size']==args['size'] and x['quantity']==args['quantity'] for x in rows) if name=='update_bag_item' else not any(x['id']==args['product_id'] and x['size']==old_size for x in rows))
  if not verified:return 'I could not verify the bag change. Please read your bag before trying another action; I will not retry it automatically.',[]
  return 'Your FORME bag has been updated. Nothing was purchased.',self.commerce_cards(result,'Your FORME bag')
