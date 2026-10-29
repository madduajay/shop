"""Local synthetic Thread authentication, isolated sessions and read-only chat archives."""
import hashlib,secrets,time,json,re,html,os
from http.cookies import SimpleCookie
from urllib.parse import parse_qs
from starlette.responses import HTMLResponse,JSONResponse,RedirectResponse,Response
# Browser cookies ignore ports; fixture deployments must not overwrite live sign-in.
_THREAD_PORT=os.getenv('THREAD3_PORT','8543')
COOKIE='__Host-thread3_thread_session'+('' if _THREAD_PORT=='8543' else '_'+_THREAD_PORT)
class ThreadAuth:
 def __init__(self,app):
  self.app=app;self.db=app.thread_accounts.db
  self.db.executescript('''CREATE TABLE IF NOT EXISTS thread_sessions(id TEXT PRIMARY KEY,customer INTEGER,csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS thread_archives(id TEXT PRIMARY KEY,customer INTEGER NOT NULL,created REAL NOT NULL,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS thread_context_resets(customer INTEGER NOT NULL,request_id TEXT NOT NULL,PRIMARY KEY(customer,request_id));''');self.db.commit()
 def session(self,r):
  c=SimpleCookie();c.load(r.headers.get('cookie',''));token=c.get(COOKIE)
  if not token:return None
  key=hashlib.sha256(token.value.encode()).hexdigest();row=self.db.execute('SELECT customer,csrf,expires FROM thread_sessions WHERE id=?',(key,)).fetchone()
  return {'id':key,'customer':row[0],'csrf':row[1]} if row and row[2]>time.time() else None
 def issue(self,customer=None):
  token=secrets.token_urlsafe(32);key=hashlib.sha256(token.encode()).hexdigest();csrf=secrets.token_urlsafe(32)
  self.db.execute('INSERT INTO thread_sessions VALUES(?,?,?,?)',(key,customer,csrf,time.time()+86400));self.db.commit();return token,{'id':key,'customer':customer,'csrf':csrf}
 def cookie(self,response,token):response.set_cookie(COOKIE,token,max_age=86400,secure=True,httponly=True,samesite='strict',path='/');return response
 def archive(self,flow):
  if not flow.messages and not flow.trace:return None
  key=secrets.token_hex(16);data={'messages':flow.messages,'trace':flow.trace}
  self.db.execute('INSERT INTO thread_archives VALUES(?,?,?,?)',(key,flow.customer,time.time(),json.dumps(data)));self.db.commit();return key
 def reset_ids(self,customer):return [r[0] for r in self.db.execute('SELECT request_id FROM thread_context_resets WHERE customer=?',(customer,))]
 def reset_done(self,customer,rid):self.db.execute('DELETE FROM thread_context_resets WHERE customer=? AND request_id=?',(customer,rid));self.db.commit()
 def forget_temporary(self,flow):
  m=self.app.memory;pending=m.pending_share(flow.customer);ids={flow.catalog_snapshot.get('filters',{}).get('request_id'),pending.get('metadata',{}).get('request_id')}
  # Only this active request is removed; another login session's newer request survives.
  tables={r[0] for r in m.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if 'thread_shopping_intents' in tables:
   row=m.db.execute('SELECT data FROM thread_shopping_intents WHERE customer=?',(flow.customer,)).fetchone()
   if row:
    value=json.loads(row[0]);ids.add(value.get('request_id') if not flow.catalog_snapshot else None)
    if value.get('request_id') in ids:
     value['current_request']={};value['expires_at']=0;m.db.execute('UPDATE thread_shopping_intents SET data=? WHERE customer=?',(json.dumps(value),flow.customer))
  if pending and pending.get('metadata',{}).get('request_id') in ids:
   pending['intent']={}
   if pending.get('preferences'):m.db.execute('UPDATE pending_forme_memory SET data=? WHERE customer=?',(json.dumps(pending),flow.customer))
   else:m.db.execute('DELETE FROM pending_forme_memory WHERE customer=?',(flow.customer,))
  if not any(ids):ids.add(secrets.token_hex(16))
  for rid in ids:
   if rid:self.db.execute('INSERT OR IGNORE INTO thread_context_resets VALUES(?,?)',(flow.customer,rid))
  m.db.commit();self.db.commit()
 async def handle(self,r):
  import sys
  module=sys.modules[type(self.app).__module__]
  AGENT,Flow,CURRENT,ROOT=module.AGENT,module.Flow,module.CURRENT,module.ROOT
  path=r.url.path
  # A concurrent favicon redirect through login can issue a late anonymous
  # cookie that replaces the newly rotated authenticated session cookie.
  if path=='/favicon.ico':return Response(status_code=204)
  s=self.session(r)
  if path=='/login':
   if s and s['customer']:return RedirectResponse('/',303)
   token=None
   if not s:token,s=self.issue()
   error=''
   if r.method=='POST':
    f={k:v[0] for k,v in parse_qs((await r.body()).decode()).items()}
    if r.headers.get('origin')!=AGENT or not secrets.compare_digest(f.get('csrf',''),s['csrf']):return HTMLResponse('Please reload sign-in.',403)
    account=self.app.thread_accounts.authenticate(f.get('email',''),f.get('password',''))
    if not account:error='Please check your email and password.'
    else:
     self.db.execute('DELETE FROM thread_sessions WHERE id=?',(s['id'],));self.db.commit();token,s=self.issue(account['customer']);return self.cookie(RedirectResponse('/',303),token)
   page=(ROOT/'thread-login.html').read_text().replace('{{csrf}}',s['csrf']).replace('{{error}}',html.escape(error))
   response=HTMLResponse(page,status_code=401 if error else 200,headers={'Cache-Control':'no-store'});return self.cookie(response,token) if token else response
  if not s or not s['customer']:
   return JSONResponse({'error':'Sign in to Thread to continue.'},401) if path.startswith('/api/') else RedirectResponse('/login',303)
  if path=='/trace-filter.js':
   return Response((ROOT/'trace-filter.js').read_text(),media_type='text/javascript',headers={'Cache-Control':'no-store'})
  if path=='/traces':
   from trace_page import render
   archive=r.query_params.get('archive');events=[]
   if archive:
    row=self.db.execute('SELECT data FROM thread_archives WHERE id=? AND customer=?',(archive,s['customer'])).fetchone()
    if not row:return HTMLResponse('Trace archive not found.',404,headers={'Cache-Control':'no-store'})
    events=json.loads(row[0]).get('trace',[])
   else:
    flow=self.app.clients.get(s['id'],{}).get(s['customer']);events=list(flow.trace) if flow else []
    events.extend(json.loads(row[0]) for row in self.db.execute('SELECT data FROM webhook_traces WHERE customer=? ORDER BY rowid',(s['customer'],)))
    events.sort(key=lambda event:event.get('timestamp',''))
   archives=[{'id':x[0],'created':x[1]} for x in self.db.execute('SELECT id,created FROM thread_archives WHERE customer=? ORDER BY created DESC',(s['customer'],))]
   return HTMLResponse(render(events,archives,archive,r.query_params.get('channel','poppy')),headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
  if path=='/':return HTMLResponse((ROOT/'index.html').read_text().replace('{{csrf}}',s['csrf']),headers={'Cache-Control':'no-store'})
  if not path.startswith('/api/') or r.method!='POST':return HTMLResponse('Not found',404)
  if r.headers.get('origin')!=AGENT or not secrets.compare_digest(r.headers.get('x-thread-csrf',''),s['csrf']):return JSONResponse({'error':'Reload Thread and try again.'},403)
  b=await r.json()
  if not isinstance(b,dict) or ('customer' in b and b['customer']!=s['customer']) or 'client' in b:return JSONResponse({'error':'Your Thread login determines your identity.'},403)
  customer=s['customer'];flow=self.app.clients.setdefault(s['id'],{}).setdefault(customer,Flow(self.app,customer))
  async with flow.lock:
   # Recheck after acquiring the lock: an earlier queued logout may revoke this session.
   if not self.session(r):return JSONResponse({'error':'Sign in to Thread to continue.'},401)
   CURRENT.set(flow)
   if path=='/api/state':result={'customer':customer,'name':self.app.memory.get(customer)['name'],'messages':flow.messages,'notifications':self.app.watch_memory.inbox(customer),'signin':flow.signurl}
   elif path=='/api/notifications/dismiss':
    event=b.get('event_id')
    if not isinstance(event,str) or not re.fullmatch('[a-f0-9]{32}',event):return JSONResponse({'error':'Invalid notification.'},400)
    if not self.app.watch_memory.dismiss(customer,event):return JSONResponse({'error':'Notification not found.'},404)
    result={'dismissed':True}
   elif path=='/api/chat':
    text=str(b.get('text',''))[:1000]
    if re.search(r'\bswitch\s+(?:to\s+)?customer\b',text,re.I):msg,cards='To change customers, sign out of Thread and sign in to the other demo account.',[]
    else:msg,cards=await flow.chat(text)
    label=next((x['name'] for x in flow.options if text=='select product '+x['id']),None)
    label=label or next((r['card']['name']+', size '+r['card']['size'] for key,r in flow.card_selections.items() if text=='select card '+key),None)
    label=label or next((x['name'] for x in self.app.watch_memory.inbox(customer) if text=='add available item '+x['event_id']),None)
    flow.messages.extend([{'role':'user','text':'Add '+label+' to my bag' if label else text},{'role':'assistant','text':msg,'cards':cards}]);result={'customer':customer,'name':self.app.memory.get(customer)['name'],'reply':msg,'cards':cards,'signin':flow.signurl}
   elif path=='/api/poll':
    msg=await flow.poll()
    if msg:
     msg,flow.poll_cards=await flow.continue_agent_task(msg,flow.poll_cards)
     flow.messages.append({'role':'assistant','text':msg,'cards':flow.poll_cards})
    result={'reply':msg,'cards':flow.poll_cards,'notifications':self.app.watch_memory.inbox(customer),'signin':flow.signurl};flow.poll_cards=[]
   elif path=='/api/trace':
    from trace_page import safe_events
    result={'events':safe_events(flow.trace)}
   elif path=='/api/archives':
    if b.get('id'):
     row=self.db.execute('SELECT data FROM thread_archives WHERE id=? AND customer=?',(b['id'],customer)).fetchone()
     if not row:return JSONResponse({'error':'Archive not found.'},404)
     from trace_page import safe_events
     archived=json.loads(row[0]);archived['trace']=safe_events(archived.get('trace',[]));result={'archive':archived}
    else:result={'archives':[{'id':r[0],'created':r[1]} for r in self.db.execute('SELECT id,created FROM thread_archives WHERE customer=? ORDER BY created DESC',(customer,))]}
   elif path=='/api/clear':
    if b.get('confirm') is not True:return JSONResponse({'error':'Confirm clearing this conversation.'},400)
    if flow.uncertain:return JSONResponse({'error':'Check the pending order status before clearing this chat.'},409)
    archive=self.archive(flow);self.forget_temporary(flow)
    await flow.clear_conversation();result={'cleared':True,'archive':archive}
   elif path=='/api/logout':
    self.archive(flow)
    self.db.execute('DELETE FROM thread_sessions WHERE id=?',(s['id'],));self.db.commit()
    for key,ticket in list(self.app.tickets.items()):
     if ticket['flow'] is flow:self.app.tickets.pop(key)
    await flow.browser.close();self.app.clients.pop(s['id'],None)
    response=JSONResponse({'signed_out':True});response.delete_cookie(COOKIE,path='/',secure=True,httponly=True,samesite='strict');return response
   else:return JSONResponse({'error':'Not found'},404)
  dismissed=set(self.app.watch_memory.dismissed(customer));result['dismissed_notifications']=sorted(dismissed)
  def visible(cards):return [c for c in cards if c.get('type')!='availability' or c.get('event_id') not in dismissed]
  for key in ('cards','notifications'):
   if key in result:result[key]=visible(result[key])
  if 'messages' in result:result['messages']=[{**m,'cards':visible(m.get('cards',[]))} for m in result['messages']]
  if result.get('signin'):
   result['signin_label']=getattr(flow,'signin_label',None) or ('Review FORME permissions' if flow.token and flow.token.signed_in else 'Sign in with FORME')
  return JSONResponse(result,headers={'Cache-Control':'no-store'})
