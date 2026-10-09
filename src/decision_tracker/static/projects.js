// Projects shares the application shell; catalog drafts stay in memory.
import {sendRetained,definitive} from './save-request.js';
import {installFileManager} from './file-manager.js';
export function projectSlug(name,used=[]){
 let base=name.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'project';
 if(!/^[a-z]/.test(base))base='project-'+base;base=base.slice(0,48).replace(/-$/,'');
 let value=base,n=2;while(used.includes(value)){const suffix='-'+n++;value=base.slice(0,48-suffix.length).replace(/-$/,'')+suffix;}return value;
}
export function installProjects({$,state,node,button,api,projects,selectProject,show,detail,listing,message,readResponse}){
 let generation=0,draft=null,leave=null;
 const manager=installFileManager({$,state,node,button,api});
 $('backups-button').onclick=()=>manager.open('backup');$('exports-button').onclick=()=>manager.open('export');
 $('verify-button').onclick=async()=>{const p=state.project,ticket=generation,b=$('verify-button');if(!p?.enabled)return;b.disabled=true;try{const r=await api(binding(p)+'/verify',{});if(current(p,ticket))manager.result($('data-result'),'Passed. Current project data is valid.',r.data);}catch(e){if(current(p,ticket))manager.result($('data-result'),e.message);}finally{b.disabled=false;}};
 const help=$('admin-info'),tip=$('admin-help');function hideHelp(){tip.hidden=true;help.setAttribute('aria-expanded','false');}function showHelp(){tip.hidden=false;help.setAttribute('aria-expanded','true');const r=help.getBoundingClientRect(),b=tip.getBoundingClientRect();tip.style.left=Math.max(18,Math.min(r.left,innerWidth-b.width-18))+'px';tip.style.top=Math.max(18,Math.min(r.bottom+6,innerHeight-b.height-18))+'px';}help.onclick=()=>tip.hidden?showHelp():hideHelp();help.onpointerenter=showHelp;help.onpointerleave=()=>{if(document.activeElement!==help)hideHelp();};help.onfocus=showHelp;help.onblur=hideHelp;help.onkeydown=e=>{if(e.key==='Escape')hideHelp();};
 const capability=name=>state.caps.includes(name);
 const error=(target,e)=>{target.hidden=false;target.textContent=e.message||String(e);};
 const binding=p=>'/api/v1/projects/'+encodeURIComponent(p.project_id);
 const current=(p,ticket)=>ticket===generation&&state.view==='projects-view'&&state.project?.project_id===p.project_id&&state.project?.ledger_uuid===p.ledger_uuid;
 function table(labels){const t=node('table',undefined,'admin-table'),head=node('thead'),row=node('tr'),body=node('tbody');for(const label of labels)row.append(node('th',label));head.append(row);t.append(head,body);return [t,body];}
 function cell(row,text){const td=node('td',text);row.append(td);return td;}
 function field(parent,label,name,attributes={}){const l=node('label',label),input=node('input');input.name=name;Object.assign(input,attributes);l.append(input);parent.append(l);return input;}
 function dirty(){return draft&&draft.initial!==new URLSearchParams(new FormData($('project-form'))).toString();}
 function close(){const invoker=draft?.invoker;draft=null;$('project-editor').close();invoker?.focus();}
 async function navigate(fn){if(manager.isBusy())return false;if(draft){if(draft.saving||draft.pending){error($('project-form-error'),Error('Resolve the pending save before leaving.'));return false;}if(dirty()){leave=fn;$('project-dirty').showModal();return false;}close();}manager.close();return (await fn())!==false;}
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
 async function saved(result){const next=leave;leave=null;close();message('Project saved.');try{await projects();await selectProject(result.data.project_id);await next?.();}catch{message('Saved; refresh to see current data.');}}
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
  submit.onclick=async()=>{submit.disabled=cancel.disabled=true;try{
   await sendRetained(operation,body,async payload=>{const r=await fetch(binding(p)+'/state',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf,'X-Ledger-UUID':p.ledger_uuid},body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)});const value=await readResponse(r);if(!r.ok){const e=Error(value.error?.message||'Could not change project access.');e.code=value.error?.code;throw e;}return value;});
   dialog.close();message('Project access saved.');try{await projects();if(state.project?.project_id===p.project_id)await selectProject(p.project_id);else await render();}catch{message('Saved; refresh to see current data.');}
  }catch(e){error($('project-confirm-error'),e);if(definitive(e)){operation.pending=null;cancel.disabled=false;if(e.code?.includes('STALE')||e.code==='REVISION_CONFLICT'){const target=$('project-confirm-error');button('Review current state',async()=>{await projects();const row=state.projects.find(x=>x.project_id===p.project_id);if(row?.enabled===body.enabled){dialog.close();await render();return;}body.expected_catalog_revision=state.catalogRevision;body.request_id=crypto.randomUUID();target.textContent='Current state loaded. Review the project, then submit again.';},target);}}else submit.textContent='Retry';}finally{submit.disabled=false;}};
  dialog.showModal();
 }
 async function render(){
  const ticket=++generation,box=$('project-admin');box.replaceChildren();
  const [t,body]=table(['Name','State','']);box.append(t);
  for(const p of state.projects){const row=node('tr');row.dataset.project=p.project_id;const name=cell(row);const select=button(p.name,()=>navigate(()=>selectProject(p.project_id)),name);select.className='project-name';select.setAttribute('aria-pressed',String(state.project?.project_id===p.project_id));cell(row,p.enabled?'Enabled':'Disabled');const action=cell(row);if(capability('registry'))button(p.enabled?'Disable':'Enable',()=>stateChange(p),action);[...row.children].forEach((td,i)=>td.dataset.label=['Name','State','Actions'][i]);body.append(row);}
  if(!state.projects.length)box.append(node('p','No projects yet.'));
  for(const [id,c] of [['backups-button','read'],['exports-button','read'],['verify-button','maintain']]){$(id).hidden=!capability(c);$(id).disabled=!state.project?.enabled;}
  const parent=$('maintenance');parent.replaceChildren(node('h2','Data','section-title'));
  const p=state.project;if(!p){parent.append(node('p','Choose a project to view its data.'));return;}
  parent.append(node('p',p.name,'data-project'));
  if(!p.enabled){parent.append(node('p','This project is disabled. Enable it to access its data.'));return;}
  const result=node('div');result.id='data-result';parent.append(result);
 }
 return {render,navigate,dirty,manager};
}
