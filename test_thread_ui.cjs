// Synthetic Thread3 UI regression only; independent Chrome/profile and normal TLS.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict');
const base='https://atlas.localhost:8545',allowed=new Set([base,'https://jacket.localhost:8545']);
const actualProvider=process.argv[3]==='actual-provider';
const smokeOnly=process.argv[4]==='smoke-only';
let chrome,ws,session,dir,next=0,stage='launch';const exchanges=[];const pending=new Map();
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function command(method,params={},sid=session){return new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('UI CDP timeout: '+method))},15000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sid?{sessionId:sid}:{})}))})}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error('Synthetic UI action failed');return r.result.value}
async function until(expression){const end=Date.now()+(actualProvider?105000:15000);while(Date.now()<end){try{if(await evaluate(expression))return}catch{}await pause(50)}throw Error('Synthetic UI assertion timed out ('+stage+'): '+JSON.stringify(exchanges)+'; '+expression+'; '+JSON.stringify(await evaluate("({path:location.pathname,title:document.title,error:document.querySelector('.error')?.textContent,status:document.querySelector('#status')?.textContent,identity:document.querySelector('#identity')?.textContent})")))}
async function login(number){
 stage='login '+number;
 await until(`location.origin===${JSON.stringify(base)}&&location.pathname==='/login'&&!!document.querySelector('#thread-login')`);
 await evaluate(`(()=>{const f=document.querySelector('#thread-login');f.elements.email.value='customer${String(number).padStart(3,'0')}@thread.local';f.elements.password.value='wardrobe';f.requestSubmit()})()`);
 await until(`location.origin===${JSON.stringify(base)}&&location.pathname==='/'&&!!document.querySelector('#chat')&&document.readyState!=='loading'`);
}
(async()=>{
 try{
  dir=fs.mkdtempSync(path.join(os.tmpdir(),'thread3-ui-fixture-'));
  chrome=cp.spawn(process.argv[2],['--headless=new','--remote-debugging-port=0','--user-data-dir='+dir,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','--disable-extensions','about:blank'],{stdio:'ignore'});
  let address;for(let i=0;i<150;i++){try{address=fs.readFileSync(path.join(dir,'DevToolsActivePort'),'utf8').trim().split('\n');if(/^\d+$/.test(address[0])&&address[1].startsWith('/devtools/browser/'))break}catch{}await pause(100)}
  assert(address);ws=new WebSocket('ws://127.0.0.1:'+address[0]+address[1]);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=()=>reject(Error('Synthetic UI Chrome unavailable'))});
  ws.onmessage=async({data})=>{const m=JSON.parse(data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error('UI CDP command refused')):p.resolve(m.result)}return}
   if(m.method==='Network.requestWillBeSent'){const p=m.params,u=new URL(p.request.url);if(allowed.has(u.origin))exchanges.push({method:p.request.method,path:u.pathname,redirect:p.redirectResponse?.status})}
   if(m.method==='Network.responseReceivedExtraInfo'&&m.params.blockedCookies?.length)exchanges.push({blocked_cookie_reasons:m.params.blockedCookies.flatMap(c=>c.blockedReasons)});
   if(m.method==='Network.responseReceived'){const u=new URL(m.params.response.url);if(allowed.has(u.origin))exchanges.push({path:u.pathname,status:m.params.response.status})}
   if(m.method==='Fetch.requestPaused'){let own=false;try{own=allowed.has(new URL(m.params.request.url).origin)}catch{}try{await command(own?'Fetch.continueRequest':'Fetch.failRequest',own?{requestId:m.params.requestId}:{requestId:m.params.requestId,errorReason:'BlockedByClient'},m.sessionId)}catch{}}
  };
  const context=(await command('Target.createBrowserContext',{},null)).browserContextId;
  const target=(await command('Target.createTarget',{url:'about:blank',browserContextId:context},null)).targetId;
  session=(await command('Target.attachToTarget',{targetId:target,flatten:true},null)).sessionId;
  await command('Page.enable');await command('Runtime.enable');await command('Network.enable');await command('Fetch.enable',{patterns:[{urlPattern:'*'}]});await command('Browser.setDownloadBehavior',{behavior:'deny',browserContextId:context},null);
  await command('Page.navigate',{url:base+'/'});await login(1);
  await evaluate(`(()=>{document.querySelector('#text').value='Show pending additions';document.querySelector('#chat').requestSubmit()})()`);
  await until("[...document.querySelectorAll('.assistant')].some(e=>e.textContent.includes('No items are waiting to be added.'))");
  const first=await evaluate("document.querySelector('#identity').textContent");
  if(smokeOnly)assert(first&&first!=='Your wardrobe');else assert(first.includes('Alex Morgan'));
  await evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))");
  const shot=await command('Page.captureScreenshot',{format:'png'});fs.writeFileSync(smokeOnly?'evidence/thread3-live-restored.png':actualProvider?'evidence/thread3-ui-live.png':'evidence/thread3-ui.png',Buffer.from(shot.data,'base64'));
  if(smokeOnly){console.log(JSON.stringify({login:true,rendered_chat:true,actual_provider_requested:actualProvider,smoke_only:true,read_only_request:true,no_clear_or_archive_changes:true,TLS_bypass:false}));return}
  await command('Page.navigate',{url:base+'/'});
  await until("[...document.querySelectorAll('.assistant')].some(e=>e.textContent.includes('No items are waiting to be added.'))");
  await evaluate("document.querySelector('#clear-chat').click()");await until("document.querySelector('#clear-dialog').open");
  await evaluate("document.querySelector('#confirm-clear').click()");await until("!document.querySelector('#clear-dialog').open&&document.querySelector('#messages').textContent.includes('A fresh start.')");
  await evaluate("document.querySelector('#archives').click()");await until("document.querySelector('#archive-dialog').open&&!!document.querySelector('#archive-list button')");
  await evaluate("document.querySelector('#archive-list button').click()");await until("document.querySelector('#archive-content').textContent.includes('No items are waiting to be added.')");
  await evaluate("document.querySelector('#close-archives').click();document.querySelector('#logout').click()");await login(2);
  assert.equal(await evaluate("document.querySelector('#messages').textContent.includes('Show pending additions')"),false);
  await evaluate("document.querySelector('#text').value='hello';document.querySelector('#chat').requestSubmit()");
  await until("document.querySelector('#identity').textContent!=='Your wardrobe'");
  const second=await evaluate("document.querySelector('#identity').textContent");assert.notEqual(first,second);
  console.log(JSON.stringify({login:true,real_deepagents_via_scripted_provider:!actualProvider,actual_provider_requested:actualProvider,rendered_chat:true,reload_restore:true,clear_archive_readonly:true,second_identity_isolated:true,TLS_bypass:false}));
 }finally{
  if(ws){try{await command('Browser.close',{},null)}catch{}ws.close()}
  if(chrome){chrome.kill('SIGTERM');await pause(300)}
  if(dir)fs.rmSync(dir,{recursive:true,force:true});
 }
})().catch(e=>{console.error(e.message);process.exitCode=1});
