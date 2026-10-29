import os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest
from app import App,Flow
@pytest.mark.asyncio
async def test_expired_consent_is_explicit_and_not_sent(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'expiry.sqlite');f=Flow(app,1)
 w={'consent':'a'*32,'status':'consented','expires_at':time.time()-1,'filters':{},'candidate':{'name':'Red shoes'}}
 app.watch_memory.save(1,w);f.authorizing_watch_consent=w['consent'];f.pending_read='watch';f.pending_watch_consent=w['consent'];f.agent_task={'status':'waiting_auth','watch_consent':w['consent']}
 try:
  reply,cards=await f.resume_watch();assert 'expired while signing in' in reply
  reply,cards=await f.continue_agent_task(reply,cards);assert f.agent_task['status']=='waiting_user' and f.pending_read is None
  assert f.watch_rows()[0]['status']=='expired' and not app.store.availability.db.execute('select * from watches').fetchall()
  assert not any('/poppy/conversations' in e.get('endpoint','') for e in f.trace)
 finally:await app.http.aclose()
