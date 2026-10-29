"""Direct FORME website shopping. Website-issued sessions; no payment integration."""
import hashlib,secrets,time,json,re,html
from datetime import datetime,timezone
from http.cookies import SimpleCookie
from urllib.parse import parse_qs,urlencode
from starlette.responses import RedirectResponse
E=html.escape
GUEST='__Host-thread3_forme_guest';ACCOUNT='__Host-thread3_forme_account'
RETURNS={'/shop/preferences','/shop','/shop/cart','/shop/checkout','/shop/account'}
class Commerce:
 def __init__(self,store):
  self.store=store;self.db=store.memory.db
  self.db.executescript('''CREATE TABLE IF NOT EXISTS storefront_sessions(token_hash TEXT PRIMARY KEY,account_id TEXT,csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS storefront_carts(owner TEXT PRIMARY KEY,data TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0,delivery TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS storefront_reviews(id TEXT PRIMARY KEY,owner TEXT NOT NULL,data TEXT NOT NULL);
''');self.db.commit()
  self.db.execute('CREATE TABLE IF NOT EXISTS cart_add_receipts(owner TEXT NOT NULL,add_id TEXT NOT NULL,PRIMARY KEY(owner,add_id))');self.db.commit()
  self.authdb=store.accounts.db
  self.authdb.executescript('CREATE TABLE IF NOT EXISTS storefront_sessions(token_hash TEXT PRIMARY KEY,account_id TEXT,csrf TEXT NOT NULL,expires REAL NOT NULL);CREATE TABLE IF NOT EXISTS identity_migrations(name TEXT PRIMARY KEY);')
  if not self.authdb.execute("SELECT 1 FROM identity_migrations WHERE name='legacy-store-sessions'").fetchone():
   self.authdb.executemany('INSERT OR IGNORE INTO storefront_sessions VALUES(?,?,?,?)',self.db.execute('SELECT * FROM storefront_sessions').fetchall())
   self.authdb.execute("INSERT INTO identity_migrations VALUES('legacy-store-sessions')")
  self.authdb.commit()
  self.authdb.execute('CREATE TABLE IF NOT EXISTS delivery_addresses(account TEXT PRIMARY KEY,data TEXT NOT NULL)')
  for number in range(1,101):
   account=f'forme_customer_{number:03}';cart=self.cart('account:'+account)
   address=cart['delivery'] or next((o['delivery'] for o in reversed(list(store.orders.values())) if o.get('account_id')==account and o.get('delivery')),None)
   address=address or dict(name=f'Synthetic Customer {number:03}',email=f'customer{number:03}@forme.local',address=f'{1000+number} Example Lane, Demo Apt {number:03}',city='Example City',postal='00000',country='US',synthetic=True)
   self.authdb.execute('INSERT OR IGNORE INTO delivery_addresses VALUES(?,?)',(account,json.dumps(address)))
  self.authdb.commit()
 def address(self,account):
  row=self.authdb.execute('SELECT data FROM delivery_addresses WHERE account=?',(account,)).fetchone();return json.loads(row[0]) if row else {}

 def digest(self,token):return hashlib.sha256(token.encode()).hexdigest()
 def cookies(self,r):
  c=SimpleCookie();c.load(r.headers.get('cookie',''));return {k:v.value for k,v in c.items()}
 def lookup(self,token):
  if not token:return None
  row=self.authdb.execute('SELECT account_id,csrf,expires FROM storefront_sessions WHERE token_hash=?',(self.digest(token),)).fetchone()
  if not row or row[2]<=time.time():return None
  return dict(account=row[0],csrf=row[1],hash=self.digest(token),owner='account:'+row[0] if row[0] else 'guest:'+self.digest(token))
 def session(self,r):
  c=self.cookies(r);account=self.lookup(c.get(ACCOUNT))
  if account and account['account']:return account
  guest=self.lookup(c.get(GUEST));return guest if guest and not guest['account'] else None
 def account(self,r):
  session=self.session(r);return session['account'] if session else None
 def create(self,account=None):
  token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);age=14*86400 if account else 30*86400
  self.authdb.execute('INSERT INTO storefront_sessions VALUES(?,?,?,?)',(self.digest(token),account,csrf,time.time()+age));self.authdb.commit();return token,self.lookup(token),age
 def cart(self,owner):
  row=self.db.execute('SELECT data,revision,delivery FROM storefront_carts WHERE owner=?',(owner,)).fetchone()
  return dict(lines=json.loads(row[0]),revision=row[1],delivery=json.loads(row[2])) if row else dict(lines=[],revision=0,delivery={})
 def add_seen(self,owner,add_id):return bool(add_id and self.db.execute('SELECT 1 FROM cart_add_receipts WHERE owner=? AND add_id=?',(owner,add_id)).fetchone())
 def save_cart(self,owner,lines,delivery=None,add_id=None):
  old=self.cart(owner);delivery=old['delivery'] if delivery is None else delivery
  with self.db:
   if add_id:
    if not re.fullmatch('[a-f0-9]{32}',add_id):raise ValueError('Invalid add operation.')
    if not self.db.execute('INSERT OR IGNORE INTO cart_add_receipts VALUES(?,?)',(owner,add_id)).rowcount:return
   self.db.execute('INSERT INTO storefront_carts VALUES(?,?,?,?) ON CONFLICT(owner) DO UPDATE SET data=excluded.data,revision=excluded.revision,delivery=excluded.delivery',(owner,json.dumps(lines),old['revision']+1,json.dumps(delivery)))

 def own_order(self,order,account):return bool(account and (order.get('account_id')==account or order.get('customer')=='usr_'+account))
 def total(self,items):return sum(x['price']*x.get('quantity',1) for x in items)
 def quantity(self,value):
  if not re.fullmatch(r'[1-9]|10',str(value or '')):raise ValueError('Choose a quantity from 1 to 10.')
  return int(value)
 def merged(self,lines,extra):
  result=[dict(x) for x in lines]
  for x in extra:
   old=next((p for p in result if p['id']==x['id'] and p['size']==x['size']),None)
   if old:old['quantity']=old.get('quantity',1)+x.get('quantity',1)
   else:result.append(dict(x))
  return result
 def summary(self,items):
  total=self.total(items)
  return f'<div class="order-totals"><p>Subtotal <strong>${total/100:.2f}</strong></p><p>Delivery <span>Included</span></p><p>Tax <span>Included</span></p><p class="grand-total">Total <strong data-bag-total="{total}">${total/100:.2f}</strong></p></div>'
 def delivery_fields(self,values):
  labels=[('name','Full name','name'),('email','Email address','email'),('address','Address','street-address'),('city','City','address-level2'),('postal','Postal code','postal-code')]
  fields=''.join(f'<label>{label}<input name="{k}" value="{E(values.get(k,""))}" type="{"email" if k=="email" else "text"}" autocomplete="{auto}" required maxlength="{254 if k=="email" else 180 if k=="address" else 100}"></label>' for k,label,auto in labels)
  fields+='<label>Country<select name="country">'+''.join(f'<option value="{k}" {"selected" if values.get("country","US")==k else ""}>{label}</option>' for k,label in [('US','United States'),('CA','Canada'),('GB','United Kingdom'),('IN','India'),('AU','Australia')])+'</select></label>'
  return fields
 def validate_delivery(self,f):
  values={k:f.get(k,'').strip() for k in ('name','email','address','city','postal','country')}
  for k,limit in [('name',100),('email',254),('address',180),('city',100),('postal',20)]:
   if not 2<=len(values[k])<=limit or any(ord(c)<32 for c in values[k]):raise ValueError('Please complete every contact and delivery field.')
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',values['email']):raise ValueError('Enter a valid email address.')
  if values['country'] not in {'US','CA','GB','IN','AU'}:raise ValueError('Choose a supported country.')
  return values
 def receipt(self,order):
  items=order['items'];delivery=order.get('delivery',{})
  detail='<p>'+E(delivery.get('name',''))+'<br>'+E(delivery.get('address',''))+'<br>'+E(' · '.join(delivery.get(k,'') for k in ('city','postal','country')))+'</p>' if delivery else ''
  return '<section class="receipt-page"><div class="receipt-heading"><span class="confirmation-mark">✓</span><p class="eyebrow">THANK YOU FOR CHOOSING FORME</p><h1>Your order is confirmed.</h1><p data-receipt>Order '+E(order['reference'])+'</p><p>Your selections are saved in your account.</p></div><div class="checkout-columns"><section class="commerce-panel">'+self.store.rows(items)+self.summary(items)+'</section><aside class="commerce-panel"><p class="eyebrow">DELIVERY DETAILS</p>'+detail+'<p>No payment has been collected.</p><a class="button" href="/shop">Continue exploring</a><p><a href="/shop/account">View your account →</a></p></aside></div></section>'
 async def handle(self,r):
  from store import page
  path=r.url.path
  routes={'/shop/login','/shop/login-success','/shop/logout','/shop/account','/shop/cart','/shop/cart/update','/shop/cart/remove','/shop/clear','/shop/checkout','/shop/shipping','/shop/review','/shop/receipt','/shop/context','/shop/preferences'}
  if path not in routes and not path.startswith('/shop/product/'):return None
  state=self.session(r);new_cookie=None
  if not state:
   token,state,age=self.create();new_cookie=(GUEST,token,age)
  account=state['account'];signed=bool(account);csrf=f'<input type="hidden" name="csrf" value="{state["csrf"]}">'
  def finish(response):
   if new_cookie:response.set_cookie(new_cookie[0],new_cookie[1],max_age=new_cookie[2],secure=True,httponly=True,samesite='lax',path='/')
   return response
  def render(body,kind='cart',status=200):return finish(page(body,kind,signed,status))
  def error(message,status=400):return render(f'<section class="panel"><p class="eyebrow">LET’S TAKE ANOTHER LOOK</p><h1>One small adjustment.</h1><p data-error>{E(message)}</p><a class="button" href="/shop/cart">Return to your bag</a></section>','error',status)
  def redirect(dest):return finish(RedirectResponse(dest,303))
  def login_url(dest):return '/shop/login?'+urlencode({'return_to':dest})
  cart=self.cart(state['owner'])
  f={}
  if r.method=='POST':
   if r.headers.get('origin')!=self.store.shop.config.base:return error('Invalid form origin.',403)
   if r.headers.get('content-type','').split(';')[0]!='application/x-www-form-urlencoded':return error('Website form required.',415)
   body=await r.body()
   if len(body)>8192:return error('Form too large.',413)
   try:vals=parse_qs(body.decode(),keep_blank_values=True)
   except UnicodeError:return error('Invalid form.')
   if any(len(v)!=1 for k,v in vals.items() if not (path=='/shop/preferences' and k in ('pref_colors','pref_excluded_colors','pref_brands'))):return error('Invalid form.')
   f={k:(v if path=='/shop/preferences' and k in ('pref_colors','pref_excluded_colors','pref_brands') else v[0]) for k,v in vals.items()}
   if not secrets.compare_digest(f.get('csrf',''),state['csrf']):return error('Please reload this page and try again.',403)
  elif r.method!='GET':return error('Method not allowed.',405)
  cart=self.cart(state['owner']) # Re-read after awaiting the form body; never overwrite another session's edit.
  if path=='/shop/login':
   dest=f.get('return_to') if r.method=='POST' else r.query_params.get('return_to','/shop/account')
   if dest not in RETURNS:return error('Invalid return destination.')
   if signed:return redirect(dest)
   problem=''
   if r.method=='POST':
    identity=self.store.accounts.authenticate(f.get('email',''),f.get('password',''))
    if not identity:problem='Please check your email address and password.'
    else:
     account=identity['id'];token,next_state,age=self.create(account)
     target=self.cart(next_state['owner']);self.save_cart(next_state['owner'],self.merged(target['lines'],cart['lines']))
     self.db.execute('DELETE FROM storefront_carts WHERE owner=?',(state['owner'],));self.authdb.execute('DELETE FROM storefront_sessions WHERE token_hash=?',(state['hash'],));self.authdb.commit();self.db.commit()
     self.store.context.ensure(account)
     if cart['lines']:self.store.context.activity(account,'cart_associated',self.store.products,items=cart['lines'])
     response=RedirectResponse('/shop/login-success?'+urlencode({'return_to':dest}),303);response.set_cookie(ACCOUNT,token,max_age=age,secure=True,httponly=True,samesite='lax',path='/');response.delete_cookie(GUEST,path='/',secure=True,httponly=True,samesite='lax');return response
   body=f'<section class="login-card"><p class="eyebrow">YOUR WARDROBE, WAITING</p><h1>Welcome to FORME.</h1><p>Sign in to save your bag and keep your orders together.</p><p class="form-error" role="alert">{E(problem)}</p><form data-shop-action="login" method="post">{csrf}<input type="hidden" name="return_to" value="{E(dest)}"><label>Email address<input type="email" name="email" value="{E(f.get("email",""))}" placeholder="customer001@forme.local" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><button>Sign in</button></form><p class="login-help">Collection access: customer001–customer100@forme.local · wardrobe</p><a href="/shop/cart">Back to your bag →</a></section>'
   return render(body,'signin',401 if problem else 200)
  if path=='/shop/login-success':
   if not signed:return redirect(login_url('/shop/account'))
   dest=r.query_params.get('return_to','/shop/account')
   if dest not in RETURNS:return error('Invalid return destination.')
   return render(f'<section class="login-card"><span class="confirmation-mark">✓</span><h1>Welcome back.</h1><p>You’re signed in. Your bag is ready.</p><a class="button" data-login-return href="{E(dest)}">Continue shopping</a></section>','signin-success')
  if path=='/shop/logout' and r.method=='POST':
   self.authdb.execute('DELETE FROM storefront_sessions WHERE token_hash=?',(state['hash'],));self.authdb.commit();self.db.commit()
   response=RedirectResponse('/shop',303);response.delete_cookie(ACCOUNT,path='/',secure=True,httponly=True,samesite='lax');response.delete_cookie(GUEST,path='/',secure=True,httponly=True,samesite='lax');return response
  if path=='/shop/preferences' and (r.method=='GET' or 'revision' in f):
   if not signed:return redirect(login_url('/shop/preferences'))
   from preferences_page import render as pref_render,save as pref_save
   message='Preferences saved.' if r.query_params.get('saved')=='1' else '';bad=False
   if r.method=='POST':
    try:
     pref_save(self.store.context,account,self.store.products,f)
     return redirect('/shop/preferences?saved=1')
    except ValueError as exc:message=str(exc);bad=True
   return render(pref_render(self.store.products,self.store.context.get(account),state['csrf'],message,bad),'preferences',400 if bad else 200)
  if path=='/shop/preferences' and r.method=='POST':
   if not signed:return error('Sign in to remember your preferences.',401)
   if set(f)!={'csrf','preferences'}:return error('Invalid preference form.')
   try:self.store.context.update(account,json.loads(f['preferences']))
   except (ValueError,TypeError):return error('Choose valid shopping preferences.')
   return redirect('/shop/account')
  if path in ('/shop/account','/shop/context'):
   if not signed:
    expired=bool(self.cookies(r).get('__Host-thread3_poppy_session'))
    return render(f'<section class="panel" data-account-status="{"expired" if expired else "signed_out"}" data-account-id=""><p class="eyebrow">YOUR FORME</p><h1>A wardrobe of your own.</h1><p>Not signed in to FORME in this browser.</p><a class="button" data-login-popup href="{login_url("/shop/account")}">Sign in</a></section>','account',401 if path=='/shop/context' else 200)
   from data import NAMES
   account_number=int(account.rsplit('_',1)[1]);profile={'name':NAMES[(account_number-1)%len(NAMES)]};orders=[o for o in self.store.orders.values() if self.own_order(o,account)]
   history=''.join(f'<a class="order-history" href="/shop/receipt?review={E(o["review_id"])}"><span>{E(o["reference"])} · {sum(x.get("quantity",1) for x in o["items"])} items</span><strong>${o["total"]/100:.2f} →</strong></a>' for o in orders[-10:][::-1]) or '<p>Your orders will appear here.</p>'
   prefs=(self.store.context.get(account) or {}).get('preferences',{});summary=', '.join(k.replace('_',' ')+': '+str(v['value']) for k,v in prefs.items()) or 'No preferences shared yet.'
   return render(f'<section class="account-page" data-account-status="signed_in" data-account-id="{E(account)}"><p class="eyebrow">YOUR FORME</p><h1>Hello, {E(profile["name"].split(" · ")[0])}.</h1><p>customer{int(account.rsplit("_",1)[1]):03}@forme.local</p><div class="checkout-columns"><section class="commerce-panel"><h2>Your orders</h2>{history}</section><aside class="commerce-panel"><h2>Your preferences</h2><a href="/shop/preferences">Edit my preferences →</a><p data-context-summary>{E(summary)}</p><p><a href="/shop/cart">Open your saved bag →</a></p><form data-shop-action="logout" method="post" action="/shop/logout">{csrf}<button class="quiet-button">Sign out</button></form></aside></div></section>','account')
  if path.startswith('/shop/product/') and r.method=='GET':
   product=self.store.by_id.get(path.split('/')[-1]);return render(self.store.card(product,csrf,True),'detail') if product else error('Product not found.',404)
  if r.method=='POST' and path in ('/shop/cart','/shop/cart/update','/shop/cart/remove','/shop/clear'):
   if f.get('cart_revision') is not None and str(cart['revision'])!=f['cart_revision']:return error('Your bag changed in another session. Reload before editing.',409)
   if path=='/shop/cart' and self.add_seen(state['owner'],f.get('add_id')):return redirect('/shop/cart')
   lines=[dict(x) for x in cart['lines']]
   try:
    if path=='/shop/clear':lines=[]
    elif path=='/shop/cart':
     if f.get('expected_price') is not None and str(self.store.by_id.get(f.get('product'),{}).get('price'))!=f['expected_price']:raise ValueError('The price changed. Review this item again before adding.')
     item=dict(id=f.get('product'),size=f.get('size'),quantity=self.quantity(f.get('quantity','1')))
     lines=self.merged(lines,[item]);self.store.items(lines)
     if len(lines)>30:raise ValueError('Your bag can hold up to 30 different selections.')
    else:
     index=next((i for i,x in enumerate(lines) if x['id']==f.get('product') and x['size']==f.get('old_size')),None)
     if index is None:raise ValueError('This item is no longer in your bag. Reload and try again.')
     old=lines.pop(index)
     if path=='/shop/cart/update':
      item=dict(id=old['id'],size=f.get('size'),quantity=self.quantity(f.get('quantity')));self.store.items([item]);lines=self.merged(lines,[item]);self.store.items(lines)
    self.save_cart(state['owner'],lines,add_id=f.get('add_id') if path=='/shop/cart' else None)
    if account:
     kind={'/shop/cart':'cart_add','/shop/cart/update':'cart_update','/shop/cart/remove':'cart_remove','/shop/clear':'cart_clear'}[path]
     observed=[item] if path in ('/shop/cart','/shop/cart/update') else [old] if path=='/shop/cart/remove' else cart['lines']
     self.store.context.activity(account,kind,self.store.products,items=observed)
   except ValueError as exc:return error(str(exc),409)
   return redirect('/shop/cart')
  if path=='/shop/cart' and r.method=='GET':
   if not cart['lines']:return render('<section class="panel empty"><p class="eyebrow">YOUR BAG</p><h1>A little room for something good.</h1><p>Your bag is empty.</p><a class="button" href="/shop">Explore the collection</a></section>')
   rows='';raw_total=0
   for item in cart['lines']:
    p=self.store.by_id[item['id']];qty=item.get('quantity',1);raw_total+=p['price']*qty;stock=p['stock'].get(item['size'],0)
    options=''.join(f'<option value="{E(size)}" {"selected" if size==item["size"] else ""} {"disabled" if n<1 and size!=item["size"] else ""}>{E(size)}{" — sold out" if n<1 else ""}</option>' for size,n in p['stock'].items())
    hidden=csrf+f'<input type="hidden" name="cart_revision" value="{cart["revision"]}"><input type="hidden" name="product" value="{E(p["id"])}"><input type="hidden" name="old_size" value="{E(item["size"])}">'
    warning='<p class="form-error">Please adjust this quantity; only '+str(stock)+' available.</p>' if stock<qty or qty>10 else ''
    rows+=f'<article class="bag-item" data-cart-item data-product-id="{E(p["id"])}" data-color="{E(p["color"])}" data-name="{E(p["name"])}" data-size="{E(item["size"])}" data-quantity="{qty}" data-price="{p["price"]}"><a href="/shop/product/{p["id"]}"><img src="{E(p["image_url"])}" alt="{E(p["image_alt"] if "image_alt" in p else p["name"])}"></a><div><p class="eyebrow">{E(p["brand"])} / {E(p["color"])}</p><h2>{E(p["name"])}</h2><p>${p["price"]/100:.2f} each</p>{warning}<form class="bag-edit" data-shop-action="cart-update" method="post" action="/shop/cart/update">{hidden}<label>Size · {E(p["size_basis"])}<select name="size">{options}</select></label><label>Quantity<input name="quantity" type="number" min="1" max="10" value="{qty}" required></label><button>Update</button></form><form method="post" action="/shop/cart/remove" data-shop-action="cart-remove">{hidden}<button class="text-button">Remove</button></form></div><strong>${p["price"]*qty/100:.2f}</strong></article>'
   summary=self.summary([dict(price=raw_total,quantity=1)])
   return render('<section class="bag-page"><p class="eyebrow">GOOD CHOICES, TOGETHER</p><h1>Your bag.</h1><div class="checkout-columns"><section>'+rows+'<p><a href="/shop">← Continue shopping</a></p></section><aside class="commerce-panel sticky-summary"><h2>Order summary</h2>'+summary+'<a class="button full" href="/shop/checkout">Continue to checkout</a><p class="small-note">Review every detail before confirming.</p></aside></div></section>')
  if path in ('/shop/checkout','/shop/shipping','/shop/review','/shop/receipt'):
   if not signed:
    if r.method=='POST':return error('Sign in to continue. Your bag is saved.',401)
    if self.cookies(r).get('__Host-thread3_poppy_session'):return error('Your shopping session has expired. Return to your stylist to reconnect.',401)
    return render(f'<section class="login-card"><p class="eyebrow">ONE STEP CLOSER</p><h1>Make it yours.</h1><p>Sign in to continue. Your bag will be waiting.</p><a class="button full" data-login-popup href="{login_url("/shop/checkout")}">Sign in to checkout</a><p><a href="/shop/cart">Back to your bag</a></p></section>','checkout-signin')
   review_id=f.get('review','') if r.method=='POST' else r.query_params.get('review','')
   existing=self.store.orders.get(review_id)
   if existing and self.own_order(existing,account):
    if existing.get('memory_schema')==1:self.store.context.activity(account,'purchase_completed',self.store.products,items=existing['items'],event_id=existing['review_id'])
    return render(self.receipt(existing),'receipt')
   if path=='/shop/receipt':return error('Order not found.',404)
   if path=='/shop/checkout' and r.method=='POST':
    row=self.db.execute('SELECT owner,data FROM storefront_reviews WHERE id=?',(review_id,)).fetchone()
    if not row or row[0]!=state['owner'] or f.get('approved')!='yes':return error('Review and confirm your current bag.',409)
    review=json.loads(row[1])
    try:items=self.store.items(cart['lines'])
    except ValueError as exc:return error(str(exc),409)
    if review['revision']!=cart['revision'] or review['items']!=items or review['delivery']!=cart['delivery']:return error('Your bag or delivery details changed. Review again.',409)
    order=dict(review_id=review_id,items=items,total=self.total(items),reference='FM-'+secrets.token_hex(4).upper(),customer='usr_'+account,account_id=account,delivery=review['delivery'],created_at=datetime.now(timezone.utc).isoformat(),fictional=True,channel='storefront',currency='USD',status='Confirmed',memory_schema=1)
    # One SQLite transaction commits the order and empties the cart; review ID is unique.
    with self.db:
     self.db.execute('INSERT INTO orders VALUES(?,?)',(review_id,json.dumps(order)))
     self.db.execute("UPDATE storefront_carts SET data='[]',delivery='{}',revision=revision+1 WHERE owner=?",(state['owner'],))
    self.store.orders[review_id]=order
    self.store.context.activity(account,'purchase_completed',self.store.products,items=items,event_id=review_id)
    for item in items:self.store.by_id[item['id']]['stock'][item['size']]-=item['quantity']
    return redirect('/shop/receipt?'+urlencode({'review':review_id}))
   if path=='/shop/review' and r.method=='GET':
    row=self.db.execute('SELECT owner,data FROM storefront_reviews WHERE id=?',(review_id,)).fetchone()
    if not row or row[0]!=state['owner']:return error('Review not found.',404)
    review=json.loads(row[1])
    if review['revision']!=cart['revision']:return error('Your bag changed. Review it again.',409)
    d=review['delivery'];address='<p>'+E(d['name'])+'<br>'+E(d['address'])+'<br>'+E(d['city']+' · '+d['postal']+' · '+d['country'])+'</p><p>'+E(d['email'])+'</p>'
    return render(f'<section class="review-page" data-review="{review_id}" data-revision="{review["revision"]}" data-total="{review["total"]}"><p class="eyebrow">02 / FINAL REVIEW</p><h1>Everything, just right.</h1><p data-summary>{len(review["items"])} selections · Total ${review["total"]/100:.2f}. Delivery and tax included.</p><div class="checkout-columns"><section class="commerce-panel">{self.store.rows(review["items"])}<a href="/shop/cart">Edit your bag →</a><hr><h2>Delivery details</h2>{address}<a href="/shop/checkout">Edit delivery details →</a></section><aside class="commerce-panel sticky-summary"><h2>Your total</h2>{self.summary(review["items"])}<p class="small-note">No card details are required. No payment is collected online.</p><form method="post" data-shop-action="checkout" action="/shop/checkout">{csrf}<input type="hidden" name="review" value="{review_id}"><button class="full" name="approved" value="yes">Confirm order</button></form></aside></div></section>','review')
   try:items=self.store.items(cart['lines'])
   except ValueError as exc:return error(str(exc),409)
   if not items:return redirect('/shop/cart')
   if path=='/shop/checkout' and r.method=='GET':self.store.context.activity(account,'checkout_started',self.store.products,items=items)
   values=cart['delivery'] or self.address(account);problem=''
   if path=='/shop/shipping' and r.method=='POST':
    try:
     values=self.validate_delivery(f);self.authdb.execute('INSERT INTO delivery_addresses VALUES(?,?) ON CONFLICT(account) DO UPDATE SET data=excluded.data',(account,json.dumps(values)));self.authdb.commit();self.save_cart(state['owner'],cart['lines'],values);cart=self.cart(state['owner'])
     self.store.context.activity(account,'checkout_reviewed',self.store.products,items=items)
     review_id=secrets.token_hex(16);review=dict(items=items,total=self.total(items),delivery=values,revision=cart['revision']);self.db.execute('INSERT INTO storefront_reviews VALUES(?,?,?)',(review_id,state['owner'],json.dumps(review)));self.db.commit();return redirect('/shop/review?'+urlencode({'review':review_id}))
    except ValueError as exc:problem=str(exc);values={k:f.get(k,'') for k in ('name','email','address','city','postal','country')}
   return render(f'<section class="shipping-page"><p class="eyebrow">01 / CONTACT & DELIVERY</p><h1>Where should it go?</h1><div class="checkout-columns"><section class="commerce-panel"><p class="form-error" role="alert">{E(problem)}</p><form method="post" action="/shop/shipping" data-shop-action="shipping">{csrf}<div class="address-fields">{self.delivery_fields(values)}</div><button>Continue to order review</button></form><p><a href="/shop/cart">← Back to your bag</a></p></section><aside class="commerce-panel sticky-summary"><h2>Your selections</h2>{self.store.rows(items)}{self.summary(items)}</aside></div></section>','shipping',400 if problem else 200)
  return error('Page not found.',404)
