import os,sys,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from constraints import extract,matches,ConstraintError
from data import catalog
from store import filtered
from app import App,Flow,CURRENT,ORIGIN

@pytest.mark.parametrize('query,expected',[
 ('white shirts size L regular fit under $81.25',{'color':'white','apparel_size':'L','fit':'regular','budget':'81.24'}),
 ('blue t-shirts size XXL between $30.50 and $70.99',{'category':'tees','min_price':'30.50','budget':'70.99'}),
 ('guayabera shirts size L',{'design_style':'guayabera','category':'shirts'}),
 ('blue shoes in size 9',{'shoe_size':'9','category':'shoes'}),
 ('jeans size 32',{'waist_size':'32','category':'jeans'}),
 ('large white shirts',{'apparel_size':'L'}),
 ('purple shirts size L',{'color':'purple'}),
 ('blue or navy shirts not white',{'include_colors':'blue,navy','exclude_colors':'white'}),
 ('at least $25.50 and at most $90.99',{'min_price':'25.50','budget':'90.99'}),
])
def test_original_requirements(query,expected):
 f=extract(query);assert all(f[k]==v for k,v in expected.items())

def test_conjunction_and_impossible_variant():
 rows=catalog();f=extract('white guayabera shirts size L regular fit between $70 and $82')
 selected=filtered(rows,f);assert selected and all(matches(p,f) for p in selected)
 assert not filtered(rows,extract('red guayabera shirts size L regular fit under $82'))
 assert not filtered(rows,extract('white shirts size XXXL'))
 for query in ('slim and relaxed shirts','shirts and shoes','not slim shirts','shirts size 4XL'):
  with pytest.raises(ConstraintError):extract(query)

@pytest.mark.asyncio
async def test_browser_constraints_refinements_and_exact_add(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'constraints.sqlite');f=Flow(app,1);CURRENT.set(f)
 p=app.memory.get(1);p.update(shirt_size='S',colors=['blue'],excluded_colors=['white'],budget=180);app.memory.save(p)
 before=[app.memory.get(i) for i in range(1,101)]
 app.company_context.update('forme_customer_001',{'shirt_size':'XS','colors':['burgundy'],'fit':'relaxed','budget':20})
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  # Normalize badly on purpose; original conjunction must remain authoritative.
  async def lossy(text,prefs):return 'find blue shirts size S budget 100' if text.startswith('show white') else text
  app.model.parse=lossy
  query='show white guayabera shirts size L regular fit between $70.50 and $81.50'
  reply,cards=await f.chat(query);assert cards,reply
  assert all(c['size']=='L' and matches(c,extract(query)) for c in cards)
  reply,cards=await f.chat('under $80.25');assert cards,reply
  filters=f.catalog_snapshot['filters'];assert filters['apparel_size']=='L' and filters['design_style']=='guayabera' and filters['fit']=='regular'
  assert filters['min_price']=='70.50'
  assert all(7050<=c['price_cents']<8025 and c['size']=='L' and c['color']=='white' for c in cards)
  # Chat selection -> sign-in -> actual controlled-browser form add; never checkout.
  chosen=cards[0];reply,_=await f.chat('the first one');assert f.pending_add['size']=='L' and f.signurl
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);reply=await f.poll();assert 'size L, is in your bag' in reply,reply
  bag=app.store.commerce.cart('account:forme_customer_001');assert bag['lines']==[{'id':chosen['id'],'size':'L','quantity':1}]
  assert app.store.commerce.cart('account:forme_customer_002')['lines']==[]
  # Explicit unavailable size returns none, never saved S; empty refinements stay constrained.
  reply,cards=await f.chat('find white guayabera shirts size XXXL');assert not cards and 'No in-stock' in reply
  reply,cards=await f.chat('under $100');assert not cards and f.catalog_snapshot['filters']['apparel_size']=='XXXL'
  # Revalidate stock immediately before any add, even if a result was valid earlier.
  reply,cards=await f.chat('find white shirts size L');assert cards
  target=cards[0];item=next(p for p in app.store.products if p['id']==target['id']);item['stock']['L']=0
  before_bag=app.store.commerce.cart('account:forme_customer_001')
  reply,_=await f.chat('the first one');assert 'Nothing was added' in reply
  assert app.store.commerce.cart('account:forme_customer_001')==before_bag
  assert [app.memory.get(i) for i in range(1,101)]==before and not app.memory.orders()
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task


def test_availability_respects_strict_price_and_category(tmp_path):
 from availability import Availability
 a=Availability(tmp_path/'watches.sqlite',catalog())
 assert a.demo_candidate(dict(extract('red shoes under $95'),demo_trigger='shoes')) is None
 assert a.demo_candidate(dict(extract('red shoes up to $95'),demo_trigger='shoes'))
 assert a.demo_candidate({'demo_trigger':'tie','category':'shirts'}) is None
