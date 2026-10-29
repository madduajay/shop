"""Conservative request lifetime. The local demo's user timezone is America/Phoenix."""
import re,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

def request_expiry(text,timezone_name='America/Phoenix'):
 now=time.time();expiry=int(now)+3600;low=text.lower()
 duration=re.search(r'\b(?:for|next)\s+(\d{1,3})\s+(minutes?|hours?)\b',low)
 if duration:return int(now)+min(172800,max(60,int(duration[1])*(3600 if duration[2].startswith('hour') else 60)))
 if timezone_name and re.search(r'\b(today|tonight|tomorrow)\b',low):
  try:
   local=datetime.fromtimestamp(now,ZoneInfo(timezone_name));days=2 if 'tomorrow' in low else 1
   expiry=int((local+timedelta(days=days)).replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
  except (ValueError,KeyError):pass
 return expiry
