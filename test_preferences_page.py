import os,sys,re,json,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,httpx,uvicorn
from app import App,Flow,CURRENT,ORIGIN
from test_commerce import login,csrf
from preferences_page import revision,options
@pytest.mark.asyncio
async def test_editor_persistence_validation_isolation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'p.sqlite');t=httpx.ASGITransport(app=app)
 before=[app.memory.get(i) for i in range(1,101)];context=app.store.context
 # Availability can add nonstandard sizes; the complete editor must still render/save.
 import copy
 extra=copy.deepcopy(next(p for p in app.store.products if p['category']=='shirts'));extra['id']='test-nonstandard';extra['stock']={'One size':5,'XXXL':2};app.store.products.append(extra)
 assert not {'One size','XXXL'}&set(options(app.store.products)['shirt_size'])
 from company_context import validate_preferences
 from preferences_page import MULTI
 for key,values in options(app.store.products).items():
  for value in values:validate_preferences({key:[value] if key in MULTI else value})
 async with httpx.AsyncClient(transport=t,base_url=ORIGIN) as a,httpx.AsyncClient(transport=t,base_url=ORIGIN) as b,httpx.AsyncClient(transport=t,base_url=ORIGIN) as guest:
  assert (await guest.get('/shop/preferences')).status_code==303
  await login(a);await login(b,2)
  page=await a.get('/shop/preferences');assert 'Made more personal' in page.text
  opts=options(app.store.products);assert {'blue','white'}<=set(opts['colors']) and 'kurta' in opts['design_style'] and 'L' in opts['shirt_size']
  account='forme_customer_001';context.update(account,{'avoid':'wool'})
  async def save(values,rev=None):
   p=await a.get('/shop/preferences');return await a.post('/shop/preferences',headers={'Origin':ORIGIN},data={'csrf':csrf(p),'revision':rev or revision(context.get(account)),**values})
  r=await save({'pref_colors':'blue','pref_shirt_size':'L','pref_shoe_size':'9','pref_fit':'regular','pref_style':'minimal','pref_design_style':'kurta','pref_budget':'150'});assert r.status_code==303
  saved={k:v['value'] for k,v in context.get(account)['preferences'].items()};assert saved['colors']==['blue'] and saved['avoid']=='wool'
  assert 'value="kurta" selected' in (await a.get('/shop/preferences')).text
  assert 'value="kurta" selected' not in (await b.get('/shop/preferences')).text
  old=revision(context.get(account));assert (await save({'pref_colors':''})).status_code==303
  assert 'colors' not in context.get(account)['preferences'] and context.get(account)['preferences']['design_style']['value']=='kurta'
  assert (await save({'pref_budget':'90'},old)).status_code==400
  for values in ({'pref_budget':'-1'},{'pref_fit':'bogus'},{'account':'forme_customer_002'},{'pref_budget_min':'200','pref_budget':'100'}):assert (await save(values)).status_code==400
  page=await a.get('/shop/preferences');assert (await b.post('/shop/preferences',headers={'Origin':ORIGIN},data={'csrf':csrf(page),'revision':revision(None),'pref_fit':'slim'})).status_code==403
  assert context.get('forme_customer_002')['preferences']=={}
  assert before==[app.memory.get(i) for i in range(1,101)] and not app.memory.orders()
  from recommendations import effective_filters
  from store import filtered
  f=effective_filters({},saved);assert f['apparel_size']=='L' and f['prefer_design_style']=='kurta'
  rows=filtered(app.store.products,f);assert rows
  fresh=App();await fresh.setup(tmp_path/'p.sqlite')
  try:assert fresh.store.context.get(account)['preferences']==context.get(account)['preferences']
  finally:await fresh.http.aclose()
 await app.http.aclose()

@pytest.mark.asyncio
async def test_editor_reflects_through_authorized_browser(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'sync.sqlite');f=Flow(app,1);before=app.memory.get(1)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  CURRENT.set(f);reply,_=await f.preference_status(True);assert f.signurl
  t=app.tickets[f.signurl.split('ticket=')[1]];assert set(t['scopes'])=={'preferences:read'}
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':t['csrf'],'email':'customer001@forme.local','password':'wardrobe'});await asyncio.sleep(5.2);await f.poll()
  async with httpx.AsyncClient(verify=app.http._transport._pool._ssl_context,base_url=ORIGIN,trust_env=False) as direct:
   await login(direct)
   async def save(value):
    p=await direct.get('/shop/preferences');rev=re.search('name="revision" value="([^"]+)"',p.text)[1]
    return await direct.post('/shop/preferences',headers={'Origin':ORIGIN},data={'csrf':csrf(p),'revision':rev,'pref_colors':value,'pref_budget':'200','pref_design_style':'blue-shirt'})
   assert (await save('blue')).status_code==303
   first=json.loads((await f.preference_status(True))[0]);assert first['lasting_preferences']['colors']==['blue']
   app.store.context.update('forme_customer_001',{'excluded_colors':['white'],'budget':1})
   reply,cards=await f.chat('find white shirts');assert cards and all(c['color']=='white' for c in cards)
   assert f.catalog_snapshot['filters']['preference_source']=='thread'
   assert f.catalog_snapshot['filters']['budget']==str(before['budget'])
   assert f.catalog_snapshot['filters'].get('prefer_design_style','')==''
   assert f.catalog_snapshot['filters']['prefer_style']==before['style']
   company_before=app.store.context.get('forme_customer_001')['preferences']
   await f.chat('remember I prefer cotton');reply,cards=await f.chat('find shirts')
   assert cards and f.catalog_snapshot['filters']['prefer_color']==before['colors'][0]
   assert app.store.context.get('forme_customer_001')['preferences']==company_before
   direct_page=await direct.get('/shop?category=shirts&preference_source=thread')
   assert 'data-result-count="0"' in direct_page.text
   explicit=await direct.get('/shop?category=shirts&color=white&budget=200')
   assert 'data-result-count="0"' not in explicit.text
   assert (await save('')).status_code==303
   second=json.loads((await f.preference_status(True))[0]);assert 'colors' not in second['lasting_preferences'] and second['revision']!=first['revision']
   # An expired browser authorization must not return the last cached company view.
   original_call=f.browser.call
   async def expired(action,**kw):return {'signed_in':False,'account_status':'expired'} if action=='account_status' else await original_call(action,**kw)
   f.browser.call=expired;assert await f.refresh_forme_preferences() is None and f.company_preference_snapshot is None;f.browser.call=original_call
   app.company_links.revoke(f.principal['id'],ORIGIN);assert await f.refresh_forme_preferences() is None and f.company_preference_snapshot is None
   assert app.memory.get(1)==before and not app.memory.orders()
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task
