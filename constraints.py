"""Explicit, bounded shopping requirements; never weakened by preference ranking."""
import re
from decimal import Decimal
from color_constraints import parse_colors
WAIST_CATEGORIES={'trousers','jeans','shorts'}

class ConstraintError(ValueError):pass

def extract(text):
 s=text.lower();f={};colors=parse_colors(text)
 if re.search(r'\b(oversized|skinny|tailored|athletic fit|bohemian|streetwear|vintage)\b',s):raise ConstraintError('The catalog does not verify that exact fit or style. Would you like to choose a supported alternative?')
 if colors['include']:f['include_colors']=','.join(colors['include']);f['color']=colors['include'][0] if len(colors['include'])==1 else ''
 if colors['exclude']:f['exclude_colors']=','.join(colors['exclude'])
 # Original wording wins over lossy model rewrites, including decimal prices.
 number=r'(\d+(?:\.\d{1,2})?)'
 m=re.search(r'\b(?:between|range)\s*\$?'+number+r'\s*(?:and|to|-)\s*\$?'+number,s)
 if m:f.update(min_price=m[1],budget=m[2])
 else:
  m=re.search(r'\b(under|below|less than|at most|up to|maximum|max|budget)\s*\$?'+number,s)
  if m:f.update(budget=str(Decimal(m[2])-(Decimal('.01') if m[1] in ('under','below','less than') else 0)))
  m=re.search(r'\b(over|above|more than|at least|minimum|min)\s*\$?'+number,s)
  if m:f['min_price']=str(Decimal(m[2])+(Decimal('.01') if m[1] in ('over','above','more than') else 0))
 if 'budget' in f and Decimal(f.get('min_price','0'))>Decimal(f['budget']):raise ConstraintError('The price bounds conflict. Please specify a minimum no higher than the maximum.')
 for key,pat in [('apparel_size',r'\b(?:shirt size|size)\s+(xs|s|m|l|xl|xxl|xxxl|xxs)\b'),('shoe_size',r'\bshoes? size\s+(\d+(?:\.\d+)?)\b'),('waist_size',r'\bwaist(?: size)?\s+(\d+)\b')]:
  m=re.search(pat,s)
  if m:f[key]=m[1].upper()
 if re.fullmatch(r'\s*(xs|s|m|l|xl|xxl|xxxl|xxs)\s*',s):f['apparel_size']=s.strip().upper()
 for label,size in [('extra extra large','XXL'),('extra large','XL'),('extra small','XS'),('medium','M'),('small','S'),('large','L')]:
  if re.search(r'\b(?:size\s+|in\s+)'+label+r'\b|\b'+label+r'\s+(?:(?:white|blue|red|black|navy|green|purple|pink)\s+)?(?:shirts?|tees?|blouses?)\b',s):
   f['apparel_size']=size;break
 m=re.search(r'\b(?:shirt size|size)\s+([a-z0-9.]+)',s)
 if m and 'apparel_size' not in f and 'shoe_size' not in f and m[1] not in ('system','is'):
  if re.search(r'\b(?:shoes?|sneakers?|boots?|loafers?|sandals?|heels?)\b',s) and re.fullmatch(r'\d+(?:\.\d+)?',m[1]):f['shoe_size']=m[1]
  elif re.search(r'\b(?:pants|trousers?|jeans?|shorts)\b',s) and m[1].isdigit():f['waist_size']=m[1]
  else:raise ConstraintError('Please specify a supported apparel size; I won’t use a saved size instead.')
 for key,vals in {'fit':['regular','slim','relaxed'],'style':['minimal','classic','sport','casual','modern'],'quality':['essential','premium','luxury'],'material':['vegan leather','alpaca wool','cotton','linen','silk','wool','denim','leather','suede','mesh','canvas','nubuck']}.items():
  hits=[v for v in vals if re.search(r'\b'+re.escape(v)+r'\b',s)]
  hits=[v for v in hits if not any(v!=w and v in w for w in hits)]
  if hits:
   if len(hits)>1 or any(re.search(r'\b(?:not|no|without|except|avoid)\s+(?:a\s+)?'+re.escape(v)+r'\b',s) for v in hits):
    raise ConstraintError(f'Please choose one required {key}; I won’t guess or relax that requirement.')
   f[key]=hits[0]
 # Match nouns at word boundaries: "shirt" must not match "t-shirt" or "sweatshirt".
 cats={'ties':r'\b(?:ties|tie|neckties?)\b','shirts':r'(?<![\w-])shirts?\b','tees':r'\b(?:t-shirts?|tees?)\b','trousers':r'\b(?:trousers?|pants|chinos?)\b','jeans':r'\bjeans?\b','jackets':r'\bjackets?\b','blouses':r'\bblouses?\b','knitwear':r'\b(?:knitwear|sweaters?|cardigans?)\b','shorts':r'\bshorts\b','activewear':r'\bactivewear\b','dresses':r'\bdresses?\b','skirts':r'\bskirts?\b','shoes':r'\b(?:shoes?|sneakers?|runners?|loafers?|boots?|sandals?|heels?|footwear)\b'}
 found=[k for k,v in cats.items() if re.search(v,s)]
 if len(found)>1:raise ConstraintError('Please search one product category at a time so I can enforce every requirement.')
 if found:f['category']=found[0];f['department']='footwear' if found[0]=='shoes' else 'accessories' if found[0]=='ties' else 'clothing'
 from global_catalog import FAMILIES,CLOTHING,REGIONAL_SHOES
 designs=[k for k in FAMILIES if k not in cats and k not in ('sneakers','loafers','boots','sandals','heels') and re.search(r'\b'+re.escape(k).replace(r'\-',r'[- ]')+r'\b',s)]
 if len(designs)>1:raise ConstraintError('Please choose one required design family.')
 if designs:
  design=designs[0];f['design_style']=design
  allowed=['shoes'] if design in REGIONAL_SHOES else [c for c,ds in CLOTHING.items() if design in ds]
  if f.get('category') and f['category'] not in allowed:raise ConstraintError('That design and product category do not match. Which should I use?')
  if not f.get('category') and allowed:f['category']=allowed[0];f['department']='footwear' if allowed[0]=='shoes' else 'clothing'
 for kind in ('sneakers','runners','loafers','boots','sandals','heels'):
  if re.search(r'\b'+kind[:-1]+r's?\b',s):f['kind']=kind
 if re.search(r'\b(?:women|women\x27s)\b',s):f['gender']='women'
 elif re.search(r'\b(?:men|men\x27s)\b',s):f['gender']='men'
 return f

def variant_size(product,filters):
 if product['category']=='ties':return filters.get('size') or 'One size'
 return filters.get('size') or filters.get('shoe_size' if product['category']=='shoes' else 'waist_size' if product['category'] in WAIST_CATEGORIES else 'apparel_size')

def matches(product,f):
 from color_constraints import values
 from catalog_search import FILTER_FIELDS
 if any(f.get(k) and str(product.get(k,''))!=str(f[k]) for k in FILTER_FIELDS):return False
 if product.get('color') in values(f.get('exclude_colors','')):return False
 included=values(f.get('include_colors',''))
 if included and product.get('color') not in included:return False
 price=product.get('price_cents',product.get('price'))
 if price is None or not Decimal(str(f.get('min_price') or 0))*100<=price<=Decimal(str(f.get('budget') or 100000))*100:return False
 size=variant_size(product,f)
 stock=product.get('stock') or {x['size']:x['stock'] for x in product.get('sizes',[])}
 return stock.get(size,0)>0 if size else any(n>0 for n in stock.values())
