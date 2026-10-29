"""Photo-backed style families. Region denotes design inspiration, never origin."""
# key: color, material, silhouette, inspiration, construction
FAMILIES={
 'shirts':('white','cotton','Cotton Shirt','Contemporary','Collared, long sleeve, button-front'),
 'blue-shirt':('blue','cotton','Cotton Shirt','Contemporary','Collared, long sleeve, button-front'),
 'blouses':('white','silk','Silk Blouse','Contemporary','Collared, long sleeve, button-front'),
 'blue-blouse':('blue','cotton','Cotton Blouse','Contemporary','Collared, long sleeve, button-front'),
 'tees':('white','cotton','Cotton Tee','Contemporary','Crew neck, short sleeve'),
 'knitwear':('white','wool','Wool Knit','Contemporary','Crew neck, long sleeve, ribbed edges'),
 'trousers':('sand','cotton','Cotton Trouser','Contemporary','Straight leg, full length'),
 'jeans':('blue','denim','Straight Jean','Contemporary','Straight leg, five pockets'),
 'black-jeans':('black','denim','Straight Jean','Contemporary','Straight leg, five pockets'),
 'navy-jeans':('navy','denim','Straight Jean','Contemporary','Straight leg, five pockets'),
 'jackets':('olive','canvas','Canvas Jacket','Contemporary','Collared, button-front, patch pockets'),
 'shorts':('sand','cotton','Cotton Short','Contemporary','Tailored, above-knee length'),
 'activewear':('navy','mesh','Training Top','Contemporary','Short sleeve, crew neck'),
 'dresses':('rose','linen','Wrap Dress','Contemporary','Short sleeve, wrap front, midi length'),
 'skirts':('sand','cotton','A-line Skirt','Contemporary','A-line, midi length'),
 'sneakers':('white','leather','Court Sneaker','Contemporary','Lace-up, rubber cupsole'),
 'loafers':('brown','leather','Penny Loafer','Contemporary','Slip-on, penny strap'),
 'boots':('black','leather','Chelsea Boot','Contemporary','Ankle height, elastic side panels'),
 'sandals':('brown','leather','Two-strap Sandal','Contemporary','Open toe, two buckle straps'),
 'runners':('navy','mesh','Running Shoe','Contemporary','Lace-up, cushioned sole'),
 'heels':('black','leather','Block-heel Pump','Contemporary','Closed toe, block heel'),
 'kurta':('blue','cotton','Kurta-inspired Tunic','South Asia','Band collar, short placket, knee length, side slits'),
 'haori':('navy','cotton','Haori-inspired Jacket','Japan','Open front, straight lapels, wide rectangular sleeves'),
 'guayabera':('white','linen','Guayabera-inspired Shirt','Caribbean','Four patch pockets, vertical pintucks, short sleeve'),
 'barong':('white','linen','Barong-inspired Shirt','Philippines','Embroidered front, long sleeve, lightweight linen'),
 'dashiki':('burgundy','cotton','Dashiki-inspired Top','West Africa','Notched neck, geometric embroidery, short sleeve'),
 'kaftan':('olive','cotton','Kaftan-inspired Dress','North Africa','Ankle length, wide sleeves, ivory neckline braid'),
 'breton':('navy','cotton','Breton Stripe Top','France','Navy and ivory horizontal stripes, boat neck, long sleeve'),
 'fair-isle':('brown','wool','Fair Isle-inspired Knit','Scotland','Cream and charcoal geometric yoke, crew neck'),
 'poncho':('sand','alpaca wool','Poncho-inspired Knit','Andes','Rectangular silhouette, striped border, fringe'),
 'espadrilles':('sand','canvas','Espadrille','Spain','Closed toe, slip-on, braided jute sole'),
 'huaraches':('brown','leather','Huarache-inspired Shoe','Mexico','Woven leather upper, closed toe, flat sole'),
 'babouches':('rose','leather','Babouche-inspired Slipper','Morocco','Backless, pointed toe, flat sole'),
 'jutti':('burgundy','leather','Jutti-inspired Flat','South Asia','Gold embroidery, pointed toe, flat sole'),
 'geta':('black','wood','Geta-inspired Sandal','Japan','Natural wood platform, two supports, black padded straps'),
 'clogs':('black','leather','Clog','Sweden','Natural wood sole, open back, brass studs'),
 'driving-loafers':('blue','suede','Driving Loafer','Italy','Moccasin seam, rubber pebbled sole and heel'),
 'yemeni':('brown','leather','Yemeni-inspired Flat','Turkey','Rounded closed toe, low sides, stitched flat sole'),
}
CLOTHING={
 'shirts':['shirts','blue-shirt','kurta','guayabera','barong','dashiki'],
 'blouses':['blouses','blue-blouse','kurta','dashiki'],
 'tees':['tees','breton'],'knitwear':['knitwear','fair-isle','poncho'],
 'trousers':['trousers'],'jeans':['jeans','black-jeans','navy-jeans'],
 'jackets':['jackets','haori'],'shorts':['shorts'],'activewear':['activewear'],
 'dresses':['dresses','kaftan'],'skirts':['skirts']}
REGIONAL_SHOES=['espadrilles','huaraches','babouches','jutti','geta','clogs','driving-loafers','yemeni']
def apply_photos(rows):
 for p in rows:
  if 'design' not in p:
   p.update(region='Contemporary',design_style=p['kind'],photo_color=p['color'])
   if p['id'] in ('denim-black','denim-indigo'):
    key='black-jeans' if p['id']=='denim-black' else 'navy-jeans';p['image_url']=f'/assets/photos/{key}.jpg'
   continue
  n=p['design']
  if p['category']=='shoes':
   # Keep familiar types and distribute eight distinct regional silhouettes.
   key=p['kind'] if n%3==0 else REGIONAL_SHOES[(n+sum(map(ord,p['kind'])))%len(REGIONAL_SHOES)]
   p['kind']=key
  else:
   choices=CLOTHING[p['category']];key=choices[n%len(choices)]
  color,material,name,region,construction=FAMILIES[key]
  collection=p['name'].split(' ',1)[0]
  p.update(name=f'{collection} {name}',color=color,material=material,region=region,design_style=key,construction=construction,photo_color=color,image_url=f'/assets/photos/{key}.jpg',image_alt=f'{color.title()} {name}: {construction}',image_note=f'{color.title()} · {name}',description=f'{material.title()} · {construction}',care='Follow the care label; specialist care for delicate materials')
  # Fit is a stocked model attribute; pictured silhouette remains the family reference.
  if key in ('kurta','haori','dashiki','kaftan','poncho'):p['fit']='relaxed'
 return rows
