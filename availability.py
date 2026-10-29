"""Company-owned synthetic stock transitions and durable availability events.
Application website feature, not a new Poppy protocol transport. Authorized browser
forms subscribe; the company advances its durable due times on page requests.
"""
import json,secrets,time,sqlite3,copy
class Availability:
 def __init__(self,path,products):
  self.db=sqlite3.connect(path);self.products=products;self.now=time.time
  self.db.executescript('''CREATE TABLE IF NOT EXISTS watches(id TEXT PRIMARY KEY, owner TEXT NOT NULL, consent TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(owner,consent));
CREATE TABLE IF NOT EXISTS scenario_products(id TEXT PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS restocks(product TEXT NOT NULL,size TEXT NOT NULL,quantity INTEGER NOT NULL,PRIMARY KEY(product,size));''');self.db.commit()
  for (data,) in self.db.execute('SELECT data FROM scenario_products'):products.append(json.loads(data))
  by_id={p['id']:p for p in products}
  for pid,size,qty in self.db.execute('SELECT * FROM restocks'):
   if pid in by_id:by_id[pid]['stock'][size]=max(qty,by_id[pid]['stock'].get(size,0))
 def candidate(self,filters):
  from store import filtered,WAIST_CATEGORIES
  if filters.get('demo_trigger') in ('shoes','tie'):return self.demo_candidate(filters)
  # Reuse only an existing accurate photo/product/price; relax stock alone.
  public=[p for p in self.products if not p.get('availability_owner')]
  if filtered(public,filters):return None
  for p in public:
   size=str(filters.get('size') or filters.get('shoe_size' if p['category']=='shoes' else 'waist_size' if p['category'] in WAIST_CATEGORIES else 'apparel_size') or '')
   allowed={str(n) for n in range(6,14)} if p['category']=='shoes' else {str(n) for n in range(26,45,2)} if p['category'] in WAIST_CATEGORIES else {'XS','S','M','L','XL','XXL'}
   if size not in allowed:continue
   variant=copy.deepcopy(p);variant['stock'][size]=5
   if filtered([variant],filters):return {'product':p['id'],'size':size,'filters':filters,'name':p['name'],'color':p['color'],'price_cents':p['price'],'image':p['image_url']}
  return None
 def rows(self,owner):return [json.loads(r[0]) for r in self.db.execute('SELECT data FROM watches WHERE owner=? ORDER BY rowid',(owner,))]
 def save(self,w):
  self.db.execute('UPDATE watches SET data=? WHERE id=?',(json.dumps(w),w['id']));self.db.commit()
 def subscribe(self,owner,consent,candidate):
  row=self.db.execute('SELECT data FROM watches WHERE owner=? AND consent=?',(owner,consent)).fetchone()
  if row:return json.loads(row[0])
  if sum(w['status']=='active' for w in self.rows(owner))>=5:raise ValueError('At most five active availability watches are allowed.')
  now=self.now();w=dict(id=secrets.token_hex(16),owner=owner,consent=consent,status='active',created_at=now,due_at=now+60,expires_at=now+86400,candidate=candidate,event_id=None)
  self.db.execute('INSERT INTO watches VALUES(?,?,?,?)',(w['id'],owner,consent,json.dumps(w)));self.db.commit();return w
 def tick(self):
  by_id={p['id']:p for p in self.products};now=self.now()
  for (data,) in self.db.execute('SELECT data FROM watches').fetchall():
   w=json.loads(data)
   if w['status'] not in ('active','ready'):continue
   if now>=w['expires_at']:w['status']='expired';self.save(w);continue
   if w['status']=='active' and now>=w['due_at']:
    c=w['candidate'];p=by_id.get(c['product'])
    if c.get('template'):
     p=dict(c['template']);p['stock']={c['size']:5};p['availability_owner']=w['owner'];p['id']='notify-'+w['id'];c['product']=p['id'];w['candidate']=c
     self.products.append(p);by_id[p['id']]=p
     self.db.execute('INSERT OR IGNORE INTO scenario_products VALUES(?,?)',(p['id'],json.dumps(p)))
    if not p:w['status']='expired';self.save(w);continue
    p['stock'][c['size']]=max(5,p['stock'].get(c['size'],0))
    w.update(status='ready',event_id=secrets.token_hex(16),available_at=now)
    with self.db:
     self.db.execute('INSERT INTO restocks VALUES(?,?,?) ON CONFLICT(product,size) DO UPDATE SET quantity=excluded.quantity',(p['id'],c['size'],p['stock'][c['size']]))
     self.db.execute('UPDATE watches SET data=? WHERE id=?',(json.dumps(w),w['id']))
 def cancel(self,owner,consent):
  for w in self.rows(owner):
   if w['consent']==consent:w['status']='cancelled';self.save(w)
 def public(self,owner):
  self.tick();return [{k:v for k,v in w.items() if k!='owner'} for w in self.rows(owner)]

 def allowed(self,product,s):
  p=next((p for p in self.products if p['id']==product),None)
  if not p or not p.get('availability_owner'):return True
  owner=json.loads(p['availability_owner'])
  return bool(s and s.client_id==owner[0] and s.pairwise_user_id==owner[1] and (not s.signed_in or s.account_id==owner[2]))
 def demo_candidate(self,f):
  from color_constraints import color_filters
  included,excluded=color_filters(f)
  if 'red' in excluded or (included and 'red' not in included):return None
  kind=f['demo_trigger'];shoe=kind=='shoes';size=str(f.get('shoe_size','7')) if shoe else 'One size'
  price=9500 if shoe else 4500
  if shoe and (size not in {str(n) for n in range(6,14)} or f.get('size_system','US')!='US' or f.get('width','standard')!='standard'):return None
  if not float(f.get('min_price',0))*100<=price<=float(f.get('budget',10000))*100:return None
  expected={'material':'leather' if shoe else 'silk','color':'red','brand':'FORME Studio','fit':'regular','quality':'premium','style':'classic','occasion':'everyday'}
  if any(f.get(k) and f[k]!=v for k,v in expected.items()):return None
  if f.get('exclude_material') in expected['material'].split():return None
  base=next(p for p in self.products if p['category']==('shoes' if shoe else 'shirts'))
  p=dict(base);p.update(id='demo-red-'+kind,name='Red Leather Court Sneakers' if shoe else 'Red Silk Classic Tie',category='shoes' if shoe else 'ties',kind='sneakers' if shoe else 'tie',department='footwear' if shoe else 'accessories',gender='unisex',color='red',brand='FORME Studio',material=expected['material'],fit='regular',quality='premium',style='classic',occasion='everyday',price=price,stock={size:0},image_url='/assets/photos/demo-red-'+('shoes' if shoe else 'tie')+'.png',image_note='Studio photograph of this red demo product',photo_color='red',construction='Red leather upper, red laces and white rubber sole' if shoe else 'Solid red woven silk, regular length',description='Red leather court sneakers' if shoe else 'Classic red silk necktie')
  p.update(model_code='DEMO-RED-COURT' if shoe else 'DEMO-RED-TIE',size_basis='US shoe' if shoe else 'One size · regular length',design_style='court sneakers' if shoe else 'classic necktie',image_alt='Red leather court sneakers with white soles' if shoe else 'Solid red silk necktie',image='shoes' if shoe else 'tie')
  if any(f.get(k) and f[k]!=p[k] for k in ('category','kind','design_style')):return None
  return {'product':p['id'],'size':size,'filters':f,'name':p['name'],'color':'red','price_cents':price,'image':p['image_url'],'template':p}
