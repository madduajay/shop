import os,sys,json,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from color_constraints import parse_colors
from data import catalog,Memory
from store import filtered
from recommendations import effective_filters,intent_filters,request_context
from company_context import validate_preferences
from app import App,Flow,CURRENT,ORIGIN

@pytest.mark.parametrize('text,excluded,positive',[
 ('show me a shirt - not white color',['white'],[]),('not white or black',['black','white'],[]),
 ('neither white nor navy',['navy','white'],[]),('anything but white',['white'],[]),
 ('not interested in white',['white'],[]),('not looking for white',['white'],[]),('without white',['white'],[]),('exclude white and black',['black','white'],[]),
 ("I don't want white",['white'],[]),('I do not want white',['white'],[]),
 ('blue or navy but not white',['white'],['blue','navy']),('white is not okay',['white'],[]),
 ('avoid ivory',['white'],[])])
def test_polarity(text,excluded,positive):
 p=parse_colors(text);assert p['exclude']==excluded and p['include']==positive

def test_hard_exclusion_precedence_and_memory(tmp_path):
 products=catalog();f=effective_filters({'exclude_colors':'white'}, {'colors':['white']}, {'inferred_interests':{'color':{'value':'white'}}})
 rows=filtered(products,f);assert rows and all(p['color']!='white' for p in rows)
 assert not filtered(products,{'color':'white','exclude_colors':'white'})
 merged=request_context({'exclude_colors':'white'},{'current_request':{'colors':['white']}})
 assert filtered(products,merged) and all(p['color']!='white' for p in filtered(products,merged))
 assert not filtered(products,{'exclude_colors':','.join(sorted({p['color'] for p in products}))})
 rows=filtered(products,{'include_colors':'navy,blue','exclude_colors':'white'});assert rows and {p['color'] for p in rows}<={'navy','blue'}
 assert all(p['color']!='white' for p in filtered(products,{'q':'shirt not white color'}))
 memory=Memory(tmp_path/'prefs.sqlite');before=memory.get(2);p,u=memory.edit(1,'remember avoid white and black');assert 'colors' not in u and u['excluded_colors']==['black','white']
 assert Memory(tmp_path/'prefs.sqlite').get(1)['excluded_colors']==['black','white'] and memory.get(2)==before
 assert validate_preferences({'excluded_colors':['white']})=={'excluded_colors':['white']}
 assert intent_filters({'excluded_colors':['white'],'colors':['blue','navy']})=={'exclude_colors':'white','include_colors':'blue,navy'}

@pytest.mark.asyncio
async def test_browser_exclusions_refinements_pagination_and_contradictions(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'colors.sqlite');f=Flow(app,1)
 original=app.memory.get(1);p=dict(original,colors=['white'],budget=1000,budget_min=0);app.memory.save(p)
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve());evidence=[]
 try:
  while not server.started:await asyncio.sleep(.05)
  CURRENT.set(f)
  app.company_context.update('forme_customer_001',{'colors':['white']})
  await f.open();f.pending_read='orders';await f.signin()
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);await f.poll();assert f.token.signed_in
  # Deliberately lossy model normalization must never erase original negation.
  async def wrong_parse(text,prefs):return 'find white shirts' if text=='show me a shirt - not white color' else text
  f.app.model.parse=wrong_parse
  for text,excluded,allowed in [('show me a shirt - not white color',{'white'},None),('show more',{'white'},None),('not blue either',{'white','blue'},None),('show more',{'white','blue'},None),('find blue or navy shirts but not white',{'white'},{'blue','navy'})]:
   reply,cards=await f.chat(text);assert cards,(text,reply)
   snap=f.catalog_snapshot;assert excluded<=set(snap['filters']['exclude_colors'].split(','))
   assert all(x['color'] not in excluded and (not allowed or x['color'] in allowed) for x in snap['products'])
   assert all(x['color']==x['photo_color'] for x in snap['products'])
   evidence.append({'query':text,'excluded':sorted(excluded),'products':[{'id':c['id'],'color':c['color'],'image':c['image']} for c in cards]})
  # A supported color absent from the catalog must remain selected in the real
  # retailer form; saved white preferences must never become substitutes.
  for query in ('show me red shirts','under $80','red'):
   reply,cards=await f.chat(query)
   assert not cards and 'No in-stock' in reply,(query,reply)
   assert f.catalog_snapshot['filters']['color']=='red'
   assert f.catalog_snapshot['filters']['include_colors']=='red'
   assert f.catalog_snapshot['filters']['category']=='shirts'
  assert f.catalog_snapshot['filters']['budget']=='79.99'
  # Even lossy model normalization cannot replace an explicit positive color.
  async def wrong_positive(text,prefs):return 'find white shirts'
  f.app.model.parse=wrong_positive
  reply,cards=await f.chat('show me red shirts')
  assert not cards and f.catalog_snapshot['filters']['include_colors']=='red'
  f.app.model.parse=wrong_parse
  # Fail closed if a future storefront regression returns a disallowed variant.
  real_call=f.browser.call
  async def broken_filter(action,**kw):
   if action=='filter':return {'products':[{'color':'blue'}],'filters':kw['filters']}
   return await real_call(action,**kw)
  f.browser.call=broken_filter
  reply,cards=await f.chat('show me red shirts')
  assert not cards and 'outside your requested colors' in reply and not f.options
  f.browser.call=real_call
  # Follow the real retailer Next link with exclusions in its query and form.
  await f.chat('find clothing not white');snap=f.catalog_snapshot;assert snap['has_next']
  snap=await f.browser.call('next');assert snap['filters']['exclude_colors']=='white' and all(p['color']!='white' for p in snap['products'])
  await f.chat('find white shirts');reply,cards=await f.chat('not white');assert cards and all(c['color']!='white' for c in cards)
  reply,cards=await f.chat('find white shirts and not white');assert not cards and 'same color' in reply and not f.options
  reply,cards=await f.chat('find clothing not navy, white, black, olive, sand, blue, brown, rose, burgundy or sage');assert not cards and not f.options
  assert app.memory.get(1)==p and not app.memory.orders()
  assert any(x.get('cookie_issued') for x in f.trace) and any(x.get('action')=='filter' for x in f.trace)
  (Path(__file__).parent/'evidence/color-exclusions-browser.json').write_text(json.dumps({'fixture_only':True,'cases':evidence,'pagination':True,'contradiction':True,'no_results':True,'profiles_unchanged':True,'orders':0},indent=2))
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task


def test_saved_exclusions_and_availability_are_hard(tmp_path):
 products=catalog();f=effective_filters({'prefer_color':'white'},{'excluded_colors':['white']})
 assert all(p['color']!='white' for p in filtered(products,f))
 from availability import Availability
 a=Availability(tmp_path/'availability.sqlite',products)
 assert a.demo_candidate({'demo_trigger':'shoes','exclude_colors':'red'}) is None
 assert parse_colors('white and not white')['conflict']


def test_empty_search_refinement_routes_without_enabling_selection():
 from chat_routing import route
 assert route('under $80',False,True)=='shopping'
 assert route('red',False,True)=='shopping'
 assert route('under $80',False,False)=='unknown'
 assert route('the first one',False,True)=='unknown'
