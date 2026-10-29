"""Deterministic merchandise models. Sizes are variants, never product counts."""
from copy import deepcopy
PALETTE={'navy':'#24364c','white':'#eee9df','black':'#292d30','olive':'#69725a','sand':'#c3ac8a','blue':'#6e8ca7','brown':'#8d6147','rose':'#bd8b89','burgundy':'#783f4a','sage':'#a3ada0'}
BRANDS=['Northline','Form & Field','Morrow','Atelier Vale','Common Ground','Stillwater','Aster Studio','Stride']
COLLECTIONS=['Alder','Arc','Ash','Aspen','Bay','Birch','Brook','Canyon','Cedar','Cliff','Coast','Cove','Dale','Dawn','Dune','Elm','Fern','Field','Flint','Glen','Harbor','Heath','Horizon','Iris','Juniper','Lake','Laurel','Linden','Meadow','Mesa','Moss','Oak','Orchard','Pine','Quarry','Reed','Ridge','River','Sage','Shore','Slate','Sol','Spruce','Stone','Summit','Terra','Vale','Willow','Wren','Yarrow']
CATEGORY_NAMES={'shirts':'Shirt','blouses':'Blouse','tees':'Tee','knitwear':'Knit','trousers':'Trouser','jeans':'Jean','jackets':'Jacket','shorts':'Short','activewear':'Training Top','dresses':'Dress','skirts':'Skirt'}
MATERIALS={'shirts':['cotton','linen','twill','poplin','oxford'],'blouses':['silk','linen','cotton','viscose','satin'],'tees':['cotton','jersey','modal','linen','hemp'],'knitwear':['wool','cashmere','cotton','merino','alpaca'],'trousers':['twill','linen','wool','cotton','corduroy'],'jeans':['denim','denim','denim','denim','denim'],'jackets':['denim','canvas','wool','nylon','leather'],'shorts':['cotton','linen','nylon','twill','denim'],'activewear':['nylon','jersey','mesh','modal','merino'],'dresses':['linen','silk','cotton','viscose','satin'],'skirts':['denim','linen','wool','cotton','satin']}
BASE_PRICE={'shirts':48,'blouses':58,'tees':24,'knitwear':68,'trousers':64,'jeans':72,'jackets':110,'shorts':38,'activewear':42,'dresses':84,'skirts':56,'shoes':85}
def build_catalog(legacy):
 rows=[]
 for old in legacy:
  p=deepcopy(old);p.update(gender='men',department='footwear' if p['category']=='shoes' else 'clothing',kind='sneakers' if p['category']=='shoes' else p['category'],image_url='/assets/'+p['image']+'.jpg',model_code='FM-'+p['id'].upper(),construction='Original collection',care='Follow the care label',size_basis='US men' if p['category']=='shoes' else 'US apparel',description=p['material'].title()+' · '+p['fit']+' fit · original collection');rows.append(p)
 for gender in ('men','women'):
  categories=['shirts' if gender=='men' else 'blouses','tees','knitwear','trousers','jeans','jackets','shorts' if gender=='men' else 'dresses','activewear' if gender=='men' else 'skirts']
  clothing=[]
  for ci,category in enumerate(categories):
   for n in range(50):
    material=MATERIALS[category][n%5];fit=['regular','relaxed','slim'][n%3];color=list(PALETTE)[(n+ci*3+(gender=='women')*2)%10];quality=['essential','premium','luxury'][n//17];brand=BRANDS[(n+ci)%8]
    cut=['straight','tapered','wide-leg','pleated','cropped'][n//10] if category in ('trousers','jeans','shorts') else ['crew-neck','v-neck','button-front','mock-neck','collared'][n//10] if category not in ('skirts','dresses','jackets') else ['tailored','wrap','panelled','belted','A-line'][n//10]
    detail=['clean-finish','contrast-stitch','patch-pocket','welt-pocket','rib-trim','side-slit','utility-pocket','piped-edge','box-pleat','textured-panel'][n%10]
    sleeve=['long sleeve','short sleeve','sleeveless','three-quarter sleeve','cap sleeve'][n%5]
    construction=f'{cut}; {detail}; '+(sleeve if category not in ('trousers','jeans','shorts','skirts') else ['full length','ankle length','cropped length'][n%3])
    id=f'{gender[0]}-{category}-{n+1:03}'
    sizes=[str(s) for s in range(26,45,2)] if category in ('trousers','jeans','shorts') else ['XS','S','M','L','XL','XXL']
    price=(BASE_PRICE[category]+(n%10)*3+(n//10)*8+(quality=='luxury')*44)*100
    clothing.append(dict(id=id,name=f'{COLLECTIONS[n]} {material.title()} {CATEGORY_NAMES[category]}',gender=gender,department='clothing',category=category,kind=category,material=material,fit=fit,color=color,quality=quality,brand=brand,price=price,occasion=['everyday','work','travel','evening','weekend'][n%5],style=['minimal','classic','casual','modern','sport'][n%5],image_url=f'/assets/products/{id}.svg',model_code=id.upper(),construction=construction,cut=cut,detail=detail,sleeve=sleeve,design=n,care='Cold wash; reshape and dry flat' if material not in ('leather','silk','wool','cashmere','alpaca') else 'Specialist care recommended',size_basis='US waist inches' if category in ('trousers','jeans','shorts') else 'US apparel',description=f'{material.title()} · {fit} fit · {construction}',stock={s:(0 if (n+k+ci)%19==0 else 3+(n+k)%12) for k,s in enumerate(sizes)}))
  # Existing listing IDs, prices and stock basis remain usable by historical orders.
  rows.extend(clothing[6:] if gender=='men' else clothing)
  footwear=[]
  for ki,kind in enumerate(['sneakers','loafers','boots','sandals','runners'] if gender=='men' else ['sneakers','loafers','boots','sandals','heels']):
   for n in range(20):
    id=f'{gender[0]}-{kind}-{n+1:03}';material=['leather','suede','canvas','mesh'][n%4] if kind in ('sneakers','runners') else ['leather','suede','vegan leather','nubuck'][n%4];color=list(PALETTE)[(n+ki*2)%10];fit='regular';quality=['essential','premium','luxury'][n//7]
    sole=['cupsole','crepe sole','lug sole','flex sole','platform sole'][n//4];detail=['tonal panels','contrast panels','perforated upper','stitched upper'][n%4];construction=f'{sole}; {detail}'
    sizes=[str(s) for s in range(6,14)] if gender=='men' else [str(s) for s in range(5,12)]
    footwear.append(dict(id=id,name=f'{COLLECTIONS[n+ki*5]} {material.title()} {kind.title()}',gender=gender,department='footwear',category='shoes',kind=kind,material=material,fit=fit,color=color,quality=quality,brand=BRANDS[(n+ki)%8],price=(BASE_PRICE['shoes']+ki*12+n*4+(quality=='luxury')*35)*100,occasion='running' if kind=='runners' else 'evening' if kind=='heels' else 'everyday',style='sport' if kind in ('runners','sneakers') else 'classic',image_url=f'/assets/products/{id}.svg',model_code=id.upper(),construction=construction,sole=sole,detail=detail,design=n,care='Wipe clean; air dry',size_basis=f'US {gender}',description=f'{material.title()} · {sole} · {detail}',stock={s:(0 if (n+k+ki)%17==0 else 3+(n+k)%8) for k,s in enumerate(sizes)}))
  rows.extend(footwear[2:] if gender=='men' else footwear)
 from global_catalog import apply_photos
 rows=apply_photos(rows)
 assert len(rows)==1000 and len({p['id'] for p in rows})==1000
 return rows
