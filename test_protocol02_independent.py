"""External-client checks: no Thread Flow/tickets, GPT, cart or purchases."""
import os,sys,asyncio,re,secrets
from pathlib import Path
os.environ['THREAD3_PORT']='8545';sys.path.insert(0,str(Path(__file__).parent))
import pytest,uvicorn
from app import App,ORIGIN,Clock,Network
from personal_agent_protocol import SessionClient,DeviceSignInClient,ConversationClient,Message
from personal_agent_protocol.demo.kit import PersonalAgentHost,personal_agent_reactor
from personal_agent_protocol.transport import DpopHttpClient
@pytest.mark.asyncio
async def test_external_device_conversation_and_revocation(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'external.sqlite')
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),log_level='error',access_log=False));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.02)
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
  await app.http.aclose();server.should_exit=True;await task
