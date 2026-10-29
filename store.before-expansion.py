import html,secrets,json
from http.cookies import SimpleCookie
from urllib.parse import parse_qs
from starlette.responses import HTMLResponse,RedirectResponse
from personal_agent_protocol.company.service import WEB_COOKIE
from data import catalog
E=html.escape
CSS=PathCSS='''*{box-sizing:border-box}[hidden]{display:none!important}h1{font-family:Georgia;font-weight:normal}body{margin:0;color:#20251f;background:#fbfaf7;font:14px Arial,sans-serif}header{padding:26px 5%;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ddd}a{color:inherit;text-decoration:none}header b{font-size:26px;letter-spacing:5px}nav{display:flex;gap:28px}main{padding:30px 5%}.hero{background:#e6e7df;padding:42px;display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}.hero h1{font:52px Georgia;margin:12px 0}.hero img{width:40%;height:240px;object-fit:cover}.eyebrow{letter-spacing:3px;font-size:11px}.layout{display:grid;grid-template-columns:190px 1fr;gap:35px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}article img{width:100%;height:290px;object-fit:cover;background:#eee}h2{font:21px Georgia;margin:12px 0}label{display:block;margin:14px 0;font-size:12px}select,input{display:block;width:100%;padding:12px;border:1px solid #ccc;background:white;margin-top:6px}button,.button{background:#243c31;color:white;border:0;padding:13px 22px;cursor:pointer}button:disabled{opacity:.4}article p{color:#687068;font-size:12px}.detail{display:grid;grid-template-columns:1fr 1fr;gap:60px;max-width:1000px;margin:20px auto}.detail img{height:560px;width:100%;object-fit:cover}.panel{max-width:700px;margin:55px auto;background:white;padding:40px;border:1px solid #ddd}.price{float:right}small{color:#697568}footer{padding:40px 5%;border-top:1px solid #ddd;margin-top:40px;color:#687068}body[data-page="signin"] header nav,body[data-page="signin"] header small{display:none}body[data-page="signin"] header{justify-content:center}body[data-page="signin"] .panel{margin:20px auto;padding:32px;border-radius:14px}body[data-page="signin"] footer{display:none}@media(max-width:800px){header small{display:none}header img{width:110px}nav{gap:14px;font-size:12px}aside form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}aside label{margin:0}aside button{grid-column:1/-1}.grid{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.hero img{display:none}.detail{grid-template-columns:1fr}.hero h1{font-size:36px}}'''
def page(body,kind='catalog',signed=False,status=200):
 return HTMLResponse(f'<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>FORME — Clothing & footwear</title><link rel="stylesheet" href="/assets/store.css"></head><body data-page="{kind}" data-signed-in="{str(signed).lower()}"><header><a href="/shop"><img width="140" src="/assets/logo.svg" alt="FORME"></a><nav><a href="/shop?category=shirts">Clothing</a><a href="/shop?category=shoes">Footwear</a><a href="/shop/cart">Bag</a></nav><small>Considered essentials.</small></header><main>{body}</main><footer>FORME &nbsp; / &nbsp; Wear it your way. <span class="price">Quality in every detail.</span></footer></body></html>',status_code=status,headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'",'Referrer-Policy':'same-origin','X-Frame-Options':'DENY'})
def filtered(products,f):
 return [p for p in products if all(not f.get(k) or p[k]==f[k] for k in ('category','color','brand','material','fit','quality','occasion')) and (not f.get('budget') or p['price']<=float(f['budget'])*100) and (not f.get('min_price') or p['price']>=float(f['min_price'])*100) and (not f.get('size') or p['stock'].get(f['size'],0)>0)]
class Store:
 def __init__(self,shop,memory):
  self.shop=shop;self.memory=memory;self.products=catalog();self.states={};self.orders={o['review_id']:o for o in memory.orders()}
  for o in self.orders.values():
   for x in o['items']:next(p for p in self.products if p['id']==x['id'])['stock'][x['size']]-=1
 async def session(self,request):
  c=SimpleCookie();c.load(request.headers.get('cookie',''));m=c.get(WEB_COOKIE);s=await self.shop._web_session(m.value if m else None)
  if s:s=await self.shop._session_by_id(s.session_id)
  return s if s and self.shop._now()<s.expires_at and not await self.shop._signed_in_before_its_end(s) else None
 def items(self,cart):
  out=[]
  for x in cart:
   p=next(p for p in self.products if p['id']==x['id'])
   if p['stock'].get(x['size'],0)<1:raise ValueError('This size is sold out. Please choose another.')
   out.append(dict(id=p['id'],name=p['name']+' · '+p['color'],size=x['size'],price=p['price']))
  return out
 def rows(self,items):return ''.join(f'<p data-cart-item data-name="{E(x["name"])}" data-size="{x["size"]}" data-price="{x["price"]}">{E(x["name"])} · {x["size"]}<strong class="price">${x["price"]/100:.2f}</strong></p>' for x in items)
 def card(self,p,csrf='',detail=False):
  options=''.join(f'<option value="{s}" data-stock="{n}" {"disabled" if n<1 else ""}>{s} {"— sold out" if n<1 else ""}</option>' for s,n in p['stock'].items())
  return f'<article data-product="{p["id"]}" data-price="{p["price"]}" data-color="{p["color"]}" data-brand="{p["brand"]}" data-material="{p["material"]}" data-image="{p["image"]}" data-quality="{p["quality"]}" data-fit="{p["fit"]}" data-occasion="{p["occasion"]}" class="{"detail" if detail else ""}"><a href="/shop/product/{p["id"]}"><img src="/assets/{p["image"]}.jpg" alt="{E(p["name"])}"></a><div><p>{p["brand"].upper()} / {p["color"].upper()}</p><h2>{p["name"]}</h2><p data-description>{p["material"].title()} · {p["fit"]} fit · {p["quality"]} quality</p><strong>${p["price"]/100:.2f}</strong>'+ (f'<p>Thoughtful construction. An effortless addition to your everyday wardrobe.</p><form method="post" action="/shop/cart">{csrf}<input type="hidden" name="product" value="{p["id"]}"><label>Size · US <select name="size">{options}</select></label><button>Add to bag</button></form>' if detail else f'<select name="size" hidden>{options}</select>')+'</div></article>'
 async def handle(self,r):
  s=await self.session(r);path=r.url.path;state=self.states.setdefault(s.session_id,dict(csrf=secrets.token_urlsafe(24),cart=[],review=None,filters={})) if s else None
  csrf=f'<input type="hidden" name="csrf" value="{state["csrf"]}">' if state else '';signed=bool(s and s.signed_in)
  def error(msg,status=400):return page(f'<section class="panel"><p data-error>{E(msg)}</p><a href="/shop">Continue shopping</a></section>','error',signed,status)
  if r.method=='POST':
   if not state:return error('Your shopping session has expired. Return to your stylist to reconnect.',401)
   if r.headers.get('origin')!=self.shop.config.base:return error('Invalid form origin.',403)
   vals=parse_qs((await r.body()).decode(),keep_blank_values=True)
   if any(len(v)!=1 for v in vals.values()):return error('Invalid form.')
   f={k:v[0] for k,v in vals.items()}
   if not secrets.compare_digest(f.get('csrf',''),state['csrf']):return error('Please reload this page.',403)
   if path=='/shop/cart':
    try:self.items([dict(id=f.get('product'),size=f.get('size'))])
    except (ValueError,StopIteration):return error('Choose an available size.',409)
    state.update(cart=[dict(id=f['product'],size=f['size'])],review=None)
    return RedirectResponse('/shop/cart',303)
   if path=='/shop/review':
    try:items=self.items(state['cart'])
    except ValueError as e:return error(str(e),409)
    if not items:return error('Your bag is empty.',409)
    state['review']=dict(id=secrets.token_hex(16),revision=1,items=items,total=sum(x['price'] for x in items))
    return RedirectResponse('/shop/review',303)
   if path=='/shop/checkout':
    v=state['review']
    if not signed or 'orders:write' not in s.scopes:return error('Sign in to continue.',403)
    if not v or f.get('review')!=v['id'] or f.get('approved')!='yes':return error('Review and approve the current bag.',409)
    if v['id'] not in self.orders:
     try:items=self.items(state['cart'])
     except ValueError as e:return error(str(e),409)
     if items!=v['items']:return error('Your bag changed. Review again.',409)
     order=dict(review_id=v['id'],items=items,total=v['total'],reference='FM-'+secrets.token_hex(4).upper(),customer=s.pairwise_user_id,fictional=True)
     self.memory.order(order);self.orders[v['id']]=order
     for x in items:next(p for p in self.products if p['id']==x['id'])['stock'][x['size']]-=1
    return RedirectResponse('/shop/review',303)
   return error('Unknown form.',404)
  if path=='/shop':
   f=dict(r.query_params);state and state.update(filters=f)
   try:products=filtered(self.products,f)
   except ValueError:return error('Enter a valid budget.')
   controls=''
   for k,vals in [('category',['shirts','trousers','shoes','jackets']),('size',['XS','S','M','L','XL','XXL']+[str(x) for x in list(range(6,14))+list(range(26,45,2))]),('color',sorted({p['color'] for p in self.products})),('brand',sorted({p['brand'] for p in self.products})),('material',sorted({p['material'] for p in self.products})),('fit',['regular','relaxed','slim']),('quality',['essential','premium']),('occasion',['everyday','work'])]:
    controls+=f'<label>{k.title()}<select name="{k}"><option value="">All</option>'+''.join(f'<option {"selected" if f.get(k)==v else ""}>{E(v)}</option>' for v in vals)+'</select></label>'
   controls+=f'<label>Minimum price<input type="number" name="min_price" min="0" value="{E(f.get("min_price",""))}"></label><label>Maximum price<input type="number" name="budget" min="1" value="{E(f.get("budget",""))}"></label>'
   return page('<div class="hero"><div><p class="eyebrow">THE EVERYDAY COLLECTION</p><h1>Good things.<br>Worn often.</h1><p>Clothing and footwear for the way you move.</p></div><img src="/assets/jacket.jpg" alt="New season collection"></div><div class="layout"><aside><form data-shop-action="filter" method="get" action="/shop">'+controls+'<button>Apply filters</button></form></aside><section><p>'+str(len(products))+' considered essentials</p><div class="grid">'+''.join(self.card(p) for p in products)+'</div></section></div>',signed=signed)
  if path.startswith('/shop/product/'):
   p=next((p for p in self.products if p['id']==path.split('/')[-1]),None)
   return page(self.card(p,csrf,True),'detail',signed) if p else error('Product not found.',404)
  if not state:return error('Ask your stylist to open your shopping session.',401)
  if path=='/shop/cart':return page('<section class="panel"><h1>Your bag</h1>'+self.rows(self.items(state['cart']))+f'<form method="post" data-shop-action="review" action="/shop/review">{csrf}<button>Review order</button></form></section>','cart',signed)
  if path=='/shop/review' and state['review']:
   v=state['review'];o=self.orders.get(v['id'])
   if o:return page(f'<section class="panel"><p class="eyebrow">THANK YOU</p><h1 data-receipt>Order {o["reference"]}</h1>'+self.rows(o['items'])+'</section>','receipt',signed)
   summary=f'{v["items"][0]["name"]}, size {v["items"][0]["size"]}. Total ${v["total"]/100:.2f}. Shipping and tax included.'
   return page(f'<section class="panel" data-review="{v["id"]}" data-revision="1" data-total="{v["total"]}"><h1>Your order, in detail.</h1><p data-summary>{E(summary)}</p>'+self.rows(v['items'])+f'<form method="post" data-shop-action="checkout" action="/shop/checkout">{csrf}<input type="hidden" name="review" value="{v["id"]}"><button name="approved" value="yes" {"" if signed else "disabled"}>Place order</button></form></section>','review',signed)
  return error('Page not found.',404)
