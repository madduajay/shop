// Dedicated Chrome process and incognito context. No personal profile, cookie injection,
// API shortcuts, TLS overrides, extensions or arbitrary caller-supplied JavaScript.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),cp=require('node:child_process'),readline=require('node:readline');
let chrome,dir,ws,session,origin,storefront,activation,next=0,context;const waiting=new Map(),listeners=new Map();
let captureEvidence=[],activationExchanges=[];const activationRequests=new Map();
function observeActivation(m){
 const p=m.params||{};
 if(m.method==='Network.requestWillBeSent' && p.request?.url===activation && p.request.method==='POST')activationRequests.set(p.requestId,{endpoint:p.request.url,request:{method:p.request.method,headers:p.request.headers,body:p.request.postData||''},request_at:new Date().toISOString()});
 if(m.method==='Network.requestWillBeSentExtraInfo' && activationRequests.has(p.requestId))activationRequests.get(p.requestId).request.headers=p.headers;
 if(m.method==='Network.responseReceivedExtraInfo' && activationRequests.has(p.requestId)){const r=activationRequests.get(p.requestId);activationRequests.delete(p.requestId);activationExchanges.push({...r,status:p.statusCode,response:{headers:p.headers,body:{capture:'Redirect response body unavailable from Chrome ExtraInfo; not reconstructed from the destination page.'}},response_at:new Date().toISOString(),network_request_id:p.requestId});}
}
function observeCookieResponse(m){
 if(m.method!=='Network.responseReceivedExtraInfo')return;
 const p=m.params,h=p.headers||{},key=Object.keys(h).find(k=>k.toLowerCase()==='x-atlas-capture-id');
 const id=key&&h[key];if(!id||!/^[a-f0-9]{24}$/.test(id))return;
 captureEvidence.push({http_request_id:id,chrome_request_id:p.requestId,observed_at:new Date().toISOString(),
  event:'Network.responseReceivedExtraInfo',status:p.statusCode,
  cookie_blocking_observed:true,
  blocked_cookies:(p.blockedCookies||[]).map(c=>({name:(c.cookieLine||'').split('=',1)[0],reasons:c.blockedReasons||[]})),
  exempted_cookies:(p.exemptedCookies||[]).map(c=>({name:c.cookie?.name||null,reason:c.exemptionReason})),
  note:'Chrome response metadata. No blocked entry is not proof of storage; subsequent server Cookie headers provide transmission evidence.'});
}
function command(method,params={},sid=session){return new Promise((resolve,reject)=>{const id=++next;const timer=setTimeout(()=>{waiting.delete(id);reject(Error('Browser command timed out'))},15000);waiting.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sid?{sessionId:sid}:{})}))})}
function event(method){
 let timer,settle,callback;
 const result=new Promise((resolve,reject)=>{settle=resolve;callback=()=>{clearTimeout(timer);resolve()};timer=setTimeout(()=>{if(listeners.get(method)===callback)listeners.delete(method);reject(Error('Browser navigation timed out'))},15000);listeners.set(method,callback)});
 result.catch(()=>{}); // The action may still be awaiting CDP when this timer rejects.
 result.cancel=()=>{clearTimeout(timer);if(listeners.get(method)===callback)listeners.delete(method);settle()};return result;
}
// Business snapshots need committed HTML and its scripts, not every image download.
// Screenshots separately await visible image decoding. Observe before the action;
// never replay a navigation/form POST when readiness cannot be confirmed.
async function documentNavigation(action){const loaded=event('Page.domContentEventFired');try{await action();await loaded;await assertPage()}finally{loaded.cancel()}}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error('Website action failed');return r.result.value}
function own(url){return new URL(url).origin===origin}
async function navigate(url){if(!own(url))throw Error('Origin refused');await documentNavigation(()=>command('Page.navigate',{url}))}
async function assertPage(){const url=await evaluate('location.href');if(!own(url)||!(new URL(url).pathname===new URL(storefront).pathname||new URL(url).pathname.startsWith(new URL(storefront).pathname+'/')))throw Error('Unexpected website destination')}
async function submit(expression){await documentNavigation(()=>evaluate(expression))}
async function launch(args){
 origin=new URL(args.origin).origin;if(!origin.startsWith('https://'))throw Error('HTTPS required');
 dir=fs.mkdtempSync(path.join(os.tmpdir(),'thread3-forme-browser-'));
 chrome=cp.spawn(args.chrome,['--headless=new','--remote-debugging-port=0','--user-data-dir='+dir,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','--disable-extensions','about:blank'],{stdio:'ignore'});
 let portFile=path.join(dir,'DevToolsActivePort'),address=[];for(let i=0;i<150;i++){try{address=fs.readFileSync(portFile,'utf8').trim().split('\n')}catch{}if(/^\d+$/.test(address[0]||'')&&(address[1]||'').startsWith('/devtools/browser/'))break;await new Promise(r=>setTimeout(r,100))}
 const [port,endpoint]=address;if(!port||!endpoint)throw Error('Chrome unavailable');
 ws=new WebSocket('ws://127.0.0.1:'+port+endpoint);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=()=>reject(Error('Browser connection failed'))});
 ws.onmessage=async({data})=>{const m=JSON.parse(data);if(m.id){const p=waiting.get(m.id);if(p){waiting.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('Browser command refused')):p.resolve(m.result)}return}
  observeCookieResponse(m);observeActivation(m);
  if(m.method==='Fetch.requestPaused'){try{await command(own(m.params.request.url)?'Fetch.continueRequest':'Fetch.failRequest',own(m.params.request.url)?{requestId:m.params.requestId}:{requestId:m.params.requestId,errorReason:'BlockedByClient'},m.sessionId)}catch{} }
  const f=listeners.get(m.method);if(f&&m.sessionId===session){listeners.delete(m.method);f()}
 };
 context=(await command('Target.createBrowserContext',{},null)).browserContextId;
 const target=(await command('Target.createTarget',{url:'about:blank',browserContextId:context},null)).targetId;
 session=(await command('Target.attachToTarget',{targetId:target,flatten:true},null)).sessionId;
 await command('Page.enable');await command('Runtime.enable');await command('Network.enable');await command('Network.setBypassServiceWorker',{bypass:true});
 await command('Fetch.enable',{patterns:[{urlPattern:'*'}]});await command('Browser.setDownloadBehavior',{behavior:'deny',browserContextId:context},null);
 return {isolated:true};
}
async function snapshot(){await assertPage();return evaluate(`(()=>({question_context:document.querySelector('[data-question-context]')?JSON.parse(document.querySelector('[data-question-context]').textContent):null,availability:document.querySelector('[data-availability]')?JSON.parse(document.querySelector('[data-availability]').textContent):null,page:document.body.dataset.page,account_status:document.querySelector('[data-account-status]')?.dataset.accountStatus||null,account_id:document.querySelector('[data-account-status]')?.dataset.accountId||null,url:location.href,filters:Object.fromEntries([...document.querySelectorAll('form[data-shop-action=filter] select,form[data-shop-action=filter] input')].filter(e=>e.name).map(e=>[e.name,e.value])),facets:Object.fromEntries([...document.querySelectorAll('form[data-shop-action=filter] select')].map(e=>[e.name,[...e.options].map(o=>({value:o.value,label:o.textContent}))])),context_saved:!!document.querySelector('[data-context-saved]'),preferences_json:document.querySelector('[data-preferences-json]')?JSON.parse(document.querySelector('[data-preferences-json]').textContent):null,context_summary:document.querySelector('[data-context-summary]')?.textContent||null,total:Number(document.querySelector('[data-result-count]')?.dataset.resultCount||0),has_next:!!document.querySelector('[data-shop-next]'),stage:document.querySelector('[data-stage]')?.dataset.stage||document.body.dataset.page,size:document.querySelector('[data-size]')?.dataset.size||document.querySelector('[data-cart-item]')?.dataset.size||null,selection:document.querySelector('[data-cart-item]')?{name:document.querySelector('[data-cart-item]').dataset.name,size:document.querySelector('[data-cart-item]').dataset.size}:null, signed_in:document.body.dataset.signedIn==='true',can_checkout:!!document.querySelector('form[data-shop-action="checkout"] button:not(:disabled)'), error:document.querySelector('[data-error]')?.textContent||null, products:[...document.querySelectorAll('[data-product]')].map(e=>({id:e.dataset.product,explanation:e.querySelector('[data-explanation]')?.textContent||null,explanation_source:e.querySelector('[data-explanation]')?.dataset.explanationSource||null,department:e.dataset.department,category:e.dataset.category,kind:e.dataset.kind,style:e.dataset.style,gender:e.dataset.gender,size_basis:e.dataset.sizeBasis,color:e.dataset.color,brand:e.dataset.brand,material:e.dataset.material,image:e.dataset.image,image_note:e.dataset.imageNote,photo_color:e.dataset.photoColor,design_style:e.dataset.designStyle,region:e.dataset.region,quality:e.dataset.quality,fit:e.dataset.fit,occasion:e.dataset.occasion,name:e.querySelector('h2').textContent,description:e.querySelector('[data-description]').textContent,price_cents:Number(e.dataset.price),sizes:[...e.querySelectorAll('select[name=size] option')].filter(o=>o.value).map(o=>({size:o.value,stock:Number(o.dataset.stock)}))})),orders_account:document.querySelector('[data-orders-account]')?.dataset.ordersAccount||null,orders_count:Number(document.querySelector('[data-orders-count]')?.dataset.ordersCount||0),orders:[...document.querySelectorAll('[data-history-order]')].map(o=>({type:'order',reference:o.dataset.reference,date:o.dataset.date,status:o.dataset.status,currency:o.dataset.currency,total_cents:Number(o.dataset.total),items:[...o.querySelectorAll('[data-history-item]')].map(i=>({id:i.dataset.productId,name:i.dataset.name,color:i.dataset.color,size:i.dataset.size,price_cents:i.dataset.price?Number(i.dataset.price):null,quantity:Number(i.dataset.quantity),image:i.querySelector('img')?.getAttribute('src')?i.querySelector('img').src:null}))})),context_reset:!!document.querySelector('[data-context-reset]'),cart:[...document.querySelectorAll('[data-cart-item]')].map(e=>({id:e.dataset.productId,name:e.dataset.name,color:e.dataset.color,image:e.querySelector('img')?.getAttribute('src')?e.querySelector('img').src:null,size:e.dataset.size,price_cents:Number(e.dataset.price),quantity:Number(e.dataset.quantity||1)})),review:document.querySelector('[data-review]')?{id:document.querySelector('[data-review]').dataset.review,revision:Number(document.querySelector('[data-review]').dataset.revision),total_cents:Number(document.querySelector('[data-review]').dataset.total),summary:document.querySelector('[data-summary]').textContent}:null,receipt:document.querySelector('[data-receipt]')?.textContent||null}))()`) }
async function dispatch(a){
 if(a.action==='launch')return launch(a);
 if(a.action==='close'){await cleanup();return {closed:true}}
 if(!session)throw Error('Browser not launched');
 if(a.action==='configure'){for(const u of [a.storefront,a.activation]){const parsed=new URL(u);if(parsed.origin!==origin||parsed.protocol!=='https:'||parsed.username||parsed.password||parsed.search||parsed.hash||!/^\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(parsed.pathname))throw Error('Unsafe company destination')}if(a.storefront===a.activation)throw Error('Distinct destinations required');storefront=a.storefront;activation=a.activation;return {configured:true}}
 if(!storefront||!activation)throw Error('Company destinations required');
 if(a.action==='join'){
  if(a.endpoint!==activation)throw Error('Bootstrap origin refused');
  const fields=JSON.stringify(a.fields),endpoint=JSON.stringify(a.endpoint);
  await documentNavigation(()=>evaluate(`(()=>{const f=document.createElement('form');f.method='POST';f.action=${endpoint};for(const [k,v] of Object.entries(${fields})){const i=document.createElement('input');i.type='hidden';i.name=k;i.value=v;f.append(i)}document.body.replaceChildren(f);f.requestSubmit()})()`));
  for(const exchange of activationExchanges){if(exchange.status<300||exchange.status>=400){try{const b=await command('Network.getResponseBody',{requestId:exchange.network_request_id});exchange.response.body=b.base64Encoded?{base64:b.body}:b.body}catch{}}}
  await assertPage();return snapshot();
 }
 if(a.action==='viewport'){await command('Emulation.setDeviceMetricsOverride',{width:a.width,height:a.height,deviceScaleFactor:1,mobile:false});return evaluate('({width:innerWidth,content:document.documentElement.scrollWidth})')}
 if(a.action==='screenshot'){await assertPage();await evaluate(`Promise.all([...document.images].filter(i=>{const r=i.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight}).map(i=>i.decode().catch(()=>{})))`);return command('Page.captureScreenshot',{format:'png',captureBeyondViewport:a.full_page===true})}
 if(a.action==='order_status')await navigate(storefront+'/review');
 else if(a.action==='clear_selection'){await navigate(storefront);await submit(`document.querySelector('form[data-shop-action="clear"]').requestSubmit()`)}
 else if(a.action==='next'){await assertPage();const href=await evaluate("document.querySelector('[data-shop-next]')?.href");if(!href)throw Error('No next page');await navigate(href)}
 else if(a.action==='edit_filter'){
  await assertPage();
  const change=()=>evaluate(`(()=>{const f=document.querySelector('form[data-shop-action="filter"]'),e=f.elements[${JSON.stringify(a.name)}];if(!e)throw Error('Unknown control');e.value=${JSON.stringify(a.value)};e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true}))})()`);
  if(a.expect_navigation)await documentNavigation(change);else await change();
 }
 else if(a.action==='catalog_layout'){
  await assertPage();return evaluate(`(()=>{const grid=document.querySelector('.grid'),pager=document.querySelector('.pagination.bottom'),form=document.querySelector('form[data-shop-action=filter]');return {width:innerWidth,content:document.documentElement.scrollWidth,pager_gap:pager.getBoundingClientRect().top-grid.getBoundingClientRect().bottom,controls:[...form.elements].filter(e=>e.name&&e.type!=='hidden').map(e=>e.name),mobile_filters_open:document.querySelector('.facet-panel').open}})()`);
 }
 else if(a.action==='scroll_catalog_end'){
  await assertPage();await evaluate("document.querySelector('.pagination.bottom').scrollIntoView({block:'end'})");
 }
 else if(a.action==='reset_filters'){const href=await evaluate("document.querySelector('[data-clear-filters]')?.href");if(!href)throw Error('No clear link');await navigate(href)}
 else if(a.action==='previous'){const href=await evaluate("document.querySelector('[data-shop-prev]')?.href");if(!href)throw Error('No previous link');await navigate(href)}
 else if(a.action==='account_status')await navigate(storefront+'/account');
 else if(a.action==='logout'){
  await navigate(storefront+'/account');
  if(await evaluate("!!document.querySelector('form[data-shop-action=logout]')"))await submit("document.querySelector('form[data-shop-action=logout]').requestSubmit()");
 }
 else if(a.action==='cart')await navigate(storefront+'/cart');
 else if(a.action==='orders')await navigate(storefront+'/orders');
 else if(a.action==='question_context')await navigate(storefront+'/question-context?query='+encodeURIComponent(JSON.stringify(a.query)));
 else if(a.action==='availability_offer')await navigate(storefront+'/availability?filters='+encodeURIComponent(JSON.stringify(a.filters)));
 else if(a.action==='availability_events')await navigate(storefront+'/availability?events=1');
 else if(a.action==='availability_subscribe'||a.action==='availability_cancel'){
  await navigate(storefront+'/availability');
  await submit(`(()=>{const f=document.querySelector('form[data-shop-action=availability]');f.elements.action.value=${JSON.stringify(a.action==='availability_cancel'?'cancel':'subscribe')};f.elements.offer.value=${JSON.stringify(a.offer||'')};f.elements.consent.value=${JSON.stringify(a.consent)};f.requestSubmit()})()`);
 }
 else if(a.action==='context_read')await navigate(storefront+'/context'+(a.request_id?'?request_id='+encodeURIComponent(a.request_id):''));
 else if(a.action==='context_update'){
  await navigate(storefront+'/context');
  const ready=await evaluate("!!document.querySelector('form[data-shop-action=context]')");
  if(!ready)return snapshot();
  await submit(`(()=>{const f=document.querySelector('form[data-shop-action="context"]');f.elements.preferences.value=${JSON.stringify(JSON.stringify(a.preferences))};if(f.elements.intent)f.elements.intent.value=${JSON.stringify(JSON.stringify(a.intent||{}))};if(f.elements.update_id)f.elements.update_id.value=${JSON.stringify(a.update_id||'')};if(f.elements.metadata)f.elements.metadata.value=${JSON.stringify(JSON.stringify(a.metadata||{}))};f.requestSubmit()})()`);
 }
 else if(a.action==='reset_context'){await navigate(storefront+'/reset');await submit(`(()=>{const f=document.querySelector('form[data-shop-action=\"reset-context\"]');f.elements.request_id.value=${JSON.stringify(a.request_id)};f.requestSubmit()})()`);}
 else if(a.action==='catalog')await navigate(storefront);
 else if(a.action==='filter'){
  await navigate(storefront+'?reset=1');
  await submit(`(()=>{const f=document.querySelector('form[data-shop-action="filter"]');for(const e of f.elements){if(e.name&&e.name!=='csrf'&&e.type!=='submit')e.value=''}for(const [k,v] of Object.entries(${JSON.stringify(a.filters)})){if(!f.elements[k])throw Error('Unsupported filter '+k);f.elements[k].value=v;if(String(f.elements[k].value)!==String(v))throw Error('Filter could not be applied: '+k)}f.requestSubmit()})()`);
 }else if(a.action==='detail'){await navigate(storefront+'/product/'+encodeURIComponent(a.product));
 }else if(a.action==='recommend'){
  await navigate(storefront);
  await submit(`(()=>{const f=document.querySelector('form[data-shop-action="recommend"]'),s=f.querySelector('select[name=size]');s.value=${JSON.stringify(a.size)};if(!s.value)throw Error();f.elements.budget.value=${JSON.stringify(a.budget??'')};f.elements.style.value=${JSON.stringify(a.style??'any')};f.requestSubmit()})()`);
 }
 else if(a.action==='add'){
  await navigate(storefront+'/product/'+encodeURIComponent(a.product));
  await submit(`(()=>{const id=${JSON.stringify(a.product)},size=${JSON.stringify(a.size)};const card=[...document.querySelectorAll('[data-product]')].find(e=>e.dataset.product===id);if(!card)throw Error();const f=card.querySelector('form'),s=f.querySelector('select[name=size]');s.value=size;if(!s.value)throw Error();if(${JSON.stringify(a.add_id||'')})f.elements.add_id.value=${JSON.stringify(a.add_id||'')};if(${JSON.stringify(a.expected_price??null)}!==null)f.elements.expected_price.value=${JSON.stringify(a.expected_price??null)};f.requestSubmit()})()`);
 }else if(a.action==='cart_update'||a.action==='cart_remove'){
  await navigate(storefront+'/cart');
  await submit(`(()=>{const row=[...document.querySelectorAll('[data-cart-item]')].find(e=>e.dataset.productId===${JSON.stringify(a.product)}&&e.dataset.size===${JSON.stringify(a.old_size)});if(!row)throw Error('Variant not found');const f=row.querySelector('form[data-shop-action="'+${JSON.stringify(a.action==='cart_update'?'cart-update':'cart-remove')}+'"]');if(!f)throw Error('Bag form missing');if(${JSON.stringify(a.action)}==='cart_update'){f.elements.size.value=${JSON.stringify(a.size)};if(!f.elements.size.value)throw Error('Size unavailable');f.elements.quantity.value=${JSON.stringify(String(a.quantity))}}f.requestSubmit()})()`);
 }else if(a.action==='review'){
  await navigate(storefront+'/cart');await submit(`document.querySelector('form[data-shop-action="review"]').requestSubmit()`);
 }else if(a.action==='checkout'){
  if(a.approved!==true)throw Error('Explicit approval required');
  await assertPage();
  await submit(`(()=>{const r=document.querySelector('[data-review]');if(!r||r.dataset.review!==${JSON.stringify(a.review)})throw Error();const f=document.querySelector('form[data-shop-action="checkout"]');f.requestSubmit(f.querySelector('button'))})()`);
 }else if(a.action!=='snapshot')throw Error('Unknown browser action');
 return snapshot();
}
async function cleanup(){if(ws){try{await command('Browser.close',{},null)}catch{}ws.close();ws=null}if(chrome){chrome.kill('SIGTERM');await new Promise(r=>setTimeout(r,300));chrome=null}if(dir){fs.rmSync(dir,{recursive:true,force:true});dir=null}}
let queue=Promise.resolve();const input=readline.createInterface({input:process.stdin});input.on('line',line=>{queue=queue.then(async()=>{let id;try{const a=JSON.parse(line);id=a.id;const result=await dispatch(a);process.stdout.write(JSON.stringify({id,result,capture_evidence:captureEvidence.splice(0),activation_exchanges:activationExchanges.splice(0)})+'\n')}catch(e){process.stderr.write(String(e.message)+'\n');process.stdout.write(JSON.stringify({id,error:'Isolated browser action failed; no credentials exposed.',capture_evidence:captureEvidence.splice(0),activation_exchanges:activationExchanges.splice(0)})+'\n')}})});input.on('close',()=>queue.finally(()=>cleanup()).finally(()=>process.exit()));process.on('SIGTERM',()=>cleanup().finally(()=>process.exit()));
