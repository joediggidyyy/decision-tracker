import {LiveMonitor} from './live.js';
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
 const r=await fetch(path,{method,headers,credentials:'same-origin',body:body===undefined?undefined:JSON.stringify(body)});
 const value=await r.json();if(binding&&(!state.project||state.project.project_id!==binding.id||state.project.ledger_uuid!==binding.uuid))throw new Error('Project changed. Discarding the previous response.');if(!r.ok){const e=new Error(value.error?.message||'Request failed');e.code=value.error?.code;e.details=value.error?.details;throw e;}return value;
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
async function selectProject(id){live.stop();state.listRevision=null;state.contextFingerprint=null;listGeneration++;detailGeneration++;$('results').replaceChildren();$('result-count').textContent='';$('load-more').hidden=true;$('notice').textContent='';$('error').hidden=true;state.project=state.projects.find(p=>p.project_id===id)||null;state.record=null;$('detail').replaceChildren(node('p','Choose a decision.'));if(!state.project){show('projects-view');return;}show('workspace');rememberView();$('project').value=state.project.project_id;$('workspace-title').textContent=state.project.name;$('new-decision').disabled=!state.caps.includes('write');await listing();live.start(state.project,null);}
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
 $('result-count').textContent=$('results').querySelectorAll('button').length+(state.cursor?' +':'');$('load-more').hidden=!state.cursor;live.update();if(!state.record)$('context').replaceChildren(node('h2',state.project.name),node('p','Ledger revision '+state.revision),node('p','Choose a decision to see its context.'));
}
$('filters').onsubmit=e=>{e.preventDefault();listing().catch(failure);};
$('load-more').onclick=()=>listing(true).catch(failure);
$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>listing().catch(failure),250);});
async function expand(value){if(!value||typeof value!=='object'||!value.chunks_url)return value;let result='',offset=0;do{const r=await api(value.chunks_url+'&offset='+offset);result+=r.data.text;offset=r.data.next_offset;}while(offset!==null);return result;}
async function all(url){const values=[];let cursor=null;do{const r=await api(url+(cursor?(url.includes('?')?'&':'?')+'cursor='+encodeURIComponent(cursor):''));values.push(...r.data);cursor=r.next_cursor;}while(cursor);return values;}
async function detail(key){
 const generation=++detailGeneration;
 const r=await api(base()+'/decisions/'+key);state.revision=r.revision;const d=r.data;
 for(const k of Object.keys(d))d[k]=await expand(d[k]);
 if(generation!==detailGeneration)return;rememberView(key);state.record=d;for(const b of $('results').querySelectorAll('button'))b.setAttribute('aria-current',b.dataset.key===key?'true':'false');
 const box=$('detail');box.replaceChildren();
 box.append(node('p',d.key+' · revision '+d.revision,'eyebrow'),node('h2',d.title),node('p',d.status+(d.locked?' · protected baseline '+d.baseline:''),'badge'));
 for(const [label,k] of [['Question','question'],['Answer','answer'],['Rationale','rationale']]){box.append(node('h3',label),node('p',d[k]||'Not recorded.','long-text'));}
 const actions=node('div',undefined,'toolbar');box.append(actions);
 const writable=state.caps.includes('write')&&!d.locked&&d.status!=='deprecated',decide=state.caps.includes('decide');
 if(writable){button('Edit',()=>edit('decision.edit'),actions);button('Add option',()=>edit('option.add'),actions);button('Add reference',()=>edit('reference.add'),actions);button('Add relationship',()=>edit('link.add'),actions);}
 if(d.status==='open'&&writable){button('Close decision',()=>edit('decision.close'),actions,!decide);button(d.work_tag==='deferred'?'Resume':'Defer',()=>edit(d.work_tag==='deferred'?'decision.resume':'decision.defer'),actions);button('Set work',()=>edit('decision.set-work'),actions);if(['deferred','under-investigation'].includes(d.work_tag))button(d.contested?'Resolve challenge':'Challenge',()=>edit(d.contested?'decision.resolve-challenge':'decision.challenge'),actions);}
 if(d.status==='closed'&&!d.locked&&decide){for(const [label,op] of [['Edit resolution','edit-resolution'],['Reopen','reopen'],['Protect baseline','lock']])button(label,()=>edit('decision.'+op),actions);}
 if(d.locked&&decide)button('Amend baseline',()=>edit('decision.amend'),actions);
 if(d.status!=='deprecated'&&decide)button('Deprecate',()=>edit('decision.deprecate'),actions);
 for(const [family,label] of [['alternatives','Options'],['references','References'],['links','Relationships']]){
  box.append(node('h3',label));const children=await all(d.collections[family].url);if(generation!==detailGeneration)return;d[family]=children;
  if(!children.length)box.append(node('p','None recorded.','muted'));
  for(const child of children){for(const k of Object.keys(child))child[k]=await expand(child[k]);const card=node('article',undefined,'child-card');
   card.append(node('strong',child.title||child.label||(child.type+' · '+child.source_key+' → '+child.target_key)));
   for(const k of (family==='alternatives'?['description','benefit','cost','disposition','reason']:family==='references'?['locator','kind','availability','authenticity','limitations']:['reason','impact','baseline_disposition']))if(child[k])card.append(node('p',k+': '+child[k],'long-text'));
   if(writable&&family!=='links'&&!child.retired&&child.disposition!=='retired'){const type=family==='alternatives'?'option':'reference';button('Edit '+(type==='option'?'option':'reference'),()=>edit(type+'.edit',child),card);button('Retire',()=>edit(type+'.retire',child),card);}
   if(writable&&family==='links'&&child.active&&child.source_key===d.key&&['relates_to','depends_on'].includes(child.type))button('Unlink',()=>edit('link.unlink',child),card);
   box.append(card);
  }
 }
 box.append(node('h3','Evidence state'),node('pre',JSON.stringify(d.evidence_state,null,2)));
 button('History',async()=>{const history=await all(base()+'/decisions/'+key+'/history');const section=node('section');section.append(node('h3','Recorded history'));for(const h of history){const row=node('p','Ledger '+h.ledger_revision+' · '+h.principal_id+' · '+h.reason);button('View snapshot',async()=>{const snapshot=(await api(base()+'/decisions/'+key+'/as-of?revision='+h.ledger_revision)).data;const pre=node('pre',JSON.stringify(snapshot,null,2));row.append(pre);},row);section.append(row);}box.append(section);},box);
 const context=(await api(base()+'/decisions/'+key+'/context')).data;
 if(generation!==detailGeneration)return;state.contextFingerprint=context.context_fingerprint;
 $('context').replaceChildren(node('h2',d.key),node('p',state.project.name),node('p','Ledger revision '+state.revision),node('p','Owner: '+(d.owner_role||'Unassigned')),node('p',d.contested?'Challenge recorded':'No active challenge'));
 for(const neighbor of context.neighbors)button(neighbor.key+' · '+neighbor.title,()=>detail(neighbor.key),$('context'));
 $('decision-columns').classList.add('show-detail');if(window.matchMedia('(max-width:980px)').matches){document.querySelector('.local-shell').classList.remove('panel-open');$('panel-toggle').setAttribute('aria-expanded','false');}
 syncFocus();live.start(state.project,key);
}
function field(name,label,value='',options=null,required=false){const wrap=node('label',label);let input;if(options){input=node('select');for(const value of options)input.add(new Option(value,value));}else input=node(['title','owner_role','baseline','target_key','replacement_key','label','locator','version','sha256'].includes(name)?'input':'textarea');input.name=name;input.value=value??'';input.required=required;if(name==='title')input.maxLength=160;wrap.append(input);$('edit-fields').append(wrap);return input;}
function edit(op,child=null){
 const d=state.record||{};state.edit={op,child,revision:state.revision,decisionRevision:d.revision,key:d.key,requestId:crypto.randomUUID(),pending:null};
 $('edit-title').textContent=op.replaceAll('.',' · ').replaceAll('-',' ');$('edit-project').textContent=state.project.name+(d.key&&op!=='decision.create'?' · '+d.key:'');
 $('edit-fields').replaceChildren();$('form-error').hidden=true;$('conflict').hidden=true;
 const common=()=>{field('reason','Reason for this change','',null,true);field('authority_refs','Authority references (one per line)');};
 if(['decision.create','decision.edit'].includes(op)){field('title','Title',op.endsWith('create')?'':d.title,null,true);field('question','Question',op.endsWith('create')?'':d.question,null,true);field('owner_role','Owner role',op.endsWith('create')?'':d.owner_role);if(op.endsWith('create')||d.status==='open'){field('answer','Answer',op.endsWith('create')?'':d.answer);field('rationale','Rationale',op.endsWith('create')?'':d.rationale);}if(op.endsWith('edit'))field('evidence_state','Evidence state (JSON; implementation, verification, acceptance)',JSON.stringify(d.evidence_state,null,2));}
 if(['decision.close','decision.edit-resolution'].includes(op)){field('answer','Answer',d.answer,null,true);field('rationale','Rationale',d.rationale,null,true);}
 if(['decision.close','decision.edit-resolution'].includes(op)){
 const selected=field('selected_option','Selected option (optional)','',[],false);
 selected.add(new Option('No selected option',''));
 for(const option of (d.alternatives||[]).filter(x=>x.disposition!=='retired'))selected.add(new Option(option.title,option.id));
 selected.value=(d.alternatives||[]).find(x=>x.disposition==='selected')?.id||'';
}
 if(op==='decision.reopen'||op==='decision.amend')field('impact','Impact statement','',null,true);
 if(op==='decision.amend'){field('title','Amendment title',d.title+' amendment',null,true);field('question','Amendment question','',null,true);field('baseline_disposition','Baseline disposition','continue',['continue','pause']);}
 if(op==='decision.lock')field('baseline','Baseline identifier','',null,true);
 if(op==='decision.defer')field('resume_trigger','Resumption trigger','',null,true);
 if(op==='decision.set-work')field('work_tag','Work state','under-investigation',['queued','under-investigation']);
 if(op==='decision.deprecate'){field('kind','Deprecation type','obsolete',['obsolete','withdrawn','duplicate','error','superseded']);field('replacement_key','Replacement decision key (when applicable)');}
 if(op.startsWith('option.')&&!op.endsWith('retire')){for(const k of ['title','description','benefit','cost'])field(k,k,child?.[k]||'',null,k==='title');field('disposition','Disposition',child?.disposition||'unselected',['unselected','rejected']);field('option_reason','Option disposition reason',child?.reason||'');}
 if(op.startsWith('reference.')&&!op.endsWith('retire')){for(const k of ['label','locator','kind','version','sha256','availability','authenticity','limitations'])field(k,k,child?.[k]||({kind:'evidence',availability:'unknown',authenticity:'unknown'}[k]||''),({kind:['evidence','authority','external-decision'],availability:['known','unavailable','unknown'],authenticity:['verified','unverified','unknown']}[k]||null),['label','locator','kind'].includes(k));}
 if(op==='link.add'){field('target_key','Target decision key','',null,true);field('type','Relationship','relates_to',['relates_to','depends_on']);}
 common();state.edit.initial=new URLSearchParams(new FormData($('edit-form'))).toString();$('editor').showModal();
}
$('new-decision').onclick=()=>edit('decision.create');
function dirty(){return state.edit&&state.edit.initial!==new URLSearchParams(new FormData($('edit-form'))).toString();}
function closeEditor(){state.edit=null;$('editor').close();}
function cancelEditor(){if(dirty())$('dirty-dialog').showModal();else closeEditor();}
$('cancel-edit').onclick=cancelEditor;$('editor').oncancel=e=>{e.preventDefault();cancelEditor();};
$('dirty-cancel').onclick=()=>$('dirty-dialog').close();
$('dirty-discard').onclick=()=>{$('dirty-dialog').close();closeEditor();};
$('dirty-save').onclick=()=>{$('dirty-dialog').close();$('edit-form').requestSubmit();};
window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue='';}});
$('edit-form').onsubmit=async event=>{
 event.preventDefault();const editState=state.edit;if(!editState)return;const save=$('save-edit');save.disabled=true;$('form-error').hidden=true;
 try{
  const f=Object.fromEntries(new FormData(event.target)),reason=f.reason,authority_refs=f.authority_refs.split('\n').map(x=>x.trim()).filter(Boolean);delete f.reason;delete f.authority_refs;
  if(f.evidence_state)f.evidence_state=JSON.parse(f.evidence_state);
  if('option_reason' in f){f.reason=f.option_reason;delete f.option_reason;}
  if(editState.op==='decision.edit-resolution'&&f.selected_option==='')f.selected_option=null;
  for(const k of Object.keys(f))if(f[k]===''&& !['title','question','answer','rationale'].includes(k))delete f[k];
  const revisions={};if(editState.op!=='decision.create')revisions[editState.key]=editState.decisionRevision;
  let other=f.target_key||f.replacement_key;if(editState.op==='link.unlink')other=editState.child.target_key;
  if(other){const target=await api(base()+'/decisions/'+encodeURIComponent(other));revisions[other]=target.data.revision;}
  const operation={op:editState.op,data:f};if(editState.op!=='decision.create')operation.key=editState.key;if(editState.child)operation.id=editState.child.id;
  const payload={expected_ledger_uuid:state.project.ledger_uuid,expected_revision:editState.revision,expected_decision_revisions:revisions,request_id:editState.requestId,reason,authority_refs,operations:[operation]};
  const fingerprint=JSON.stringify(payload);if(editState.pending&&editState.pending!==fingerprint)throw new Error('A prior request may have committed. Reload current state before changing the retained request.');
  editState.pending=fingerprint;
  const result=await api(base()+'/changes',payload);const key=result.data[0]?.key;closeEditor();message('Saved at ledger revision '+result.revision);await listing();if(key)await detail(key);
 }catch(e){
  $('form-error').textContent=e.message+(e.details?' '+JSON.stringify(e.details):'');$('form-error').hidden=false;
  if(['REVISION_CONFLICT','STALE_REVISION','REQUEST_ID_REUSED'].includes(e.code)||e.code?.includes('STALE')){
   const c=$('conflict');c.hidden=false;c.replaceChildren(node('p','Your draft is preserved. Review the current record before rebasing this draft.'));
   button('Load current state alongside draft',async()=>{const r=await api(base()+(editState.op==='decision.create'?'/decisions':'/decisions/'+editState.key));c.append(node('pre',JSON.stringify(r.data,null,2)));button('Use these revisions; keep draft for review',()=>{editState.revision=r.revision;editState.decisionRevision=editState.op==='decision.create'?undefined:r.data.revision;editState.requestId=crypto.randomUUID();editState.pending=null;message('Draft retained. Review differences, then save explicitly.');},c);},c);
  }else if(e.code)editState.pending=null;
 }finally{save.disabled=false;}
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
 divider.setAttribute('aria-valuetext',Math.round(contextShare)+' percent context; remaining space for results');
 if(persist)try{localStorage.setItem('dt.contextShare',String(contextShare));}catch{}
}
divider.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();divider.focus();divider.setPointerCapture(event.pointerId);divider.classList.add('dragging');});
divider.addEventListener('pointermove',event=>{if(!divider.hasPointerCapture(event.pointerId))return;const rect=sidebar.getBoundingClientRect();resizePanel((event.clientY-rect.top)/rect.height*100);});
for(const type of ['pointerup','pointercancel'])divider.addEventListener(type,event=>{if(divider.hasPointerCapture(event.pointerId))divider.releasePointerCapture(event.pointerId);divider.classList.remove('dragging');resizePanel(contextShare,true);});
divider.addEventListener('keydown',event=>{const step=event.shiftKey?10:3;const values={ArrowUp:contextShare-step,ArrowDown:contextShare+step,Home:0,End:100};if(event.key in values){event.preventDefault();resizePanel(values[event.key],true);}});
new ResizeObserver(()=>resizePanel(contextShare)).observe(sidebar);

const workspaceDivider=$('workspace-divider'),shell=document.querySelector('.local-shell');
let sidebarWidth=280;
try{const saved=Number(localStorage.getItem('dt.sidebarWidth'));if(saved>=230&&saved<=640)sidebarWidth=saved;}catch{}
function resizeWorkspace(value,persist=false){
 const width=shell.getBoundingClientRect().width;if(width<=980)return;
 const maximum=Math.min(640,width-570),minimum=230;
 sidebarWidth=Math.min(maximum,Math.max(minimum,value));shell.style.setProperty('--sidebar-width',sidebarWidth+'px');
 workspaceDivider.setAttribute('aria-valuenow',String(Math.round(sidebarWidth)));workspaceDivider.setAttribute('aria-valuemax',String(Math.floor(maximum)));
 workspaceDivider.setAttribute('aria-valuetext',Math.round(sidebarWidth)+' pixel side panel');
 if(persist)try{localStorage.setItem('dt.sidebarWidth',String(sidebarWidth));}catch{}
}
workspaceDivider.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.preventDefault();workspaceDivider.focus();workspaceDivider.setPointerCapture(event.pointerId);workspaceDivider.classList.add('dragging');});
workspaceDivider.addEventListener('pointermove',event=>{if(!workspaceDivider.hasPointerCapture(event.pointerId))return;resizeWorkspace(shell.getBoundingClientRect().right-event.clientX-5);});
for(const type of ['pointerup','pointercancel'])workspaceDivider.addEventListener(type,event=>{if(workspaceDivider.hasPointerCapture(event.pointerId))workspaceDivider.releasePointerCapture(event.pointerId);workspaceDivider.classList.remove('dragging');resizeWorkspace(sidebarWidth,true);});
workspaceDivider.addEventListener('keydown',event=>{const step=event.shiftKey?50:15;const values={ArrowLeft:sidebarWidth+step,ArrowRight:sidebarWidth-step,Home:230,End:640};if(event.key in values){event.preventDefault();resizeWorkspace(values[event.key],true);}});
new ResizeObserver(()=>resizeWorkspace(sidebarWidth)).observe(shell);

const panelToggle=$('panel-toggle');
panelToggle.addEventListener('click',()=>{const open=shell.classList.toggle('panel-open');panelToggle.setAttribute('aria-expanded',String(open));if(open)$('decision-sidebar').focus();});

const live=new LiveMonitor(()=>({key:state.record?.key||null,decisionRevision:state.record?.revision,listRevision:state.listRevision,contextFingerprint:state.contextFingerprint}), (color,label)=>{
 const control=$('freshness'),text=color==='green'?'':color==='yellow'?'Updates available':color==='red'?'Out of sync':label||'Disconnected';
 const accessible=color==='green'?'Connected and current':text;
 control.className='freshness '+color;control.title=accessible;control.setAttribute('aria-label',accessible);$('freshness-label').textContent=text;
 if($('freshness-announcement').textContent!==accessible)$('freshness-announcement').textContent=accessible;
});
function syncFocus(){
 const compact=matchMedia('(max-width:980px)').matches,visible=compact?shell.classList.contains('panel-open'):!shell.classList.contains('focus-view');
 $('focus-toggle').setAttribute('aria-pressed',String(!visible));$('focus-toggle').title=visible?'Focus decision':'Show context and results';$('focus-toggle').setAttribute('aria-label',$('focus-toggle').title);
 $('panel-toggle').setAttribute('aria-expanded',String(visible));
}
$('focus-toggle').onclick=()=>{if(matchMedia('(max-width:980px)').matches)shell.classList.toggle('panel-open');else shell.classList.toggle('focus-view');syncFocus();};
$('panel-toggle').addEventListener('click',syncFocus);new MutationObserver(syncFocus).observe(shell,{attributes:true,attributeFilter:['class']});matchMedia('(max-width:980px)').addEventListener('change',syncFocus);syncFocus();
window.addEventListener('pagehide',()=>live.stop());
$('close-live-review').onclick=()=>$('live-review').close();
$('freshness').onclick=async()=>{
 const content=$('live-review-content');content.replaceChildren();$('live-review').showModal();
 content.append(node('p',$('freshness').getAttribute('aria-label')));
 if(!live.connected){button('Sign in again',()=>{const form=node('form'),label=node('label','Credential'),input=node('input');input.type='password';input.autocomplete='off';input.required=true;input.maxLength=4096;label.append(input);form.append(label);const submit=node('button','Sign in');submit.type='submit';form.append(submit);content.append(form);form.onsubmit=async event=>{event.preventDefault();const token=input.value;input.value='';try{const result=(await api('/api/v1/session',{token})).data;state.csrf=result.csrf_token;state.caps=result.capabilities;live.start(state.project,state.record?.key||null);$('live-review').close();}catch(error){content.append(node('p',error.message));}};},content);button('Retry connection',()=>{live.start(state.project,state.record?.key||null);$('live-review').close();},content);return;}
 button('Refresh results',async()=>{const scroll=$('results').scrollTop;await listing();$('results').scrollTop=scroll;live.update();$('live-review').close();},content);
 if(!state.record)return;
 button('Refresh context',async()=>{const r=await api(base()+'/decisions/'+state.record.key+'/context');state.contextFingerprint=r.data.context_fingerprint;$('context').replaceChildren(node('h2',state.record.key),node('p',state.project.name));for(const neighbor of r.data.neighbors)button(neighbor.key+' · '+neighbor.title,()=>detail(neighbor.key),$('context'));live.update();$('live-review').close();},content);
 button('Review changes',async()=>{
  const current=await api(base()+'/decisions/'+state.record.key);for(const field of Object.keys(current.data))current.data[field]=await expand(current.data[field]);
  for(const family of ['alternatives','references','links']){current.data[family]=await all(current.data.collections[family].url);for(const child of current.data[family])for(const k of Object.keys(child))child[k]=await expand(child[k]);}
  const differences=Object.keys(current.data).filter(k=>!['collections','updated_at'].includes(k)&&JSON.stringify(current.data[k])!==JSON.stringify(state.record[k]));
  content.append(node('p',differences.length?'Changed fields: '+differences.join(', '):'The selected record is unchanged; the project has advanced.'));
  const comparison=node('div',undefined,'revision-comparison');
  const format=value=>typeof value==='object'?JSON.stringify(value,null,2):String(value??'Not recorded');
  for(const field of differences){const row=node('section');row.append(node('h3',field));const cells=node('div',undefined,'comparison-cells');for(const [label,value] of [['Displayed',state.record[field]],['Current saved',current.data[field]]]){const cell=node('div');cell.append(node('strong',label),node('pre',format(value)));cells.append(cell);}if(state.edit){const draft=$('edit-fields').querySelector('[name="'+field+'"]');if(draft){const cell=node('div');cell.append(node('strong','Your draft'),node('pre',draft.value));cells.append(cell);}}row.append(cells);comparison.append(row);}content.append(comparison);
  if(state.edit){button('Rebase draft for review',()=>{state.edit.revision=current.revision;state.edit.decisionRevision=current.data.revision;state.edit.requestId=crypto.randomUUID();state.edit.pending=null;message('Draft retained. Review before saving.');$('live-review').close();},content);}
  else button('Use latest',async()=>{const scroll=$('main-content').scrollTop;await detail(state.record.key);$('main-content').scrollTop=scroll;$('live-review').close();},content);
 },content);
};

button('Review workspace updates',()=>$('freshness').click(),$('edit-form'));
