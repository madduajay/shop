"""FORME-owned data: accepts only validated website input, never Thread memory."""
import json,sqlite3,re
from datetime import datetime,timezone
from catalog import PALETTE,BRANDS,MATERIALS
PREFERENCE_VALUES={
 'gender':{'men','women'},'design_style':set(__import__('global_catalog').FAMILIES),
 'shirt_size':{'XS','S','M','L','XL','XXL'},'size_system':{'US','UK','EU'},
 'fit':{'regular','relaxed','slim'},'quality':{'essential','premium','luxury'},
 'material':{v[1] for v in __import__('global_catalog').FAMILIES.values()}|{m for values in MATERIALS.values() for m in values}|{'leather','mesh','suede','nubuck','vegan leather'},
 'occasion':{'everyday','work','running','evening','travel','weekend'},'style':{'minimal','classic','sport','casual','modern'},
 'width':{'standard','wide'},'avoid':{'none','wool','leather','polyester'}}
def validate_preferences(values):
 if not isinstance(values,dict) or not values:raise ValueError('Share at least one explicit preference.')
 out={}
 for k,v in values.items():
  if k in PREFERENCE_VALUES:valid=isinstance(v,str) and v in PREFERENCE_VALUES[k]
  elif k in ('budget','budget_min'):valid=type(v) is int and 0<=v<=10000
  elif k in ('waist','inseam','shoe_size'):
   valid=isinstance(v,str) and bool(re.fullmatch(r'\d{1,2}(?:\.5)?',v)) and (1<=float(v)<=18 if k=='shoe_size' else 20<=float(v)<=50)
  elif k in ('colors','excluded_colors','brands'):
   allowed=set(PALETTE)|{'red'} if k in ('colors','excluded_colors') else set(BRANDS)|{'Nike','Levi’s'}
   valid=isinstance(v,list) and 0<len(v)<=10 and all(isinstance(x,str) and x in allowed for x in v)
  else:valid=False
  if not valid:raise ValueError('Unsupported company preference field or value.')
  out[k]=v
 return out
class CompanyContext:
 def __init__(self,path):
  self.path=path;self.db=sqlite3.connect(path)
  self.db.execute('''CREATE TABLE IF NOT EXISTS customer_context(
   account_id TEXT PRIMARY KEY, preferences_json TEXT NOT NULL DEFAULT '{}',
   recent_constraints_json TEXT NOT NULL DEFAULT '{}', constraints_received_at TEXT,
   constraints_source TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''');self.db.commit()
 def now(self):return datetime.now(timezone.utc).isoformat()
 def ensure(self,account):
  now=self.now();self.db.execute('INSERT OR IGNORE INTO customer_context(account_id,created_at,updated_at) VALUES(?,?,?)',(account,now,now));self.db.commit()
 def get(self,account):
  row=self.db.execute('SELECT preferences_json,recent_constraints_json,constraints_received_at,constraints_source,created_at,updated_at FROM customer_context WHERE account_id=?',(account,)).fetchone()
  if not row:return None
  return dict(preferences=json.loads(row[0]),recent_constraints=json.loads(row[1]),constraints_received_at=row[2],constraints_source=row[3],created_at=row[4],updated_at=row[5])
 def update(self,account,values,source="explicit_storefront_preference_form"):
  values=validate_preferences(values);self.ensure(account);old=self.get(account);prefs=old['preferences'];now=self.now()
  combined={k:v['value'] for k,v in prefs.items()}|values
  if combined.get('budget_min',0)>combined.get('budget',10000):raise ValueError('Saved minimum budget exceeds maximum budget.')
  for k,v in values.items():prefs[k]=dict(value=v,updated_at=now,source=source,scope='lasting')
  self.db.execute('UPDATE customer_context SET preferences_json=?,updated_at=? WHERE account_id=?',(json.dumps(prefs),now,account));self.db.commit()
 def patch(self,account,values,clear):
  values=validate_preferences(values) if values else {}
  if any(k not in set(PREFERENCE_VALUES)|{'colors','excluded_colors','brands','budget','budget_min','waist','inseam','shoe_size'} for k in clear):raise ValueError('Unsupported clear field.')
  self.ensure(account);old=self.get(account);prefs=old['preferences'];combined={k:v['value'] for k,v in prefs.items() if k not in clear}|values
  if combined.get('budget_min',0)>combined.get('budget',10000):raise ValueError('Minimum budget must not exceed maximum budget.')
  now=self.now()
  for k in clear:prefs.pop(k,None)
  for k,v in values.items():prefs[k]=dict(value=v,updated_at=now,source='explicit_storefront_preference_form',scope='lasting')
  self.db.execute('UPDATE customer_context SET preferences_json=?,updated_at=? WHERE account_id=?',(json.dumps(prefs),now,account));self.db.commit()
 def observe_filters(self,account,filters,products):
  # No raw query, tokens, identifiers, arbitrary strings, or private Thread fields.
  kept={}
  for key in ('gender','department','category','kind','color','brand','material','fit','quality','occasion','style'):
   if filters.get(key) in {p[key] for p in products}:kept[key]=filters[key]
  for key in ('size','apparel_size','waist_size','shoe_size'):
   v=filters.get(key)
   if v in {'XS','S','M','L','XL','XXL'} or isinstance(v,str) and re.fullmatch(r'\d{1,2}(?:\.5)?',v):kept[key]=v
  for key in ('budget','min_price'):
   v=filters.get(key)
   if isinstance(v,str) and re.fullmatch(r'\d{1,4}(?:\.\d{1,2})?',v):kept[key]=v
  for key in ('color','brand','material','fit','quality'):
   v=filters.get('prefer_'+key)
   if v in {p[key] for p in products}:kept['prefer_'+key]=v
  if filters.get('exclude_material') in PREFERENCE_VALUES['avoid']:kept['exclude_material']=filters['exclude_material']
  from color_constraints import values
  for key in ('include_colors','exclude_colors'):
   if filters.get(key):kept[key]=','.join(sorted(values(filters[key])))
  self.ensure(account);now=self.now()
  self.db.execute('UPDATE customer_context SET recent_constraints_json=?,constraints_received_at=?,constraints_source=?,updated_at=? WHERE account_id=?',(json.dumps(kept),now,'authenticated_storefront_filter_form',now,account));self.db.commit()
  self.activity(account,'filters_selected',products,filters=kept|{k:filters[k] for k in ('request_id','expires_at') if k in filters})

 # Behavioral memory stays separate from explicit preferences and never contains contact data.
 def init_behavior(self):
  self.db.executescript('''CREATE TABLE IF NOT EXISTS shopping_events(account_id TEXT NOT NULL,event_id TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,occurred_at TEXT NOT NULL,source TEXT NOT NULL,PRIMARY KEY(account_id,event_id));
CREATE TABLE IF NOT EXISTS purchase_memory_keys(account_id TEXT NOT NULL,order_id TEXT NOT NULL,PRIMARY KEY(account_id,order_id));''');self.db.commit()
 def activity(self,account,kind,products,items=None,filters=None,event_id=None):
  import secrets
  if not account:return False
  if kind not in {'filters_selected','cart_associated','cart_add','cart_update','cart_remove','cart_clear','checkout_started','checkout_reviewed','purchase_completed'}:raise ValueError('Unknown shopping activity')
  self.init_behavior();by_id={p['id']:p for p in products};payload={}
  fields=('color','brand','material','fit','quality','occasion','style','category','kind','region','design_style')
  if items is not None:
   safe=[]
   for item in items[:30]:
    p=by_id.get(item.get('id'))
    if p:
     safe.append({k:p[k] for k in fields}|{'product_id':p['id'],'quantity':max(1,min(10,int(item.get('quantity',1)))),'size':item.get('size') if item.get('size') in p['stock'] else None,'unit_price_cents':item.get('price',p['price']) if type(item.get('price',p['price'])) is int else p['price']})
   payload['items']=safe
  if filters is not None:
   from recommendations import safe_current
   payload['filters']=safe_current(filters,products)
   import time
   expiry=filters.get('expires_at')
   expiry=int(expiry) if str(expiry or '').isdigit() else int(time.time())+3600
   payload['scope']='request';payload['expires_at']=min(expiry,int(time.time())+172800);payload['request_id']=filters.get('request_id') if re.fullmatch('[a-f0-9]{32}',str(filters.get('request_id',''))) else secrets.token_hex(16)
  encoded=json.dumps(payload,sort_keys=True)
  if kind=='filters_selected':
   if not payload.get('filters'):return False
   last=self.db.execute("SELECT payload FROM shopping_events WHERE account_id=? AND kind='filters_selected' ORDER BY rowid DESC LIMIT 1",(account,)).fetchone()
   if last and json.loads(last[0]).get('filters')==payload.get('filters') and json.loads(last[0]).get('expires_at',0)>time.time():return False
  if kind=='purchase_completed':
   if not event_id:raise ValueError('Purchase identity required')
   if self.db.execute('SELECT 1 FROM purchase_memory_keys WHERE account_id=? AND order_id=?',(account,event_id)).fetchone():return False
  self.ensure(account);event_id=event_id or secrets.token_hex(16)
  with self.db:
   if kind=='purchase_completed':self.db.execute('INSERT INTO purchase_memory_keys VALUES(?,?)',(account,event_id))
   self.db.execute('INSERT OR IGNORE INTO shopping_events VALUES(?,?,?,?,?,?)',(account,event_id,kind,encoded,self.now(),'authenticated_forme_'+kind))
   self.db.execute('DELETE FROM shopping_events WHERE account_id=? AND rowid NOT IN (SELECT rowid FROM shopping_events WHERE account_id=? ORDER BY rowid DESC LIMIT 200)',(account,account))
  return True
 def history(self,account):
  self.init_behavior()
  return [dict(kind=r[0],payload=json.loads(r[1]),occurred_at=r[2],source=r[3]) for r in self.db.execute('SELECT kind,payload,occurred_at,source FROM shopping_events WHERE account_id=? ORDER BY rowid DESC LIMIT 200',(account,))]
 def behavior(self,account):
  from collections import Counter,defaultdict
  events=self.history(account);scores=defaultdict(Counter);counts=Counter(e['kind'] for e in events)
  weights={'cart_associated':2,'cart_add':3,'cart_update':2,'cart_remove':-3,'purchase_completed':5}
  for e in events:
   import time
   if e['kind']=='filters_selected' and e['payload'].get('expires_at',0)<=time.time():continue
   weight=weights.get(e['kind'],0)
   if not weight:continue
   values=e['payload'].get('items',[]) or [e['payload'].get('filters',{})]
   for p in values:
    for key in ('color','brand','material','fit','quality','occasion','style'):
     if p.get(key):scores[key][p[key]]+=weight
  inferred={key:{'value':counter.most_common(1)[0][0],'score':counter.most_common(1)[0][1],'source':'observed FORME shopping activity','inferred':True} for key,counter in scores.items() if counter and counter.most_common(1)[0][1]>=3}
  return {'inferred_interests':inferred,'activity_counts':dict(counts),'history_limit':200}
 def shared_intent(self,account,request_id=None):
  self.db.execute('CREATE TABLE IF NOT EXISTS shared_shopping_intents(account_id TEXT PRIMARY KEY,data TEXT NOT NULL,received_at TEXT NOT NULL,source TEXT NOT NULL)')
  row=self.db.execute('SELECT data,received_at,source FROM shared_shopping_intents WHERE account_id=?',(account,)).fetchone()
  if not row:return None
  import time
  value=json.loads(row[0])
  if value.get('expires_at',0)<=time.time() or not request_id or value.get('request_id')!=request_id:return None
  return {'current_request':value.get('values',{}),'scope':'request','expires_at':value['expires_at'],'received_at':row[1],'source':row[2]}
 def accept_shared(self,account,preferences,intent,update_id,metadata):
  import time
  if not isinstance(metadata,dict) or set(metadata)!={'preference_scope','intent_scope','source','expires_at','request_id'} or metadata['preference_scope']!='lasting' or metadata['intent_scope']!='request' or metadata['source']!='thread_chat':raise ValueError('Invalid memory scope')
  if not isinstance(metadata['request_id'],str) or not re.fullmatch('[a-f0-9]{32}',metadata['request_id']):raise ValueError('Invalid request identity')
  if type(metadata['expires_at']) is not int or not time.time()<metadata['expires_at']<=time.time()+172860:raise ValueError('Invalid request expiry')
  if not isinstance(update_id,str) or not re.fullmatch('[a-f0-9]{32}',update_id):raise ValueError('Invalid memory update identity')
  if not isinstance(preferences,dict) or not isinstance(intent,dict) or not (preferences or intent):raise ValueError('Empty shopping update')
  if preferences:preferences=validate_preferences(preferences)
  if intent:intent=validate_preferences(intent)
  self.shared_intent(account)
  self.db.execute('CREATE TABLE IF NOT EXISTS shared_memory_receipts(account_id TEXT NOT NULL,update_id TEXT NOT NULL,PRIMARY KEY(account_id,update_id))')
  if self.db.execute('SELECT 1 FROM shared_memory_receipts WHERE account_id=? AND update_id=?',(account,update_id)).fetchone():return
  if preferences:self.update(account,preferences,source='authenticated_thread_chat_lasting')
  else:self.ensure(account)
  with self.db:
   self.db.execute('INSERT INTO shared_shopping_intents VALUES(?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET data=excluded.data,received_at=excluded.received_at,source=excluded.source',(account,json.dumps({'values':intent,'scope':'request','expires_at':metadata['expires_at'],'request_id':metadata['request_id']}),self.now(),'authenticated_thread_browser_form'))
   self.db.execute('INSERT INTO shared_memory_receipts VALUES(?,?)',(account,update_id))
