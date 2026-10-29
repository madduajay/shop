"""Protocol credential lifecycle; references only are exposed to Flow, never secrets."""
import time
from personal_agent_protocol.accounts import AccountTokenClient,AccountTokenContext
from personal_agent_protocol import SessionClient
class AccountLifecycle:
 def accounts_client(self):return AccountTokenClient(reactor=self.reactor,http_client=self.app.http)
 def account_context(self):return AccountTokenContext(token_endpoint=self.metadata['token_endpoint'],revocation_endpoint=self.metadata['revocation_endpoint'],client_id=self.app.identity.client_id,**self.who)
 async def ensure_current_token(self):
  if not self.token or not hasattr(self,'metadata'):return
  if time.time()<getattr(self,'token_received_at',time.time())+self.token.expires_in-30:return
  await self.stop_watch_streams()
  ref=getattr(self,'account_token_reference',None)
  if ref:
   result=await self.accounts_client().refresh(ref,context=self.account_context(),session_id=self.token.session_id)
   if result.token:self.token=result.token;self.token_received_at=time.time();return
   self.account_token_reference=None
  self.token=await SessionClient(reactor=self.reactor,http_client=self.app.http).renew(client_id=self.app.identity.client_id,token_endpoint=self.metadata['token_endpoint'],session_id=self.token.session_id,**self.who)
  self.token_received_at=time.time()
 async def revoke_account_token(self,reference=None):
  ref=reference or getattr(self,'account_token_reference',None)
  if ref:await self.accounts_client().revoke(ref,context=self.account_context())
  if ref==getattr(self,'account_token_reference',None):self.account_token_reference=None
