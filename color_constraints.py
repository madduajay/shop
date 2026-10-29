"""Color constraints are eligibility rules, separate from preference ranking.

Parse polarity from the original utterance before model normalization. A negative
list extends across comma/and/or/nor, but ends at an adversative or new clause.
"""
import re
from catalog import PALETTE
COLORS=set(PALETTE)|{'red','purple','green','orange','yellow','pink','grey','cream','tan','turquoise','maroon'}
ALIASES={'gray':'grey','ivory':'white','beige':'sand','indigo':'navy'}
COLOR=r'(?:'+ '|'.join(sorted(COLORS|set(ALIASES),key=len,reverse=True))+r')'
NEG=r"(?:anything\s+but|other\s+than|rather\s+than|except(?:\s+for)?|excluding|exclude|avoid|without|neither|not(?:\s+(?:interested\s+in|looking\s+for|keen\s+on|in))?|no|never|don['’]?t\s+(?:want|like|show|wear|prefer|include)(?:\s+me)?|do\s+not\s+(?:want|like|show|wear|prefer|include)(?:\s+me)?)"
LIST=COLOR+r'(?:\s*(?:,|and|or|nor|/)\s*'+COLOR+r')*'
def parse_colors(text):
 text=text.lower();negative=set();masked=list(text)
 pattern=r'\b'+NEG+r'\s+(?:(?:the|any|color|colour|in)\s+)*('+LIST+r')\b'
 for m in re.finditer(pattern,text):
  negative.update(ALIASES.get(c,c) for c in re.findall(COLOR,m[1]))
  masked[m.start():m.end()]=' '*(m.end()-m.start())
 # Postposed rejection: "white is not okay" / "white isn't wanted".
 for m in re.finditer(r'\b('+LIST+r")\s+(?:is|are|isn['’]?t|aren['’]?t)\s+(?:not\s+)?(?:wanted|allowed|okay|ok|acceptable)\b",text):
  if re.search(r"\bnot\b|n['’]?t",m[0]):
   negative.update(ALIASES.get(c,c) for c in re.findall(COLOR,m[1]));masked[m.start():m.end()]=' '*(m.end()-m.start())
 positive={ALIASES.get(m[0],m[0]) for m in re.finditer(r'\b'+COLOR+r'\b',''.join(masked))}
 return {'include':sorted(positive-negative),'exclude':sorted(negative),'conflict':bool(positive and not positive-negative and negative),'mentioned':bool(positive or negative),'search_text':''.join(masked)}
def values(value):
 if isinstance(value,list):parts=value
 elif isinstance(value,str):parts=[x.strip().lower() for x in value.split(',') if x.strip()]
 else:raise ValueError('Colors must be a list or comma-separated names.')
 if any(not isinstance(x,str) or x not in COLORS for x in parts):raise ValueError('Choose supported colors.')
 return set(parts)
def color_filters(f):
 excluded=values(f.get('exclude_colors',''));included=values(f.get('include_colors',''))
 return included,excluded
