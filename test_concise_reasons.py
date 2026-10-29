import sys,asyncio
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from types import SimpleNamespace
from recommendations import Explainer
from data import catalog

def test_concise_fallback_all_catalog_and_no_invented_preferences():
 async def run():
  ex=Explainer(SimpleNamespace(key=None));products=catalog()
  result=await ex.explain(products,{}, {},{},{'inferred_interests':{'material':{'value':'cotton'}}})
  for row in result.values():
   assert 15<=len(row['text'].split())<=25 and 'preference' not in row['text'] and row['source']=='deterministic'
  p=products[0];result=await ex.explain([p],{'material':p['material'],'budget':'180','apparel_size':'M'}, {},{})
  assert p['material'] in result[p['id']]['text'] and len(result[p['id']]['text'].split())<=25
 asyncio.run(run())
