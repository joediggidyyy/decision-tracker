import {installActionForm,titles} from './action-form.js';
import {installDecisionForm} from './decision-form.js';
import {sendRetained,definitive,readResponse} from './save-request.js';
import {LiveMonitor} from './live.js';
import {installAccount} from './account.js';
const $=id=>document.getElementById(id);
const state={csrf:null,caps:[],projects:[],project:null,revision:0,record:null,cursor:null,edit:null,listRevision:null,contextFingerprint:null};
let listGeneration=0,detailGeneration=0,searchTimer=null;
function rememberView(key=null){if(state.project){const params=new URLSearchParams({project:state.project.project_id});if(key)params.set('decision',key);history.replaceState(null,'','#'+params);}}
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function message(text,error=false){const e=$(error?'error':'notice');e.textContent=text;e.hidden=false;}
function failure(e){message(e.message,true);}
async function api(path,body,method=body===undefined?'GET':'POST'){
 const bound=path.match(/^\/api\/v1\/projects\/([^/]+)\//);
 const binding=bound&&state.project?{id:state.project.project_id,uuid:state.project.ledger_uuid}:null;
 if(bound&&(!binding||decodeURIComponent(bound[1])!==binding.id))throw new Error('Project changed. Reload the selected project.');
 const headers={};if(state.project)headers['X-Ledger-UUID']=state.project.ledger_uuid;
 if(body!==undefined)headers['Content-Type']='application/json';
 if(state.csrf)headers['X-CSRF-Token']=state.csrf;
 const r=await fetch(path,{method,headers,credentials:'same-origin',body:body===undefined?undefined:JSON.stringify(body),signal:path.endsWith('/changes')?AbortSignal.timeout(15000):undefined});
 const value=r.status===204?{ok:true,data:{}}:await readResponse(r);if(binding&&(!state.project||state.project.project_id!==binding.id||state.project.ledger_uuid!==binding.uuid))throw new Error('Project changed. Discarding the previous response.');if(!r.ok){const e=new Error(value.error?.message||'Request failed');e.code=value.error?.code;e.details=value.error?.details;throw e;}return value;
}
const base=()=>'/api/v1/projects/'+encodeURIComponent(state.project.project_id);
function button(label,fn,parent,disabled=false){const b=node('button',label);b.type='button';b.disabled=disabled;b.onclick=()=>Promise.resolve().then(fn).catch(failure);parent.append(b);return b;}
function show(view){$('focus-toggle').hidden=view!=='workspace';for(const id of ['login-view','workspace','projects-view'])$(id).hidden=id!==view;}
async function projects(){
 const r=await api('/api/v1/projects');state.catalogRevision=r.catalog_revision;state.projects=r.data;
 $('project').replaceChildren(new Option('Choose project',''));
 for(const p of r.data.filter(p=>p.enabled))$('project').add(new Option(p.name,p.project_id));
 if(state.project)$('project').value=state.project.project_id;
 $('create-project').hidden=$('register-project').hidden=!state.caps.includes('registry');
}
async function signedIn(data){state.csrf=data.csrf_token;state.caps=data.capabilities;$('signout').hidden=false;$('login-view').hidden=true;await projects();const saved=new URLSearchParams(location.hash.slice(1));if(state.projects.some(p=>p.enabled&&p.project_id===saved.get('project'))){await selectProject(saved.get('project'));if(/^D[0-9]{6}$/.test(saved.get('decision')||''))await detail(saved.get('decision'));}else{show('projects-view');await admin();}}
$('login-form').onsubmit=async e=>{e.preventDefault();const token=$('token').value;$('token').value='';try{await signedIn((await api('/api/v1/session',{token})).data);}catch(err){failure(err);}};
$('signout').onclick=async()=>{live.stop();try{await api('/api/v1/session',undefined,'DELETE');location.reload();}catch(e){failure(e);}};
async function selectProject(id){live.stop();state.listRevision=null;state.contextFingerprint=null;listGeneration++;detailGeneration++;$('results').replaceChildren();$('result-count').textContent='';$('load-more').hidden=true;$('notice').textContent='';$('error').hidden=true;state.project=state.projects.find(p=>p.project_id===id)||null;state.record=null;$('context').replaceChildren();$('detail').replaceChildren(node('p','Choose a decision.'));if(!state.project){show('projects-view');return;}show('workspace');rememberView();$('project').value=state.project.project_id;$('workspace-title').textContent=state.project.name;$('new-decision').disabled=!state.caps.includes('write');await listing();live.start(state.project,null);}
$('project').onchange=()=>selectProject($('project').value).catch(failure);
async function listing(more=false){
 if(!state.project)return;const generation=++listGeneration;
 const q=new URLSearchParams({q:$('search').value,status:$('status').value,work:$('work').value});
 if(more&&state.cursor)q.set('cursor',state.cursor);
 const r=await api(base()+'/decisions?'+q);if(generation!==listGeneration)return;state.revision=r.revision;state.listRevision=r.revision;state.cursor=r.next_cursor;
 if(!more)$('results').replaceChildren();
 for(const d of r.data){const b=button(d.key+' · '+d.title,()=>detail(d.key),$('results'));b.className='decision-row';b.dataset.key=d.key;b.setAttribute('aria-current',state.record?.key===d.key?'true':'false');b.append(node('span',d.status+(d.locked?' · protected':'')+(d.work_tag?' · '+d.work_tag:''),'muted'));}
 if(state.record){let label=$('outside-filters');if(label)label.remove();if(![...$('results').querySelectorAll('button')].some(b=>b.dataset.key===state.record.key)&&!state.cursor){label=node('p','Outside current filters','muted');label.id='outside-filters';$('detail').prepend(label);}}
 if(!$('results').children.length)$('results').append(node('p','No decisions match these filters.','muted'));
 $('result-count').textContent=$('results').querySelectorAll('button').length+(state.cursor?' +':'');$('load-more').hidden=!state.cursor;live.update();if(!state.record)$('context').replaceChildren(node('p','Choose a decision to see its controls.'));
}
$('filters').onsubmit=e=>{e.preventDefault();listing().catch(failure);};
$('load-more').onclick=()=>listing(true).catch(failure);
$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>listing().catch(failure),250);});
async function expand(value){if(!value||typeof value!=='object'||!value.chunks_url)return value;let result='',offset=0;do{const r=await api(value.chunks_url+'&offset='+offset);result+=r.data.text;offset=r.data.next_offset;}while(offset!==null);return result;}
async function all(url){const values=[];let cursor=null;do{const r=await api(url+(cursor?(url.includes('?')?'&':'?')+'cursor='+encodeURIComponent(cursor):''));values.push(...r.data);cursor=r.next_cursor;}while(cursor);return values;}
async function detail(key){
 const generation=++detailGeneration;
 const r=await api(base()+'/decisions/'+key);state.revision=r.revision;state.schemaVersion=r.schema_version;const d=r.data;
 for(const k of Object.keys(d))d[k]=await expand(d[k]);
 if(generation!==detailGeneration)return;rememberView(key);state.record=d;for(const b of $('results').querySelectorAll('button'))b.setAttribute('aria-current',b.dataset.key===key?'true':'false');
 const box=$('detail');box.dataset.loaded='false';box.replaceChildren();
 box.append(node('p',d.key+' · revision '+d.revision,'eyebrow'),node('h2',d.title),node('p',d.status+(d.locked?' · protected baseline '+d.baseline:''),'badge'));
 if(state.schemaVersion<2)box.append(node('p','This project needs a verified data-format upgrade before the new decision form can be used. Existing decisions remain readable.','notice'));
 const question=node('section',undefined,'question-section'),heading=node('div',undefined,'question-heading');heading.append(node('h3','Question','section-title'));question.append(heading,node('p',d.question,'long-text'));box.append(question);
 for(const [label,k] of [['Answer','answer'],['Rationale','rationale']])box.append(node('h3',label),node('p',d[k]||'Not recorded.','long-text'));
 const approval=d.latest_resolution_approval;
 if(approval){box.append(node('h3','Approval','section-title'),node('p',approval.mode==='authenticated_now'?'Approved in this application by '+approval.recorded_by:approval.mode==='reported'?'Approved by (reported): '+approval.reported_approver:'Approval recorded from legacy references; approver and date are unknown.'));box.append(node('p','Decision date: '+(approval.occurred_at||approval.occurred_date||'Unknown')),node('p','Recorded by '+approval.recorded_by+' at '+approval.recorded_at));}
 const controls=$('context');controls.replaceChildren();
 const primary=node('div',undefined,'control-grid control-primary'),actions=node('div',undefined,'control-grid control-secondary'),supporting=node('div',undefined,'control-grid control-supporting');controls.append(primary,actions,supporting);
 const helpEntries=new Map(),help=button('\u24d8',()=>{const opening=help.getAttribute('aria-expanded')!=='true';if(opening)showHelp();else tip.hidden=true;help.setAttribute('aria-expanded',String(opening));},controls);help.className='panel-info';help.setAttribute('aria-label','About these controls');help.setAttribute('aria-expanded','false');
 const tip=node('div',undefined,'control-tooltip');tip.id='panel-control-help';tip.setAttribute('role','tooltip');tip.hidden=true;controls.append(tip);help.setAttribute('aria-describedby',tip.id);help.setAttribute('aria-controls',tip.id);
 const showHelp=()=>{tip.replaceChildren();for(const row of [primary,actions,supporting]){if(!row.children.length)continue;const list=node('dl');for(const cell of row.children){const entry=helpEntries.get(cell),term=node('dt',entry.label),description=node('dd');if(entry.label!==entry.full)description.append(node('strong',entry.full));description.append(node('span',entry.description));list.append(term,description);}tip.append(list);}tip.hidden=false;const rect=help.getBoundingClientRect(),bounds=tip.getBoundingClientRect();tip.style.left=Math.max(18,Math.min(rect.left,innerWidth-bounds.width-18))+'px';tip.style.top=Math.max(18,Math.min(rect.bottom+6,innerHeight-bounds.height-18))+'px';},hideHelp=()=>{tip.hidden=true;help.setAttribute('aria-expanded','false');};

 help.addEventListener('pointerenter',showHelp);help.addEventListener('pointerleave',()=>{if(document.activeElement!==help)hideHelp();});help.addEventListener('focus',showHelp);help.addEventListener('blur',hideHelp);help.addEventListener('keydown',e=>{if(e.key==='Escape'){hideHelp();e.stopPropagation();}});
 function control(label,full,description,op,parent,disabled=false){const cell=node('div',undefined,'compact-control'),action=button(label,()=>{hideHelp();edit(op);},cell,disabled);action.setAttribute('aria-label',full);parent.append(cell);helpEntries.set(cell,{label,full,description});}
 const writable=state.caps.includes('write')&&!d.locked&&d.status!=='deprecated',decide=state.caps.includes('decide');
 if(writable)control('Edit','Edit','Change this record.','decision.edit',primary);
 else if(d.status==='closed'&&!d.locked&&decide)control('Edit','Edit','Change the recorded decision.','decision.edit-resolution',primary);
 if(writable){control('opt','Add option','Propose a solution.','option.add',supporting);control('ref','Add reference','Attach a source.','reference.add',supporting);control('rel','Add relationship','Link another decision.','link.add',supporting);}
 const closure=node('div',undefined,'closure-slot');question.append(closure);
 if(d.status==='open'&&writable){button('Close',()=>edit('decision.close'),closure,!decide).className='primary';control('Status','Status',d.work_tag==='deferred'?'Resume work before changing status.':'Change the work status.','decision.set-work',primary,d.work_tag==='deferred');control(d.work_tag==='deferred'?'res':'def',d.work_tag==='deferred'?'Resume':'Defer',d.work_tag==='deferred'?'Restart work on this question.':'Pause work until a stated condition is met.',d.work_tag==='deferred'?'decision.resume':'decision.defer',actions);control(d.contested?'resolve':'chal',d.contested?'Resolve challenge':'Challenge',d.contested?'Record how the disagreement was settled.':'Flag a disagreement.',d.contested?'decision.resolve-challenge':'decision.challenge',actions,!['deferred','under-investigation'].includes(d.work_tag));}
 if(d.status==='closed'){button('Reopen',()=>edit('decision.reopen'),closure,d.locked||!decide).className='primary';if(d.locked)closure.append(node('small','Amend the protected baseline to make changes.'));if(!d.locked&&decide)control('protect','Protect baseline','Require an amendment for future changes.','decision.lock',actions);}
 if(d.locked&&decide)control('amend','Amend baseline','Create a linked amendment.','decision.amend',actions);
 if(d.status!=='deprecated'&&decide)control('dep','Deprecate','End use of this decision; keep its history.','decision.deprecate',actions);
 for(const row of [primary,actions,supporting])if(!row.children.length)row.remove();
 for(const [family,label] of [['alternatives','Options'],['references','References'],['links','Relationships']]){
  box.append(node('h3',label,'section-title'));const children=await all(d.collections[family].url);if(generation!==detailGeneration)return;d[family]=children;
  if(!children.length)box.append(node('p','None recorded.','muted'));
  for(const child of children){for(const k of Object.keys(child))child[k]=await expand(child[k]);const card=node('article',undefined,'child-card');
   card.append(node('strong',child.title||child.label||(child.type+' · '+child.source_key+' → '+child.target_key)));
   for(const k of (family==='alternatives'?['description','benefit','cost','disposition','reason']:family==='references'?['locator','kind','availability','authenticity','limitations']:['reason','impact','baseline_disposition']))if(child[k])card.append(node('p',k+': '+child[k],'long-text'));
   if(writable&&family!=='links'&&!child.retired&&child.disposition!=='retired'){const type=family==='alternatives'?'option':'reference';const pair=node('div',undefined,'item-actions');card.append(pair);button('Edit',()=>edit(type+'.edit',child),pair,child.disposition==='selected');button('Retire',()=>edit(type+'.retire',child),pair,child.disposition==='selected');if(child.disposition==='selected')card.append(node('p','Use Edit on the decision to change the selected solution.','muted'));}
   if(writable&&family==='links'&&child.active&&child.source_key===d.key&&['relates_to','depends_on'].includes(child.type))button('Unlink',()=>edit('link.unlink',child),card);
   box.append(card);
  }
 }
 box.append(node('h3','Evidence state','section-title'),node('pre',JSON.stringify(d.evidence_state,null,2)));
 const historyBox=node('section');box.append(historyBox);let historyOpen=false,historyRequest=0;
 const historyButton=button('History',async()=>{
  historyOpen=!historyOpen;const request=++historyRequest;historyButton.setAttribute('aria-expanded',String(historyOpen));historyBox.replaceChildren();if(!historyOpen)return;
  historyBox.append(node('p','Loading history…'));try{const history=await all(base()+'/decisions/'+key+'/history');if(!historyOpen||request!==historyRequest||generation!==detailGeneration)return;historyBox.replaceChildren(node('h3','Recorded history','section-title'));
  for(const h of history){const row=node('section');row.append(node('p','Ledger '+h.ledger_revision+' · '+h.principal_id+' · '+h.reason));const content=node('div');let open=false,serial=0;
   const toggle=button('View snapshot',async()=>{open=!open;const ticket=++serial;toggle.setAttribute('aria-expanded',String(open));content.replaceChildren();if(!open)return;content.append(node('p','Loading snapshot…'));try{const snapshot=(await api(base()+'/decisions/'+key+'/as-of?revision='+h.ledger_revision)).data;if(open&&ticket===serial&&historyOpen&&request===historyRequest&&generation===detailGeneration)content.replaceChildren(node('pre',JSON.stringify(snapshot,null,2)));}catch(e){if(open&&ticket===serial&&content.isConnected)content.replaceChildren(node('p',e.message,'error'));}},row);toggle.setAttribute('aria-expanded','false');row.append(content);historyBox.append(row);}
  }catch(e){if(historyOpen&&request===historyRequest&&generation===detailGeneration)historyBox.replaceChildren(node('p',e.message,'error'));}
 },box);box.append(historyBox);historyButton.setAttribute('aria-expanded','false');
 const context=(await api(base()+'/decisions/'+key+'/context')).data;if(generation!==detailGeneration)return;state.contextFingerprint=context.context_fingerprint;
 $('decision-columns').classList.add('show-detail');
 box.dataset.loaded='true';syncFocus();live.start(state.project,key);
}
function edit(op,child=null){
 if(['decision.close','decision.edit-resolution'].includes(op)&&state.schemaVersion<2){message('This project needs a data-format upgrade before decisions can be recorded.',true);return;}
 const d=state.record||{},invoker=document.activeElement;
 state.edit={op,child,revision:state.revision,decisionRevision:d.revision,key:d.key,requestId:crypto.randomUUID(),pending:null,invoker};
 $('edit-title').textContent=titles[op];$('edit-project').textContent=state.project.name+(d.key&&op!=='decision.create'?' · '+d.key:'');
 const fields=$('edit-fields');fields.replaceChildren();$('form-error').hidden=true;$('conflict').hidden=true;
 if(d.status==='closed'&&['decision.edit','decision.edit-resolution'].includes(op)){
  const views=node('div',undefined,'form-views');fields.append(views);
  for(const [label,target] of [['Details','decision.edit'],['Decision','decision.edit-resolution']]){const b=button(label,()=>{if(state.edit.saving||state.edit.pending)return;if(dirty()){state.edit.afterDiscard=()=>edit(target);$('dirty-dialog').showModal();}else{closeEditor();edit(target);}},views,target==='decision.edit-resolution'?!state.caps.includes('decide'):!state.caps.includes('write'));b.setAttribute('aria-pressed',String(op===target));}
 }
 if(['decision.close','decision.edit-resolution'].includes(op))state.edit.resolution=installDecisionForm(fields,d,op==='decision.edit-resolution');
 else state.edit.action=installActionForm(fields,op,d,child,{decide:state.caps.includes('decide'),findDecisions:q=>all(base()+'/decisions?q='+encodeURIComponent(q))});
 $('save-edit').textContent=state.edit.action?.submit||'Save decision';state.edit.initial=new URLSearchParams(new FormData($('edit-form'))).toString();
 if(!$('editor').open)$('editor').showModal();fields.querySelector('input:not([disabled]),textarea,select')?.focus();
}
$('new-decision').onclick=()=>edit('decision.create');
$('edit-form').addEventListener('invalid',e=>{e.target.closest('details')?.setAttribute('open','');e.target.setAttribute('aria-invalid','true');},true);
$('edit-form').addEventListener('input',e=>e.target.removeAttribute('aria-invalid'));
function dirty(){return state.edit&&state.edit.initial!==new URLSearchParams(new FormData($('edit-form'))).toString();}
function closeEditor(){const invoker=state.edit?.invoker;state.edit=null;$('editor').close();if(invoker?.isConnected)invoker.focus();else{$('detail').tabIndex=-1;$('detail').focus();}}
function cancelEditor(){if(state.edit?.saving||state.edit?.pending){message('Resolve the pending save before closing this form.',true);return;}if(dirty())$('dirty-dialog').showModal();else closeEditor();}
$('cancel-edit').onclick=cancelEditor;$('editor').oncancel=e=>{e.preventDefault();cancelEditor();};
$('dirty-cancel').onclick=()=>{if(state.edit)state.edit.afterDiscard=null;$('dirty-dialog').close();};
$('dirty-discard').onclick=()=>{const next=state.edit?.afterDiscard;$('dirty-dialog').close();closeEditor();next?.();};
$('dirty-save').onclick=()=>{$('dirty-dialog').close();$('edit-form').requestSubmit();};
$('dirty-dialog').oncancel=()=>{if(state.edit)state.edit.afterDiscard=null;};
window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue='';}});
$('edit-form').onsubmit=async event=>{
 event.preventDefault();const editState=state.edit;if(!editState)return;const save=$('save-edit');save.disabled=true;editState.saving=true;$('form-error').hidden=true;
 try{
  const values=(editState.resolution||editState.action).read(),f=values.data,reason=values.reason,authority_refs=values.authority_refs;
  const revisions={};if(editState.op!=='decision.create')revisions[editState.key]=editState.decisionRevision;
  let other=f.target_key||f.replacement_key;if(editState.op==='link.unlink')other=editState.child.target_key;
  if(other){const target=await api(base()+'/decisions/'+encodeURIComponent(other));revisions[other]=target.data.revision;}
  const operation={op:editState.op,data:f};if(editState.op!=='decision.create')operation.key=editState.key;if(editState.child)operation.id=editState.child.id;
  const payload={expected_ledger_uuid:state.project.ledger_uuid,expected_revision:editState.revision,expected_decision_revisions:revisions,request_id:editState.requestId,reason,authority_refs,operations:[operation]};
  const result=await sendRetained(editState,payload,body=>api(base()+'/changes',body));const key=result.data[0]?.key,next=editState.afterDiscard;closeEditor();message(editState.resolution?(editState.op==='decision.close'?'Decision saved. This question is closed. Implementation status has not changed.':'Decision updated. Implementation status has not changed.'):'Saved at ledger revision '+result.revision);try{await listing();if(key)await detail(key);next?.();}catch(e){message('Saved successfully. Refresh the view to see current data.');}
 }catch(e){
  if(definitive(e)){editState.pending=null;editState.requestId=crypto.randomUUID();}const error=$('form-error');error.textContent=e.message;(editState.resolution||editState.action)?.showError(e,error);error.hidden=false;error.tabIndex=-1;error.focus();
  if(['REVISION_CONFLICT','STALE_REVISION','REQUEST_ID_REUSED','PROPOSAL_CHANGED'].includes(e.code)||e.code?.includes('STALE')){
   const c=$('conflict');c.hidden=false;c.replaceChildren(node('p','Your draft is preserved. Review the current record before rebasing this draft.'));
   button('Load current state alongside draft',async()=>{const r=await api(base()+(editState.op==='decision.create'?'/decisions':'/decisions/'+editState.key));c.querySelector('.current-comparison')?.remove();const comparison=node('pre',JSON.stringify(r.data,null,2),'current-comparison');c.append(comparison);button('Use these revisions; keep draft for review',()=>{editState.revision=r.revision;editState.decisionRevision=editState.op==='decision.create'?undefined:r.data.revision;editState.requestId=crypto.randomUUID();editState.pending=null;message('Draft retained. Review differences, then save explicitly.');},c);},c);
   if(e.code==='PROPOSAL_CHANGED')button('Keep my text as a written answer',()=>{editState.resolution.asWritten();message('Proposal selection cleared. Review current revisions before saving your written answer.');},c);
  }else if(editState.pending&&(!e.code||e.code==='INTERNAL_ERROR')){
   const c=$('conflict');c.hidden=false;c.replaceChildren(node('p','The save outcome is unknown. Your original request is retained. Retry it before changing the draft.'));
   button('Retry original save',async()=>{const result=await api(base()+'/changes',JSON.parse(editState.pending));const key=result.data[0]?.key;closeEditor();message('Saved successfully.');try{await listing();if(key)await detail(key);}catch{message('Saved successfully. Refresh the view to see current data.');}},c);
  }else editState.pending=null;
 }finally{save.disabled=false;editState.saving=false;}
};
async function admin(){
 const box=$('project-admin'),access=$('project-access-actions');box.replaceChildren();access.replaceChildren();
 $('project-management').hidden=!state.caps.includes('registry');
 for(const p of state.projects){
  box.append(node('p',p.name+' · '+(p.enabled?'enabled':'disabled')));
  if(state.caps.includes('registry')){
   const section=node('section',undefined,'project-access-card');section.append(node('h3',p.name),node('p',p.enabled?'Available for project work.':'Project access is disabled.','muted'));
   const actions=node('div',undefined,'toolbar');section.append(actions);
   button(p.enabled?'Disable project':'Enable project',async()=>{const previous=state.project;state.project=p;try{await api(base()+'/state',{enabled:!p.enabled,expected_catalog_revision:state.catalogRevision,request_id:crypto.randomUUID()});}finally{state.project=previous;}await projects();await admin();},actions);
   access.append(section);
  }
 }
 const maintenance=$('maintenance');maintenance.replaceChildren();if(state.project){maintenance.append(node('h2','Data · '+state.project.name));for(const [label,route] of [['Export native JSON','exports'],['Create backup','backups'],['Verify ledger','verify']])button(label,async()=>{const r=await api(base()+'/'+route,{});maintenance.append(node('pre',JSON.stringify(r.data,null,2)));await artifacts(maintenance);},maintenance,!state.caps.includes(route==='exports'?'read':'maintain'));await artifacts(maintenance);}
}
async function artifacts(parent){const rows=await all(base()+'/artifacts');for(const a of rows.filter(x=>x.state==='complete')){const row=node('p',a.kind+' · revision '+a.revision);button('Download',async()=>{const r=await fetch(base()+'/artifacts/'+a.artifact_id+'/content',{headers:{'X-Ledger-UUID':state.project.ledger_uuid}});if(!r.ok)throw new Error('Artifact download failed.');const url=URL.createObjectURL(await r.blob());const anchor=node('a');anchor.href=url;anchor.download=a.artifact_id+(a.kind==='backup'?'.sqlite':'.json');anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},row);if(a.kind==='backup'&&state.caps.includes('maintain'))button('Restore check',async()=>{const r=await api(base()+'/restore-check',{artifact_id:a.artifact_id});parent.append(node('pre',JSON.stringify(r.data,null,2)));},row);parent.append(row);}}
$('projects-button').onclick=()=>{if(!state.csrf)return;show('projects-view');admin().catch(failure);};
$('back-workspace').onclick=()=>{if(state.project)show('workspace');};
for(const [id,kind] of [['create-project','create'],['register-project','register']])$(id).onsubmit=async e=>{e.preventDefault();try{const fields=Object.fromEntries(new FormData(e.target));const r=await api('/api/v1/projects',{...fields,kind,expected_catalog_revision:state.catalogRevision,request_id:crypto.randomUUID()});await projects();await selectProject(r.data.project_id);$('project').value=r.data.project_id;e.target.reset();}catch(err){failure(err);}};
new ResizeObserver(entries=>{document.documentElement.style.setProperty('--header-height',entries[0].target.offsetHeight+'px');}).observe(document.querySelector('.topbar'));
api('/api/v1/session').then(r=>signedIn(r.data)).catch(()=>show('login-view'));

// Store only a layout preference; credentials and record drafts stay in memory.
const divider=$('panel-divider'),sidebar=document.querySelector('.local-sidebar');
let contextShare=50;
try{const saved=Number(localStorage.getItem('dt.contextShare'));if(saved>=10&&saved<=90)contextShare=saved;}catch{}
function resizePanel(value,persist=false){
 const height=sidebar.getBoundingClientRect().height;if(height<262)return;
 const low=100/height*100,high=(height-162)/height*100;
 contextShare=Math.min(high,Math.max(low,value));sidebar.style.setProperty('--context-share',contextShare+'%');
 divider.setAttribute('aria-valuenow',String(Math.round(contextShare)));divider.setAttribute('aria-valuemin',String(Math.ceil(low)));divider.setAttribute('aria-valuemax',String(Math.floor(high)));
 divider.setAttribute('aria-valuetext',Math.round(contextShare)+' percent controls; remaining space for results');
 if(persist)try{localStorage.setItem('dt.contextShare',String(contextShare));}catch{}
}
divider.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();divider.focus();divider.setPointerCapture(event.pointerId);divider.classList.add('dragging');});
divider.addEventListener('pointermove',event=>{if(!divider.hasPointerCapture(event.pointerId))return;const rect=sidebar.getBoundingClientRect();resizePanel((event.clientY-rect.top)/rect.height*100);});
for(const type of ['pointerup','pointercancel'])divider.addEventListener(type,event=>{if(divider.hasPointerCapture(event.pointerId))divider.releasePointerCapture(event.pointerId);divider.classList.remove('dragging');resizePanel(contextShare,true);});
divider.addEventListener('keydown',event=>{const step=event.shiftKey?10:3;const values={ArrowUp:contextShare-step,ArrowDown:contextShare+step,Home:0,End:100};if(event.key in values){event.preventDefault();resizePanel(values[event.key],true);}});
new ResizeObserver(()=>resizePanel(contextShare)).observe(sidebar);

const workspaceDivider=$('workspace-divider'),shell=document.querySelector('.local-shell');
let sidebarWidth=280;
try{const saved=Number(localStorage.getItem('dt.sidebarWidth'));if(saved>=240&&saved<=640)sidebarWidth=saved;}catch{}
function resizeWorkspace(value,persist=false){
 const width=shell.getBoundingClientRect().width;if(width<=980)return;
 const maximum=Math.min(640,width-570),minimum=240;
 sidebarWidth=Math.min(maximum,Math.max(minimum,value));shell.style.setProperty('--sidebar-width',sidebarWidth+'px');
 workspaceDivider.setAttribute('aria-valuenow',String(Math.round(sidebarWidth)));workspaceDivider.setAttribute('aria-valuemax',String(Math.floor(maximum)));
 workspaceDivider.setAttribute('aria-valuetext',Math.round(sidebarWidth)+' pixel side panel');
 if(persist)try{localStorage.setItem('dt.sidebarWidth',String(sidebarWidth));}catch{}
}
workspaceDivider.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();workspaceDivider.focus();workspaceDivider.setPointerCapture(event.pointerId);workspaceDivider.classList.add('dragging');});
workspaceDivider.addEventListener('pointermove',event=>{if(!workspaceDivider.hasPointerCapture(event.pointerId))return;resizeWorkspace(shell.getBoundingClientRect().right-event.clientX-5);});
for(const type of ['pointerup','pointercancel'])workspaceDivider.addEventListener(type,event=>{if(workspaceDivider.hasPointerCapture(event.pointerId))workspaceDivider.releasePointerCapture(event.pointerId);workspaceDivider.classList.remove('dragging');resizeWorkspace(sidebarWidth,true);});
workspaceDivider.addEventListener('keydown',event=>{const step=event.shiftKey?50:15;const values={ArrowLeft:sidebarWidth+step,ArrowRight:sidebarWidth-step,Home:240,End:640};if(event.key in values){event.preventDefault();resizeWorkspace(values[event.key],true);}});
new ResizeObserver(()=>resizeWorkspace(sidebarWidth)).observe(shell);

const live=new LiveMonitor(()=>({key:state.record?.key||null,decisionRevision:state.record?.revision,listRevision:state.listRevision,contextFingerprint:state.contextFingerprint}), (color,label)=>{
 const control=$('freshness'),text=color==='green'?'':color==='yellow'?'Updates available':color==='red'?'Out of sync':label||'Disconnected';
 const accessible=color==='green'?'Connected and current':text;
 control.className='freshness '+color;control.title=accessible;control.setAttribute('aria-label',accessible);$('freshness-label').textContent=text;
 if($('freshness-announcement').textContent!==accessible)$('freshness-announcement').textContent=accessible;
});
function syncFocus(){
 const compact=matchMedia('(max-width:980px)').matches,visible=compact||!shell.classList.contains('focus-view');
 $('focus-toggle').setAttribute('aria-pressed',String(!visible));$('focus-toggle').title=visible?'Focus decision':'Show controls and results';$('focus-toggle').setAttribute('aria-label',$('focus-toggle').title);
}
$('focus-toggle').onclick=()=>{if(!matchMedia('(max-width:980px)').matches)shell.classList.toggle('focus-view');syncFocus();};
new MutationObserver(syncFocus).observe(shell,{attributes:true,attributeFilter:['class']});matchMedia('(max-width:980px)').addEventListener('change',syncFocus);syncFocus();
window.addEventListener('pagehide',()=>live.stop());
$('close-live-review').onclick=()=>$('live-review').close();
$('freshness').onclick=async()=>{
 const content=$('live-review-content');content.replaceChildren();$('live-review').showModal();
 content.append(node('p',$('freshness').getAttribute('aria-label')));
 if(!live.connected&&live.label==='Service stopped'){const launch=node('a','Start service');launch.href='decision-tracker://open';content.append(launch);return;}
 if(!live.connected){button('Sign in again',()=>{if(content.querySelector('form'))return;const form=node('form'),label=node('label','Password'),input=node('input');input.type='password';input.autocomplete='current-password';input.required=true;input.maxLength=128;label.append(input);form.append(label);const submit=node('button','Sign in');submit.type='submit';form.append(submit);content.append(form);form.onsubmit=async event=>{event.preventDefault();const token=input.value;input.value='';try{const result=await account.authenticate(token);state.csrf=result.csrf_token;state.caps=result.capabilities;live.start(state.project,state.record?.key||null);$('live-review').close();}catch(error){content.append(node('p',error.message));}};},content);button('Retry connection',()=>{live.start(state.project,state.record?.key||null);$('live-review').close();},content);return;}
 button('Refresh results',async()=>{const scroll=$('results').scrollTop;await listing();$('results').scrollTop=scroll;live.update();$('live-review').close();},content);
 if(!state.record)return;
 button('Review changes',async()=>{
  const current=await api(base()+'/decisions/'+state.record.key);for(const field of Object.keys(current.data))current.data[field]=await expand(current.data[field]);
  for(const family of ['alternatives','references','links']){current.data[family]=await all(current.data.collections[family].url);for(const child of current.data[family])for(const k of Object.keys(child))child[k]=await expand(child[k]);}
  const differences=Object.keys(current.data).filter(k=>!['collections','updated_at'].includes(k)&&JSON.stringify(current.data[k])!==JSON.stringify(state.record[k]));
  content.append(node('p',differences.length?'Changed fields: '+differences.join(', '):'The selected record is unchanged; the project has advanced.'));
  content.querySelector('.revision-comparison')?.remove();const comparison=node('div',undefined,'revision-comparison');
  const format=value=>typeof value==='object'?JSON.stringify(value,null,2):String(value??'Not recorded');
  for(const field of differences){const row=node('section');row.append(node('h3',field));const cells=node('div',undefined,'comparison-cells');for(const [label,value] of [['Displayed',state.record[field]],['Current saved',current.data[field]]]){const cell=node('div');cell.append(node('strong',label),node('pre',format(value)));cells.append(cell);}if(state.edit){const draft=$('edit-fields').querySelector('[name="'+field+'"]');if(draft){const cell=node('div');cell.append(node('strong','Your draft'),node('pre',draft.value));cells.append(cell);}}row.append(cells);comparison.append(row);}content.append(comparison);
  if(state.edit){button('Rebase draft for review',()=>{state.edit.revision=current.revision;state.edit.decisionRevision=current.data.revision;state.edit.requestId=crypto.randomUUID();state.edit.pending=null;message('Draft retained. Review before saving.');$('live-review').close();},content);}
  else button('Use latest',async()=>{const scroll=$('main-content').scrollTop;await detail(state.record.key);$('main-content').scrollTop=scroll;$('live-review').close();},content);
 },content);
};

button('Review workspace updates',()=>$('freshness').click(),$('edit-form'));

const account=installAccount({$,state,api,signedIn,show,message,dirty,live});
