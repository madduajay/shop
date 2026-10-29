"""Additional in-process protocol evidence; does not replace blocked real TLS/socket tests."""
"""External-client checks: no Thread Flow/tickets, GPT, cart or purchases."""
import os,sys,asyncio,re,secrets
from pathlib import Path
os.environ['THREAD3_PORT']='8545';sys.path.insert(0,str(Path(__file__).parent))
import pytest,httpx
from app import App,ORIGIN,Clock,Network
from personal_agent_protocol import SessionClient,DeviceSignInClient,ConversationClient,Message
from personal_agent_protocol.demo.kit import PersonalAgentHost,personal_agent_reactor
from personal_agent_protocol.transport import DpopHttpClient
@pytest.mark.asyncio
async def test_asgi_device_conversation_and_revocation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 # The ASGI fixture has no DNS or socket transport. Keep its allowlist and supply
 # a loopback routing key locally; this changes no machine networking settings.
 import direct_network
 async def fixture_dns(host):return ['127.0.0.1']
 monkeypatch.setattr(direct_network,'resolve_addresses',fixture_dns)
 app=App();await app.setup(tmp_path/'external.sqlite')
 await app.http._transport.aclose();app.http._transport=httpx.ASGITransport(app=app)
 try:
  reactor=personal_agent_reactor(PersonalAgentHost(app.identity,Clock()),network=Network(),http_client=app.http,plugins=[app.policy])
  who=dict(tenant_id='independent',pairwise_user_id='usr_independent_'+secrets.token_hex(16),issuer=ORIGIN)
  sessions=SessionClient(reactor=reactor,http_client=app.http)
  token=await sessions.start(client_id=app.identity.client_id,token_endpoint=ORIGIN+'/oauth/token',**who)
  transport=DpopHttpClient(reactor=reactor,http_client=app.http);client=ConversationClient(transport=transport);ep=ORIGIN+'/poppy/conversations'
  def msg(text):return Message(id='msg_'+secrets.token_hex(16),sender='agent',text=text)
  p=await client.start(ep,msg('Please arrange a restock notification.'),token=token,wait=0,**who)
  assert any(e.type=='authorization' and e.error=='sign_in_required' for e in p.events)
  device=DeviceSignInClient(reactor=reactor,http_client=app.http)
  async def begin(t):return await device.begin(device_authorization_endpoint=ORIGIN+'/oauth/device',token_endpoint=ORIGIN+'/oauth/token',client_id=app.identity.client_id,session_id=t.session_id,scopes=('availability:watch',),**who)
  started=await begin(token);assert not app.tickets and not app.clients
  page=await app.http.get(started.verification_uri_complete);assert page.status_code==200 and 'Thread3 personal stylist' in page.text and 'availability' in page.text
  csrf=re.search(r'name="csrf" value="([^"]+)"',page.text)[1]
  assert (await device.poll(started.reference)).status=='pending'
  bad=await app.http.post(started.verification_uri_complete,headers={'Origin':ORIGIN},data={'csrf':'wrong','email':'customer098@forme.local','password':'wardrobe'});assert bad.status_code==403
  approved=await app.http.post(started.verification_uri_complete,headers={'Origin':ORIGIN},data={'csrf':csrf,'email':'customer098@forme.local','password':'wardrobe'});assert approved.status_code==200 and 'all set' in approved.text
  await asyncio.sleep(5.1);done=await device.poll(started.reference);assert done.token and done.token.signed_in;token=done.token
  # Exercise refresh at the actual Flow.chat entrypoint before the new graph.
  from app import Flow
  from graph_fixtures import ScriptModel,plan,call,finish
  flow=Flow(app,98);flow.token=token;flow.reactor=reactor;flow.who=who
  flow.metadata={'token_endpoint':ORIGIN+'/oauth/token','revocation_endpoint':ORIGIN+'/oauth/revoke'}
  flow.account_token_reference=done.account_token_reference;flow.token_received_at=0
  app.deep_model=ScriptModel(script=[plan('read Thread identity'),call('read_thread_user_data'),call('read_thread_user_data'),finish()])
  app.model.key='fixture-only-no-model-network'
  reply,_=await flow.chat('Who am I JSON')
  assert flow.token.session_id==token.session_id and flow.token.signed_in
  assert flow.token_received_at>0 and flow.agent_task['status']=='completed'
  assert app.thread_accounts.by_profile(98)['email'] in reply
  token=flow.token;app.model.key=''
  sent=await client.send(ep,p.conversation_id,msg('Thanks. What can you do?'),token=token,wait=0,**who);assert sent.conversation_id==p.conversation_id
  handoff=await client.handoff(ep,p.conversation_id,token=token,**who);assert handoff.status=='idle' and handoff.responder=='agent'
  direct=await client.start_direct(ep,p.conversation_id,msg('I want to speak directly.'),token=token,**who)
  with pytest.raises(Exception) as exc:await client.send(ep,p.conversation_id,msg('While child open'),token=token,**who)
  assert exc.value.code=='direct_conversation_open'
  await client.close(ep,direct.conversation_id,token=token,**who);await client.close(ep,p.conversation_id,token=token,**who)
  page=await client.read_events(ep,p.conversation_id,token=token,**who);assert page.status=='closed' and any(e.type=='direct_closed' for e in page.events)
  count=len(page.events);await client.close(ep,p.conversation_id,token=token,**who);assert len((await client.read_events(ep,p.conversation_id,token=token,**who)).events)==count
  from personal_agent_protocol.accounts import AccountTokenClient,AccountTokenContext
  accounts=AccountTokenClient(reactor=reactor,http_client=app.http);context=AccountTokenContext(client_id=app.identity.client_id,token_endpoint=ORIGIN+'/oauth/token',revocation_endpoint=ORIGIN+'/oauth/revoke',**who)
  await accounts.revoke(done.account_token_reference,context=context)
  with pytest.raises(Exception):await client.read_events(ep,p.conversation_id,token=token,**who)
  fresh=await sessions.start(client_id=app.identity.client_id,token_endpoint=ORIGIN+'/oauth/token',**who)
  denied=await begin(fresh);page=await app.http.get(denied.verification_uri_complete);csrf=re.search(r'name="csrf" value="([^"]+)"',page.text)[1]
  await app.http.post(denied.verification_uri_complete,headers={'Origin':ORIGIN},data={'csrf':csrf,'decision':'decline'})
  await asyncio.sleep(5.1)
  with pytest.raises(Exception) as rejected:await device.poll(denied.reference)
  assert rejected.value.code=='access_denied'
  assert not app.memory.orders() and not app.tickets
 finally:
  await app.http.aclose()


@pytest.mark.asyncio
async def test_asgi_browser_activation_negative_assertions(tmp_path,monkeypatch):
 """Validate real signed activation requests, without claiming rendered Chrome evidence."""
 import time,jwt
 from app import AGENT
 from cryptography.hazmat.primitives.asymmetric import ec
 import direct_network
 async def fixture_dns(host):return ['127.0.0.1']
 monkeypatch.setattr(direct_network,'resolve_addresses',fixture_dns)
 app=App();await app.setup(tmp_path/'assertions.sqlite')
 await app.http._transport.aclose();app.http._transport=httpx.ASGITransport(app=app)
 try:
  reactor=personal_agent_reactor(PersonalAgentHost(app.identity,Clock()),network=Network(),http_client=app.http,plugins=[app.policy])
  who=dict(tenant_id='synthetic',pairwise_user_id='fixture_'+secrets.token_hex(16),issuer=ORIGIN)
  token=await SessionClient(reactor=reactor,http_client=app.http).start(client_id=app.identity.client_id,token_endpoint=ORIGIN+'/oauth/token',**who)
  now=int(time.time());base=dict(iss=app.identity.client_id,sub=who['pairwise_user_id'],aud=ORIGIN+'/poppy/browser-session',session_id=token.session_id,return_to=ORIGIN+'/shop',iat=now,exp=now+50,jti=secrets.token_urlsafe(24))
  def sign(claims,typ='poppy-browser+jwt',key=None):return jwt.encode(claims,key or app.identity.private_key,algorithm='ES256',headers={'typ':typ,'kid':app.identity.kid})
  assertion=sign(base)
  good=await app.http.post(base['aud'],data={'assertion':assertion})
  assert good.status_code==303
  assert all(s in good.headers['set-cookie'] for s in ('__Host-thread3_poppy_session','Secure','HttpOnly','SameSite=Lax','Path=/'))
  replay=await app.http.post(base['aud'],data={'assertion':assertion})
  assert replay.status_code==400 and 'set-cookie' not in replay.headers
  updates=[dict(aud=AGENT),dict(sub='wrong'),dict(session_id='wrong'),dict(exp=now-1),dict(exp=now+61),dict(return_to='https://example.com/'),dict(return_to=ORIGIN+'@example.com/')]
  for update in updates:
   result=await app.http.post(base['aud'],data={'assertion':sign(dict(base,jti=secrets.token_urlsafe(24),**update))})
   assert result.status_code==400 and 'set-cookie' not in result.headers
  for assertion in [sign(dict(base,jti=secrets.token_urlsafe(24)),typ='poppy-session+jwt'),sign(dict(base,jti=secrets.token_urlsafe(24)),key=ec.generate_private_key(ec.SECP256R1()))]:
   result=await app.http.post(base['aud'],data={'assertion':assertion})
   assert result.status_code==400 and 'set-cookie' not in result.headers
 finally:
  await app.http.aclose()
