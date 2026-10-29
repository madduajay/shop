import html,secrets,json,math,time,re
from datetime import datetime,timezone
from recommendations import effective_filters,safe_current
from http.cookies import SimpleCookie
from urllib.parse import parse_qs,urlencode
from starlette.responses import HTMLResponse,RedirectResponse
from personal_agent_protocol.company.service import WEB_COOKIE
from data import catalog
from catalog_search import FILTER_FIELDS,query_matches,facet_options
E=html.escape
CSS=PathCSS='''*{box-sizing:border-box}[hidden]{display:none!important}h1{font-family:Georgia;font-weight:normal}body{margin:0;color:#20251f;background:#fbfaf7;font:14px Arial,sans-serif}header{padding:26px 5%;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ddd}a{color:inherit;text-decoration:none}header b{font-size:26px;letter-spacing:5px}nav{display:flex;gap:28px}main{padding:30px 5%}.hero{background:#e6e7df;padding:42px;display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}.hero h1{font:52px Georgia;margin:12px 0}.hero img{width:40%;height:240px;object-fit:cover}.eyebrow{letter-spacing:3px;font-size:11px}.layout{display:grid;grid-template-columns:190px 1fr;gap:35px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}article img{width:100%;height:auto;aspect-ratio:5/6;object-fit:contain;background:#eee}h2{font:21px Georgia;margin:12px 0}label{display:block;margin:14px 0;font-size:12px}select,input{display:block;width:100%;padding:12px;border:1px solid #ccc;background:white;margin-top:6px}button,.button{background:#243c31;color:white;border:0;padding:13px 22px;cursor:pointer}button:disabled{opacity:.4}article p{color:#687068;font-size:12px}.detail{display:grid;grid-template-columns:1fr 1fr;gap:60px;max-width:1000px;margin:20px auto}.detail img{height:560px;width:100%;object-fit:contain}.panel{max-width:700px;margin:55px auto;background:white;padding:40px;border:1px solid #ddd}.price{float:right}small{color:#697568}footer{padding:40px 5%;border-top:1px solid #ddd;margin-top:40px;color:#687068}body[data-page="signin"] header nav,body[data-page="signin"] header small{display:none}body[data-page="signin"] header{justify-content:center}body[data-page="signin"] .panel{margin:20px auto;padding:32px;border-radius:14px}body[data-page="signin"] footer{display:none}.photo-note{font-size:11px!important;line-height:1.45;color:#5e665e!important}.pagination{display:flex;justify-content:space-between;align-items:center;padding:18px 0;margin-bottom:15px;border-block:1px solid #dedfd7}.pagination a{font-weight:bold}.compact{padding:30px 36px}.compact h1{font-size:44px}.compact img{height:200px;width:30%;object-fit:contain}.collections{flex-wrap:wrap;font-size:12px;margin-top:25px}.collections a{border-bottom:1px solid;padding-bottom:5px}.remove{margin:20px 0}.remove button{background:transparent;color:#526350;padding:0;text-decoration:underline}.reset{display:inline-block;margin-top:16px}.empty .button{display:inline-block;margin:18px 18px 0 0}@media(max-width:800px){header small{display:none}header img{width:110px}nav{gap:14px;font-size:12px}aside form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}aside label{margin:0}aside button{grid-column:1/-1}.grid{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.hero img{display:none}.detail{grid-template-columns:1fr}.hero h1{font-size:36px}}'''
from pathlib import Path
CSS+=Path(__file__).with_name('assets').joinpath('store-polish.css').read_text()
PAGE_SIZE=24
WAIST_CATEGORIES={'trousers','jeans','shorts'}
def page(body,kind='catalog',signed=False,status=200):
 return HTMLResponse(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FORME — Clothing & footwear</title><link rel="stylesheet" href="/assets/store.css"><script src="/assets/store.js" defer></script></head><body data-page="{kind}" data-signed-in="{str(signed).lower()}"><header><a href="/shop" aria-label="FORME home"><img width="140" src="/assets/logo.svg" alt="FORME"></a><nav aria-label="Main navigation"><a href="/shop?department=clothing">Clothing</a><a href="/shop?department=footwear">Footwear</a><a href="/shop/cart">Bag</a><a href="/shop/preferences">My preferences</a><a href="{'/shop/account' if signed else '/shop/login?return_to=/shop/account'}" {'' if signed else 'data-login-popup'}>{'Account' if signed else 'Sign in'}</a></nav><small>Considered essentials.</small></header><main>{body}</main><footer>FORME &nbsp; / &nbsp; Wear it your way. <small>Studio photography shared within matching style families.</small> <span class="price">Quality in every detail.</span></footer></body></html>',status_code=status,headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'",'Referrer-Policy':'same-origin','X-Frame-Options':'DENY'})
def filtered(products,f):
 lo=float(f.get('min_price') or 0);hi=float(f.get('budget') if f.get('budget') not in ('',None) else 100000)
 if not math.isfinite(lo) or not math.isfinite(hi) or lo<0 or hi<lo:raise ValueError('Enter a valid price range.')
 from color_constraints import color_filters,parse_colors
 included,excluded=color_filters(f)
 q=f.get('q','').lower().strip()
 query_colors=parse_colors(q)
 excluded |= set(query_colors['exclude'])
 if query_colors['exclude']:q=query_colors['search_text']
 def matches(p):
  if p['color'] in excluded or (included and p['color'] not in included):return False
  if any(f.get(k) and p[k]!=f[k] for k in FILTER_FIELDS):return False
  if not lo*100<=p['price']<=hi*100:return False
  if q and not query_matches(p,q):return False
  if f.get('exclude_material') and f['exclude_material'] in p['material'].split():return False
  size=f.get('size') or f.get('shoe_size' if p['category']=='shoes' else 'waist_size' if p['category'] in WAIST_CATEGORIES else 'apparel_size')
  if p['category']=='shoes' and f.get('width')=='wide':return False
  if size and (f.get('size_system') or 'US')!='US':return False
  return (p['stock'].get(size,0)>0) if size else any(n>0 for n in p['stock'].values())
 rows=[p for p in products if matches(p)]
 sort=f.get('sort','featured')
 if sort=='price-low':rows.sort(key=lambda p:(p['price'],p['id']))
 elif sort=='price-high':rows.sort(key=lambda p:(-p['price'],p['id']))
 elif sort=='name':rows.sort(key=lambda p:(p['name'],p['id']))
 else:
  preferred={k:f.get('prefer_'+k,'') for k in ('color','brand','material','quality','fit','occasion','style','design_style')}
  if any(preferred.values()):rows.sort(key=lambda p:tuple(bool(v and p[k] not in str(v).split(',')) for k,v in preferred.items()))
 return rows
class Store:
 def __init__(self,shop,memory,context,explainer,accounts=None):
  self.accounts=accounts
  self.shop=shop;self.memory=memory;self.context=context;self.explainer=explainer;self.products=catalog();self.by_id={p['id']:p for p in self.products};self.states={};self.guests={};self.orders={o['review_id']:o for o in memory.orders()}
  from commerce import Commerce
  self.commerce=Commerce(self)
  for o in self.orders.values():
   for x in o['items']:
    p=self.by_id.get(x['id'])
    if p and x['size'] in p['stock']:p['stock'][x['size']]=max(0,p['stock'][x['size']]-x.get('quantity',1))
  from availability import Availability
  self.availability=Availability(Path(context.path).with_name(Path(context.path).stem+'-availability.sqlite'),self.products)
  self.by_id.update({p['id']:p for p in self.products})
  for o in self.orders.values():
   for item in o['items']:
    p=self.by_id.get(item['id'])
    if p and p.get('availability_owner'):p['stock'][item['size']]=max(0,p['stock'].get(item['size'],0)-item.get('quantity',1))
  for order in self.orders.values():
   if order.get('memory_schema')==1:self.context.activity(order['account_id'],'purchase_completed',self.products,items=order['items'],event_id=order['review_id'])
 async def session(self,request):
  c=SimpleCookie();c.load(request.headers.get('cookie',''));m=c.get(WEB_COOKIE);s=await self.shop._web_session(m.value if m else None)
  if s:s=await self.shop._session_by_id(s.session_id)
  return s if s and self.shop._now()<s.expires_at and not await self.shop._signed_in_before_its_end(s) else None
 def new_state(self):return dict(csrf=secrets.token_urlsafe(24),cart=[],review=None,filters={})
 def items(self,cart):
  out=[];seen=set()
  for x in cart:
   p=self.by_id.get(x.get('id'));quantity=x.get('quantity',1);key=(x.get('id'),x.get('size'))
   if key in seen:raise ValueError('Duplicate size selection. Update the bag first.')
   seen.add(key)
   if type(quantity) is not int or not 1<=quantity<=10:raise ValueError('Choose a quantity from 1 to 10.')
   if not p or p['stock'].get(x.get('size'),0)<quantity:raise ValueError('This size or quantity is unavailable. Please adjust your bag.')
   out.append(dict(id=p['id'],name=p['name']+' · '+p['color'],size=x['size'],price=p['price'],quantity=quantity,color=p['color'],image_url=p.get('image_url')))
  return out
 def rows(self,items):
  rows=[]
  for x in items:
   p=self.by_id.get(x['id'],{});image=x.get('image_url') or p.get('image_url','');color=x.get('color') or p.get('color','Not recorded')
   photo=f'<img src="{E(image)}" alt="{E(x["name"]+" · "+color)}" width="72" height="84" style="object-fit:contain">' if image else '<span>Image unavailable</span>'
   rows.append(f'<div class="review-item" data-cart-item data-product-id="{E(x["id"])}" data-color="{E(color)}" data-name="{E(x["name"])}" data-size="{E(x["size"])}" data-price="{x["price"]}" data-quantity="{x.get("quantity",1)}">{photo}<span>{E(x["name"])}<small>Size {E(x["size"])} · {E(color)} · Quantity {x.get("quantity",1)}</small></span><strong>${x["price"]*x.get("quantity",1)/100:.2f}</strong></div>')
  return ''.join(rows)
 def card(self,p,csrf='',detail=False,explanation=None):
  options=''.join(f'<option value="{s}" data-stock="{n}" {"disabled" if n<1 else ""}>{s} {"— sold out" if n<1 else ""}</option>' for s,n in p['stock'].items())
  attrs=' '.join(f'data-{key.replace("_","-")}="{E(str(p[key]))}"' for key in ('color','brand','material','quality','fit','occasion','gender','department','category','kind','style','size_basis','photo_color','design_style','region'))
  photo_note=p.get('image_note','Representative photograph')
  image_alt=p.get('image_alt',p['color']+' '+p['name'])
  result=f'<article data-product="{p["id"]}" data-price="{p["price"]}" data-image="{E(p["image_url"])}" data-image-note="{E(photo_note)}" {attrs} class="{"detail" if detail else ""}"><a href="/shop/product/{p["id"]}"><img loading="lazy" decoding="async" width="500" height="600" src="{E(p["image_url"])}" alt="{E(image_alt)}"></a><div><p class="product-meta">{E(p["brand"].upper())} / {E(p["gender"].upper())} / {E(p["color"].upper())}</p><h2>{E(p["name"])}</h2><p data-description>{E(p["description"])}</p><strong>${p["price"]/100:.2f}</strong>'
  if explanation:
   result+=f'<p data-explanation data-explanation-source="{E(explanation["source"])}">{E(explanation["text"])}</p><small>{"FORME · GPT-grounded reasons" if explanation["source"]=="gpt-grounded" else "FORME · catalog-based reasons (GPT unavailable)"}</small>'
  if detail:
   result+='<p class="photo-note">Generated studio photography is shared within matching color and silhouette families. Style inspiration describes design influences, not manufacture or authenticity.</p>' if 'design' in p else ''
   result+=f'<p class="eyebrow">{E(p["model_code"])}</p><p>{E(p["construction"])}. {E(p["quality"].title())} quality, designed for {E(p["occasion"])}.</p><p>{E(p["care"])}</p><form method="post" action="/shop/cart">{csrf}<input type="hidden" name="add_id" value="{secrets.token_hex(16)}"><input type="hidden" name="expected_price" value="{p["price"]}"><input type="hidden" name="product" value="{p["id"]}"><label>Size · {E(p["size_basis"])}<select name="size">{options}</select></label><label>Quantity<input type="number" name="quantity" min="1" max="10" value="1" required></label><button>Add to bag</button></form><p><a href="/shop?gender={p["gender"]}&category={p["category"]}">Explore the collection →</a></p>'
  else:result+=f'<select name="size" hidden>{options}</select>'
  return result+'</div></article>'
 async def handle(self,r):
  self.availability.tick();self.by_id.update({p['id']:p for p in self.products})
  s=await self.session(r);path=r.url.path
  if not s:
   direct=await self.commerce.handle(r)
   if direct is not None:return direct
  account=s.account_id if s and s.signed_in else self.commerce.account(r) if not s else None
  signed=bool(account);new_guest=None
  state=self.states.setdefault(s.session_id,self.new_state()) if s else None
  if not s and path not in ('/shop/review','/shop/checkout'):
   c=SimpleCookie();c.load(r.headers.get('cookie',''));g=c.get('__Host-thread3_forme_guest');key=g.value if g else None
   old=self.guests.get(key)
   if old and old['expires']>time.time():state=old['state']
   elif path!='/shop':
    key=secrets.token_urlsafe(32);state=self.new_state();self.guests[key]=dict(state=state,expires=time.time()+86400);new_guest=key
  if s and account and state.get('account_bound')!=account:
   if state['cart']:self.context.activity(account,'cart_associated',self.products,items=state['cart'])
   state['account_bound']=account
  if s and account:
   shared_cart=self.commerce.cart('account:'+account);state['cart']=shared_cart['lines'];state['cart_revision']=shared_cart['revision']
  csrf=f'<input type="hidden" name="csrf" value="{state["csrf"]}">' if state else ''
  def finish(response):
   if new_guest:response.set_cookie('__Host-thread3_forme_guest',new_guest,max_age=86400,secure=True,httponly=True,samesite='lax',path='/')
   return response
  def error(msg,status=400):return finish(page(f'<section class="panel"><p data-error>{E(msg)}</p><a href="/shop">Continue shopping</a></section>','error',signed,status))
  if r.method=='POST':
   if not state:return error('Your shopping session has expired. Return to your stylist to reconnect.',401)
   if r.headers.get('origin')!=self.shop.config.base:return error('Invalid form origin.',403)
   if r.headers.get('content-type','').split(';')[0]!='application/x-www-form-urlencoded':return error('Website form required.',415)
   raw=await r.body()
   if len(raw)>8192:return error('Form too large.',413)
   vals=parse_qs(raw.decode(),keep_blank_values=True)
   if any(len(v)!=1 for k,v in vals.items() if not (path=='/shop/preferences' and k in ('pref_colors','pref_excluded_colors','pref_brands'))):return error('Invalid form.')
   f={k:(v if path=='/shop/preferences' and k in ('pref_colors','pref_excluded_colors','pref_brands') else v[0]) for k,v in vals.items()}
   if not secrets.compare_digest(f.get('csrf',''),state['csrf']):return error('Please reload this page.',403)
   if s and account:
    shared_cart=self.commerce.cart('account:'+account);state['cart']=shared_cart['lines'];state['cart_revision']=shared_cart['revision']
   if path=='/shop/availability':
    if not s or not signed or 'availability:watch' not in s.scopes:return error('Authorize availability notifications first.',403)
    owner=json.dumps([s.client_id,s.pairwise_user_id,account])
    if not re.fullmatch('[a-f0-9]{32}',f.get('consent','')):return error('Invalid notification consent.')
    if f.get('action')=='cancel':
     self.availability.cancel(owner,f['consent']);payload={'cancelled':True}
    elif f.get('action')=='subscribe':
     offer=state.get('availability_offer',{})
     if offer.get('id')!=f.get('offer') or offer.get('expires',0)<self.availability.now():return error('Notification offer expired.')
     try:watch=self.availability.subscribe(owner,f['consent'],offer['candidate'])
     except ValueError as e:return error(str(e))
     payload={'watch':{k:v for k,v in watch.items() if k!='owner'}}
    else:return error('Unsupported notification action.')
    return page('<pre data-availability>'+E(json.dumps(payload))+'</pre>','availability',signed)
   if path=='/shop/reset':
    if set(f)!={'csrf','request_id'} or not re.fullmatch('[a-f0-9]{32}',f.get('request_id','')):return error('Invalid request reset.')
    if signed:
     if 'preferences:write' not in s.scopes:return error('Authorize preference access to continue.',403)
     self.context.shared_intent(account)
     row=self.context.db.execute('SELECT data FROM shared_shopping_intents WHERE account_id=?',(account,)).fetchone()
     if row and json.loads(row[0]).get('request_id')==f['request_id']:
      value=json.loads(row[0]);value['expires_at']=0;value['values']={};self.context.db.execute('UPDATE shared_shopping_intents SET data=? WHERE account_id=?',(json.dumps(value),account));self.context.db.commit()
    state.update(review=None,filters={},explanations={})
    return page('<section data-context-reset="true"><h1>Ready for a fresh conversation.</h1><p>Your bag and lasting preferences are unchanged.</p></section>','context',signed)
   if path=='/shop/logout':
    if signed and s.account_id:
     await self.shop.disconnect(s.client_id,s.account_id)
     if self.accounts:self.accounts.db.execute('DELETE FROM authorization_logins WHERE account=?',(s.account_id,));self.accounts.db.commit()
    return RedirectResponse('/shop/account',303)
   if path=='/shop/preferences':
    if not signed or 'preferences:write' not in s.scopes:return error('Authorize preference editing before saving.',403)
    from preferences_page import save as pref_save,render as pref_render
    try:pref_save(self.context,account,self.products,f)
    except ValueError as exc:return page(pref_render(self.products,self.context.get(account),state['csrf'],str(exc),True),'preferences',signed,400)
    return RedirectResponse('/shop/preferences?saved=1',303)
   if path=='/shop/context':
    if not signed or not s.account_id:return error('Sign in to save FORME preferences.',401)
    if 'preferences:write' not in s.scopes:return error('Authorize preference access to continue.',403)
    if set(f) not in ({'csrf','preferences'},{'csrf','preferences','intent','update_id','metadata'}):return error('Only shopping memory updates are accepted.')
    try:
     if f.get('update_id'):self.context.accept_shared(s.account_id,json.loads(f['preferences']),json.loads(f.get('intent','{}')),f['update_id'],json.loads(f.get('metadata','{}')))
     else:
      if f.get('intent','{}')!='{}' or f.get('metadata','{}')!='{}':raise ValueError('Missing scoped update identity')
      self.context.update(s.account_id,json.loads(f['preferences']))
    except (ValueError,TypeError):return error('Invalid explicit preference update.')
    return RedirectResponse('/shop/context?saved=1',303)
   if path=='/shop/cart':
    if not signed or 'orders:write' not in s.scopes:return error('Sign in with FORME to add to your bag.',403)
    if not self.availability.allowed(f.get('product'),s):return error('This demo item belongs to another availability scenario.',403)
    if self.commerce.add_seen('account:'+account,f.get('add_id')):return finish(RedirectResponse('/shop/cart',303))
    try:
     if f.get('expected_price') is not None and str(self.by_id.get(f.get('product'),{}).get('price'))!=f['expected_price']:raise ValueError('The price changed. Review this item again before adding.')
     item=dict(id=f.get('product'),size=f.get('size'),quantity=self.commerce.quantity(f.get('quantity','1')))
     cart=self.commerce.merged(state['cart'],[item]);self.items(cart)
    except ValueError as exc:return error(str(exc),409)
    self.commerce.save_cart('account:'+account,cart,add_id=f.get('add_id'))
    state.update(cart=cart,review=None)
    if account:self.context.activity(account,'cart_add',self.products,items=[item])
    return finish(RedirectResponse('/shop/cart',303))
   if path in ('/shop/cart/update','/shop/cart/remove'):
    if not signed or 'orders:write' not in s.scopes:return error('Authorize bag changes first.',403)
    if str(state.get('cart_revision',0))!=f.get('cart_revision'):return error('Your bag changed. Reload it before editing.',409)
    try:
     cart=[dict(x) for x in state['cart']];index=next((i for i,x in enumerate(cart) if x['id']==f.get('product') and x['size']==f.get('old_size')),None)
     if index is None:raise ValueError('That variant is no longer in your bag.')
     old=cart.pop(index)
     if path.endswith('/update'):
      item=dict(id=old['id'],size=f.get('size'),quantity=self.commerce.quantity(f.get('quantity')));self.items([item]);cart=self.commerce.merged(cart,[item]);self.items(cart)
     self.commerce.save_cart('account:'+account,cart);state.update(cart=cart,review=None)
    except ValueError as exc:return error(str(exc),409)
    return finish(RedirectResponse('/shop/cart',303))
   if path=='/shop/clear':
    if account:self.context.activity(account,'cart_clear',self.products,items=state['cart'])
    if account:self.commerce.save_cart('account:'+account,[])
    state.update(cart=[],review=None);return finish(RedirectResponse('/shop/cart',303))
   if path=='/shop/review':
    try:items=self.items(state['cart'])
    except ValueError as e:return error(str(e),409)
    if not items:return error('Your bag is empty.',409)
    if account:
     self.context.activity(account,'checkout_started',self.products,items=state['cart'])
     self.context.activity(account,'checkout_reviewed',self.products,items=state['cart'])
    state['review']=dict(id=secrets.token_hex(16),revision=state.get('cart_revision',0),items=items,delivery=self.commerce.address(account) if account else {},total=sum(x['price']*x['quantity'] for x in items))
    return RedirectResponse('/shop/review',303)
   if path=='/shop/checkout':
    v=state['review']
    if not signed or 'orders:write' not in s.scopes:return error('Sign in to continue.',403)
    if not v or f.get('review')!=v['id'] or f.get('approved')!='yes':return error('Review and approve the current bag.',409)
    if v['id'] not in self.orders:
     try:items=self.items(state['cart'])
     except ValueError as e:return error(str(e),409)
     if v.get('delivery')!=self.commerce.address(account):return error('Delivery details changed. Review again.',409)
     if state.get('cart_revision',0)!=v['revision']:return error('Your bag changed. Review again.',409)
     if items!=v['items']:return error('Your bag changed. Review again.',409)
     order=dict(review_id=v['id'],items=items,total=v['total'],delivery=v['delivery'],reference='FM-'+secrets.token_hex(4).upper(),customer=s.pairwise_user_id,account_id=s.account_id,created_at=datetime.now(timezone.utc).isoformat(),currency='USD',status='Confirmed',fictional=True,memory_schema=1)
     with self.memory.db:
      self.memory.db.execute('INSERT INTO orders VALUES(?,?)',(order['review_id'],json.dumps(order)))
      self.memory.db.execute("UPDATE storefront_carts SET data='[]',revision=revision+1 WHERE owner=?",('account:'+account,))
     self.orders[v['id']]=order
     self.context.activity(account,'purchase_completed',self.products,items=items,event_id=v['id'])
     for x in items:self.by_id[x['id']]['stock'][x['size']]-=x['quantity']
     state['cart']=[]
    return RedirectResponse('/shop/review',303)
   return error('Unknown form.',404)
  if r.method!='GET':return error('Method not allowed.',405)
  if path=='/shop/question-context':
   if not s or not signed:return error('Authorize FORME information access first.',401)
   from context_qa import company_context
   try:
    if len(r.query_params.get('query',''))>4096:raise ValueError('Context request too large')
    result=company_context(self,s,json.loads(r.query_params.get('query','{}')))
   except PermissionError:return error('Authorize the requested FORME information.',403)
   except (ValueError,TypeError,KeyError):return error('Invalid read-only context request.')
   return page('<pre data-question-context>'+E(json.dumps(result))+'</pre>','question-context',signed)
  if account:self.context.ensure(account)
  if path=='/shop/account':
   account=s.account_id if signed else ''
   status='signed_in' if signed else 'signed_out' if s else 'expired'
   body=f'<section class="panel" data-account-status="{status}" data-account-id="{E(account)}"><h1>Your FORME account</h1><p>{("Signed in as "+E(account)) if signed else "Not signed in to FORME in this browser."}</p>'
   if signed:body+=f'<form method="post" data-shop-action="logout" action="/shop/logout">{csrf}<button>Sign out</button></form>'
   return finish(page(body+'</section>','account',signed))
  if path=='/shop/availability':
   if not s:return error('Open this feature in the controlled store browser.',401)
   payload={}
   if r.query_params.get('filters'):
    try:
     filters=json.loads(r.query_params['filters']);candidate=self.availability.candidate(filters)
    except (ValueError,TypeError,KeyError):return error('Unsupported availability constraints.')
    if candidate:
     offer={'id':secrets.token_hex(16),'candidate':candidate,'expires':self.availability.now()+600};state['availability_offer']=offer;payload={'candidate':candidate,'offer':offer['id']}
   elif r.query_params.get('events'):
    if not signed or 'availability:watch' not in s.scopes:return error('Authorize availability notifications first.',403)
    payload={'watches':self.availability.public(json.dumps([s.client_id,s.pairwise_user_id,account]))}
   body='<pre data-availability>'+E(json.dumps(payload))+'</pre>'
   if signed and 'availability:watch' in s.scopes:body+=f'<form method="post" data-shop-action="availability">{csrf}<input name="action"><input name="offer"><input name="consent"><button>Confirm availability notification</button></form>'
   return page(body,'availability',signed)
  if path=='/shop/orders':
   if not signed:return error('Sign in to view your FORME orders.',401)
   if s and 'orders:read' not in s.scopes:return error('Authorize order-history access to continue.',403)
   owned=[o for o in self.orders.values() if self.commerce.own_order(o,account)]
   body=f'<section class="purchase-history" data-orders-account="{E(account)}" data-orders-count="{len(owned)}"><p class="eyebrow">YOUR FORME</p><h1>Your orders.</h1><p>Purchase records from FORME, separate from Thread chat archives.</p>'
   for order in owned[-50:][::-1]:
    date=order.get('created_at') or 'Date not recorded';status=order.get('status') or 'Recorded';currency=order.get('currency','USD')
    body+=f'<article class="commerce-panel" data-history-order data-reference="{E(order["reference"])}" data-date="{E(date)}" data-status="{E(status)}" data-currency="{E(currency)}" data-total="{order["total"]}"><h2>{E(order["reference"])}</h2><p>{E(date)} · {E(status)} · {E(currency)} {order["total"]/100:.2f}</p>'
    for item in order['items']:
     product=self.by_id.get(item['id'],{});image=item.get('image_url') or product.get('image_url','');name=item.get('name') or product.get('name',item['id']);size=item.get('size','Not recorded');quantity=item.get('quantity',1)
     body+=f'<div data-history-item data-product-id="{E(item["id"])}" data-color="{E(item.get("color") or product.get("color","Not recorded"))}" data-price="{item.get("price", "")}" data-name="{E(name)}" data-size="{E(size)}" data-quantity="{quantity}"><img src="{E(image)}" data-verified-image="{E(image)}" width="70" alt="{E(name)}"><span>{E(name)} · Size {E(size)} · Quantity {quantity}</span></div>'
    body+='</article>'
   if not owned:body+='<p data-orders-empty>No orders found for this FORME account.</p>'
   return page(body+'</section>','orders',signed)
  if path=='/shop/preferences' and r.method=='GET':
   if not signed:return error('Sign in to view FORME preferences.',401)
   if not set(s.scopes)&{'preferences:read','preferences:write'}:return error('Authorize preference access to continue.',403)
   from preferences_page import render as pref_render
   body=pref_render(self.products,self.context.get(account),state['csrf'],'Preferences saved.' if r.query_params.get('saved')=='1' else '')
   if 'preferences:write' not in s.scopes:body='<p>This connection can view preferences. Open FORME in your own browser to edit them.</p><fieldset disabled>'+body+'</fieldset>'
   return page(body,'preferences',signed)
  if path=='/shop/context':
   if not signed or not s.account_id:return error('Sign in to view FORME preferences.',401)
   if not set(s.scopes)&{'preferences:read','preferences:write'}:return error('Authorize preference access to continue.',403)
   record=self.context.get(s.account_id) or {'preferences':{}}
   summary=', '.join(k.replace('_',' ')+': '+str(v['value']) for k,v in record['preferences'].items()) or 'No preferences shared yet.'
   body='<section class="panel"><h1>Your FORME preferences</h1><p data-context-summary>'+E(summary)+'</p><p>Lasting preferences, current requests and observed shopping activity are stored separately for your account.</p>'
   envelope=self.context.shared_intent(account,r.query_params.get('request_id'))
   payload={'source':'FORME','revision':__import__('preferences_page').revision(record),'updated_at':record.get('updated_at'),'lasting_preferences':{k:v['value'] for k,v in record['preferences'].items()},'temporary_constraints':None,'inferred_interests':{'status':'loaded','values':self.context.behavior(account)['inferred_interests']}}
   if envelope:payload['temporary_constraints']={'scope':'request','request_id':r.query_params['request_id'],'expires_at':datetime.fromtimestamp(envelope['expires_at'],timezone.utc).isoformat(),'source':envelope['source'],'values':envelope['current_request']}
   body+='<pre data-preferences-json>'+E(json.dumps(payload,indent=2,ensure_ascii=False))+'</pre>'
   if r.query_params.get('saved')=='1':body+='<p data-context-saved>Preferences saved by FORME.</p>'
   if 'preferences:write' in s.scopes:body+=f'<form data-shop-action="context" method="post" action="/shop/context">{csrf}<input type="hidden" name="preferences" value="{{}}"><input type="hidden" name="intent" value="{{}}"><input type="hidden" name="update_id" value=""><input type="hidden" name="metadata" value="{{}}"><button>Save shared preferences</button></form>'
   return page(body+'</section>','context',signed)
  if path=='/shop/reset' and s:
   return page('<form data-shop-action="reset-context" method="post">'+csrf+'<input type="hidden" name="request_id"><button>Reset request context</button></form>','context',signed)
  if path=='/shop':
   received=dict(r.query_params);expired=False
   if received.get('expires_at'):
    if not received['expires_at'].isdigit() or int(received['expires_at'])>time.time()+172860:return error('Invalid search lifetime.')
    if int(received['expires_at'])<=time.time():received={};expired=True
   if received.get('request_id') and not re.fullmatch('[a-f0-9]{32}',received['request_id']):return error('Invalid search identity.')
   received['request_id']=received.get('request_id') or secrets.token_hex(16);received['expires_at']=received.get('expires_at') or str(int(time.time())+3600)
   from recommendations import request_context
   envelope=self.context.shared_intent(account,received['request_id']) if account and not expired and received.get('reset')!='1' and received.get('preference_source')!='thread' else None
   if envelope:received['expires_at']=str(min(int(received['expires_at']),envelope['expires_at']))
   received=request_context(received,envelope)
   saved={k:v['value'] for k,v in (self.context.get(account) or {}).get('preferences',{}).items()} if account else {}
   behavior=self.context.behavior(account) if account else {}
   if s and received.get('preference_source')=='thread':saved={};behavior={}
   f=effective_filters(received,{} if received.get('reset')=='1' else saved,{} if received.get('reset')=='1' else behavior)
   if state:state['filters']=received
   try:products=filtered([p for p in self.products if not p.get('availability_owner')],f);number=max(1,int(f.get('page','1')))
   except ValueError:return error('Enter a valid price range and page number.')
   if account:self.context.observe_filters(account,received,self.products)
   pages=max(1,math.ceil(len(products)/PAGE_SIZE));number=min(number,pages);start=(number-1)*PAGE_SIZE;visible=products[start:start+PAGE_SIZE]
   explanations={}
   if s and f.get('explain')=='1' and visible:
    current=safe_current(received,self.products)
    cache_key=json.dumps([current,saved,behavior,[{k:p[k] for k in ('id','price','stock')} for p in visible]],sort_keys=True)
    cached=state.get('explanations',{})
    if cached.get('key')==cache_key:explanations=cached['values']
    else:
     explanations=await self.explainer.explain(visible,current,saved,f,behavior)
     state['explanations']={'key':cache_key,'values':explanations}
   labels={'gender':'Collection','department':'Department','category':'Category','kind':'Shoe silhouette','size':'Size · US','region':'Style inspiration','design_style':'Design family','sort':'Sort by'}
   controls=f'<label class="search-label">Search the collection<input type="search" name="q" value="{E(f.get("q",""))}" placeholder="Try blue shirt or Japanese sandals"></label>'
   facets=facet_options([p for p in self.products if not p.get('availability_owner')],f,filtered)
   for k in ('gender','department','category','kind','size','color','brand','material','fit','quality','occasion','style','region','design_style'):
    vals=facets[k];label=labels.get(k,k.title())
    if k=='color':
     from color_constraints import COLORS
     vals={v:vals.get(v,0) for v in sorted(COLORS|set(vals))}
    controls+=f'<label>{label}<select name="{k}"><option value="">All</option>'+''.join(f'<option value="{E(v)}" {"selected" if f.get(k)==v else ""}>{E(v.replace("-"," ").title())} ({count})</option>' for v,count in vals.items())+'</select></label>'
   controls+='<label>Sort by<select name="sort">'+''.join(f'<option value="{v}" {"selected" if f.get("sort","featured")==v else ""}>{label}</option>' for v,label in [('featured','Recommended'),('price-low','Price: low to high'),('price-high','Price: high to low'),('name','Name: A to Z')])+'</select></label>'
   controls+=f'<label>Exclude colors<input name="exclude_colors" value="{E(f.get("exclude_colors",""))}" placeholder="white, black"></label>'
   for key in ('preference_source','include_colors','apparel_size','waist_size','shoe_size','exclude_material','prefer_color','prefer_brand','prefer_material','prefer_quality','prefer_fit','prefer_occasion','prefer_style','prefer_design_style','size_system','width','explain','reset','request_id','expires_at'):
    controls+=f'<input type="hidden" name="{key}" value="{E(f.get(key,""))}">'
   controls+=f'<div class="price-range"><label>Minimum $<input type="number" name="min_price" min="0" step="0.01" value="{E(f.get("min_price",""))}"></label><label>Maximum $<input type="number" name="budget" min="0" step="0.01" value="{E(f.get("budget",""))}"></label></div>'
   chips=''
   for k in ('q',*FILTER_FIELDS,'size','min_price','budget','include_colors','exclude_colors'):
    if f.get(k):
     remaining={key:value for key,value in f.items() if key not in (k,'page')};remaining['reset']='1'
     chips+=f'<a class="chip" href="/shop?{E(urlencode(remaining))}" aria-label="Remove {E(labels.get(k,k))} {E(str(f[k]))}">{E(labels.get(k,k.replace("_"," ")).title())}: {E(str(f[k]))} <span aria-hidden="true">×</span></a>'
   def link(n):return '/shop?'+urlencode(dict(f,page=n))
   pager='<nav class="pagination" aria-label="Catalog pages">'
   if number>1:pager+=f'<a href="{E(link(number-1))}" data-shop-prev>← Previous</a>'
   pager+=f'<span>Page {number} of {pages}</span>'
   if number<pages:pager+=f'<a href="{E(link(number+1))}" data-shop-next>Next →</a>'
   pager+='</nav>'
   collection=f.get('gender','').title();dept='Footwear' if f.get('department')=='footwear' or f.get('category')=='shoes' else 'Clothing' if f.get('department')=='clothing' else 'The collection'
   heading=(collection+' '+dept).strip()
   footwear=f.get('department')=='footwear' or f.get('category')=='shoes'
   hero_image=('/assets/photos/heels.jpg' if f.get('gender')=='women' else '/assets/photos/sneakers.jpg') if footwear else ('/assets/photos/dresses.jpg' if f.get('gender')=='women' else '/assets/photos/jackets.jpg')
   hero=f'<div class="hero compact"><div><p class="eyebrow">FORME / THE WORLD IN YOUR WARDROBE</p><h1>{E(heading)}</h1><p>Familiar essentials. Distinctive silhouettes. Discover your next everyday favorite.</p><nav class="collections"><a href="/shop?gender=men&department=clothing">Shop men</a><a href="/shop?gender=women&department=clothing">Shop women</a><a href="/shop?department=footwear">Explore footwear</a></nav></div><img src="{hero_image}" alt="Considered clothing collection"></div>'
   notice='<p class="search-expired">Your previous search expired. Start a new search to apply fresh filters.</p>' if expired else ''
   count=notice+f'<p data-result-count="{len(products)}">{len(products):,} styles'+(f' · Showing {start+1}–{min(start+PAGE_SIZE,len(products))}' if products else '')+'</p>'
   empty='<div class="empty-results"><p class="eyebrow">A FRESH START</p><h2>No exact matches.</h2><p>Remove a selected filter or broaden your search. Your choices are kept so you can adjust them.</p><a class="button" data-clear-filters href="/shop?reset=1">Clear all filters</a></div>'
   remember=''
   if account:
    selected={}
    for key in ('color','brand','material','fit','quality','occasion','style'):
     if received.get(key):selected[{'color':'colors','brand':'brands'}.get(key,key)]=[received[key]] if key in ('color','brand') else received[key]
    for key,target in [('budget','budget'),('min_price','budget_min')]:
     if received.get(key) and received[key].isdigit():selected[target]=int(received[key])
    size=received.get('size','')
    if size in ('XS','S','M','L','XL','XXL'):selected['shirt_size']=size
    elif size and (received.get('category')=='shoes' or received.get('department')=='footwear'):selected['shoe_size']=size
    elif size and received.get('category') in WAIST_CATEGORIES:selected['waist']=size
    if selected:
     token=state['csrf'] if s else self.commerce.session(r)['csrf']
     action='/shop/context' if s else '/shop/preferences'
     remember=f'<form class="remember-filter" method="post" action="{action}"><input type="hidden" name="csrf" value="{token}"><input type="hidden" name="preferences" value="{E(json.dumps(selected),quote=True)}"><button class="quiet-button">Remember selected preferences</button><p class="small-note">Save these choices for future visits. Other filters stay temporary.</p></form>'
   form='<details class="facet-panel" open><summary>Refine your selection</summary><form data-shop-action="filter" method="get" action="/shop"><div class="filter-actions"><button>Apply filters</button><a data-clear-filters href="/shop?reset=1">Clear all</a></div>'+controls+'</form></details>'
   return finish(page(hero+'<div class="layout"><aside>'+form+remember+'</aside><section class="results" aria-live="polite"><div class="result-heading">'+count+'<span>Clothing & footwear · 1,000 listings</span></div><div class="active-filters">'+chips+'</div>'+pager+'<div class="grid">'+(''.join(self.card(p,explanation=explanations.get(p['id'])) for p in visible) if products else empty)+'</div>'+pager.replace('class="pagination"','class="pagination bottom"')+'</section></div>',signed=signed))
  if path.startswith('/shop/product/'):
   if not self.availability.allowed(path.rsplit('/',1)[-1],s):return error('This demo item belongs to another availability scenario.',403)
   p=self.by_id.get(path.split('/')[-1]);return finish(page(self.card(p,csrf,True),'detail',signed)) if p else error('Product not found.',404)
  if path=='/shop/cart':
   items=[]
   try:items=self.items(state['cart']) if state else []
   except ValueError:return error('An item is no longer available. Return to the collection.',409)
   if not items:return finish(page('<section class="panel empty"><p class="eyebrow">YOUR BAG</p><h1>A little room for something good.</h1><p>Your bag is empty.</p><a class="button" href="/shop?department=clothing">Explore clothing</a> <a href="/shop?department=footwear">Shop footwear →</a></section>','cart',signed))
   action=f'<form method="post" data-shop-action="review" action="/shop/review">{csrf}<button>Review order</button></form>' if s else '<p>Your storefront bag is saved in this browser. To place an order with your personal stylist, select the item in your Thread conversation.</p><a class="button" href="'+self.shop.config.base.replace('jacket.localhost','atlas.localhost')+'/">Open Thread</a>'
   rows=self.rows(items)
   for x in items:
    product=self.by_id[x['id']];hidden=csrf+f'<input type="hidden" name="product" value="{E(x["id"])}"><input type="hidden" name="old_size" value="{E(x["size"])}"><input type="hidden" name="cart_revision" value="{state.get("cart_revision",0)}">'
    options=''.join(f'<option value="{E(size)}" {"selected" if size==x["size"] else ""}>{E(size)}</option>' for size,stock in product['stock'].items() if stock>0 or size==x['size'])
    forms=f'<form data-shop-action="cart-update" action="/shop/cart/update" method="post">{hidden}<label>Size<select name="size">{options}</select></label><label>Quantity<input name="quantity" type="number" min="1" max="10" value="{x.get("quantity",1)}"></label><button>Update</button></form><form data-shop-action="cart-remove" action="/shop/cart/remove" method="post">{hidden}<button>Remove</button></form>'
    needle=f'data-product-id="{E(x["id"])}" data-color='
    start=rows.index(needle);end=rows.index('</div>',start);rows=rows[:end]+forms+rows[end:]
   return finish(page('<section class="panel"><h1>Your bag</h1>'+rows+action+f'<form class="remove" method="post" data-shop-action="clear" action="/shop/clear">{csrf}<button>Remove item</button></form><a href="/shop">Continue shopping →</a></section>','cart',signed))
  if not s:return error('Your shopping session has expired. Return to your stylist to reconnect.',401)
  if path=='/shop/review' and state['review']:
   v=state['review'];o=self.orders.get(v['id'])
   if o:return page(f'<section class="panel"><p class="eyebrow">THANK YOU</p><h1 data-receipt>Order {o["reference"]}</h1>'+self.rows(o['items'])+'</section>','receipt',signed)
   summary='\n'.join(f'{x["name"]}, size {x["size"]}, quantity {x.get("quantity",1)}' for x in v['items'])+f'\nTotal USD {v["total"]/100:.2f} · Shipping and tax included.\n\nDelivery on file:\n'+'\n'.join(str(v.get('delivery',{}).get(k,'')) for k in ('name','address','city','postal','country'))+'\nSimulated delivery only.'
   return page(f'<section class="panel" data-review="{v["id"]}" data-revision="{v["revision"]}" data-total="{v["total"]}"><h1>Your order, in detail.</h1><p data-summary>{E(summary)}</p>'+self.rows(v['items'])+f'<form method="post" data-shop-action="checkout" action="/shop/checkout">{csrf}<input type="hidden" name="review" value="{v["id"]}"><button name="approved" value="yes" {"" if signed and "orders:write" in s.scopes else "disabled"}>Place order</button></form></section>','review',signed)
  return error('Page not found.',404)
CSS+='''
.preferences-page{max-width:1150px;margin:30px auto 60px}.preferences-page h1{font-size:52px;margin:16px 0}.pref-intro{max-width:600px;color:#687068;line-height:1.7}.pref-layout{display:grid;grid-template-columns:240px 1fr;gap:48px;margin-top:40px}.pref-aside{background:#e8ebe2;padding:26px;height:fit-content;line-height:1.7}.pref-aside h2{font-size:26px}.pref-fields{display:grid;grid-template-columns:1fr 1fr;gap:20px 28px}.preference-field{border-bottom:1px solid #dedfd7;padding-bottom:16px}.preference-field label{font-size:13px;margin:0}.preference-field select,.preference-field input{border-radius:4px;min-height:44px}.pref-clear{background:none;color:#526350;padding:8px 0 0;font-size:11px;text-decoration:underline}.pref-save{display:flex;align-items:center;gap:24px;padding:24px 0;margin-top:24px;border-top:1px solid #ccc}.pref-save span{color:#687068;font-size:12px}.pref-feedback{background:#e8ebe2;padding:18px;border-left:3px solid #314c3a}.pref-feedback[role=alert]{border-color:#a34b36;background:#fbede6}@media(max-width:700px){header{flex-wrap:wrap;gap:18px}header nav{flex-wrap:wrap;gap:14px}.preferences-page h1{font-size:38px}.pref-layout{grid-template-columns:1fr;gap:24px}.pref-fields{gap:16px}.pref-save{flex-wrap:wrap}.pref-aside{padding:18px}}@media(max-width:420px){.pref-fields{grid-template-columns:1fr}}
'''
CSS+='''.preference-field select[multiple]{height:120px}@media(max-width:700px){.pref-aside{order:2}.pref-fields{order:1}.preferences-page{margin-top:12px}}'''
