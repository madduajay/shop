"""Token search and disjunctive inventory facets shared by rendered controls."""
import re
from collections import Counter
FILTER_FIELDS=('gender','department','category','kind','color','brand','material','fit','quality','occasion','style','region','design_style')
ALIASES={'shirt':'shirts','blouse':'shirts','blouses':'shirts','tshirt':'tees','tee':'tees','tshirts':'tees','shoe':'shoes','footwear':'shoes','sneaker':'sneakers','dress':'dresses','skirt':'skirts','jean':'jeans','trouser':'trousers','pants':'trousers','jacket':'jackets','boot':'boots','sandal':'sandals','loafer':'loafers','man':'men','mens':'men','woman':'women','womens':'women','female':'women','male':'men','ivory':'white','beige':'sand','indigo':'navy','japanese':'japan','indian':'asia','mexican':'mexico','turkish':'turkey','italian':'italy','moroccan':'morocco','swedish':'sweden','french':'france'}
def tokens(text):
 text=text.lower().replace("women's",'women').replace("men's",'men').replace('t-shirt','tshirt')
 return {ALIASES.get(t,t) for t in re.findall(r'[a-z0-9]+',text) if t not in {'a','an','the','for','in','find','me','some','and','with','show','color','colour','but','or'}}
def query_matches(product,query):
 wanted=tokens(query)
 text=' '.join(str(product.get(k,'')) for k in ('name','brand','model_code','material','construction','color','category','kind','gender','department','region','design_style','style'))
 return wanted<=tokens(text)
def facet_options(products,f,filter_fn):
 result={}
 for field in (*FILTER_FIELDS,'size'):
  scope={k:v for k,v in f.items() if k!=field}
  rows=filter_fn(products,scope)
  if field=='size':counts=Counter(size for p in rows for size,n in p['stock'].items() if n>0)
  elif field=='kind':counts=Counter(p[field] for p in rows if p['category']=='shoes')
  else:counts=Counter(p[field] for p in rows)
  # Supported empty categories remain selectable without inventing stock.
  if field=='category':counts.setdefault('ties',0)
  if field=='department':counts.setdefault('accessories',0)
  selected=f.get(field)
  if selected and selected not in counts:counts[selected]=0
  result[field]=dict(sorted(counts.items()))
 return result
