import os,sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import pytest
os.environ["THREAD3_PORT"]="8545"
from app import App,Flow
from conversation import conversational_reply,without_greeting
@pytest.mark.asyncio
async def test_conversation_without_tools(tmp_path):
 app=App();await app.setup(tmp_path/'smalltalk.sqlite');f=Flow(app,1)
 async def forbidden(*a,**k):raise AssertionError('Smalltalk must not read data or browse')
 f.open=forbidden;f.answer_question=forbidden
 try:
  first,_=await f.chat('hello');assert app.memory.get(1)['name'] in first
  second,_=await f.chat('hi');assert app.memory.get(1)['name'] not in second
  other=Flow(app,2);reply,_=await other.chat('hello');assert app.memory.get(2)['name'] in reply and app.memory.get(1)['name'] not in reply
  anonymous=Flow(app,1);anonymous.principal=None;reply,_=await anonymous.chat('hello');assert reply.startswith('Hello!')
  for q in ['hello','hi','hey!','Thanks','thank you so much','how are you?','good morning','bye','what can you do?']:
   reply,cards=await f.chat(q);assert reply and 'not sure' not in reply and not cards
  assert without_greeting('Hi, who am I?')=='who am I?'
  assert conversational_reply('hello, checkout') is None
 finally:await app.http.aclose()

@pytest.mark.asyncio
async def test_real_gpt_local_context(tmp_path):
 if not os.environ.get('OPENAI_API_KEY'):pytest.skip('Actual GPT required')
 app=App();await app.setup(tmp_path/'real.sqlite');f=Flow(app,1)
 before=[app.memory.get(i) for i in range(1,101)];results=[]
 observed=[];actual_structured=app.model.structured
 async def observe(instructions,payload,*args,**kwargs):
  observed.extend(fact for row in payload.get('tool_results',[]) for fact in row.get('facts',[]))
  return await actual_structured(instructions,payload,*args,**kwargs)
 app.model.structured=observe
 try:
  for q in ['hello','hi','thanks','Hi, who am I?','What is my name and shirt size?','What is my birthday?','What about that account?']:
   reply,cards=await f.chat(q);results.append({'question':q,'reply':reply});assert not cards and not f.signurl
   if q=='hello':assert before[0]['name'] in reply
   if q=='What is my name and shirt size?':
    assert before[0]['name'].split(' · ')[0] in reply
    size=str(before[0]['shirt_size']);aliases={'XS':'extra small','S':'small','M':'medium','L':'large','XL':'extra large','XXL':'extra extra large'}
    assert re.search(r'\b(?:'+re.escape(size)+'|'+re.escape(aliases.get(size,size))+r')\b',reply,re.I)
    assert any(x['source']=='Thread' and x['key']=='name' and x['value']==before[0]['name'] for x in observed)
    assert any(x['source']=='Thread' and x['key']=='preferences' and x['value'].get('shirt_size')==before[0]['shirt_size'] for x in observed)
   if q=='What is my birthday?':assert any(x in reply.lower() for x in ('not','unknown','unavailable',"don't",'don’t','couldn’t'))
  assert app.model.calls>0 and before==[app.memory.get(i) for i in range(1,101)]
  Path('evidence/commerce-images/actual-conversation.json').write_text(__import__('json').dumps(results,indent=2))
 finally:await f.browser.close();await app.http.aclose()
