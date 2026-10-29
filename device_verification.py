"""Company-owned device verification. Works without Thread tickets or Flow objects."""
import hashlib,secrets,time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs
from store import page,E
from personal_agent_protocol.company.store import USER_CODE,DEVICE,UserCode,PendingDevice
from personal_agent_protocol.company import CLIENT_RESOLVERS
from personal_agent_protocol.reactor import first_contribution
async def verify(app,r,origin,cookie_name):
 code=r.query_params.get('ticket','').strip().upper()
 if not code:return page('<section class="panel"><h1>Connect to FORME</h1><form method="get"><label>Verification code<input name="ticket" required></label><button>Continue</button></form></section>','signin')
 pointer=await app.shop._read(USER_CODE,code,UserCode.from_json)
 pending=await app.shop._read(DEVICE,pointer.device,PendingDevice.from_json) if pointer else None
 linked=app.tickets.get(code) # Optional UX association, never protocol authority.
 if not pending or pending.denied or pending.expires_at<=app.shop._now() or (linked and linked['expiry']<time.time()):return page('<section class="panel"><h1>This sign-in link expired.</h1><p>Return to your personal agent and request sign-in again.</p></section>','signin',status=400)
 resolver=first_contribution(app.shop.reactor,CLIENT_RESOLVERS,'client')
 metadata,_=await resolver.resolve(pending.client_id)
 agent=metadata.client_name or pending.client_id
 if not hasattr(app,'device_forms'):app.device_forms={}
 form=app.device_forms.setdefault(code,{'csrf':linked['csrf'] if linked else secrets.token_urlsafe(32),'attempts':0,'retry_at':0})
 expected=linked['flow'].customer if linked and linked.get('flow') else None
 cookies=SimpleCookie();cookies.load(r.headers.get('cookie',''));cookie=cookies.get(cookie_name)
 row=app.forme_accounts.db.execute('SELECT account FROM authorization_logins WHERE id=? AND expires>?',(hashlib.sha256(cookie.value.encode()).hexdigest(),time.time())).fetchone() if cookie else None
 account_row=app.forme_accounts.db.execute('SELECT profile_number FROM accounts WHERE id=?',(row[0],)).fetchone() if row else None
 known=app.forme_accounts.by_profile(account_row[0]) if account_row and (expected is None or account_row[0]==expected) else None
 error='';auth_cookie=None
 if r.method=='POST':
  f={k:v[0] for k,v in parse_qs((await r.body()).decode()).items()}
  if r.headers.get('origin')!=origin or not secrets.compare_digest(f.get('csrf',''),form['csrf']):return page('<p>Invalid sign-in form.</p>',status=403)
  if f.get('decision')=='decline':
   if pending.account_id is None:await app.shop.deny_device(code)
   return page('<section class="panel"><h1>Access declined.</h1><p>No new access was granted.</p></section>','signin')
  if time.time()<form['retry_at']:
   response=page('<p>Too many sign-in attempts. Please try again shortly.</p>','signin',status=429);response.headers['Retry-After']=str(max(1,int(form['retry_at']-time.time())+1));return response
  account=app.forme_accounts.authenticate(f.get('email',''),f.get('password','')) if f.get('email') or f.get('password') else known
  if not account or (expected is not None and account['customer']!=expected):
   form['attempts']+=1
   if form['attempts']>=5:form['retry_at']=time.time()+30
   error='Please check your email and password for the matching FORME demo account.'
  elif pending.account_id is None and not pending.denied:
   await app.shop.approve_device(code,account_id=account['id'],scopes=pending.scopes)
   if linked:linked['done']=True
   auth_cookie=secrets.token_urlsafe(32);app.forme_accounts.db.execute('INSERT INTO authorization_logins VALUES(?,?,?)',(hashlib.sha256(auth_cookie.encode()).hexdigest(),account['id'],time.time()+86400));app.forme_accounts.db.commit()
   response=page('<section class="panel"><h1>You’re all set.</h1><p>Return to your personal agent to continue.</p></section>','signin',True)
   response.set_cookie(cookie_name,auth_cookie,max_age=86400,secure=True,httponly=True,samesite='lax',path='/');return response
 if pending.account_id is not None:return page('<section class="panel"><h1>You’re all set.</h1><p>This authorization was already completed.</p></section>','signin',True)
 if pending.denied:return page('<p>This authorization was declined.</p>','signin')
 email=f'customer{expected:03}@forme.local' if expected is not None else ''
 login=('<p>Signed in as '+E(known['email'])+'. Confirm the requested access below.</p>') if known else f'<label>Email address<input type="email" name="email" value="{email}" autocomplete="username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" required></label><p><small>Demo access: wardrobe</small></p>'
 scopes='; '.join(app.shop.config.custom_scopes.get(s,s) for s in pending.scopes)
 body=f'<section class="panel"><img width="130" src="/assets/logo.svg" alt="FORME"><p class="eyebrow">YOUR WARDROBE, CONNECTED</p><h1>Review account access.</h1><p>FORME · {E(origin)}</p><p>{E(agent)} is requesting access.</p><p>{E(error)}</p><form method="post"><input type="hidden" name="csrf" value="{form["csrf"]}">{login}<button>{"Authorize additional access" if known else "Authorize & connect"}</button><p><small>Allow {E(agent)} to: {E(scopes)}</small></p></form><form method="post"><input type="hidden" name="csrf" value="{form["csrf"]}"><button name="decision" value="decline">Decline access</button></form></section>'
 return page(body,'signin')
