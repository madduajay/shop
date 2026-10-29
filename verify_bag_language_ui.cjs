// Disposable headless UI verification. No personal browser profile or cookie writes.
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),cp=require('node:child_process');
const base=process.argv[2],out=process.argv[3];if(!/^https:\/\/atlas\.localhost:844[357]$/.test(base))throw Error('Local demo only');
const allowed=new Set([base,base.replace('atlas.','jacket.')]);const dir=fs.mkdtempSync(path.join(os.tmpdir(),'thread3-ui-check-'));let chrome,ws,id=0,sid;const pending=new Map();
const delay=ms=>new Promise(r=>setTimeout(r,ms));
function cmd(method,params={},session=sid){return new Promise((resolve,reject)=>{const n=++id,timer=setTimeout(()=>reject(Error(method+' timeout')),30000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params,...(session?{sessionId:session}:{})}))})}
async function ev(expression,session=sid){const r=await cmd('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true},session);if(r.exceptionDetails)throw Error('UI evaluation failed');return r.result.value}
async function until(expression){for(let i=0;i<300;i++){if(await ev(expression))return;await delay(100)}throw Error('UI state timeout')}
async function chat(text){const before=await ev("document.querySelectorAll('.assistant').length");await ev(`(()=>{document.querySelector('#text').value=${JSON.stringify(text)};document.querySelector('#chat').requestSubmit()})()`);await until(`document.querySelectorAll('.assistant').length>${before} && document.querySelector('#status').textContent===''`);return ev("({reply:(()=>{const e=[...document.querySelectorAll('.assistant')].at(-1);return e?.querySelector('code')?.textContent||e?.textContent})(),identity:document.querySelector('#identity').textContent,cards:[...document.querySelectorAll('.card')].map(e=>({name:e.querySelector('h3').textContent,explanation:e.querySelector('.explanation').textContent,source:[...e.querySelectorAll('small')].at(-1).textContent}))})")}
async function shot(name){await ev(name.includes('explanations')?"[...document.querySelectorAll('.cards')].at(-1).scrollIntoView({block:'start'})":"document.querySelector('#messages').scrollIntoView({block:'start'})");await delay(200);const x=await cmd('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name),Buffer.from(x.data,'base64'))}
(async()=>{const report=[];try{
 chrome=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--remote-debugging-port=0','--user-data-dir='+dir,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-extensions','about:blank'],{stdio:'ignore'});
 let address;for(let i=0;i<100;i++){try{address=fs.readFileSync(path.join(dir,'DevToolsActivePort'),'utf8').trim().split('\n');break}catch{}await delay(100)}
 ws=new WebSocket('ws://127.0.0.1:'+address[0]+address[1]);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});ws.onmessage=({data})=>{const m=JSON.parse(data);if(m.id){const p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}}};
 const ctx=(await cmd('Target.createBrowserContext',{},null)).browserContextId;const target=(await cmd('Target.createTarget',{url:'about:blank',browserContextId:ctx},null)).targetId;sid=(await cmd('Target.attachToTarget',{targetId:target,flatten:true},null)).sessionId;
 await cmd('Page.enable');await cmd('Runtime.enable');await cmd('Emulation.setDeviceMetricsOverride',{width:1180,height:1300,deviceScaleFactor:1,mobile:false});await cmd('Page.navigate',{url:base+'/'});await until("!!document.querySelector('#thread-login')");
 const loginShot=await cmd('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'thread-login.png'),Buffer.from(loginShot.data,'base64'));
 async function login(number){await ev(`(()=>{const f=document.querySelector('#thread-login');f.elements.email.value='customer${String(number).padStart(3,'0')}@thread.local';f.elements.password.value='wardrobe';f.requestSubmit()})()`);await until("!!document.querySelector('#chat') && document.querySelector('#identity').textContent.includes('"+String(number).padStart(3,'0')+"')")}
 await login(1);
 const first=await chat('show me what is on the baf');report.push({query:'show me what is on the baf',...first});if(!first.reply.includes('Sign in with FORME'))throw Error('Bag did not request authorization');
 await until("!!document.querySelector('#auth button')");await ev("document.querySelector('#auth button').click()");
 let popup;for(let i=0;i<50;i++){const ts=(await cmd('Target.getTargets',{},null)).targetInfos;popup=ts.find(x=>x.url.startsWith(base.replace('atlas.','jacket.')+'/signin?'));if(popup)break;await delay(100)}if(!popup)throw Error('Sign-in popup missing');
 const ps=(await cmd('Target.attachToTarget',{targetId:popup.targetId,flatten:true},null)).sessionId;
 await ev("(()=>{const f=document.querySelector('form');f.elements.password.value='wardrobe';f.requestSubmit()})()",ps);
 await until("!document.querySelector('#auth button') && [...document.querySelectorAll('.assistant')].at(-1).textContent.includes('Essential Crew Tee')");
 for(const q of ['show me what is on the bag','what have I got in my basket?','show the shirts in my cart','could you check what I already put in there?','how much is that altogether?','whats in my crat','lemme see whats inside the shopping basket']){
  const r=await chat(q);report.push({query:q,...r});if(!r.reply.includes('Essential Crew Tee')||!r.reply.includes('32.00'))throw Error('Bag semantic read failed: '+q+' '+r.reply);
 }
 await shot('bag-language-live-gpt.png');
 for(const q of ['empty my basket','remove everything from my cart','buy everything in my bag']){const r=await chat(q);report.push({query:q,...r});if(/Order FM-|placed|removed successfully/.test(r.reply))throw Error('Mutation claimed');}
 fs.writeFileSync(path.join(out,'bag-language-live-ui.json'),JSON.stringify({fixture_only:true,cases:report},null,2));console.log('Semantic bag live GPT UI passed');
 }finally{if(ws){try{await cmd('Browser.close',{},null)}catch{}ws.close()}if(chrome)chrome.kill();await delay(300);fs.rmSync(dir,{recursive:true,force:true})}})().catch(e=>{console.error(e.message);process.exitCode=1});
