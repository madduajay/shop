"""Conversation-owned card selections, independent of the latest search."""
import copy,re,secrets
class CardContext:
 def remember_card(self,card,requirements):
  key=secrets.token_hex(16);card=dict(card,card_id=key)
  self.card_selections[key]={'card':copy.deepcopy(card),'requirements':copy.deepcopy(requirements),'state':'ready'}
  return card
 def requested_card(self,text):
  """Resolve user selection independently of any model-proposed card ID."""
  q=text.strip().lower();rows=list(self.card_selections.items())
  if not re.search(r'\b(add|take|buy|put|get)\b',q) and not re.fullmatch(r'(?:the )?(?:first|second|third|1st|2nd|3rd)(?: one)?[.!]?',q):return None
  if re.search(r"\b(?:don't|do not|never|not yet|might|maybe|tomorrow)\b",q):return None
  named=[(k,r) for k,r in rows if r['card']['name'].lower() in q]
  ordinal=re.search(r'\b(first|second|third|1st|2nd|3rd)\b',q)
  if named:
   unique={(r['card']['id'],r['card']['size'],r['card']['color']):(k,r) for k,r in named};matches=list(unique.values())
  elif ordinal and not re.search(r'\b(earlier|previous|old)\b',q):
   index={'first':0,'1st':0,'second':1,'2nd':1,'third':2,'3rd':2}[ordinal[1]]
   matches=[(self.options[index]['card_id'],self.card_selections[self.options[index]['card_id']])] if index<len(self.options) else []
  else:return None
  if len(matches)!=1:return None
  key,record=matches[0];card=record['card']
  from color_constraints import parse_colors
  colors=parse_colors(q)
  if colors['include'] and card['color'] not in colors['include'] or card['color'] in colors['exclude']:return None
  size=re.search(r'\bsize\s+([0-9]+(?:\.[0-9]+)?|xxl|xl|xs|[sml])\b',q)
  if size and str(card['size']).lower()!=size[1]:return None
  if re.search(r'\b(shoes?|sneakers?|sandals?|boots?)\b',q) and card['category']!='shoes':return None
  if re.search(r'\bshirts?\b',q) and card['category'] not in ('shirts','blouses','tees'):return None
  return key
 def unselected_add_search(self,text):
  q=text.strip()
  if q.startswith('add available item '):return None
  # New product descriptions are discovery, not consent to an old card.
  m=re.fullmatch(r'(?:please )?add (.+?)(?: to (?:my |the )?(?:bag|cart))?[.!]?',q,re.I)
  if not m:return None
  if re.search(r'\b(first|second|third|1st|2nd|3rd|this|that|earlier|previous)\b',m[1],re.I):return None
  if any(r['card']['name'].lower() in q.lower() for r in self.card_selections.values()):return None
  return 'find '+m[1]
 async def select_card(self,key):
  record=self.card_selections.get(key)
  if not record:return 'That card is not available in this conversation. Please search again.',[]
  if record['state']=='added':return 'That card was already added once. Check your bag to change its quantity.',[]
  if record['state']=='pending':return await self.recover_pending_add(key)
  if record['state']=='uncertain':return 'I could not confirm the previous add. Please check your bag; I won’t submit another add automatically.',[]
  c=record['card'];requirements=dict(record['requirements']);requirements.pop('expires_at',None)
  # Bind the variant attributes even where the originating search allowed alternatives.
  requirements.update(color=c['color'],include_colors=c['color'])
  return await self.add_selected(c['id'],c['size'],c['name'],requirements=requirements,card_id=key,quoted_price=c['price_cents'])
 async def historical_selection(self,text):
  q=text.strip().lower().rstrip('.!')
  m=re.fullmatch(r'(?:add|buy|take)(?: the| that| this| earlier| previous| earlier shown)* (shirt|shoe|shoes|sneaker|sneakers)(?: to (?:my |the )?(?:bag|cart))?',q)
  rows=list(self.card_selections.items())
  if m:
   categories={'shirts','blouses','tees'} if m[1]=='shirt' else {'shoes'}
   rows=[(k,r) for k,r in rows if r['card']['category'] in categories]
  elif re.match(r'^(?:add|buy|take) ',q):
   rows=[(k,r) for k,r in rows if r['card']['name'].lower() in q]
   if not rows:return None
  else:return None
  unique={ (r['card']['id'],r['card']['size'],r['card']['color'],r['card']['price_cents']):(k,r) for k,r in rows }
  if not unique:return 'I don’t have an earlier matching card in this conversation. Please search for it first.',[]
  if len(unique)==1:return await self.select_card(next(iter(unique.values()))[0])
  self.card_clarification=[k for k,r in unique.values()]
  cards=[r['card'] for k,r in unique.values()]
  return 'Which one did you mean? Choose its original card below; I’ll keep that card’s size and color.',cards
