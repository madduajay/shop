"""Local vector product photography alternative: model-specific studio illustrations.
No external resources, embedded scripts, or network image dependencies.
"""
from html import escape
from functools import lru_cache
from catalog import PALETTE
@lru_cache(maxsize=1100)
def product_svg(product_id,category,kind,color,material,design,gender):
 c=PALETTE[color];n=design;line='#25312c';stroke=f'stroke="{line}" stroke-opacity=".32" stroke-width="2" stroke-linejoin="round"';fill='fill="url(#cloth)"';details='';shape='';bottom=category in ('trousers','jeans','shorts','skirts');short=n%5 in (1,4)
 if category=='shoes':
  if kind in ('boots',):path='M135 169 L252 160 L271 285 Q311 314 367 323 Q404 332 416 369 L414 389 L92 389 L95 354 L130 323 Z'
  elif kind=='sandals':path='M95 337 Q160 311 208 326 L287 342 Q341 328 398 354 L418 379 L405 393 L85 393 Z'
  elif kind=='heels':path='M104 269 L156 272 Q202 350 240 339 L351 321 Q397 326 419 359 L412 376 L233 377 Q193 365 165 343 L148 411 L124 411 L132 324 Z'
  else:path='M97 298 Q141 306 161 265 L206 251 Q225 280 267 302 L325 319 Q385 320 414 352 L420 382 Q266 410 92 384 L82 355 Z'
  shape=f'<path d="{path}" {fill} {stroke}/>'
  if kind not in ('heels',):details+='<path d="M88 374 Q244 401 416 376 L416 394 Q245 421 88 395Z" fill="#e3dfd6" stroke="#a09b90" stroke-width="2"/>'
  if kind in ('sneakers','runners','boots'):
   details+='<path d="M165 280L263 324M160 291L250 332M151 305L235 340M142 318L218 347" stroke="#ede6d9" stroke-width="6" stroke-linecap="round"/><path d="M288 320Q276 352 286 382M129 325L112 378" fill="none" stroke="#fff" stroke-opacity=".3" stroke-width="3"/>'
  if kind=='sandals':details+='<path d="M146 327L201 372M239 339L287 382" stroke="#d6c7ac" stroke-width="28"/><path d="M140 327L193 373M235 339L280 382" stroke="#322c25" stroke-opacity=".4" stroke-width="2"/>'
  if kind=='loafers':details+='<path d="M167 285Q191 344 279 343L294 325" fill="none" stroke="#e3d4b8" stroke-width="4"/><path d="M176 314L257 340" stroke="#353029" stroke-opacity=".6" stroke-width="12"/>'
  if n%4==1:details+='<path d="M296 331Q343 327 376 349L354 366L298 365Z" fill="#e0d7c8" opacity=".85"/>'
  if n%4==2:details+=''.join(f'<circle cx="{300+x*15}" cy="{347+y*10}" r="2" fill="#1b2020" opacity=".35"/>' for x in range(5) for y in range(3))
  if n//4==2:details+=''.join(f'<path d="M{x} 394v12h13v-12" fill="#393b37"/>' for x in range(100,410,26))
 elif category in ('trousers','jeans','shorts'):
  end=365 if category=='shorts' else 468;inner=235 if n//10==2 else 215;outer=105 if n//10==2 else 135
  shape=f'<path d="M151 112L352 112L367 215L{500-outer} {end}L{500-inner} {end}L249 257L{inner} {end}L{outer} {end}L135 215Z" {fill} {stroke}/>'
  details=f'<path d="M151 137H352M249 137V250M159 141Q164 186 139 197M344 141Q336 186 363 197M{outer} {end-13}H{inner}M{500-inner} {end-13}H{500-outer}" fill="none" stroke="#f5e8cc" stroke-opacity=".55" stroke-width="2"/>'
  details+='<circle cx="255" cy="125" r="5" fill="#b4aa8e"/>'
  if n%10 in (2,6):details+='<path d="M140 230L199 230L198 290L143 288ZM304 230L362 230L357 290L303 288Z" fill="none" stroke="#eadfc8" stroke-opacity=".5" stroke-width="2"/>'
  if n//10==3:details+='<path d="M185 141L171 420M315 141L329 420" stroke="#202723" stroke-opacity=".3" stroke-width="3"/>'
 elif category=='skirts':
  hem=438 if n%3==0 else 375 if n%3==1 else 470
  shape=f'<path d="M181 133L319 133L390 {hem}Q250 {hem+18}110 {hem}Z" {fill} {stroke}/>'
  details=f'<path d="M177 151H323M181 157L154 {hem-8}M214 157L207 {hem-6}M286 157L293 {hem-6}M319 157L346 {hem-8}" fill="none" stroke="#fff" stroke-opacity=".28" stroke-width="2"/>'
 else:
  dress=category=='dresses';end=465 if dress else 394;waist=184 if gender=='women' else 158
  if short:edges=f'M202 114L154 128L95 210L145 239L166 213L{waist} 288L{128 if dress else 160} {end}Q250 {end+15} {372 if dress else 340} {end}L{500-waist} 288L334 213L355 239L405 210L346 128L298 114'
  elif n%5==2:edges=f'M202 114L170 131L181 232L{waist} 288L{128 if dress else 160} {end}Q250 {end+15} {372 if dress else 340} {end}L{500-waist} 288L319 232L330 131L298 114'
  else:edges=f'M202 114L155 131L105 203L76 365L120 376L170 226L{waist} 288L{128 if dress else 160} {end}Q250 {end+15} {372 if dress else 340} {end}L{500-waist} 288L330 226L380 376L424 365L395 203L345 131L298 114'
  shape=f'<path d="{edges}Q250 163 202 114Z" {fill} {stroke}/>'
  if n//10==1:details+='<path d="M202 114L250 186L298 114" fill="#302f29" opacity=".25"/>'
  elif n//10==4 or category in ('shirts','blouses','jackets'):details+='<path d="M202 114L250 145L223 177L192 131ZM298 114L250 145L277 177L308 131Z" fill="url(#cloth)" stroke="#22352f" stroke-opacity=".35" stroke-width="2"/>'
  else:details+='<path d="M202 114Q250 169 298 114" fill="none" stroke="#22352f" stroke-opacity=".3" stroke-width="9"/>'
  if n//10==2 or category in ('shirts','blouses','jackets'):
   details+=f'<path d="M250 148V{end-8}" stroke="#26352d" stroke-opacity=".3" stroke-width="2"/>'+''.join(f'<circle cx="254" cy="{y}" r="3" fill="#eee4d5"/>' for y in range(193,end-10,34))
  if n%10 in (2,3,6):details+='<path d="M282 206H321V256Q300 270 282 256Z" fill="none" stroke="#ebe3d7" stroke-opacity=".65" stroke-width="2"/>'
  if n%10 in (1,7):details+=f'<path d="M{waist+10} 288L{waist+15} {end-12}M{490-waist} 288L{485-waist} {end-12}" stroke="#f5ead7" stroke-width="2" opacity=".7"/>'
  if n//10==3 or (dress and n//10==3):details+='<path d="M179 288H321" stroke="#222d29" stroke-opacity=".5" stroke-width="14"/><rect x="238" y="280" width="24" height="16" fill="none" stroke="#c4ad73" stroke-width="3"/>'
 texture=''
 if material in ('wool','cashmere','merino','alpaca','jersey'):texture='<pattern id="weave" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 0L4 6L8 0" stroke="#fff" stroke-opacity=".12" fill="none"/></pattern>'
 else:texture='<pattern id="weave" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 0L6 6" stroke="#fff" stroke-opacity=".09"/></pattern>'
 # Texture is clipped to the precise silhouette, and each model changes construction.
 return f'''<svg xmlns="http://www.w3.org/2000/svg" width="500" height="600" viewBox="0 0 500 600"><title>{escape(product_id)} · {escape(color)} {escape(kind)}</title><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#f3f1ea"/><stop offset="1" stop-color="#e6e5dd"/></linearGradient><linearGradient id="cloth" x2="1" y2=".5"><stop stop-color="{c}"/><stop offset=".5" stop-color="{c}"/><stop offset="1" stop-color="{c}" stop-opacity=".78"/></linearGradient><filter id="shadow"><feDropShadow dx="0" dy="16" stdDeviation="12" flood-color="#25392b" flood-opacity=".17"/></filter>{texture}</defs><rect width="500" height="600" fill="url(#bg)"/><ellipse cx="250" cy="496" rx="143" ry="12" fill="#606859" opacity=".08"/><g filter="url(#shadow)">{shape}</g><clipPath id="product">{shape}</clipPath><rect x="60" y="90" width="380" height="410" fill="url(#weave)" clip-path="url(#product)"/>{details}<text x="250" y="552" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" letter-spacing="3" fill="#737b70">FORME / {escape(gender.upper())}</text></svg>'''
