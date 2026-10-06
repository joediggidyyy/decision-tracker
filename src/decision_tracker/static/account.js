/* Human account controls and bounded draft leases. No secrets survive page memory. */
export function installAccount({$,state,api,signedIn,show,message,dirty,live,hasDraft=dirty,onReauthenticated=()=>{}}){
 let legacy=false,setup=false,precsrf=null,returnEditor=false,lease=null,leaseBusy=false,renewAt=0;
 const tabNonce=crypto.randomUUID();
 async function preauth(){
  const response=await fetch('/api/v1/session/setup',{credentials:'same-origin'});
  if(response.status===404){legacy=true;return null;}
  const value=await response.json();if(!response.ok)throw Error(value.error?.message||'Sign-in is unavailable.');
  legacy=false;precsrf=value.data.csrf_token;setup=value.data.setup_available;return value.data;
 }
 async function loginView(){
  try{const info=await preauth();$('setup-fields').hidden=!setup;$('setup-confirm-label').hidden=!setup;$('token').autocomplete=setup?'new-password':'current-password';$('setup-code').required=setup;$('setup-confirm').required=setup;
   $('login-submit').textContent=setup?'Set password':'Sign in';$('login-heading').textContent=setup?'Create your password':'Sign in';
   $('login-help').textContent=legacy?'Use the isolated preview credential.':info?.recovery_pending?'Password recovery is in progress. Complete it using the local CLI.':setup?'Enter the one-time setup code from your local terminal, then choose a private password.':'Security Efficiency Awareness Minimalism';
   $('login-form').hidden=!!info?.recovery_pending;
  }catch(error){message(error.message,true);}
 }
 async function authenticate(password){
  await preauth();
  const headers={'Content-Type':'application/json'};if(precsrf)headers['X-CSRF-Token']=precsrf;
  const response=await fetch('/api/v1/session',{method:'POST',credentials:'same-origin',headers,body:JSON.stringify(legacy?{token:password}:{password})});
  const result=await response.json();if(!response.ok)throw Error(result.error?.message||'Sign-in failed.');return result.data;
 }
 $('login-form').onsubmit=async event=>{
  event.preventDefault();const password=$('token').value,confirmation=$('setup-confirm').value,code=$('setup-code').value;
  $('token').value=$('setup-confirm').value=$('setup-code').value='';
  try{
   if(setup){const response=await fetch('/api/v1/session/setup',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':precsrf},body:JSON.stringify({bootstrap_code:code,new_password:password,confirmation})});
    if(!response.ok){const r=await response.json();throw Error(r.error?.message||'Setup failed.');}
    message('Password created. Sign in to continue.');await loginView();
   }else{const data=await authenticate(password);await signedIn(data);$('account-toggle').hidden=legacy;}
  }catch(error){message(error.message,true);await loginView();}
 };
 function closeAccount(){
  $('account-form').reset();$('account-dialog').close();
  if(returnEditor&&state.edit){$('editor').showModal();returnEditor=false;}
 }
 async function openAccount(){
  if(legacy)return;
  returnEditor=$('editor').open;if(returnEditor)$('editor').close();
  $('close-account').textContent=returnEditor?'Return to draft':'Close';$('account-error').hidden=true;$('account-message').textContent='';$('account-dialog').showModal();
  try{const result=await api('/api/v1/account');$('account-message').textContent=result.data.other_sessions+' other active session(s). Agent access is unaffected.';}
  catch(error){$('account-message').textContent='Sign in below to manage your account or return to your draft.';}
 }
 $('account-toggle').onclick=openAccount;$('editor-account').onclick=openAccount;
 $('close-account').onclick=closeAccount;$('account-dialog').oncancel=event=>{event.preventDefault();closeAccount();};
 async function rotated(){const result=await api('/api/v1/session');state.csrf=result.data.csrf_token;lease=null;await protectDraft();}
 $('account-form').onsubmit=async event=>{
  event.preventDefault();const body={current_password:$('current-password').value,new_password:$('new-password').value,confirmation:$('confirm-password').value};
  try{await api('/api/v1/account/password',body);await rotated();$('account-form').reset();$('account-message').textContent='Password changed. Other browser sessions signed out. Agent access is unchanged.';}
  catch(error){$('account-error').textContent=error.message;$('account-error').hidden=false;}
 };
 $('revoke-sessions').onclick=async()=>{
  try{await api('/api/v1/account/sessions/revoke-others',{current_password:$('current-password').value});await rotated();$('account-form').reset();$('account-message').textContent='Other browser sessions signed out.';}
  catch(error){$('account-error').textContent=error.message;$('account-error').hidden=false;}
 };
 $('account-signin').onclick=async()=>{
  try{const data=await authenticate($('current-password').value);state.csrf=data.csrf_token;state.caps=data.capabilities;$('current-password').value='';$('account-message').textContent='Signed in. Your draft is retained.';lease=null;await protectDraft();if(state.project)live.start(state.project,state.record?.key||null);onReauthenticated();}
  catch(error){$('account-error').textContent=error.message;$('account-error').hidden=false;}
 };
 async function protectDraft(){
  if(legacy||leaseBusy)return;leaseBusy=true;
  try{
   if(!dirty()||!state.project){if(lease){const old=lease;lease=null;await api('/api/v1/service/draft-leases/'+old,undefined,'DELETE');}$('draft-protection').textContent='';return;}
   if(Date.now()<renewAt)return;
   const body={project_id:state.project.project_id,expected_ledger_uuid:state.project.ledger_uuid,tab_nonce:tabNonce};
   const result=await api('/api/v1/service/draft-leases'+(lease?'/'+lease:''),body,lease?'PUT':'POST');
   lease=result.data.lease_id;renewAt=Date.now()+60000;$('draft-protection').textContent='';
  }catch(error){lease=null;renewAt=Date.now()+60000;$('draft-protection').textContent='Draft protection unavailable. Use Account & access to sign in; your unsaved text is still here.';}
  finally{leaseBusy=false;}
 }
 let protectionTimer;
 $('edit-form').addEventListener('input',()=>{clearTimeout(protectionTimer);protectionTimer=setTimeout(()=>{renewAt=0;protectDraft();},350);});
 $('editor').addEventListener('close',()=>protectDraft());
 const heartbeat=setInterval(protectDraft,60000);window.addEventListener('pagehide',()=>clearInterval(heartbeat));
 $('stop-service').onclick=async()=>{
  $('stop-service-confirm').hidden=false;
 };
 $('confirm-stop-service').onclick=async()=>{
  const submit=$('confirm-stop-service');submit.disabled=true;
  try{if(hasDraft())throw Error('Save or discard your unsaved changes before stopping the backend.');await api('/api/v1/service/stop',{});live.stop('Service stopped');$('service-status').textContent='Stopping. Start opens the application again.';$('service-details').textContent='Saved data is retained.';$('stop-service-confirm').hidden=true;$('stop-service').hidden=true;$('start-service').hidden=false;}catch(error){$('service-status').textContent=error.message;}finally{submit.disabled=false;}
 };
 $('cancel-stop-service').onclick=()=>$('stop-service-confirm').hidden=true;
 loginView();api('/api/v1/account').then(()=>{$('account-toggle').hidden=false;}).catch(()=>{});
 return {authenticate,loginView};
}
