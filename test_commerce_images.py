import os,sys,asyncio,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent));os.environ['THREAD3_PORT']='8545'
import pytest,uvicorn
from app import App,Flow,CURRENT,ORIGIN

@pytest.mark.asyncio
async def test_verified_bag_review_receipt_images(tmp_path,monkeypatch):
 monkeypatch.delenv('OPENAI_API_KEY',raising=False);app=App();await app.setup(tmp_path/'images.sqlite');f=Flow(app,1);CURRENT.set(f)
 profiles=[app.memory.get(i) for i in range(1,101)]
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8545,ssl_certfile=str(app.tls/'cert.pem'),ssl_keyfile=str(app.tls/'key.pem'),access_log=False,log_level='critical'));task=asyncio.create_task(server.serve())
 try:
  while not server.started:await asyncio.sleep(.05)
  for product,size in [('tee','L'),('oxford','M')]:await f.add_selected(product,size,app.store.by_id[product]['name'])
  ticket=app.tickets[f.signurl.split('ticket=')[1]]
  await app.http.post(f.signurl,headers={'Origin':ORIGIN},data={'csrf':ticket['csrf'],'email':'customer001@forme.local','password':'wardrobe'})
  await asyncio.sleep(5.2);await f.poll();assert not f.pending_adds
  outputs=[]
  for action,title in [(f.show_bag,'Your FORME bag'),(f.begin_checkout,'Review your order')]:
   reply,cards=await action();assert cards[0]['reference']==title
   items=cards[0]['items'];assert [(i['id'],i['size']) for i in items]==[('tee','L'),('oxford','M')]
   for i in items:
    p=app.store.by_id[i['id']];assert i['image']==ORIGIN+p['image_url'] and i['color']==p['color'] and i['price_cents']==p['price'] and i['quantity']==1
   assert cards[0]['total_cents']==sum(i['price_cents'] for i in items)
   outputs.append({'role':'assistant','text':reply,'cards':cards})
  assert not app.memory.orders() and 'I approve this order' in reply
  reply,cards=await f.chat('I approve this order');assert 'Order FM-' in reply and cards[0]['reference']=='Order confirmed';assert cards[0]['items']==items
  outputs.append({'role':'assistant','text':reply,'cards':cards});await f.chat('I approve this order');assert len(app.memory.orders())==1
  # Historical receipt image identity survives a later catalog-image change.
  app.store.by_id['tee']['image_url']='/assets/not-the-purchased-image.png'
  # A receipt recovered after an uncertain response must also include images.
  f.uncertain=True;reply,recovered=await f.chat('show me shirts');assert recovered and recovered[0]['items']==items
  assert profiles==[app.memory.get(i) for i in range(1,101)]
  Path('evidence/commerce-images').mkdir(exist_ok=True);Path('evidence/commerce-images/cards.json').write_text(json.dumps(outputs,indent=2))
  for image in (None,'https://unverified.example/assets/other.jpg','https://jacket.localhost:8545/other.jpg'):
   c=f.commerce_cards({'signed_in':True,'cart':[dict(items[0],image=image)]},'fixture');assert c[0]['items'][0]['image'] is None
  assert not f.commerce_cards({'signed_in':False,'cart':items},'fixture')
 finally:await f.browser.close();await app.http.aclose();server.should_exit=True;await task
