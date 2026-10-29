"""Account-bound explicit preference editor; no inferred/temporary data writes."""
import json,hashlib
from html import escape as E
MULTI={'colors','excluded_colors','brands'}
LABELS={'gender':'Collection','size_system':'Size system','shirt_size':'Clothing size','waist':'Waist size','shoe_size':'Shoe size','colors':'Favorite colors','excluded_colors':'Colors to exclude','fit':'Fit','style':'Style','design_style':'Design family','material':'Material','brands':'Favorite brands','quality':'Quality','occasion':'Occasion','budget_min':'Minimum budget · USD','budget':'Maximum budget · USD'}
def revision(record):return hashlib.sha256(json.dumps((record or {}).get('preferences',{}),sort_keys=True).encode()).hexdigest()
def options(products,gender=''):
 rows=[p for p in products if not gender or p['gender']==gender]
 opts={k:sorted({p[{'colors':'color','excluded_colors':'color','brands':'brand'}.get(k,k)] for p in rows}) for k in ('colors','excluded_colors','brands','fit','style','design_style','material','quality','occasion')}
 opts.update(gender=sorted({p['gender'] for p in products}),size_system=['US'])
 for key,categories in [('shirt_size',None),('waist',{'trousers','jeans','shorts'}),('shoe_size',{'shoes'})]:
  sizes={s for p in rows if (p['category'] in categories if categories else p['category'] not in {'shoes','trousers','jeans','shorts'}) for s in p['stock']}
  opts[key]=sorted(sizes,key=lambda x:(0,float(x)) if x.replace('.','').isdigit() else (1,(['XXS','XS','S','M','L','XL','XXL','XXXL'].index(x) if x in ['XXS','XS','S','M','L','XL','XXL','XXXL'] else 99),x))
 # Availability-only labels are not necessarily supported lasting preferences.
 from company_context import validate_preferences
 for key,values in opts.items():
  supported=[]
  for value in values:
   try:validate_preferences({key:[value] if key in MULTI else value})
   except ValueError:continue
   supported.append(value)
  opts[key]=supported
 return opts

def render(products,record,csrf,message='',error=False):
 saved={k:v['value'] for k,v in (record or {}).get('preferences',{}).items()};opts=options(products,saved.get('gender',''));fields=''
 for key,label in LABELS.items():
  value=saved.get(key,[] if key in MULTI else '')
  if key.startswith('budget'):
   control=f'<input type="number" name="pref_{key}" min="0" max="10000" step="1" value="{E(str(value))}">'
  else:
   choices=opts[key];selected=value if isinstance(value,list) else [value]
   choices=list(dict.fromkeys(choices+[v for v in selected if v and v not in choices]))
   control=(f'<input type="hidden" name="pref_{key}" value="">' if key in MULTI else '')+f'<select name="pref_{key}"'+(' multiple size="4"' if key in MULTI else '')+'>'
   if key not in MULTI:control+='<option value="">No preference</option>'
   control+=''.join(f'<option value="{E(v)}"'+(' selected' if v in selected else '')+'>'+E(v.replace('-',' ').title() if key not in ('brands','shirt_size','size_system') else v)+'</option>' for v in choices)+'</select>'
  fields+=f'<div class="preference-field"><label>{label}{control}</label><button type="button" class="pref-clear" data-clear-pref="pref_{key}">Clear {label.lower()}</button></div>'
 data={g:options(products,g) for g in ('','men','women')}
 return '<section class="preferences-page"><div class="eyebrow">YOUR FORME / YOUR WAY</div><h1>Made more personal.</h1><p class="pref-intro">A few details make finding your next favorite easier. These preferences belong to your FORME account.</p>'+('<p role="'+('alert' if error else 'status')+'" class="pref-feedback">'+E(message)+'</p>' if message else '')+f'<form method="post" action="/shop/preferences" id="preferences-form"><input type="hidden" name="csrf" value="{E(csrf)}"><input type="hidden" name="revision" value="{revision(record)}"><div class="pref-layout"><aside class="pref-aside"><h2>Your wardrobe, considered.</h2><p>Choose several colors or brands with ⌘/Ctrl. Use Clear to remove a saved preference, then save.</p><p>Sizes follow this catalog’s US system. Collection changes adjust available sizes and design families; your current choices stay until you edit them.</p><p>Thread reads the latest FORME preferences when you ask, through your authorized connection. Your Thread preferences stay separate.</p></aside><div class="pref-fields">{fields}</div></div><div class="pref-save"><button>Save preferences</button><a href="/shop">Back to the collection</a><span>Only your explicit choices are saved.</span></div></form><div hidden id="preference-options">'+E(json.dumps(data))+'</div></section>'

def save(context,account,products,form):
 old=context.get(account) or {'preferences':{}}
 if form.get('revision')!=revision(old):raise ValueError('Your preferences changed in another tab. Reload before saving.')
 allowed={'csrf','revision'}|{'pref_'+k for k in LABELS}
 if set(form)-allowed:raise ValueError('Unexpected preference field.')
 current={k:v['value'] for k,v in old['preferences'].items()};updates={};clear=[]
 gender=form.get('pref_gender',current.get('gender',''));opts=options(products,gender)
 for k in LABELS:
  if 'pref_'+k not in form:continue
  raw=form['pref_'+k];value=raw if k in MULTI else raw
  if k in MULTI:value=[v for v in (raw if isinstance(raw,list) else [raw]) if v]
  if value in ('',[]):
   if k in current:clear.append(k)
   continue
  if value==current.get(k) or k in MULTI and set(value)==set(current.get(k,[])):continue
  if k.startswith('budget'):
   if not str(value).isdigit():raise ValueError('Budgets must be whole dollar amounts.')
   value=int(value)
  elif any(v not in opts[k] for v in (value if isinstance(value,list) else [value])):raise ValueError('Choose a valid '+LABELS[k].lower()+' for this collection.')
  updates[k]=value
 combined={k:v for k,v in current.items() if k not in clear}|updates
 if set(combined.get('colors',[]))&set(combined.get('excluded_colors',[])):raise ValueError('A color cannot be both a favorite and excluded.')
 context.patch(account,updates,clear)
