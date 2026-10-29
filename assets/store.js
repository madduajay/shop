'use strict';
const form=document.querySelector('form[data-shop-action="filter"]');
if(form){
 let timer;
 const submit=()=>{clearTimeout(timer);if(form.elements.request_id)form.elements.request_id.value='';if(form.elements.expires_at)form.elements.expires_at.value='';if(form.reportValidity())form.requestSubmit()};
 form.addEventListener('change',e=>{if(e.target.matches('select'))submit()});
 form.addEventListener('input',e=>{if(e.target.matches('input:not([type=hidden])')){clearTimeout(timer);timer=setTimeout(submit,550)}});
 form.addEventListener('submit',()=>{form.setAttribute('aria-busy','true');document.querySelector('.results')?.setAttribute('aria-busy','true');const b=form.querySelector('button');b.textContent='Updating…'});
 const panel=document.querySelector('.facet-panel');if(matchMedia('(max-width:800px)').matches)panel.open=false;
}
let loginWindow=null,loginReturn='/shop/account';
document.querySelectorAll('[data-login-popup]').forEach(link=>link.addEventListener('click',e=>{
 const url=new URL(link.href);if(url.origin!==location.origin)return;
 loginReturn=url.searchParams.get('return_to')||'/shop/account';
 loginWindow=window.open(url.href,'forme-account-login','popup,width=540,height=780');
 if(loginWindow)e.preventDefault();
}));
window.addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==loginWindow||e.data?.type!=='forme-signed-in')return;if(!['/shop','/shop/cart','/shop/checkout','/shop/account','/shop/preferences'].includes(loginReturn))return;loginWindow.close();location.assign(loginReturn)});
if(document.body.dataset.page==='signin-success'){
 if(window.opener){window.opener.postMessage({type:'forme-signed-in'},location.origin);window.close()}
 else{const link=document.querySelector('[data-login-return]');if(link)setTimeout(()=>location.assign(link.href),350)}
}
const preferenceForm=document.querySelector('#preferences-form');
if(preferenceForm){
 document.querySelectorAll('[data-clear-pref]').forEach(b=>b.addEventListener('click',()=>{const el=preferenceForm.querySelector('select[name="'+b.dataset.clearPref+'"]')||preferenceForm.elements[b.dataset.clearPref];if(el.multiple)[...el.options].forEach(o=>o.selected=false);else el.value='';el.dispatchEvent(new Event('change',{bubbles:true}));}));
 const choices=JSON.parse(document.querySelector('#preference-options').textContent);
 preferenceForm.elements.pref_gender.addEventListener('change',()=>{const opts=choices[preferenceForm.elements.pref_gender.value]||choices[''];for(const k of ['shirt_size','waist','shoe_size','design_style']){const el=preferenceForm.elements['pref_'+k],old=el.value;el.replaceChildren(new Option('No preference',''),...opts[k].map(v=>new Option(v.replaceAll('-',' '),v)));if(old&&!opts[k].includes(old))el.add(new Option(old+' · previously saved',old));el.value=old;}});
 preferenceForm.addEventListener('submit',()=>{preferenceForm.querySelector('.pref-save button')?.setAttribute('aria-busy','true');});
}
