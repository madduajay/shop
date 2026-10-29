"""Original completion contract exercised through the real Deep Agents graph."""
import pytest
from app import App,Flow
from graph_fixtures import ScriptModel,plan,call,finish

@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['premature','after_execution','bounded','unavailable'])
async def test_completion_repair_never_repeats_action(tmp_path,mode):
 app=App();await app.setup(tmp_path/'completion.sqlite');f=Flow(app,1);executed=[]
 script=[plan()]
 if mode=='premature':script += [finish('old_card_id')]
 if mode=='bounded':script += [finish('old_card_id'),finish('old_card_id')]
 else:
  script += [call('read_thread_user_data'),call('read_thread_user_data')]
  if mode in ('after_execution','unavailable'):script += [finish('old_card_id' if mode=='after_execution' else 'result_1')]
  script += [finish(status='unavailable' if mode=='unavailable' else 'satisfied')]
 app.deep_model=ScriptModel(script=script)
 async def execute(*args):
  executed.append(True)
  if mode=='unavailable':raise ValueError('Uncertain action: never retry')
  return 'Verified identity.',[]
 f.execute_tool_calls=execute
 try:
  await f.plan_and_execute('Who am I?')
  assert len(executed)==(0 if mode=='bounded' else 1)
  assert f.agent_task['status']==('incomplete' if mode in ('bounded','unavailable') else 'completed')
  assert f.agent_task['completion_rejections']==(2 if mode=='bounded' else 1)
  assert app.deep_model.position<=6
 finally:
  await app.http.aclose()
  if hasattr(app,'graph_saver'):app.graph_saver.close()
