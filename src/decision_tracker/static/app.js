import {installProjectAttention} from './project-attention.js';
import {recordSection,approvalMetadata,evidenceDisplay,supportingEntry} from './record-display.js';
import {installPageLayouts,placeControlHelp} from './page-layout.js';
import {measureHeader} from './header-locking.js';
import {onSessionExpired} from './session.js';
import {sessionFetch} from './session.js';
import {installProjects} from './projects.js';
import {installSavedDecisions} from './saved-decisions.js';
import {installActionForm,titles} from './action-form.js';
import {installDecisionForm} from './decision-form.js';
import {installPlanningLinkForm} from './planning-link-form.js';
import {sendRetained,definitive,readResponse} from './save-request.js';
import {LiveMonitor} from './live.js';
import {collectWorkspace,collectProjects} from './refresh.js';
import {YellowSync} from './yellow-sync.js';
import {installAccount} from './account.js';
import {installLegacyHistory} from './legacy-history.js';
const $=id=>document.getElementById(id);
const layout=installPageLayouts($);
const state={csrf:null,caps:[],projects:[],project:null,revision:0,record:null,cursor:null,edit:null,listRevision:null,contextFingerprint:null,view:null};
const planningLinkPrefill=new URLSearchParams(location.hash.slice(1));
let pageGeneration=0,listGeneration=0,detailGeneration=0,acceptedRoute=location.hash;
function rememberView(key=null){if(state.view==='library-view'){history.replaceState(null,'','#view=library');acceptedRoute=location.hash;return;}if(state.project){const params=new URLSearchParams({project:state.project.project_id});if(state.view==='projects-view')params.set('view','projects');else if(key)params.set('decision',key);else params.set('view','decisions');history.replaceState(null,'','#'+params);}else if(state.view==='projects-view')history.replaceState(null,'','#view=projects');acceptedRoute=location.hash;}
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function message(text,error=false){const e=$(error?'error':'notice');e.textContent=text;e.hidden=false;}
function failure(e){message((e.stage?e.stage+': ':'')+e.message,true);}
const pageFailure=(view,generation=pageGeneration)=>e=>{if(state.view===view&&pageGeneration===generation)failure(e);};
async function api(path,body,method=body===undefined?'GET':'POST',signal){
 const bound=path.match(/^\/api\/v1\/projects\/([^/]+)\//);
 const binding=bound&&state.project?{id:state.project.project_id,uuid:state.project.ledger_uuid}:null;
 if(bound&&(!binding||decodeURIComponent(bound[1])!==binding.id))throw new Error('Project changed. Reload the selected project.');
 const headers={};if(state.project)headers['X-Ledger-UUID']=state.project.ledger_uuid;
 if(body!==undefined)headers['Content-Type']='application/json';
 if(state.csrf)headers['X-CSRF-Token']=state.csrf;
 const r=await sessionFetch(path,{method,headers,credentials:'same-origin',body:body===undefined?undefined:JSON.stringify(body),signal:signal||(body!==undefined?AbortSignal.timeout(15000):undefined)});
 const value=r.status===204?{ok:true,data:{}}:await readResponse(r);if(binding&&(!state.project||state.project.project_id!==binding.id||state.project.ledger_uuid!==binding.uuid))throw new Error('Project changed. Discarding the previous response.');if(!r.ok){const e=new Error(value.error?.message||'Request failed');e.code=value.error?.code;e.details=value.error?.details;throw e;}if(binding&&(value.project_id!==binding.id||value.ledger_uuid!==binding.uuid)){const e=Error('Response project identity did not match.');e.code='LEDGER_IDENTITY_MISMATCH';throw e;}return value;
}
const attention=installProjectAttention({$,state,read:async(p,signal)=>{
 const r=await sessionFetch('/api/v1/projects/'+encodeURIComponent(p.project_id)+'/summary',{headers:{'X-Ledger-UUID':p.ledger_uuid},credentials:'same-origin',signal});
 const value=await readResponse(r);if(!r.ok){const e=Error(value.error?.message||'Open decision count unavailable');e.code=value.error?.code;throw e;}return value;
}});

const base=()=>'/api/v1/projects/'+encodeURIComponent(state.project.project_id);
function button(label,fn,parent,disabled=false){const b=node('button',label);b.type='button';b.disabled=disabled;b.onclick=()=>{const view=state.view,generation=pageGeneration;return Promise.resolve().then(fn).catch(pageFailure(view,generation));};parent.append(b);return b;}
function emptyDecisionControls(){const box=$('context');box.replaceChildren();
 for(const [cls,labels] of [['control-primary',['Edit','Status','Evidence']],['control-secondary',['Defer','Challenge','Deprecate']],['control-supporting',['Options','References','Relationships']]]){const grid=node('div',undefined,'control-grid '+cls);for(const label of labels){const cell=node('div',undefined,'compact-control');button(label,()=>{},cell,true);grid.append(cell);}box.append(grid);}
 const help=button('ⓘ',()=>{tip.hidden=!tip.hidden;help.setAttribute('aria-expanded',String(!tip.hidden));if(!tip.hidden){placeControlHelp(help,tip);}},box);help.className='panel-info';help.setAttribute('aria-label','About these controls');help.setAttribute('aria-expanded','false');
 const tip=node('div',undefined,'control-tooltip');tip.hidden=true;tip.id='empty-control-help';help.setAttribute('aria-controls',tip.id);for(const entries of [[['Edit','Change this record.'],['Status','Set open work to Queued or Under investigation.'],['Evidence','Update implementation, verification and acceptance evidence.']],[['def','Defer: pause work.'],['chal','Challenge: flag a disagreement.'],['dep','Deprecate: end use.']],[['opt','Option: propose a solution.'],['ref','Reference: attach a source.'],['rel','Relationship: link decisions.']]]){const list=node('dl');for(const [label,text] of entries)list.append(node('dt',label),node('dd',text));tip.append(list);}box.append(tip);help.onblur=()=>{tip.hidden=true;help.setAttribute('aria-expanded','false');};help.onkeydown=e=>{if(e.key==='Escape'){tip.hidden=true;help.setAttribute('aria-expanded','false');}};
}
async function defaultDecision(){if(!state.project?.enabled||state.record||state.view!=='workspace')return;const generation=detailGeneration,project=state.project;
 let r=await api(base()+'/decisions?status=open&limit=1');if(!r.data.length)r=await api(base()+'/decisions?limit=1');if(project!==state.project||generation!==detailGeneration||state.record||state.view!=='workspace')return;
 if(r.data.length)await detail(r.data[0].key);else {emptyDecisionControls();$('detail').replaceChildren(node('p','No decisions yet.'));}
}
function show(view){if(view==='login-view'){attention.session();}if(state.view==='workspace'&&state.view!==view)layout.remember();if(state.view!==view){attention.cancel();pageGeneration++;$('notice').textContent='';$('error').textContent='';$('error').hidden=true;}state.view=view;$('page-watermark').hidden=!['workspace','projects-view','library-view'].includes(view);$('page-watermark').dataset.side=view==='workspace'?'left':'right';document.body.classList.toggle('signed-out',view==='login-view');document.body.classList.toggle('tracker-active',['workspace','projects-view'].includes(view));$('context').hidden=view!=='workspace';$('admin-watermark').hidden=true;$('admin-controls').hidden=true;const picker=$('project-picker');picker.hidden=!['workspace','projects-view'].includes(view);if(!picker.hidden){const heading=view==='workspace'?document.querySelector('.workspace-heading'):$('projects-heading');heading.insertBefore(picker,heading.querySelector('.tracker-heading-actions'));}for(const [id,target] of [['decisions-button','workspace'],['projects-button','projects-view'],['saved-button','library-view']]){if(view===target)$(id).setAttribute('aria-current','page');else $(id).removeAttribute('aria-current');}savedUI.visible(view==='library-view');document.body.classList.toggle('library-active',view==='library-view');if(['projects-view','library-view'].includes(view)){document.querySelector('.local-shell').classList.remove('focus-view');rememberView();}$('focus-toggle').hidden=view!=='workspace';for(const id of ['login-view','workspace','projects-view','library-view'])$(id).hidden=id!==view;if(view==='workspace'&&!state.record)emptyDecisionControls();layout.sync();syncLiveView();}
async function projects(prepared=null){
 const r=prepared||await api('/api/v1/projects');state.catalogRevision=r.catalog_revision;state.projects=r.data;
 if(state.project&&!r.data.some(p=>p.project_id===state.project.project_id&&p.ledger_uuid===state.project.ledger_uuid&&p.enabled)){state.project=null;state.record=null;live.stop();$('record-identity').replaceChildren();$('record-actions').replaceChildren();emptyDecisionControls();}
 $('project').replaceChildren(new Option('Choose project',''));
 for(const p of r.data.filter(p=>p.enabled))$('project').add(new Option(p.name,p.project_id));
 if(state.project)$('project').value=state.project.project_id;
 $('new-project').hidden=!state.caps.includes('registry');$('add-existing').hidden=!state.caps.includes('registry')||!state.caps.includes('maintain');
}
async function signedIn(data){attention.session();state.csrf=data.csrf_token;state.caps=data.capabilities;state.runtime=(await api('/api/v1/schema'))['x-decision-tracker'];$('signout').hidden=false;$('login-view').hidden=true;await projects();const saved=new URLSearchParams(location.hash.slice(1));if(saved.get('view')==='library'){show('library-view');await savedUI.open();return;}if(state.projects.some(p=>p.enabled&&p.project_id===saved.get('project'))){show(saved.get('decision')||saved.get('view')==='decisions'?'workspace':'projects-view');await selectProject(saved.get('project'),/^D[0-9]{6}$/.test(saved.get('decision')||'')?saved.get('decision'):null);if(/^D[0-9]{6}$/.test(saved.get('decision')||'')){show('workspace');if(state.record?.key!==saved.get('decision'))await detail(saved.get('decision'));}else if(saved.get('view')==='decisions'){show('workspace');if(!state.record&&!layout.compact)await defaultDecision();}else {show('projects-view');await admin();}}else{show('projects-view');await admin();}}
$('login-form').onsubmit=async e=>{e.preventDefault();const token=$('token').value;$('token').value='';try{await signedIn((await api('/api/v1/session',{token})).data);}catch(err){failure(err);}};
$('signout').onclick=()=>guardedNavigate(async()=>{live.stop();let warning='';try{await api('/api/v1/session',undefined,'DELETE',AbortSignal.timeout(5000));}catch(e){warning='The server could not confirm sign-out. Sign in again when it is available.';}account.requireSignin(warning||'Signed out. Sign in to continue.');});
async function selectProject(id,requestedKey=null){attention.cancel();const adminView=state.view==='projects-view';const nextProject=state.projects.find(p=>p.project_id===id)||null;projectUI.bindSelection(nextProject);const rememberedKey=layout.project(nextProject),cachedKey=requestedKey||rememberedKey;live.stop();state.listRevision=null;state.contextFingerprint=null;listGeneration++;detailGeneration++;$('results').replaceChildren();$('result-count').textContent='';$('load-more').hidden=true;$('notice').textContent='';$('error').hidden=true;state.project=state.projects.find(p=>p.project_id===id)||null;state.record=null;$('detail').dataset.loaded='false';$('record-identity').replaceChildren();$('record-actions').replaceChildren();$('context').replaceChildren();$('detail').replaceChildren(node('p','Choose a decision.'));if(!state.project||!state.project.enabled){$('project').value='';if(state.project&&!state.project.enabled)state.project=null;show('projects-view');rememberView();await admin();return;}show(adminView?'projects-view':'workspace');rememberView();$('project').value=state.project.project_id;$('workspace-title').textContent=state.project.name;$('new-decision').disabled=!state.caps.includes('write');await listing(false,false);if(!adminView){if(cachedKey)try{await detail(cachedKey);layout.restore();}catch(e){if(e.code==='NOT_FOUND')await defaultDecision();else throw e;}else if(!layout.compact)await defaultDecision();}syncLiveView();if(adminView)await admin();}
$('project').onchange=()=>guardedNavigate(async()=>{await selectProject($('project').value);});
function renderList(r,more=false){
 state.revision=r.revision;state.listRevision=r.revision;state.cursor=r.next_cursor;
 if(!more)$('results').replaceChildren();
 for(const d of r.data){const b=button(d.key+' · '+d.title,()=>guardedNavigate(async()=>{layout.remember();history.pushState(null,'','#'+new URLSearchParams({project:state.project.project_id,decision:d.key}));show('workspace');await detail(d.key);layout.record({focus:true});}),$('results'));b.className='decision-row';b.dataset.key=d.key;b.setAttribute('aria-current',state.record?.key===d.key?'true':'false');b.append(node('span',d.status+(d.linked?' · linked':d.planning_link_recorded?' · recorded':'')+(d.locked?' · protected':'')+(d.work_tag?' · '+d.work_tag:''),'muted'));}
 if(state.record){let label=$('outside-filters');if(label)label.remove();if(![...$('results').querySelectorAll('button')].some(b=>b.dataset.key===state.record.key)&&!state.cursor){label=node('p','Outside current filters','muted');label.id='outside-filters';$('detail').prepend(label);}}
 if(!$('results').children.length)$('results').append(node('p','No decisions match these filters.','muted'));
 const loaded=$('results').querySelectorAll('button').length;$('result-count').textContent=loaded+(state.cursor?' +':'');$('result-count').setAttribute('aria-label',loaded+' loaded'+(state.cursor?', more available':''));$('load-more').hidden=!state.cursor;live.update();
}
async function listing(more=false,selectDefault=true){
 if(!state.project)return;const generation=++listGeneration;
 const q=new URLSearchParams({q:$('search').value,status:$('status').value,work:$('work').value});
 if(more&&state.cursor)q.set('cursor',state.cursor);
 const r=await api(base()+'/decisions?'+q);if(generation!==listGeneration)return;state.revision=r.revision;state.listRevision=r.revision;state.cursor=r.next_cursor;
 renderList(r,more);if(selectDefault&&!state.record&&state.view==='workspace'&&!layout.compact)await defaultDecision();
}
$('filters').onsubmit=e=>{e.preventDefault();$('decision-browse-body').scrollTop=0;listing().catch(pageFailure(state.view));};
$('load-more').onclick=()=>listing(true).catch(pageFailure(state.view));

async function expand(value){if(!value||typeof value!=='object'||!value.chunks_url)return value;let result='',offset=0;do{const r=await api(value.chunks_url+'&offset='+offset);result+=r.data.text;offset=r.data.next_offset;}while(offset!==null);return result;}
async function all(url){const values=[];let cursor=null;do{const r=await api(url+(cursor?(url.includes('?')?'&':'?')+'cursor='+encodeURIComponent(cursor):''));values.push(...r.data);cursor=r.next_cursor;}while(cursor);return values;}
async function detail(key,prepared=null){
 const generation=++detailGeneration;
 $('detail').dataset.loaded='false';
 const r=prepared?{data:prepared.record,revision:prepared.revision,schema_version:prepared.list.schema_version}:await api(base()+'/decisions/'+key);state.revision=r.revision;state.schemaVersion=r.schema_version;const d=r.data;
 for(const k of Object.keys(d))d[k]=await expand(d[k]);
 if(generation!==detailGeneration)return;rememberView(key);state.record=d;for(const b of $('results').querySelectorAll('button'))b.setAttribute('aria-current',b.dataset.key===key?'true':'false');
 const box=$('detail');box.dataset.loaded='false';box.replaceChildren();
 $('record-actions').replaceChildren();
 const identity=$('record-identity');identity.replaceChildren(node('p',d.key+' · revision '+d.revision,'eyebrow'),node('h2',d.title));
 const badges=node('div',undefined,'decision-badges');badges.append(node('span',d.status+(d.locked?' · protected baseline '+d.baseline:''),'badge'));
 if(d.status==='closed'){
  if(d.planning_link?.recorded)badges.append(node('span',d.planning_link.linked?'linked':'recorded','badge linked-tag'));
  else button('link',()=>edit('decision.link'),badges,!state.caps.includes('write')).className='badge link-button';
 }
 identity.append(badges);
 if(state.schemaVersion<2)box.append(node('p','This project needs a verified data-format upgrade before the new decision form can be used. Existing decisions remain readable.','notice'));
 const fieldText=k=>{const origin=d.legacy_origin?.fields.find(f=>f.field===k);if(d[k]!==null&&d[k]!==undefined)return d[k];return origin?.known_state==='explicit_source_unknown'?'Unknown in source.':origin?.known_state==='not_projected'?'Not projected.':'Not recorded.';};
 const question=node('section',undefined,'question-section record-section'),heading=node('div',undefined,'question-heading');heading.append(node('h3','Question','section-title'));question.append(heading,node('p',fieldText('question'),'long-text'));box.append(question);
 for(const [label,k] of [['Answer','answer'],['Rationale','rationale']]){const {section}=recordSection(label);section.append(node('p',fieldText(k),'long-text'));box.append(section);}
 installLegacyHistory({box,record:d,base,api,node,button,current:()=>generation===detailGeneration});
 const approval=d.latest_resolution_approval,approvalRegion=node('section',undefined,'approval-section record-section'),approvalHeading=node('div',undefined,'approval-heading');
 approvalHeading.append(node('h3','Approval','section-title'));approvalRegion.append(approvalHeading);
 if(approval)approvalRegion.append(approvalMetadata(approval));
 else if(d.status==='open')approvalRegion.append(node('p','Not recorded.','muted'));
 else approvalRegion.append(approvalMetadata(null));
 box.append(approvalRegion);
 if(d.latest_deprecation_approval){const {section}=recordSection('Deprecation approval','approval-section');section.append(approvalMetadata(d.latest_deprecation_approval,'Approval date'));box.append(section);}

 const controls=$('context');controls.replaceChildren();
 const primary=node('div',undefined,'control-grid control-primary'),actions=node('div',undefined,'control-grid control-secondary'),supporting=node('div',undefined,'control-grid control-supporting');controls.append(primary,actions,supporting);
 const helpEntries=new Map(),help=button('\u24d8',()=>{const opening=help.getAttribute('aria-expanded')!=='true';if(opening)showHelp();else tip.hidden=true;help.setAttribute('aria-expanded',String(opening));},controls);help.className='panel-info';help.setAttribute('aria-label','About these controls');help.setAttribute('aria-expanded','false');
 const tip=node('div',undefined,'control-tooltip');tip.id='panel-control-help';tip.setAttribute('role','tooltip');tip.hidden=true;controls.append(tip);help.setAttribute('aria-describedby',tip.id);help.setAttribute('aria-controls',tip.id);
 const showHelp=()=>{tip.replaceChildren();for(const row of [primary,actions,supporting]){if(!row.children.length)continue;const list=node('dl');for(const cell of row.children){const entry=helpEntries.get(cell),term=node('dt',entry.label),description=node('dd');if(entry.label!==entry.full)description.append(node('strong',entry.full));description.append(node('span',entry.description));list.append(term,description);}tip.append(list);}tip.hidden=false;placeControlHelp(help,tip);},hideHelp=()=>{tip.hidden=true;help.setAttribute('aria-expanded','false');};

 help.addEventListener('pointerenter',showHelp);help.addEventListener('pointerleave',()=>{if(document.activeElement!==help)hideHelp();});help.addEventListener('focus',showHelp);help.addEventListener('blur',hideHelp);help.addEventListener('keydown',e=>{if(e.key==='Escape'){hideHelp();e.stopPropagation();}});
 function control(label,full,description,op,parent,disabled=false){label=({res:'Resume',def:'Defer',resolve:'Resolve challenge',chal:'Challenge',dep:'Deprecate',opt:'Options',ref:'References',rel:'Relationships'})[label]||label;const cell=node('div',undefined,'compact-control'),action=button(label,()=>{hideHelp();edit(op);},cell,disabled);action.setAttribute('aria-label',full);parent.append(cell);helpEntries.set(cell,{label,full,description});}
 const writable=state.caps.includes('write')&&!d.locked&&d.status==='open',supplemental=canSupplement(d),decide=state.caps.includes('decide');
 control('Edit','Edit','Change this open record.','decision.edit',primary,!writable);
 control('Status','Status','Set an open decision to Queued or Under investigation. Use Resume for deferred work.','decision.set-work',primary,!writable||d.work_tag==='deferred');
 control('Evidence','Evidence','Update implementation, verification and acceptance evidence on an active decision.','decision.set-evidence',primary,!supplemental);
 control(d.status==='open'&&d.work_tag==='deferred'?'res':'def',d.status==='open'&&d.work_tag==='deferred'?'Resume':'Defer','Pause or resume work on an open record.',d.work_tag==='deferred'?'decision.resume':'decision.defer',actions,!writable);
 control(d.status==='open'&&d.contested?'resolve':'chal',d.status==='open'&&d.contested?'Resolve challenge':'Challenge','Record a disagreement or its resolution on an open record.',d.contested?'decision.resolve-challenge':'decision.challenge',actions,!writable||!['deferred','under-investigation'].includes(d.work_tag));
 control('dep','Deprecate','End use of this decision; keep its history.','decision.deprecate',actions,d.status==='deprecated'||!decide);
 for(const [label,full,description,op] of [['opt','Add option','Propose a solution.','option.add'],['ref','Add reference','Attach a source.','reference.add'],['rel','Add relationship','Link active open or closed decisions.','link.add']])control(label,full,description,op,supporting,op==='option.add'?!writable:!(writable||supplemental));
 const closure=node('div',undefined,'closure-slot');question.append(closure);
 if(d.status==='open')button('Decide',()=>edit('decision.close'),$('record-actions'),!writable||!decide).className='primary';
 if(d.status==='closed'){
  button('Reopen',()=>edit('decision.reopen'),$('record-actions'),d.locked||!decide).className='primary';
  if(d.locked)closure.append(node('small','Amend the protected baseline to make changes.'));
  button(d.locked?'Amend':'Protect',()=>edit(d.locked?'decision.amend':'decision.lock'),approvalHeading,!decide).setAttribute('aria-label',d.locked?'Amend baseline':'Protect baseline');
 }
 for(const [family,label] of [['alternatives','Options'],['references','References'],['links','Relationships']]){
  const {section,heading}=recordSection(label);box.append(section);const children=prepared?d[family]:await all(d.collections[family].url);if(generation!==detailGeneration)return;d[family]=children;
  if(!children.length)heading.append(node('span','None recorded','muted record-empty'));
  for(const child of children){for(const k of Object.keys(child))child[k]=await expand(child[k]);const card=supportingEntry(family,child,key=>{if(key===d.key)return node('span',key);const link=node('a',key,'record-decision-link');link.href='#'+new URLSearchParams({project:state.project.project_id,decision:key});link.onclick=event=>{if(event.button||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;event.preventDefault();if(generation===detailGeneration)navigateRelated(key,link);};return link;});
   if(writable&&family!=='links'&&!child.retired&&!['retired','selected'].includes(child.disposition)){const type=family==='alternatives'?'option':'reference';const pair=node('div',undefined,'item-actions');card.append(pair);button('Edit',()=>edit(type+'.edit',child),pair);button('Retire',()=>edit(type+'.retire',child),pair);}
   if((writable||supplemental)&&family==='links'&&child.active&&(child.source_key===d.key||(supplemental&&child.type==='relates_to'))&&['relates_to','depends_on'].includes(child.type)){const other=child.source_key===d.key?child.target_key:child.source_key;const target=prepared?prepared.targets[other]:(await api(base()+'/decisions/'+other)).data;if(generation!==detailGeneration)return;if((writable&&target.status==='open'&&!target.locked)||(supplemental&&activeContext(target)))button('Unlink',()=>edit('link.unlink',child),card);}
   section.append(card);
  }
 }
 const {section:evidenceRegion}=recordSection('Evidence state');evidenceRegion.append(evidenceDisplay(d.evidence_state));box.append(evidenceRegion);if(d.status==='closed'&&!canSupplement(d)&&state.caps.includes('write'))box.append(node('p','A runtime update supporting closed context is required to add relationships, references or evidence.','notice'));
 const historyBox=node('section');box.append(historyBox);let historyOpen=false,historyRequest=0;
 const historyButton=button('History',async()=>{
  historyOpen=!historyOpen;const request=++historyRequest;historyButton.setAttribute('aria-expanded',String(historyOpen));historyBox.replaceChildren();if(!historyOpen)return;
  historyBox.append(node('p','Loading history…'));try{const history=await all(base()+'/decisions/'+key+'/history');if(!historyOpen||request!==historyRequest||generation!==detailGeneration)return;historyBox.replaceChildren(node('h3','Recorded history','section-title'));
  for(const h of history){const row=node('section');row.append(node('p','Ledger '+h.ledger_revision+' · '+h.principal_id+' · '+h.reason));if(h.deprecation_approval){const a=h.deprecation_approval;row.append(node('p','Deprecation approval: '+(a.mode==='reported'?a.reported_approver+' (reported)':a.mode==='authenticated_now'?a.recorded_by+' (authenticated)':'Legacy references; approver unknown')+' · '+(a.occurred_at||a.occurred_date||'Date unknown')));}const content=node('div');let open=false,serial=0;
   const toggle=button('View snapshot',async()=>{open=!open;const ticket=++serial;toggle.setAttribute('aria-expanded',String(open));content.replaceChildren();if(!open)return;content.append(node('p','Loading snapshot…'));try{const snapshot=(await api(base()+'/decisions/'+key+'/as-of?revision='+h.ledger_revision)).data;if(open&&ticket===serial&&historyOpen&&request===historyRequest&&generation===detailGeneration)content.replaceChildren(node('pre',JSON.stringify(snapshot,null,2)));}catch(e){if(open&&ticket===serial&&content.isConnected)content.replaceChildren(node('p',e.message,'error'));}},row);toggle.setAttribute('aria-expanded','false');row.append(content);historyBox.append(row);}
  const receipts=await all(base()+'/decisions/'+key+'/planning-links');if(!historyOpen||request!==historyRequest||generation!==detailGeneration)return;
  for(const receipt of receipts){const row=node('section',undefined,'planning-link-history');row.append(node('h3',receipt.anchor?'Planning link':'Planning incorporation record'),node('p','Ledger '+receipt.ledger_revision+' · '+receipt.recorded_by+' · '+receipt.recorded_at),node('p',receipt.anchor?receipt.anchor.path+' · '+receipt.anchor.section.heading:'Anchor omitted'),node('pre',JSON.stringify(receipt,null,2)));historyBox.append(row);}
  }catch(e){if(historyOpen&&request===historyRequest&&generation===detailGeneration)historyBox.replaceChildren(node('p',e.message,'error'));}
 },box);box.append(historyBox);historyButton.setAttribute('aria-expanded','false');
 const context=prepared?prepared.context:(await api(base()+'/decisions/'+key+'/context')).data;if(generation!==detailGeneration)return;state.contextFingerprint=context.context_fingerprint;
 $('decision-columns').classList.add('show-detail');
 box.dataset.loaded='true';layout.record({key});syncFocus();syncLiveView();
}
function edit(op,child=null){
 $('editor').classList.toggle('planning-link-editor',op==='decision.link');
 $('editor').classList.toggle('decision-editor',op==='decision.close');
 $('edit-context').querySelector('.resolution-question')?.remove();
 const heading=$('edit-heading');
 if(op==='decision.close')$('edit-form').insertBefore(heading,$('edit-context'));
 else $('edit-context').prepend(heading);
 $('editor').classList.toggle('action-header-locked',op!=='decision.close');
 if(op==='decision.link'&&state.schemaVersion<3){message('Upgrade this ledger before recording a planning link.',true);return;}
 if(['decision.close','decision.edit-resolution'].includes(op)&&state.schemaVersion<2){message('This project needs a data-format upgrade before decisions can be recorded.',true);return;}
 const d=state.record||{},invoker=document.activeElement;
 if(supplementalOps.has(op)&&!(op!=='decision.set-evidence'&&d.status==='open'&&!d.locked)&&!canSupplement(d)){message('This record cannot receive supplemental context with the current runtime.',true);return;}
 if(op==='decision.edit-resolution'||(d.status!=='open'&&['decision.edit','decision.set-work','decision.defer','decision.resume','decision.challenge','decision.resolve-challenge','option.add','option.edit','option.retire','reference.edit','reference.retire'].includes(op))){message('Reopen this decision before changing its content.',true);return;}
 state.edit={op,child,revision:state.revision,decisionRevision:d.revision,key:d.key,requestId:crypto.randomUUID(),pending:null,invoker};
 $('edit-title').textContent=op==='decision.link'?'Link to planning':titles[op];$('edit-project').textContent=state.project.name+(d.key&&op!=='decision.create'?' · '+d.key:'');
 const fields=$('edit-fields');fields.replaceChildren();$('form-error').hidden=true;$('conflict').hidden=true;
 if(op==='decision.close')state.edit.resolution=installDecisionForm(fields,d,false,$('edit-context'));
 else if(op==='decision.link')state.edit.action=installPlanningLinkForm(fields,d,{api,base,onReady:ready=>{if(state.edit?.op==='decision.link'&&!state.edit.saving)$('save-edit').disabled=!ready;},onPrefilled:()=>{if(state.edit?.op==='decision.link')state.edit.initial=new URLSearchParams(new FormData($('edit-form'))).toString();},prefill:planningLinkPrefill.get('project')===state.project.project_id&&planningLinkPrefill.get('decision')===d.key?{document:planningLinkPrefill.get('planning-document'),section:planningLinkPrefill.get('planning-section'),sha256:planningLinkPrefill.get('planning-sha256')}:null});
 else state.edit.action=installActionForm(fields,op,d,child,{decide:state.caps.includes('decide'),findDecisions:async q=>{const items=await all(base()+'/decisions?q='+encodeURIComponent(q));return op==='link.add'?items.filter(item=>canSupplement(d)?activeContext(item):item.status==='open'&&!item.locked):items;}});
 $('save-edit').textContent=state.edit.action?.submit||'Save decision';$('save-edit').disabled=state.edit.action?.ready?!state.edit.action.ready():false;state.edit.initial=new URLSearchParams(new FormData($('edit-form'))).toString();
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
 event.preventDefault();const originView=state.view;const editState=state.edit;if(!editState)return;const save=$('save-edit');save.disabled=true;editState.saving=true;$('form-error').hidden=true;
 try{
  const values=(editState.resolution||editState.action).read();if(values.unchanged){message('No evidence changes to save.');return;}const f=values.data,reason=values.reason,authority_refs=values.authority_refs;
  const revisions={};if(editState.op!=='decision.create')revisions[editState.key]=editState.decisionRevision;
  let other=f.target_key||f.replacement_key;if(editState.op==='link.unlink')other=editState.child.source_key===editState.key?editState.child.target_key:editState.child.source_key;
  if(other){const target=await api(base()+'/decisions/'+encodeURIComponent(other));revisions[other]=target.data.revision;}
  const operation={op:editState.op,data:f};if(editState.op!=='decision.create')operation.key=editState.key;if(editState.child)operation.id=editState.child.id;
  const payload={expected_ledger_uuid:state.project.ledger_uuid,expected_revision:editState.revision,expected_decision_revisions:revisions,request_id:editState.requestId,reason,authority_refs,operations:[operation]};
  const result=await sendRetained(editState,payload,body=>api(base()+'/changes',body));const key=result.data[0]?.key,next=editState.afterDiscard;if(state.view===originView)message(editState.resolution?(editState.op==='decision.close'?'Decision saved. This question is closed. Implementation status has not changed.':'Decision updated. Implementation status has not changed.'):'Saved at ledger revision '+result.revision);try{await refreshWorkspace({key:key||state.record?.key||null,commitSaved:true});closeEditor();next?.();}catch(e){closeEditor();if(state.view===originView)message('Saved successfully. Refresh the view to see current data.');}
 }catch(e){
  if(definitive(e)){editState.pending=null;editState.requestId=crypto.randomUUID();}const error=$('form-error');error.textContent=e.message;(editState.resolution||editState.action)?.showError(e,error);error.hidden=false;error.tabIndex=-1;error.focus();
  if(e.code==='INVALID_TRANSITION')error.textContent+=supplementalOps.has(editState.op)?' Your draft is preserved. Review the current record and relationship endpoints.':' Your draft is preserved. Review the current record and reopen it before editing.';
  if(['REVISION_CONFLICT','STALE_REVISION','REQUEST_ID_REUSED','PROPOSAL_CHANGED'].includes(e.code)||e.code?.includes('STALE')){
   const c=$('conflict');c.hidden=false;c.replaceChildren(node('p','Your draft is preserved. Review the current record before rebasing this draft.'));
   button('Load current state alongside draft',async()=>{
    if(editState.op==='decision.create'){const r=await api(base()+'/decisions');if(editState.saving||editState.pending)throw Error('Resolve the pending save first.');c.querySelector('.current-comparison')?.remove();c.append(node('pre',JSON.stringify(r.data,null,2),'current-comparison'));button('Use these revisions; keep draft for review',()=>{if(editState.saving||editState.pending)throw Error('Resolve the pending save first.');editState.revision=r.revision;editState.requestId=crypto.randomUUID();},c);return;}
    const captured=refreshIdentity(),candidate=await refreshWorkspace({review:true});c.querySelector('.current-comparison')?.remove();c.querySelector('.conflict-rebase')?.remove();c.append(node('pre',JSON.stringify(candidate.record,null,2),'current-comparison'));
    if(canRebase(editState,candidate.record)){const apply=button('Use these revisions; keep draft for review',()=>rebaseReviewed(candidate,captured),c);apply.className='conflict-rebase';}
   },c);
   if(e.code==='PROPOSAL_CHANGED')button('Keep my text as a written answer',()=>{editState.resolution.asWritten();message('Proposal selection cleared. Review current revisions before saving your written answer.');},c);
  }else if(editState.pending&&(!e.code||e.code==='INTERNAL_ERROR')){
   const c=$('conflict');c.hidden=false;c.replaceChildren(node('p','The save outcome is unknown. Your original request is retained. Retry it before changing the draft.'));
   button('Retry original save',async()=>{if(editState.saving)return;editState.saving=true;try{const result=await api(base()+'/changes',JSON.parse(editState.pending));const key=result.data[0]?.key;message('Saved successfully.');try{await refreshWorkspace({key:key||state.record?.key||null,commitSaved:true});}catch{message('Saved successfully. Refresh the view to see current data.');}closeEditor();}finally{editState.saving=false;}},c);
  }else editState.pending=null;
 }finally{editState.saving=false;save.disabled=editState.action?.ready?!editState.action.ready():false;}
};
async function admin(prepared=null){await projectUI.render(prepared);syncLiveView();if(!prepared)void attention.sweep();}
const projectUI=installProjects({$,state,node,button,api,projects,selectProject,show,detail,listing,message,readResponse,onFreshness:()=>syncLiveView(),onRefresh:()=>refreshWorkspace(),attention,viewDecisions:()=>$('decisions-button').click()});
function guardedNavigate(fn){const move=()=>projectUI.navigate(()=>savedUI.navigate(fn));if(state.edit?.saving||state.edit?.pending)return Promise.resolve(false);if(dirty()){state.edit.afterDiscard=()=>move().catch(failure);$('dirty-dialog').showModal();return Promise.resolve(false);}if(state.edit)closeEditor();return move().catch(e=>{failure(e);return false;});}
let relationshipAttempt=null;
function navigateRelated(key,link){
 if(relationshipAttempt)return;
 return guardedNavigate(async()=>{
  if(relationshipAttempt||!link.isConnected||!state.project?.enabled)return false;
  const captured=refreshIdentity(),controller=new AbortController();relationshipAttempt=controller;
  const deadline=setTimeout(()=>controller.abort(),20000),supersession=setInterval(()=>{if(!stillCurrent(captured))controller.abort();},50);
  link.setAttribute('aria-disabled','true');
  try{
   let candidate;
   for(let attempt=0;attempt<2;attempt++){
    try{candidate=await collectWorkspace((path,signal)=>api(path,undefined,'GET',signal),base(),captured.query,key,controller.signal,$('results').querySelectorAll('button[data-key]').length);break;}
    catch(error){if(attempt||!['REFRESH_CHANGED','CURSOR_STALE','STALE_REVISION'].includes(error.code))throw error;}
   }
   controller.signal.throwIfAborted();if(!stillCurrent(captured))return false;
   layout.remember();history.pushState(null,'','#'+new URLSearchParams({project:captured.id,decision:key}));
   await detail(key,candidate);$('record-identity').focus();return true;
  }catch(error){
   if(!stillCurrent(captured)||!link.isConnected)return false;
   if(['NOT_FOUND','FORBIDDEN','PROJECT_DISABLED','LEDGER_IDENTITY_MISMATCH'].includes(error.code)){
    link.replaceWith(node('span',key));message('Related decision unavailable.',true);
   }else if(error.code!=='UNAUTHORIZED')message('Could not open related decision. Try the link again.',true);
   return false;
  }finally{clearTimeout(deadline);clearInterval(supersession);controller.abort();if(relationshipAttempt===controller)relationshipAttempt=null;link.removeAttribute('aria-disabled');}
 });
}
const savedUI=installSavedDecisions({$,state,node,api,projects});
$('saved-button').onclick=()=>{if(!state.csrf)return;guardedNavigate(async()=>{history.pushState(null,'','#view=library');show('library-view');rememberView();await savedUI.open();});};
$('projects-button').onclick=()=>{if(!state.csrf)return;guardedNavigate(async()=>{history.pushState(null,'','#'+new URLSearchParams({project:state.project?.project_id||'',view:'projects'}));show('projects-view');await admin();});};
$('decisions-button').onclick=()=>state.csrf&&guardedNavigate(async()=>{history.pushState(null,'','#'+new URLSearchParams({project:state.project?.project_id||'',view:'decisions'}));show('workspace');rememberView(state.record?.key);if(state.project?.enabled){if(state.record){const browsing=layout.mode==='browse';await detail(state.record.key);layout.restore();if(browsing)layout.browse();}else if(layout.selectedKey){await listing(false,false);await detail(layout.selectedKey);layout.restore();}else await listing();}else $('detail').replaceChildren(node('p','Choose an enabled project.'));});
window.addEventListener('popstate',async()=>{if(!state.csrf)return;const previous=acceptedRoute,params=new URLSearchParams(location.hash.slice(1));const moved=await guardedNavigate(async()=>{if(params.get('view')==='library'){show('library-view');rememberView();await savedUI.open();return;}if(params.get('project')&&params.get('project')!==state.project?.project_id)await selectProject(params.get('project'),params.get('decision'));show(params.get('decision')||params.get('view')==='decisions'?'workspace':'projects-view');if(state.view==='projects-view')await admin();else if(state.project?.enabled){if(params.get('decision'))await detail(params.get('decision'));else {layout.browse();rememberView();}}});if(!moved)history.pushState(null,'',previous||location.pathname);});
new ResizeObserver(entries=>{document.documentElement.style.setProperty('--header-height',entries[0].target.offsetHeight+'px');}).observe(document.querySelector('.topbar'));
new ResizeObserver(entries=>{document.documentElement.style.setProperty('--decision-heading-height',entries[0].target.getBoundingClientRect().height+'px');}).observe(document.querySelector('#workspace>.workspace-heading'));
new ResizeObserver(entries=>{$('editor').style.setProperty('--decision-context-height',entries[0].target.getBoundingClientRect().height+'px');}).observe($('edit-context'));
document.querySelector('.skip-link').addEventListener('click',event=>{event.preventDefault();const main=$('main-content');main.focus();main.scrollIntoView({block:'start'});});
api('/api/v1/session').then(r=>signedIn(r.data)).catch(()=>show('login-view'));

function monitorProject(){return state.view==='projects-view'?projectUI.selected:state.view==='workspace'?state.project:null;}
function monitorKey(){return state.view==='workspace'?state.record?.key||null:null;}
function syncLiveView(){const p=monitorProject();if(p?.enabled)live.ensure(p,monitorKey());else live.stop(state.view==='projects-view'?'Catalog only':'Select project');live.update();}
const live=new LiveMonitor(()=>state.view==='projects-view'?{key:null,listRevision:projectUI.freshnessRevision}:{key:state.record?.key||null,decisionRevision:state.record?.revision,listRevision:state.listRevision,contextFingerprint:state.contextFingerprint}, (color,label)=>{
 if(state.view==='projects-view'&&projectUI.freshnessRevision===null)color='gray';
 const control=$('freshness'),text=color==='green'?'':color==='yellow'?'Updates available':color==='red'?'Out of sync':label||'Disconnected';
 const accessible=color==='green'?'Connected and current':text;
 control.className='freshness '+color;control.title=accessible;control.setAttribute('aria-label',accessible);$('freshness-label').textContent=text;
 if($('freshness-announcement').textContent!==accessible)$('freshness-announcement').textContent=accessible;
 const popupStatus=$('live-review-content').querySelector('.live-current-status');if(popupStatus)popupStatus.textContent=accessible;
});
function syncFocus(){layout.sync();}

$('back-decisions').onclick=()=>guardedNavigate(async()=>{layout.remember();history.pushState(null,'','#'+new URLSearchParams({project:state.project?.project_id||'',view:'decisions'}));acceptedRoute=location.hash;layout.browse();});
$('decisions-refresh').onclick=()=>{const generation=pageGeneration;return refreshWorkspace().catch(pageFailure('workspace',generation));};
$('projects-refresh').onclick=()=>refreshWorkspace().catch(pageFailure('projects-view',pageGeneration));

let refreshAttempt=null,refreshPromise=null,refreshAutomatic=false,refreshSerial=0,reviewInvoker=null;
let yellowSync=null;
function refreshIdentity(){return {project:state.project,id:state.project?.project_id,uuid:state.project?.ledger_uuid,key:state.record?.key||null,view:state.view,page:pageGeneration,list:listGeneration,detail:detailGeneration,edit:state.edit,administrative:projectUI.selectionIdentity,query:new URLSearchParams({q:$('search').value,status:$('status').value,work:$('work').value}).toString()};}
function stillCurrent(c){return c.administrative===projectUI.selectionIdentity&&c.project===state.project&&c.id===state.project?.project_id&&c.uuid===state.project?.ledger_uuid&&c.key===(state.record?.key||null)&&c.view===state.view&&c.page===pageGeneration&&c.list===listGeneration&&c.detail===detailGeneration&&c.edit===state.edit&&c.query===new URLSearchParams({q:$('search').value,status:$('status').value,work:$('work').value}).toString();}
function refreshWorkspace(options={}){
 if(refreshPromise){if(!options.automatic&&refreshAutomatic){refreshAttempt?.abort(Error('Manual refresh superseded automatic refresh.'));return refreshPromise.catch(()=>{}).then(()=>refreshWorkspace(options));}return refreshPromise;}
 const run=()=>performRefresh(options);refreshAutomatic=!!options.automatic;
 refreshPromise=Promise.resolve().then(()=>state.view==='projects-view'&&!options.automatic?projectUI.navigate(run):run()).finally(()=>{refreshPromise=null;refreshAutomatic=false;});return refreshPromise;
}
async function performRefresh({retry=false,key=state.record?.key||null,review=false,commitSaved=false,automatic=false,signal=null}={}){
 if(state.view==='workspace'&&!state.project?.enabled)throw Error('Choose an enabled project.');
 if(state.view!=='projects-view'&&['Service stopped','Unavailable','Sign in required'].includes(live.label))throw Error(live.label);

 const captured=refreshIdentity(),controller=new AbortController(),serial=++refreshSerial;refreshAttempt=controller;const syncBinding=yellowSnapshot().binding;const abort=()=>controller.abort(signal.reason);if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
 const deadline=setTimeout(()=>controller.abort(Error('Refresh exceeded the 20-second budget.')),20000);
 const supersession=setInterval(()=>{if(!stillCurrent(captured))controller.abort(Error('Selection or view changed. Refresh cancelled.'));},50);
 const content=$('live-review-content'),busy=[...content.querySelectorAll('button'),$('decisions-refresh'),$('projects-refresh')];busy.forEach(b=>b.disabled=true);
 let applied=false;const presentation=layout.mode,scroll={results:$('decision-browse-body').scrollTop,detail:$('record-body').scrollTop,projects:$('project-browse-body').scrollTop,data:$('project-data-body').scrollTop,x:scrollX,y:scrollY},focus=document.activeElement;
 if(!automatic&&!commitSaved){$('error').hidden=true;$('notice').hidden=true;}
 try{
  if(state.view==='library-view'){await savedUI.refresh();content.append(node('p','Library refreshed. Staging retains its existing copies.'));return;}
  if(state.view==='projects-view'){
   let candidate;for(let attempt=0;attempt<2;attempt++)try{candidate=await collectProjects((path,signal)=>api(path,undefined,'GET',signal),projectUI.selected,controller.signal,catalog=>{
    const old=projectUI.selected,active=state.project;
    if(old&&!catalog.data.some(p=>p.project_id===old.project_id&&p.ledger_uuid===old.ledger_uuid&&p.enabled===old.enabled)||active&&!catalog.data.some(p=>p.project_id===active.project_id&&p.ledger_uuid===active.ledger_uuid&&p.enabled)){
     projectUI.invalidate();for(const id of ['backups-button','exports-button','verify-button'])$(id).disabled=true;
     if(active&&!catalog.data.some(p=>p.project_id===active.project_id&&p.ledger_uuid===active.ledger_uuid&&p.enabled)){$('record-identity').replaceChildren();$('record-actions').replaceChildren();emptyDecisionControls();live.stop('Unavailable');}
    }
   });break;}catch(e){if(attempt||!['REFRESH_CHANGED','CURSOR_STALE','STALE_REVISION'].includes(e.code))throw e;}
   controller.signal.throwIfAborted();if(!stillCurrent(captured))throw Error('Selection or view changed. Refresh cancelled.');
   if(candidate.selected?.enabled){if(retry)live.start(candidate.selected,null);else live.ensure(candidate.selected,null);await live.ready(controller.signal,candidate.regions.revision);}
   controller.signal.throwIfAborted();if(!stillCurrent(captured))throw Error('Selection or view changed. Refresh cancelled.');
   if(automatic)checkAutomatic(candidate.regions?.revision,null);
   await projects(candidate.catalog);await admin(candidate.regions);void attention.sweep(automatic);applied=true;live.update();
   if(!automatic){yellowSync?.recovered(syncBinding);content.append(node('p',candidate.regions?'Projects refreshed.':'Catalog refreshed.'));message(candidate.regions?'Projects refreshed.':'Catalog refreshed.');}return candidate;
  }
  let candidate;
  for(let attempt=0;attempt<2;attempt++){
   try{candidate=await collectWorkspace((path,signal)=>api(path,undefined,'GET',signal),base(),captured.query,key,controller.signal,$('results').querySelectorAll('button[data-key]').length);break;}
   catch(error){if(attempt||!['REFRESH_CHANGED','CURSOR_STALE','STALE_REVISION'].includes(error.code))throw error;}
  }
  controller.signal.throwIfAborted();if(!stillCurrent(captured)||serial!==refreshSerial)throw Error('Selection or view changed. Refresh cancelled.');
  if(retry)live.start(state.project,key);else live.ensure(state.project,key);
  await live.ready(controller.signal,candidate.revision);
  controller.signal.throwIfAborted();if(!stillCurrent(captured))throw Error('Selection or view changed. Refresh cancelled.');
  if(automatic)checkAutomatic(candidate.revision,candidate.record);
  if((captured.edit&&!commitSaved)||review){renderList(candidate.list);showComparison(candidate,captured);}
  else await detailCandidate(candidate,key);
  applied=true;clearInterval(supersession);live.update();if(!automatic)yellowSync?.recovered(syncBinding);
  const color=$('freshness').className;
  if((captured.edit&&!commitSaved)||review)content.append(node('p',captured.edit?'Draft retained. Review differences before explicitly rebasing.':'Review the saved state, then use latest explicitly.'));
  else if(!color.includes('green'))content.append(node('p','Refresh completed, but newer updates remain. Review or refresh again.'));
  else if($('live-review').open)$('live-review').close();
  return candidate;
 }catch(error){if(state.view==='projects-view'&&!controller.signal.aborted&&error.code!=='AUTO_DEFERRED'){projectUI.invalidate(error);live.update();}if(error.code==='UNAUTHORIZED')live.stop('Sign in required');else if(['FORBIDDEN','PROJECT_DISABLED','LEDGER_IDENTITY_MISMATCH'].includes(error.code))live.stop('Unavailable');if(!automatic)message((error.stage?error.stage+': ':'')+error.message,true);if($('live-review').open)content.append(node('p',(error.stage?error.stage+': ':'')+error.message,'error'));throw error;}
 finally{
  signal?.removeEventListener('abort',abort);clearTimeout(deadline);clearInterval(supersession);controller.abort();refreshAttempt=null;
  if($('live-review').open)connectionControls(content);busy.forEach(b=>{if(b.isConnected)b.disabled=false;});
  const sameView=captured.page===pageGeneration&&captured.view===state.view&&captured.id===state.project?.project_id&&captured.uuid===state.project?.ledger_uuid;
  if(applied&&sameView){$('decision-browse-body').scrollTop=scroll.results;$('record-body').scrollTop=scroll.detail;$('project-browse-body').scrollTop=scroll.projects;$('project-data-body').scrollTop=scroll.data;if(state.view==='workspace'&&presentation==='browse')layout.browse({focus:false});window.scrollTo(scroll.x,scroll.y);}
  if(!automatic&&sameView&&focus?.isConnected&&(!$('editor').open||$('editor').contains(focus)||$('live-review').contains(focus)))focus.focus();
 }
}
async function detailCandidate(candidate,key){if(key)await detail(key,candidate);renderList(candidate.list);if(!key){state.contextFingerprint=null;syncLiveView();}}
const supplementalOps=new Set(['reference.add','link.add','link.unlink','decision.set-evidence']);
function activeContext(d){return !!d&&['open','closed'].includes(d.status)&&(!d.locked||d.status==='closed');}
function canSupplement(d){const policy=state.runtime?.mutation_policy;return state.schemaVersion>=2&&state.caps.includes('write')&&state.runtime?.capabilities?.includes('closed_context_v1')&&['reference.add','link.add','link.unlink','decision.set-evidence'].every(op=>policy?.closed_supplemental?.includes(op)&&policy?.protected_closed_supplemental?.includes(op))&&activeContext(d);}
const ordinaryEdits=new Set(['decision.edit','option.add','option.edit','option.retire','reference.add','reference.edit','reference.retire','link.add','link.unlink','decision.set-work','decision.defer','decision.resume','decision.challenge','decision.resolve-challenge']);
function canRebase(editState,d){
 if(!editState||!d||d.status==='deprecated')return false;
 if(supplementalOps.has(editState.op))return canSupplement(d)||(editState.op!=='decision.set-evidence'&&state.caps.includes('write')&&d.status==='open'&&!d.locked);
 if(d.locked&&!['decision.amend','decision.deprecate','decision.link'].includes(editState.op))return false;
 if(ordinaryEdits.has(editState.op)||editState.op==='decision.close')return d.status==='open';
 if(['decision.reopen','decision.lock','decision.link'].includes(editState.op))return d.status==='closed';
 if(editState.op==='decision.amend')return d.status==='closed'&&d.locked;
 return true;
}
async function rebaseReviewed(candidate,captured){
 const editState=state.edit;
 if(!editState||editState!==captured.edit||captured.project!==state.project||captured.key!==state.record?.key||captured.uuid!==state.project?.ledger_uuid)throw Error('Editor or project changed. Review again.');
 if(editState.saving||editState.pending)throw Error('Resolve the pending save with Retry original save before rebasing.');
 const d=candidate.record;
 const saved=await api(base()+'/decisions/'+editState.key,undefined,'GET',AbortSignal.timeout(15000));
 if(state.edit!==editState||captured.project!==state.project||captured.key!==state.record?.key||editState.saving||editState.pending)throw Error('Editor changed or a save is pending. Review again.');
 if(saved.revision!==candidate.revision||saved.data.revision!==d?.revision)throw Error('Saved state changed after comparison. Review changes again before rebasing.');
 if(d.key!==editState.key||!canRebase(editState,d))throw Error('Your draft is preserved. Use the existing Reopen or Amend workflow for the current record.');
 editState.action?.rebase?.(d);editState.revision=candidate.revision;editState.decisionRevision=d.revision;editState.requestId=crypto.randomUUID();
 await detailCandidate(candidate,d.key);live.update();message('Draft retained. Review differences, then save explicitly.');
}
function showComparison(candidate,captured){
 const content=$('live-review-content'),current=candidate.record,displayed=state.record;
 content.querySelector('.revision-comparison')?.remove();content.querySelector('.review-apply')?.remove();
 if(!current)return;
 const differences=Object.keys(current).filter(k=>!['collections','updated_at'].includes(k)&&JSON.stringify(current[k])!==JSON.stringify(displayed[k]));
 const comparison=node('div',undefined,'revision-comparison');comparison.append(node('p',differences.length?'Changed fields: '+differences.join(', '):'The selected record is unchanged; the project has advanced.'));
 const format=value=>typeof value==='object'?JSON.stringify(value,null,2):String(value??'Not recorded');
 for(const field of differences){const row=node('section');row.append(node('h3',field));const cells=node('div',undefined,'comparison-cells');for(const [label,value] of [['Displayed',displayed[field]],['Current saved',current[field]]]){const cell=node('div');cell.append(node('strong',label),node('pre',format(value)));cells.append(cell);}if(state.edit){const draft=[...$('edit-fields').querySelectorAll('[name]')].find(n=>n.name===field);if(draft){const cell=node('div');cell.append(node('strong','Your draft'),node('pre',draft.value));cells.append(cell);}}row.append(cells);comparison.append(row);}content.append(comparison);
 if(state.edit&&!canRebase(state.edit,current)){content.append(node('p','Your draft is preserved. Use the existing Reopen or Amend workflow for the current record.'));return;}
 const apply=button(state.edit?'Rebase draft for review':'Use latest',async()=>{if(state.edit)await rebaseReviewed(candidate,captured);else await refreshWorkspace();$('live-review').close();},content);apply.className='review-apply';
}
function yellowSnapshot(){const p=monitorProject();return {binding:state.csrf&&p?.enabled?[state.view,p.project_id,p.ledger_uuid].join('\0'):null,color:$('freshness').classList.contains('yellow')?'yellow':$('freshness').classList.contains('green')?'green':'other',hidden:document.hidden};}
const heldInputs=new Set();
function automaticEligible(){
 const focus=document.activeElement,selection=getSelection();
 return ['workspace','projects-view'].includes(state.view)&&!!state.csrf&&!!monitorProject()?.enabled&&!refreshAttempt&&!heldInputs.size&&!state.edit&&!projectUI.busy&&!savedUI.dirty()&&!document.querySelector('dialog[open]')&&!selection?.toString()&&!focus?.matches('input,textarea,select,[contenteditable=true]')&&!focus?.closest('#detail,#record-head,#results,#project-data,#project-admin')&&!document.querySelector('#detail [aria-expanded=true],#detail details[open],#projects-view details[open]');
}
function checkAutomatic(revision,record){
 const eligible=automaticEligibleDuringRefresh();
 if(!eligible||!live.connected||live.latest?.ledger_revision!==revision||state.view==='workspace'&&(record?.revision!==state.record?.revision||record&&(live.latest?.decision_revision!==record.revision||!live.latest?.selected_exists))){const e=Error('Automatic refresh deferred; use Refresh or Review changes.');e.code='AUTO_DEFERRED';throw e;}
}
function automaticEligibleDuringRefresh(){const held=refreshAttempt;refreshAttempt=null;try{return automaticEligible()&&yellowSnapshot().color==='yellow';}finally{refreshAttempt=held;}}
yellowSync=new YellowSync({snapshot:yellowSnapshot,eligible:automaticEligible,run:signal=>refreshWorkspace({automatic:true,signal}),failure:error=>{if(error.code!=='AUTO_DEFERRED')message('Automatic refresh paused. '+error.message+' Use Refresh to retry.',true);}});
live.listeners.add(()=>{const l=live.latest;yellowSync.observe(JSON.stringify([live.binding,l?.ledger_revision,l?.decision_revision,l?.context_fingerprint,live.connected]));});
for(const event of ['pointerdown','keydown'])document.addEventListener(event,e=>{heldInputs.add(event==='pointerdown'?'pointer:'+e.pointerId:'key:'+e.code);},{capture:true,passive:true});
for(const event of ['pointerup','pointercancel','keyup'])document.addEventListener(event,e=>{heldInputs.delete(event.startsWith('pointer')?'pointer:'+e.pointerId:'key:'+e.code);yellowSync.activity();},{capture:true,passive:true});
window.addEventListener('blur',()=>{heldInputs.clear();yellowSync.activity();});
for(const event of ['pointerdown','pointerup','keydown','keyup','input','change','scroll','selectionchange','focusin','focusout','toggle','close'])document.addEventListener(event,()=>yellowSync.activity(),{capture:true,passive:true});
document.addEventListener('visibilitychange',()=>{yellowSync.activity();if(!document.hidden)yellowSync.wake();});
window.addEventListener('pagehide',()=>yellowSync.stop());
window.addEventListener('pagehide',()=>{refreshAttempt?.abort(Error('Page hidden.'));live.stop();});
window.addEventListener('pageshow',event=>{if(event.persisted&&state.csrf)syncLiveView();});
$('live-review').addEventListener('close',()=>{const active=document.activeElement;if(reviewInvoker?.isConnected&&(active===document.body||$('live-review').contains(active)))reviewInvoker.focus();});
$('close-live-review').onclick=()=>$('live-review').close();
function connectionControls(content){
 content.querySelector('.connection-actions')?.remove();if(state.view!=='projects-view'&&!state.project?.enabled)return;
 if(live.label==='Service stopped'){$('service-controls').hidden=false;$('service-status').textContent='Stopped';$('service-details').textContent='The backend is not running.';$('stop-service').hidden=true;$('start-service').hidden=false;}
 const controls=node('div',undefined,'connection-actions');content.prepend(controls);
 if(!live.connected){
  if(live.label==='Sign in required')button('Sign in again',()=>{if(content.querySelector('form'))return;const form=node('form'),label=node('label','Password'),input=node('input');input.type='password';input.autocomplete='current-password';input.required=true;input.maxLength=128;label.append(input);form.append(label);const submit=node('button','Sign in');submit.type='submit';form.append(submit);content.append(form);form.onsubmit=async event=>{event.preventDefault();const token=input.value;input.value='';try{const result=await account.authenticate(token);state.csrf=result.csrf_token;state.caps=result.capabilities;live.start(state.project,state.record?.key||null);await refreshWorkspace();}catch(error){content.append(node('p',error.message,'error'));}};},controls);
  if(!['Unavailable','Sign in required','Service stopped'].includes(live.label))button('Retry connection',()=>refreshWorkspace({retry:true}),controls,!!refreshAttempt);
 }
 if(state.view==='projects-view'&&!['Sign in required','Service stopped'].includes(live.label)||!['Unavailable','Sign in required','Service stopped'].includes(live.label)){
  button('Refresh results',()=>refreshWorkspace(),controls,!!refreshAttempt);
  if(state.view==='workspace'&&state.record)button('Review changes',()=>refreshWorkspace({review:true}),controls,!!refreshAttempt);
 }
}
live.listeners.add(()=>{if($('live-review').open&&!refreshAttempt)connectionControls($('live-review-content'));});
$('freshness').onclick=async()=>{
 const content=$('live-review-content');content.replaceChildren();reviewInvoker=document.activeElement;if(!$('live-review').open)$('live-review').showModal();
 content.append(node('p',$('freshness').getAttribute('aria-label'),'live-current-status'));connectionControls(content);
 $('service-controls').hidden=true;$('stop-service-confirm').hidden=true;$('stop-service').disabled=false;$('stop-service').hidden=false;$('start-service').hidden=true;
 if(live.label==='Service stopped'){$('service-controls').hidden=false;$('service-status').textContent='Stopped';$('service-details').textContent='The backend is not running.';$('stop-service').hidden=true;$('start-service').hidden=false;return;}
 try{const r=await api('/api/v1/service/lifecycle');$('service-controls').hidden=false;$('service-status').textContent=r.data.state==='RUNNING'?'Running':'Stopping';$('service-details').textContent=r.data.operation_count+' active operations · '+r.data.lease_count+' protected drafts';$('stop-service').disabled=r.data.state!=='RUNNING';}catch{}
};

button('Review workspace updates',()=>$('freshness').click(),$('edit-form'));

const account=installAccount({$,state,api,signedIn,show,message,dirty,live,hasDraft:()=>dirty()||projectUI.dirty()||savedUI.dirty(),onReauthenticated:()=>projectUI.manager.reauthenticated()});

onSessionExpired(()=>{attention.session();account.requireSignin();});

measureHeader(document.querySelector('#projects-heading'),$('main-content'),'--projects-heading-height');
measureHeader(document.querySelector('#live-review>.dialog-heading'),$('live-review'),'--locked-heading-height');
