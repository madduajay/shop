"""Non-shopping intents are resolved before any model or preference writes."""
import re
def catalog_discovery(text):
 s=text.strip().lower()
 browsing=bool(re.match(r"^(?:(?:can|could|would) you )?(?:please )?(?:show|display|find|browse|search|recommend|look for|shop for|i(?:'m| am) looking for|i (?:need|want|would like)|do you (?:sell|carry|stock|have))\b",s))
 context=bool(re.search(r'\b(my|preferences?|profile|account|orders?|purchases?|history|cart|basket|baf|crat|what|inside|there|altogether|memory|remember|checkout)\b',s))
 # A new bag is a product; the user's bag is cart state. Plural bags are products.
 if re.search(r'\bbag\b',s) and not re.search(r'\b(?:a|new|another) bag\b',s):context=True
 return browsing and not context

def bag_read_intent(text,last_read=None):
 if catalog_discovery(text):return False
 if re.search(r'\b(bag|cart|basket|baf|crat)\b',text,re.I):return True
 return last_read=='bag' and bool(re.search(r'\b(there|inside|altogether|total)\b|how much is that',text,re.I))

UNSUPPORTED='Sorry i am not sure how to handle this request'

def route(text,has_options=False,has_search=False):
 if (has_options or has_search) and re.fullmatch(r'(?:under|below|up to|at most|at least|over|above) \$?\d+(?:\.\d{1,2})?|between \$?\d+(?:\.\d{1,2})? and \$?\d+(?:\.\d{1,2})?',text.strip(),re.I):return 'shopping'
 s=re.sub(r'[^a-z0-9\s]',' ',text.lower());s=' '.join(s.split())
 from color_constraints import parse_colors
 if parse_colors(text)['exclude']:return 'shopping'
 # Questions about memory/status must never become shopping commands.
 q=re.sub(r'^(?:please )|(?: please)$','',s)
 if re.fullmatch(r'(?:(?:can|could|would) you )?(?:show|list|tell)(?: me)? (?:my )?(?:previous |past |recent )?(?:orders|purchases|order history)|(?:my |forme )?(?:previous |past |recent )?(?:orders|purchases|order history|purchase history)|what (?:did|have) i (?:buy|bought|order|ordered|purchase|purchased)(?: before| previously| from forme)?',q):return 'orders'
 q=re.sub(r' (?:in|as) (?:pretty printed )?json(?: format)?$','',q)
 if re.fullmatch(r'(?:(?:can|could) you )?(?:show|display)(?: me)? (?:my )?(?:forme )?preferences',q):return 'company_preferences' if 'forme' in q else 'preferences'
 pref_subject=r'(?:preferences|sizes?|sizes preferences|saved preferences|clothing preferences|shirt size|shoe size|waist size|budget|favourite colors|favorite colors)'
 preference_query=bool(re.fullmatch(r'(?:my )?'+pref_subject,q) or re.fullmatch(r'(?:do you know|do you remember|can you (?:tell me|show me)|tell me|show me|what (?:are|is)) my '+pref_subject,q) or re.fullmatch(r'what (?:do you (?:know|remember)|have you (?:saved|remembered))(?: about me)?',q))
 if re.fullmatch(r'what (?:does|did) forme (?:know|remember|save)(?: about me)?',q) or re.fullmatch(r'(?:my|what are my|do you know my) (?:preferences|sizes)(?: at| with| in| on) forme',q):return 'company_preferences'
 if re.fullmatch(r'(?:show|display|tell)(?: me)? (?:my )?(?:saved )?preferences (?:at|in|on|with|recorded on|saved in) forme',q) or re.fullmatch(r'what preferences does forme (?:have|remember)(?: about me)?',q):return 'company_preferences'
 if preference_query:return 'preferences'
 if re.fullmatch(r'(?:do you know|can you tell me|tell me) (?:who is (?:logged|signed) in|the (?:user|customer)(?: who is| that is)? (?:logged|signed) in|the (?:logged|signed) in (?:user|customer))',q):return 'identity'
 if re.search(r'\b(log\s*out|logout|sign\s*out)\b',s) and not re.search(r'\b(am i|who|status)\b',s):return 'logout'
 if (re.search(r'\b(who am i|which customer|which user|what customer|what user|selected customer|current customer|active customer|current user|active user|my identity|login status|sign in status|authentication status|am i (?:currently )?(?:logged|signed) in)\b',s)
     or re.search(r'\bwho (?:is|s)\b',s) and re.search(r'\b(user|customer|logged|signed)\b',s)
     or re.search(r'\b(?:logged|signed) in\b',s) and re.search(r'\b(who|which|whether|status)\b',s)):
  return 'identity'
 if s in ('my preferences','what do you remember','preferences'):return 'preferences'
 if re.fullmatch(r'(?:show me |show |view |read |what is in |what s in |what do i have in )?(?:my |the |forme |my forme )?(?:bag|cart)',s):return 'bag'
 if s in ('checkout','check out','proceed to checkout','ready to checkout','i want to checkout','buy now'):return 'checkout'
 if s in ('i approve this order','approve this order','confirm order','sign in','signin'):return 'action'
 if re.search(r'\b(remember|save|update) (at|with|for) forme\b',s):return 'shopping'
 if re.match(r'^(?:why is|who is|what is|tell me a|how does|what is the weather)\b',s) and not re.search(r'\b(clothing|clothes|shirt|shoe|shoes|size|fit|fabric|preferences|forme|thread|customer|order)\b',s):return 'unknown'
 if (has_options or has_search) and re.fullmatch(r'(?:under|up to|below) \d+(?: dollars)?|between \d+ and \d+|(?:xs|s|m|l|xl|xxl)|(?:in )?(?:red|navy|white|black|olive|sand|blue|brown|rose|burgundy|sage)',s):return 'shopping'
 if has_options and re.fullmatch(r'(?:the )?(?:first|second|third)(?: one| item| option)?|(?:choose|select|pick|take|i want|i ll take) (?:the )?(?:first|second|third)(?: one| item| option)?|show more|next page|more options|next options|(?:something |a bit |make it )?(?:cheaper|lighter|darker|more expensive|different|another)(?: please)?',s):return 'shopping'
 if re.search(r'\b(shopping|shop|clothes|clothing|outfit|wear|ties|tie|neckties|necktie|shirt|shirts|blouse|blouses|tee|tees|tshirt|trousers|pants|chinos|jeans|denim|jacket|jackets|knitwear|sweater|cardigan|shorts|activewear|dress|dresses|skirt|skirts|shoe|shoes|sneakers?|runners?|loafers?|boots?|sandals?|heels?|kurta|haori|guayabera|barong|dashiki|kaftan|breton|fair isle|poncho|espadrilles?|huaraches?|babouches?|jutti|geta|clogs?|yemeni|size|waist|inseam|budget|price|color|colour|fabric|material|fit|quality|width|brand|style|occasion|cotton|linen|silk|wool|leather|suede|red|navy|white|black|olive|sand|blue|brown|rose|burgundy|sage|formal|casual|wedding|office|gym|weekend|travel)\b',s):return 'shopping'
 return 'unknown'
