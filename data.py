import json,sqlite3,re
from pathlib import Path
NAMES=['Alex Morgan','Jordan Lee','Sam Rivera','Taylor Chen','Casey Patel','Riley Brooks','Jamie Kim','Avery Singh','Morgan Ellis','Quinn Davis']
from catalog import PALETTE,BRANDS,MATERIALS
COLORS=list(PALETTE)
class Memory:
 def __init__(self,path):
  self.db=sqlite3.connect(path);self.db.execute('create table if not exists profiles(id integer primary key,data text)');self.db.execute('create table if not exists orders(id text primary key,data text)')
  for i in range(1,101):
   p=dict(id=i,name=NAMES[(i-1)%10]+f' · {i:03}',shirt_size=['M','S','L','XL'][((i-1)//10)%4],waist=str(28+2*((i-1)%6)),shoe_size=str(7+(i-1)%6),size_system='US',colors=[['navy','white','black','olive','sand','blue'][(i-1)%6]],quality='premium',budget=180,budget_min=20,brands=['Northline','Form & Field'][i%2:i%2+1],fit='regular',material='cotton',occasion='everyday',style='minimal',width='standard',inseam='30',avoid='none')
   self.db.execute('insert or ignore into profiles values (?,?)',(i,json.dumps(p)))
  self.db.commit()
 def intent(self,customer,durable,temporary,request_id=None,expires_at=None):
  from datetime import datetime,timezone
  import secrets
  self.db.execute('CREATE TABLE IF NOT EXISTS thread_shopping_intents(customer INTEGER PRIMARY KEY,data TEXT NOT NULL,updated_at TEXT NOT NULL)')
  self.db.execute('CREATE TABLE IF NOT EXISTS pending_forme_memory(customer INTEGER PRIMARY KEY,data TEXT NOT NULL)')
  now=datetime.now(timezone.utc).isoformat();expires=expires_at or int(datetime.now(timezone.utc).timestamp())+3600;request_id=request_id or secrets.token_hex(16);record={'explicit_preferences':durable,'current_request':temporary,'source':'thread_chat','updated_at':now,'expires_at':expires,'preference_scope':'lasting','intent_scope':'request','request_id':request_id}
  previous=self.db.execute('SELECT data FROM thread_shopping_intents WHERE customer=?',(customer,)).fetchone()
  previous=json.loads(previous[0]) if previous else {}
  if previous.get('request_id')==request_id and previous.get('expires_at',0)>datetime.now(timezone.utc).timestamp():
   temporary=dict(previous.get('current_request',{}))|temporary
   record['current_request']=temporary
  pending=self.pending_share(customer);combined=dict(pending.get('preferences',{}));combined.update(durable)
  payload={'preferences':combined,'intent':temporary,'update_id':secrets.token_hex(16),'updated_at':now,'metadata':{'preference_scope':'lasting','intent_scope':'request','source':'thread_chat','expires_at':expires,'request_id':request_id}}
  with self.db:
   if durable:
    profile=self.get(customer);profile.update(durable);self.db.execute('UPDATE profiles SET data=? WHERE id=?',(json.dumps(profile),customer))
   self.db.execute('INSERT INTO thread_shopping_intents VALUES(?,?,?) ON CONFLICT(customer) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(customer,json.dumps(record),now))
   self.db.execute('INSERT INTO pending_forme_memory VALUES(?,?) ON CONFLICT(customer) DO UPDATE SET data=excluded.data',(customer,json.dumps(payload)))
  return payload
 def queue_company_preferences(self,customer,values,request_id,expires_at):
  # An explicit FORME edit does not write Thread's saved profile or combine queued Thread values.
  import secrets
  self.db.execute('CREATE TABLE IF NOT EXISTS pending_forme_memory(customer INTEGER PRIMARY KEY,data TEXT NOT NULL)')
  payload={'preferences':values,'intent':{},'update_id':secrets.token_hex(16),'metadata':{'preference_scope':'lasting','intent_scope':'request','source':'thread_chat','expires_at':expires_at,'request_id':request_id}}
  self.db.execute('INSERT INTO pending_forme_memory VALUES(?,?) ON CONFLICT(customer) DO UPDATE SET data=excluded.data',(customer,json.dumps(payload)));self.db.commit()
 def pending_share(self,customer):
  self.db.execute('CREATE TABLE IF NOT EXISTS pending_forme_memory(customer INTEGER PRIMARY KEY,data TEXT NOT NULL)')
  row=self.db.execute('SELECT data FROM pending_forme_memory WHERE customer=?',(customer,)).fetchone();pending=json.loads(row[0]) if row else {}
  if pending:
   import time
   if pending.get('metadata',{}).get('expires_at',0)<=time.time():
    pending['intent']={}
    if not pending.get('preferences'):return {}
    pending['metadata']={'preference_scope':'lasting','intent_scope':'request','source':'thread_chat','expires_at':int(time.time())+3600,'request_id':pending.get('metadata',{}).get('request_id',pending['update_id'])}
  return pending
 def shared(self,customer,update_id):
  pending=self.pending_share(customer)
  if pending.get('update_id')==update_id:self.db.execute('DELETE FROM pending_forme_memory WHERE customer=?',(customer,));self.db.commit()
 def get(self,i):
  r=self.db.execute('select data from profiles where id=?',(i,)).fetchone()
  if not r:raise ValueError('Choose customer 1–100.')
  return json.loads(r[0])
 def save(self,p):self.db.execute('update profiles set data=? where id=?',(json.dumps(p),p['id']));self.db.commit()
 def edit(self,i,text,commit=True):
  p=self.get(i);updates={};low=text.lower()
  for word,size in [('extra small','XS'),('extra large','XL'),('medium','M'),('small','S'),('large','L')]:
   if re.search(r'\bi (?:usually )?wear '+word+r'\b',low):updates['shirt_size']=size
  for material in ['cotton','linen','silk','wool','leather']:
   if re.search(r'\bi (?:usually )?(?:prefer|like) '+material+r'\b',low):updates['material']=material
  patterns={'shirt_size':r'(?:shirt size|size)\s+(?:(?:is|of)\s+)?(XS|S|M|L|XL|XXL)\b','waist':r'waist\s+(?:is\s+)?(2[6-9]|[3-4][0-9])\b','shoe_size':r'(?:shoe size|shoes? size)\s+(?:is\s+)?(\d{1,2}(?:\.5)?)\b','budget':r'(?:under|budget|max|up to)\s*(?:is\s+)?\$?(\d{1,4})\b','inseam':r'inseam\s+(\d{2})\b'}
  for k,pat in patterns.items():
   m=re.search(pat,text,re.I)
   if m:updates[k]=int(m[1]) if k=='budget' else m[1].upper()
  enums={'fit':['regular','slim','relaxed'],'material':sorted({m for values in MATERIALS.values() for m in values}|{'leather','suede','mesh','nubuck','vegan leather'}),'occasion':['everyday','work','running','evening','travel'],'style':['minimal','classic','sport','casual'],'quality':['premium','essential','luxury'],'size_system':['US','UK','EU'],'width':['standard','wide'],'avoid':['wool','leather','polyester']}
  for k,vals in enums.items():
   for v in vals:
    if re.search(r'\b'+re.escape(k.replace('_',' '))+r'\s+(?:is\s+)?'+v+r'\b',text,re.I):updates[k]=v
  from color_constraints import parse_colors
  colors=parse_colors(text)
  if colors['include']:updates['colors']=colors['include']
  if colors['exclude']:updates['excluded_colors']=colors['exclude']
  brands=[b for b in BRANDS+['Nike','Levi’s'] if b.lower() in low]
  if brands:updates['brands']=brands
  price_range=re.search(r'(?:between|range)\s*\$?(\d+)\s*(?:and|to|-)\s*\$?(\d+)',low)
  if price_range:
   a,b=map(int,price_range.groups())
   if not 0<=a<=b<=10000:raise ValueError('Choose a price range between $0 and $10,000.')
   updates.update(budget_min=a,budget=b)
  p.update(updates)
  if commit:self.save(p)
  return p,updates
 def order(self,row):
  self.db.execute('insert or ignore into orders values (?,?)',(row['review_id'],json.dumps(row)));self.db.commit()
 def orders(self):return [json.loads(r[0]) for r in self.db.execute('select data from orders')]
def legacy_catalog():
 specs=[
 ('oxford','Oxford Cotton Shirt','shirts','white','Northline','cotton','regular','premium','work','shirt',59),
 ('tee','Essential Crew Tee','shirts','white','Form & Field','cotton','regular','essential','everyday','tee',32),
 ('denim-blue','Straight Denim','trousers','blue',"Levi’s",'denim','regular','premium','everyday','trousers',89),
 ('denim-black','Straight Denim','trousers','black',"Levi’s",'denim','regular','premium','everyday','trousers',89),
 ('denim-indigo','Straight Denim','trousers','navy',"Levi’s",'denim','regular','premium','everyday','trousers',95),
 ('court','Air Force Utility','shoes','brown','Nike','leather','regular','premium','everyday','shoes',120),
 ('runner','Air Max Essential','shoes','white','Nike','leather','regular','premium','everyday','sneaker',145),
 ('denim-jacket','Sherpa Denim Jacket','jackets','navy','Northline','denim','regular','premium','everyday','jacket',159)]
 rows=[]
 for i,(id,name,category,color,brand,material,fit,quality,occasion,image,price) in enumerate(specs):
  sizes=['XS','S','M','L','XL','XXL'] if category in ('shirts','jackets') else [str(x) for x in range(26,45,2)] if category=='trousers' else [str(x) for x in range(6,14)]
  rows.append(dict(id=id,name=name,category=category,color=color,brand=brand,material=material,fit=fit,quality=quality,occasion=occasion,image=image,price=price*100,style='minimal',stock={s:(0 if i==2 and k==0 else 5+k%4) for k,s in enumerate(sizes)}))
 return rows


def catalog():
 from catalog import build_catalog
 return build_catalog(legacy_catalog())
