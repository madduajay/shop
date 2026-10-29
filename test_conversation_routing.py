"""Deterministic routing safeguards; real-model browser evidence is recorded separately."""
import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import pytest
from app import App,Flow
from chat_routing import UNSUPPORTED

@pytest.mark.asyncio
@pytest.mark.parametrize('answer',['yes','yes please','notify me','no','no thanks','cancel watch'])
async def test_pending_watch_precedes_generic_qa(tmp_path,monkeypatch,answer):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'fixture.sqlite');f=Flow(app,1);app.model.key='fixture-only'
 async def forbidden(*args):raise AssertionError('Notification reply reached generic QA')
 async def resume():return 'authorization required',[]
 f.answer_question=forbidden;f.resume_watch=resume
 app.watch_memory.save(1,{'consent':'a'*32,'status':'offered','expires_at':time.time()+600,'filters':{'demo_trigger':'tie'},'candidate':{'name':'Red tie'}})
 before=app.memory.get(1)
 try:
  reply,_=await f.legacy_chat(answer)
  assert f.watch_rows()[0]['status']==('cancelled' if answer in ('no','no thanks','cancel watch') else 'consented')
  assert not app.memory.orders() and app.memory.get(1)==before
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_unknown_refinement_and_plain_yes_cannot_purchase(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False)
 app=App();await app.setup(tmp_path/'fixture.sqlite');f=Flow(app,1);app.model.key='fixture-only';before=app.memory.get(1)
 async def forbidden(*args):raise AssertionError('Safe guard reached model')
 app.model.context_tools=forbidden
 try:
  assert 'search for it first' in (await f.legacy_chat('Another color please'))[0]
  assert 'Ask for an unavailable item' in (await f.legacy_chat('yes'))[0]
  assert 'couldn’t complete that read-only lookup' in (await f.legacy_chat('Who won the football game?'))[0]
  assert 'Do you mean' in (await f.legacy_chat('what about that account?'))[0]
  assert app.memory.get(1)==before and not app.memory.orders() and not f.token
 finally:await app.http.aclose()
