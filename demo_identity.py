"""Independent local company identity repositories. Public demo credentials only."""
import sqlite3,secrets,hashlib,hmac,time,json
from functools import lru_cache
@lru_cache(maxsize=200)
def fixture_credential(company,number):
 salt=secrets.token_hex(16)
 return salt,hashlib.pbkdf2_hmac('sha256',b'wardrobe',salt.encode(),60000).hex()
class DemoAccounts:
 def __init__(self,path,company):
  self.company=company;self.db=sqlite3.connect(path)
  if company=='forme':self.db.execute('CREATE TABLE IF NOT EXISTS authorization_logins(id TEXT PRIMARY KEY,account TEXT NOT NULL,expires REAL NOT NULL)')
  self.db.execute('CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,profile_number INTEGER UNIQUE NOT NULL,email TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL,pairwise_id TEXT NOT NULL)')
  for n in range(1,101):
   if self.db.execute('SELECT 1 FROM accounts WHERE profile_number=?',(n,)).fetchone():continue
   salt,digest=fixture_credential(company,n)
   identity='th_'+secrets.token_hex(16) if company=='thread' else f'forme_customer_{n:03}'
   self.db.execute('INSERT INTO accounts VALUES(?,?,?,?,?,?)',(identity,n,f'customer{n:03}@{company}.local',salt,digest,'pw_'+secrets.token_hex(16)))
  self.db.commit()
 def by_profile(self,n):
  row=self.db.execute('SELECT id,profile_number,email,pairwise_id FROM accounts WHERE profile_number=?',(n,)).fetchone()
  return dict(id=row[0],customer=row[1],email=row[2],pairwise=row[3]) if row else None
 def authenticate(self,email,password):
  row=self.db.execute('SELECT id,profile_number,salt,password_hash FROM accounts WHERE email=?',(email.strip().lower(),)).fetchone()
  if not row:return None
  digest=hashlib.pbkdf2_hmac('sha256',password.encode(),row[2].encode(),60000).hex()
  return self.by_profile(row[1]) if hmac.compare_digest(digest,row[3]) else None
class CompanyLinks:
 def __init__(self,db):
  self.db=db;db.execute('CREATE TABLE IF NOT EXISTS company_links(principal TEXT NOT NULL,issuer TEXT NOT NULL,account TEXT NOT NULL,scopes TEXT NOT NULL,status TEXT NOT NULL,linked_at REAL NOT NULL,PRIMARY KEY(principal,issuer),UNIQUE(issuer,account))');db.commit()
 def get(self,principal,issuer):
  row=self.db.execute('SELECT account,scopes,status FROM company_links WHERE principal=? AND issuer=?',(principal,issuer)).fetchone()
  return dict(account=row[0],scopes=json.loads(row[1]),status=row[2]) if row else None
 def bind(self,principal,issuer,account,scopes):
  old=self.get(principal,issuer)
  if old and old['account']!=account:raise ValueError('This Thread identity is linked to a different FORME account.')
  other=self.db.execute('SELECT principal FROM company_links WHERE issuer=? AND account=?',(issuer,account)).fetchone()
  if other and other[0]!=principal:raise ValueError('This FORME account is linked to another Thread identity.')
  self.db.execute('INSERT INTO company_links VALUES(?,?,?,?,?,?) ON CONFLICT(principal,issuer) DO UPDATE SET scopes=excluded.scopes,status=excluded.status,linked_at=excluded.linked_at',(principal,issuer,account,json.dumps(list(scopes)),'active',time.time()));self.db.commit()
 def revoke(self,principal,issuer):self.db.execute("UPDATE company_links SET status='revoked' WHERE principal=? AND issuer=?",(principal,issuer));self.db.commit()
 def authorized(self,principal,issuer,account,scope):
  link=self.get(principal,issuer);return bool(link and link['status']=='active' and link['account']==account and scope in link['scopes'])
