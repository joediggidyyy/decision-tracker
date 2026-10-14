import {placeControlHelp} from './page-layout.js';
import {sessionFetch} from './session.js';
// Projects shares the application shell; catalog drafts stay in memory.
import {sendRetained,definitive} from './save-request.js';
import {installFileManager} from './file-manager.js';
export function projectSlug(name,used=[]){
 let base=name.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'project';
 if(!/^[a-z]/.test(base))base='project-'+base;base=base.slice(0,48).replace(/-$/,'');
 let value=base,n=2;while(used.includes(value)){const suffix='-'+n++;value=base.slice(0,48-suffix.length).replace(/-$/,'')+suffix;}return value;
}
export function installProjects({$,state,node,button,api,projects,selectProject,show,detail,listing,message,readResponse,viewDecisions}){
 let generation=0,draft=null,leave=null,administrative=undefined,accessPending=false;
 const loads=new Map();
 const manager=installFileManager({$,state,node,button,api});
 $('backups-button').onclick=()=>manager.open('backup');$('exports-button').onclick=()=>manager.open('export');
 $('verify-button').onclick=async()=>{const p=selected(),ticket=generation,b=$('verify-button');if(!p?.enabled||p.project_id!==state.project?.project_id||p.ledger_uuid!==state.project?.ledger_uuid)return;b.disabled=true;try{const r=await api(binding(p)+'/verify',{});if(current(p,ticket))manager.result($('data-result'),'Passed. Current project data is valid.',r.data);}catch(e){if(current(p,ticket))manager.result($('data-result'),e.message);}finally{const active=selected();b.disabled=!active?.enabled||active.project_id!==state.project?.project_id||active.ledger_uuid!==state.project?.ledger_uuid;}};
 const help=$('admin-info'),tip=$('admin-help');function hideHelp(){tip.hidden=true;help.setAttribute('aria-expanded','false');}function showHelp(){tip.hidden=false;help.setAttribute('aria-expanded','true');placeControlHelp(help,tip);}help.onclick=()=>tip.hidden?showHelp():hideHelp();help.onpointerenter=showHelp;help.onpointerleave=()=>{if(document.activeElement!==help)hideHelp();};help.onfocus=showHelp;help.onblur=hideHelp;help.onkeydown=e=>{if(e.key==='Escape')hideHelp();};
 const capability=name=>state.caps.includes(name);
 const error=(target,e)=>{target.hidden=false;target.textContent=e.message||String(e);};
 const binding=p=>'/api/v1/projects/'+encodeURIComponent(p.project_id);
 const current=(p,ticket)=>ticket===generation&&state.view==='projects-view'&&state.project?.project_id===p.project_id&&state.project?.ledger_uuid===p.ledger_uuid&&selected()?.project_id===p.project_id&&selected()?.ledger_uuid===p.ledger_uuid;
 function table(labels){const t=node('table',undefined,'admin-table'),head=node('thead'),row=node('tr'),body=node('tbody');for(const label of labels)row.append(node('th',label));head.append(row);t.append(head,body);return [t,body];}
 function cell(row,text){const td=node('td',text);row.append(td);return td;}
 function field(parent,label,name,attributes={}){const l=node('label',label),input=node('input');input.name=name;Object.assign(input,attributes);l.append(input);parent.append(l);return input;}
 function dirty(){return draft&&draft.initial!==new URLSearchParams(new FormData($('project-form'))).toString();}
 function close(){const invoker=draft?.invoker;draft=null;$('project-editor').close();invoker?.focus();}
 async function navigate(fn){if(manager.isBusy()||accessPending)return false;if(draft){if(draft.saving||draft.pending){error($('project-form-error'),Error('Resolve the pending save before leaving.'));return false;}if(dirty()){leave=fn;$('project-dirty').showModal();return false;}close();}manager.close();return (await fn())!==false;}
 $('project-cancel').onclick=()=>navigate(async()=>{});
 $('project-editor').oncancel=e=>{e.preventDefault();navigate(async()=>{});};
 $('project-dirty-keep').onclick=()=>{leave=null;$('project-dirty').close();};
 $('project-dirty').oncancel=()=>{leave=null;};
 $('project-dirty-discard').onclick=async()=>{const next=leave;leave=null;$('project-dirty').close();close();await next?.();};
 $('project-dirty-save').onclick=()=>{$('project-dirty').close();$('project-form').requestSubmit();};
 $('project-signin').onclick=()=>$('account-toggle').click();
 window.addEventListener('beforeunload',e=>{if(dirty()||draft?.pending){e.preventDefault();e.returnValue='';}});
 async function open(kind){
  draft={kind,requestId:crypto.randomUUID(),revision:state.catalogRevision,invoker:document.activeElement,pending:null,saving:false,manual:false,candidates:[]};
  const d=draft,fields=$('project-fields');fields.replaceChildren();$('project-form-error').hidden=true;$('project-recovery').replaceChildren();
  $('project-editor-title').textContent=kind==='create'?'New project':'Add existing project';$('project-save').textContent=kind==='create'?'Create project':'Add project';$('project-save').disabled=false;
  const name=field(fields,'Name','name',{required:true,maxLength:160});
  const idDetails=node('details'),summary=node('summary','Optional details'),preview=node('p',undefined,'muted');idDetails.append(summary);fields.append(preview,idDetails);
  const id=field(idDetails,'ID','project_id',{required:true,maxLength:48,pattern:'[a-z][a-z0-9-]{0,47}'});
  idDetails.append(node('p','Start with a lowercase letter. Use letters, numbers and hyphens; up to 48 characters.','field-hint'));
  function suggest(){if(!d.manual)id.value=projectSlug(name.value,state.projects.map(p=>p.project_id));preview.textContent='ID: '+id.value;}
  name.addEventListener('input',suggest);id.addEventListener('input',()=>{d.manual=true;preview.textContent='ID: '+id.value;});suggest();
  if(kind==='register'){
   fields.append(node('p','Adds a project; does not replace another project.'));
   const label=node('label','Prepared project'),picker=node('select');picker.name='candidate_id';picker.required=true;picker.append(new Option('Choose a project',''));label.append(picker);fields.append(label);
   const info=node('div'),more=node('div');fields.append(info,more);let cursor=null;
   const load=async()=>{try{const r=await api('/api/v1/candidates'+(cursor?'?cursor='+encodeURIComponent(cursor):''));if(draft!==d)return;d.candidates.push(...r.data);for(const c of r.data)picker.add(new Option(c.ledger_uuid.slice(0,8)+' · revision '+c.ledger_revision+' · '+new Date(c.prepared_at).toLocaleString(),c.candidate_id));cursor=r.next_cursor;more.replaceChildren();if(cursor)button('Load more',load,more);if(!d.candidates.length)info.replaceChildren(node('p','No prepared projects available.'),node('p','Import and prepare a project through the CLI or API.'));}catch(e){if(draft!==d)return;if(e.code==='CURSOR_STALE'){cursor=null;d.candidates=[];picker.replaceChildren(new Option('Choose a project',''));await load();}else error($('project-form-error'),e);}};
   picker.onchange=()=>{info.replaceChildren();const c=d.candidates.find(c=>c.candidate_id===picker.value);if(!c)return;info.append(node('p','Revision '+c.ledger_revision+' · data version '+c.schema_version));if(c.schema_version<2)info.append(node('p','Read-only until upgraded.','notice'));const details=node('details');details.append(node('summary','Details'),node('p','Identity: '+c.ledger_uuid),node('p','Prepared: '+new Date(c.prepared_at).toLocaleString()));info.append(details);};
   d.reloadCandidates=async()=>{cursor=null;d.candidates=[];picker.replaceChildren(new Option('Choose a project',''));info.replaceChildren();await load();};
   load();
  }
  d.initial=new URLSearchParams(new FormData($('project-form'))).toString();$('project-editor').showModal();name.focus();
 }
 $('project-form').addEventListener('invalid',e=>{e.target.closest('details')?.setAttribute('open','');},true);
 $('new-project').onclick=()=>open('create');$('add-existing').onclick=()=>open('register');
 async function saved(result){administrative=undefined;const next=leave;leave=null;close();message('Project saved.');try{await projects();await selectProject(result.data.project_id);await next?.();}catch{message('Saved; refresh to see current data.');}}
 $('project-form').onsubmit=async event=>{
  event.preventDefault();const d=draft;if(!d||d.saving)return;d.saving=true;$('project-save').disabled=true;$('project-form-error').hidden=true;$('project-recovery').replaceChildren();
  try{
   const values=Object.fromEntries(new FormData(event.target));values.name=values.name.trim();if(!values.name)throw Error('Enter a project name.');
   if(d.kind==='register'){const c=d.candidates.find(c=>c.candidate_id===values.candidate_id);if(!c)throw Error('Choose a prepared project.');values.expected_candidate_digest=c.logical_digest;}
   const body={...values,kind:d.kind,expected_catalog_revision:d.revision,request_id:d.requestId};
   await saved(await sendRetained(d,body,b=>api('/api/v1/projects',b)));
  }catch(e){
   error($('project-form-error'),e);
   if(definitive(e)){d.pending=null;d.requestId=crypto.randomUUID();}
   const recovery=$('project-recovery');
   if(['CANDIDATE_CHANGED','CANDIDATE_UNPREPARED','DUPLICATE_LEDGER'].includes(e.code))button('Review prepared projects',()=>d.reloadCandidates?.(),recovery);
   if(d.pending){button('Retry original save',async()=>{if(d.saving)return;d.saving=true;try{await saved(await api('/api/v1/projects',JSON.parse(d.pending)));}catch(err){if(definitive(err)){d.pending=null;d.requestId=crypto.randomUUID();recovery.replaceChildren();}error($('project-form-error'),err);}finally{d.saving=false;}},recovery);}
   else if(['PROJECT_EXISTS','STALE_REVISION','REVISION_CONFLICT'].includes(e.code)||e.code?.includes('STALE')){
    button('Review current projects',async()=>{await projects();const suggested=projectSlug(valuesName(),state.projects.map(p=>p.project_id));recovery.replaceChildren(node('p','Current catalog loaded. Suggested ID: '+suggested));button('Use ID',()=>{const input=$('project-fields').querySelector('[name=project_id]');input.value=suggested;input.dispatchEvent(new Event('input'));d.revision=state.catalogRevision;recovery.replaceChildren(node('p','Review the form, then save.'));},recovery);button('Keep ID',()=>{d.revision=state.catalogRevision;recovery.replaceChildren(node('p','Review the form, then save.'));},recovery);},recovery);
   }
  }finally{d.saving=false;$('project-save').disabled=false;}
 };
 function valuesName(){return $('project-fields').querySelector('[name=name]').value;}
 async function stateChange(p){
  const operation={pending:null},body={enabled:!p.enabled,expected_catalog_revision:state.catalogRevision,request_id:crypto.randomUUID()};
  const dialog=$('project-confirm');$('project-confirm-title').textContent=p.enabled?'Disable project':'Enable project';$('project-confirm-text').textContent=(p.enabled?'Disable ':'Enable ')+p.name+'? '+(p.enabled?'This hides access and retains its data.':'This restores access to its data.');$('project-confirm-error').hidden=true;
  const submit=$('project-confirm-save');submit.textContent=p.enabled?'Disable':'Enable';submit.disabled=false;
  const cancel=$('project-confirm-cancel');cancel.disabled=false;cancel.onclick=()=>dialog.close();dialog.oncancel=e=>{if(operation.pending)e.preventDefault();};
  submit.onclick=async()=>{accessPending=true;submit.disabled=cancel.disabled=true;try{
   await sendRetained(operation,body,async payload=>{const r=await sessionFetch(binding(p)+'/state',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf,'X-Ledger-UUID':p.ledger_uuid},body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)});const value=await readResponse(r);if(!r.ok){const e=Error(value.error?.message||'Could not change project access.');e.code=value.error?.code;throw e;}return value;});
   operation.pending=null;message('Project access saved.');try{await projects();administrative={id:p.project_id,uuid:p.ledger_uuid};if(body.enabled||state.project?.project_id===p.project_id)await selectProject(p.project_id);await render();}catch{message('Saved; refresh to see current data.');}dialog.close();
  }catch(e){error($('project-confirm-error'),e);if(definitive(e)){operation.pending=null;cancel.disabled=false;if(e.code?.includes('STALE')||e.code==='REVISION_CONFLICT'){const target=$('project-confirm-error');button('Review current state',async()=>{await projects();const row=state.projects.find(x=>x.project_id===p.project_id);if(row?.enabled===body.enabled){dialog.close();await render();return;}body.expected_catalog_revision=state.catalogRevision;body.request_id=crypto.randomUUID();target.textContent='Current state loaded. Review the project, then submit again.';},target);}}else submit.textContent='Retry';}finally{accessPending=!!operation.pending;submit.disabled=false;}};
  dialog.showModal();
 }
 function selected(){
  if(administrative===null)return null;
  if(administrative)return state.projects.find(p=>p.project_id===administrative.id&&p.ledger_uuid===administrative.uuid)||null;
  return state.projects.find(p=>p.project_id===state.project?.project_id&&p.ledger_uuid===state.project?.ledger_uuid)||null;
 }
 async function choose(p){return navigate(async()=>{administrative={id:p.project_id,uuid:p.ledger_uuid};if(p.enabled)await selectProject(p.project_id);await render();});}
 function renderBrowse(){
  const box=$('project-admin'),query=$('project-search').value.toLocaleLowerCase(),rows=state.projects.filter(p=>p.name.toLocaleLowerCase().includes(query)).sort((a,b)=>a.name.localeCompare(b.name)||a.project_id.localeCompare(b.project_id)),p=selected();box.replaceChildren();
  $('project-count').textContent=String(rows.length);
  for(const project of rows){const row=node('div',undefined,'project-row');row.dataset.project=project.project_id;const name=button(project.name,()=>choose(project),row);name.className='project-name';name.setAttribute('aria-pressed',String(project.project_id===p?.project_id&&project.ledger_uuid===p?.ledger_uuid));row.append(node('span',project.enabled?'Enabled':'Disabled','muted'));box.append(row);}
  if(!rows.length)box.append(node('p',state.projects.length?'No matching projects.':'No projects.','muted'));
  $('project-data-identity').querySelector('[data-outside]')?.remove();if(p&&!rows.includes(p)){const outside=node('p','Outside current filters','muted');outside.dataset.outside='';$('project-data-identity').append(outside);}
 }
 $('project-search').oninput=renderBrowse;
 function stamp(value){if(!value||!Number.isFinite(Date.parse(value)))return node('span','—');const t=node('time',new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'long'}).format(new Date(value)));t.dateTime=value;t.title=value;t.setAttribute('aria-label',value);return t;}
 function metadataRow(parent,label,value,{copy=false,muted=false}={}){
  const row=node('div',undefined,'project-metadata-row'),term=node('dt',label),description=node('dd');row.append(term,description);parent.append(row);
  if(copy){const feedback=node('span',undefined,'project-copy-feedback muted');feedback.setAttribute('role','status');const b=button(value,async()=>{try{if(!navigator.clipboard?.writeText)throw Error('Clipboard unavailable');await navigator.clipboard.writeText(value);if(feedback.isConnected)feedback.textContent='Copied';}catch{if(feedback.isConnected)feedback.textContent='Select and copy manually';}},description);b.className='project-copy-value'+(muted?' project-uuid muted':'');b.title='Copy';b.setAttribute('aria-label','Copy '+label);description.append(feedback);}
  else description.append(typeof value==='string'?node('span',value):value);
  return row;
 }
 async function loadRegion(kind,p,ticket,target){
  if(!current(p,ticket)||!target.isConnected)return;
  loads.get(kind)?.abort();const controller=new AbortController();loads.set(kind,controller);const timer=setTimeout(()=>controller.abort(),20000);target.replaceChildren(node('p','Loading…','muted'));
  if(kind==='summary')$('project-updated').replaceChildren(node('span','—'));
  const valid=()=>current(p,ticket)&&target.isConnected&&!controller.signal.aborted;
  try{
   if(kind==='summary'){
    const r=await api(binding(p)+'/summary',undefined,'GET',controller.signal);if(!valid())return;
    const data=r.data,list=node('dl',undefined,'project-metadata');for(const [status,label] of [['open','Open'],['closed','Closed'],['deprecated','Deprecated']]){if(!Number.isSafeInteger(data.counts?.[status])||data.counts[status]<0)throw Error('Invalid project summary');metadataRow(list,label,String(data.counts[status]));}
    metadataRow(list,'Latest decision activity',stamp(data.latest_activity_at));target.replaceChildren(list);target.dataset.revision=String(r.revision);$('project-updated').replaceChildren(stamp(data.last_write_at));
   }else{
    let cursor=null,revision=null,roots=[],rows=[];const seen=new Set();
    do{const r=await api(binding(p)+'/planning-documents?limit=200'+(cursor?'&cursor='+encodeURIComponent(cursor):''),undefined,'GET',controller.signal);if(!valid())return;if(revision!==null&&r.revision!==revision)throw Error('Sources changed; retry');revision=r.revision;roots=r.data.roots||[];rows.push(...r.data.entries.filter(x=>x.kind==='document'));cursor=r.next_cursor;if(!cursor&&!r.complete)throw Error('Source inventory incomplete');if(cursor&&seen.has(cursor))throw Error('Source cursor repeated');if(cursor)seen.add(cursor);}while(cursor);
    const unique=[...new Map(rows.map(x=>[x.path.replaceAll('\\','/').toLowerCase()+'\0'+x.document_id,x])).values()],names=new Map();for(const row of unique){row.name=row.path.split(/[\\/]/).pop();names.set(row.name,(names.get(row.name)||0)+1);}
    unique.sort((a,b)=>a.name.localeCompare(b.name)||a.path.localeCompare(b.path));const list=node('ul',undefined,'project-source-list');for(const row of unique){let label=row.name;if(names.get(row.name)>1){const normalized=row.path.replaceAll('\\','/'),root=roots.find(r=>normalized.toLowerCase().startsWith(r.path.replaceAll('\\','/').replace(/\/$/,'').toLowerCase()+'/'));label=root?root.name+'/'+normalized.slice(root.path.replaceAll('\\','/').replace(/\/$/,'').length+1):row.document_id+' · '+row.name;}const item=node('li'),link=node('a',label,'project-source-inactive');link.setAttribute('role','link');link.setAttribute('aria-disabled','true');link.tabIndex=-1;item.append(link);list.append(item);}target.replaceChildren(unique.length?list:node('p','No sources','muted'));
   }
  }catch(e){if(current(p,ticket)&&target.isConnected&&loads.get(kind)===controller){const stateRow=node('div',undefined,'project-load-state');stateRow.append(node('p',kind==='summary'?'Summary unavailable':'Sources unavailable','muted'));button('Retry',()=>loadRegion(kind,p,ticket,target),stateRow);target.replaceChildren(stateRow,node('p',controller.signal.aborted?'Request timed out. Retry when available.':e.message,'project-load-error'));}}
  finally{clearTimeout(timer);if(loads.get(kind)===controller)loads.delete(kind);}
 }
 async function render(){
  generation++;for(const c of loads.values())c.abort();loads.clear();const p=selected(),ticket=generation;if(administrative&&!p)administrative=null;
  const identity=$('project-data-identity'),tools=$('project-data-actions');identity.replaceChildren();const header=node('div',undefined,'project-context-row'),access=node('div',undefined,'project-access-actions');header.append(node('h2',p?p.name:'Choose project','data-project'),tools,access);identity.append(header);
  if(p&&capability('registry'))button(p.enabled?'Disable':'Enable',()=>stateChange(p),access);access.append(help,tip);
  if(p){const metadata=node('dl',undefined,'project-metadata project-identity-metadata');metadataRow(metadata,'Project ID',p.project_id,{copy:true});metadataRow(metadata,'Ledger UUID',p.ledger_uuid,{copy:true,muted:true});metadataRow(metadata,'State',p.enabled?'Enabled':'Disabled');metadataRow(metadata,'Registered',stamp(p.created_at));const updated=metadataRow(metadata,'Updated',node('span','—'));updated.querySelector('dd').id='project-updated';identity.append(metadata);}
  renderBrowse();
  for(const [id,c] of [['backups-button','read'],['exports-button','read'],['verify-button','maintain']]){$(id).hidden=!capability(c);$(id).disabled=!p?.enabled||p.project_id!==state.project?.project_id||p.ledger_uuid!==state.project?.ledger_uuid;}
  const parent=$('maintenance'),previousResult=$('data-result');parent.replaceChildren();
  if(!p)return;
  const operational=p.enabled&&p.project_id===state.project?.project_id&&p.ledger_uuid===state.project?.ledger_uuid&&capability('read');
  const overview=node('section'),summary=node('div');summary.id='project-summary';overview.append(node('h3','Overview'),summary);parent.append(overview);
  const view=button('View decisions',()=>{if(current(p,ticket)&&p.enabled)viewDecisions();},parent,!operational);view.id='project-view-decisions';
  const sourceSection=node('section'),sources=node('div');sources.id='project-sources';sourceSection.append(node('h3','Sources'),sources);parent.append(sourceSection);
  if(!operational){summary.append(node('p','Unavailable','muted'));sources.append(node('p','Unavailable','muted'));return;}
  const context=p.project_id+'\0'+p.ledger_uuid,result=previousResult?.dataset.context===context?previousResult:node('div');result.id='data-result';result.dataset.context=context;parent.append(result);
  void loadRegion('summary',p,ticket,summary);void loadRegion('sources',p,ticket,sources);
 }
 return {render,navigate,dirty,manager,get selectionIdentity(){const p=selected();return p?p.project_id+'\0'+p.ledger_uuid:null;},bindSelection:p=>{administrative=p?{id:p.project_id,uuid:p.ledger_uuid}:null;}};
}
