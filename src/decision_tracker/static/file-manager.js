// One project-bound, bounded collection; no file content or selected IDs persist.
export function installFileManager({$,state,node,button,api}){
 const dialog=$('file-manager');let active=null,serial=0;
 const cap=c=>state.caps.includes(c);
 let pageSize=25;try{const n=Number(localStorage.getItem('dt.filePageSize'));if([10,25,50,100].includes(n))pageSize=n;}catch{}
 const bound=m=>state.project?.project_id===m.project.project_id&&state.project?.ledger_uuid===m.project.ledger_uuid&&state.project?.enabled;
 const valid=m=>active===m&&bound(m)&&dialog.open;
 function result(target,label,value={}){
  target.replaceChildren(node('p',label));
  const details=node('details'),list=node('dl',undefined,'result-details');details.append(node('summary','Details'),list);
  for(const [key,title] of [['integrity','Integrity'],['revision','Revision'],['ledger_uuid','Project identity'],['artifact_id','File ID'],['state','State'],['size','Bytes'],['logical_sha256','Content fingerprint'],['sha256','File fingerprint']])if(value[key]!==undefined)list.append(node('dt',title),node('dd',String(value[key]==='ok'?'Passed':value[key])));
  if(value.activated!==undefined)list.append(node('dt','Active data changed'),node('dd',value.activated?'Yes':'No'));
  if(list.children.length)target.append(details);
 }
 function close(){if(active?.busy)return;const m=active;active=null;serial++;dialog.close();m?.invoker?.focus();}
 $('file-close').onclick=close;dialog.oncancel=e=>{e.preventDefault();close();};
 $('file-account').onclick=()=>$('account-toggle').click();
 function controls(){const m=active;if(!m)return;const ready=m.selected?.state==='complete',allowed=valid(m)&&!m.busy&&!m.loading&&!m.stale&&!m.authExpired;
  $('file-download').disabled=!allowed||!ready;
  $('file-check').hidden=m.kind!=='backup';$('file-check').disabled=!allowed||!ready||!cap('maintain');
  $('file-create').disabled=!allowed||m.unknown||!cap(m.kind==='backup'?'maintain':'read');
  $('file-refresh').disabled=m.busy||m.loading;$('file-rows').disabled=m.busy||m.loading;
  $('file-prev').disabled=!allowed||!m.page?.previous_cursor;$('file-next').disabled=!allowed||!m.page?.next_cursor;
  $('file-close').disabled=m.busy;
  $('file-selected').textContent=m.selected?'Selected: '+new Date(m.selected.created_at).toLocaleDateString()+' · revision '+m.selected.revision+(ready?'':' · '+(m.selected.state==='pending'?'Pending':'Failed')+' — unavailable'):'Select a file.';
 }
 function dateCell(date){const d=new Date(date),time=node('time',undefined,'file-datetime');time.dateTime=date;time.append(node('span',d.toLocaleDateString()),node('span',d.toLocaleTimeString()));return time;}
 function draw(){const m=active,box=$('file-list');box.replaceChildren();
  if(!m.page?.data.length){box.append(node('p',m.kind==='backup'?'No backups yet.':'No exports yet.','muted'));return;}
  const t=node('table',undefined,'admin-table manager-table'),head=node('thead'),tr=node('tr'),body=node('tbody');
  for(const h of ['','Created','Revision','State'])tr.append(node('th',h));head.append(tr);t.append(head,body);box.append(t);
  for(const a of m.page.data){const row=node('tr');row.dataset.artifact=a.artifact_id;const select=node('td'),radio=node('input');radio.type='radio';radio.name='selected-file';radio.value=a.artifact_id;radio.setAttribute('aria-label','Select '+new Date(a.created_at).toLocaleString()+' revision '+a.revision);select.append(radio);row.append(select);
   for(const [label,value] of [['Created',dateCell(a.created_at)],['Revision',String(a.revision)],['State',a.state==='complete'?'Ready':a.state==='pending'?'Pending':'Failed']]){const td=node('td');td.dataset.label=label;typeof value==='string'?td.textContent=value:td.append(value);row.append(td);}
   const choose=()=>{if(m.busy||m.loading)return;m.selected=a;radio.checked=true;for(const r of body.children)r.classList.toggle('selected-file',r===row);$('file-result').replaceChildren();controls();if(a.state!=='complete')result($('file-result'),'This file is '+a.state+'; Download and Check are unavailable.',a);};
   radio.onchange=choose;row.onclick=choose;body.append(row);
  }
 }
 async function load(cursor=null){const m=active;if(!m||m.busy)return;const ticket=++serial;m.selected=null;m.loading=true;m.stale=false;$('file-result').replaceChildren();$('file-error').hidden=true;controls();
  try{const q=new URLSearchParams({kind:m.kind,order:'newest',limit:pageSize});if(cursor)q.set('cursor',cursor);const r=await api('/api/v1/projects/'+encodeURIComponent(m.project.project_id)+'/artifacts?'+q);
   if(!valid(m)||ticket!==serial)return;m.page=r;m.authExpired=false;draw();$('file-page').textContent='Page '+r.page_index+' of '+r.page_count+' · '+r.total_count+' files';
  }catch(e){if(active!==m||ticket!==serial)return;m.stale=e.code==='CURSOR_STALE';$('file-error').hidden=false;$('file-error').textContent=m.stale?'Files changed; refresh the list.':e.message;if(['PROJECT_DISABLED','LEDGER_IDENTITY_MISMATCH','FORBIDDEN','NOT_FOUND'].includes(e.code)){$('file-list').replaceChildren();m.stale=true;}if(e.code==='UNAUTHORIZED'){m.authExpired=true;$('file-account').hidden=false;}
  }finally{if(active===m&&ticket===serial){m.loading=false;controls();}}
 }
 function open(kind){if(!state.project?.enabled)return;active={kind,project:{...state.project},invoker:document.activeElement,selected:null,page:null,busy:false,loading:false,stale:false};$('file-title').textContent=kind==='backup'?'Backups':'Exports';$('file-project').textContent=active.project.name;$('file-create-result').replaceChildren();$('file-result').replaceChildren();$('file-account').hidden=true;$('file-rows').value=String(pageSize);dialog.showModal();load();}
 $('file-rows').onchange=()=>{pageSize=Number($('file-rows').value);try{localStorage.setItem('dt.filePageSize',pageSize);}catch{}load();};
 $('file-refresh').onclick=()=>load();$('file-prev').onclick=()=>load(active?.page?.previous_cursor);$('file-next').onclick=()=>load(active?.page?.next_cursor);
 $('file-create').onclick=async()=>{const m=active;if(!m||m.busy)return;m.busy=true;controls();$('file-create-result').replaceChildren(node('p','Creating…'));
  try{const r=await api('/api/v1/projects/'+encodeURIComponent(m.project.project_id)+'/'+(m.kind==='backup'?'backups':'exports'),{});if(!valid(m))return;result($('file-create-result'),'Created; refresh to see the file.',r.data);m.busy=false;await load();if(valid(m)&&$('file-error').hidden)$('file-create-result').querySelector('p').textContent='Created.';
  }catch(e){if(active!==m)return;m.unknown=!e.code||['SERVICE_UNAVAILABLE','INTERNAL_ERROR'].includes(e.code);result($('file-create-result'),m.unknown?'Outcome unknown. Refresh files to inspect; do not repeat Create until resolved.':e.message);if(e.code==='UNAUTHORIZED'){m.authExpired=true;$('file-account').hidden=false;}
  }finally{if(active===m){m.busy=false;controls();if(m.unknown)$('file-create').disabled=true;}}
 };
 $('file-check').onclick=async()=>{const m=active,a=m?.selected;if(!a||m.busy)return;m.busy=true;controls();try{const r=await api('/api/v1/projects/'+encodeURIComponent(m.project.project_id)+'/restore-check',{artifact_id:a.artifact_id});if(valid(m)&&m.selected===a)result($('file-result'),'Passed. Active data was not changed.',r.data);}catch(e){if(valid(m))result($('file-result'),e.message);if(e.code==='UNAUTHORIZED'){m.authExpired=true;$('file-account').hidden=false;}}finally{if(active===m){m.busy=false;controls();}}};
 $('file-download').onclick=async()=>{const m=active,a=m?.selected;if(!a||m.busy)return;m.busy=true;controls();try{const r=await fetch('/api/v1/projects/'+encodeURIComponent(m.project.project_id)+'/artifacts/'+a.artifact_id+'/content',{headers:{'X-Ledger-UUID':m.project.ledger_uuid},signal:AbortSignal.timeout(30000)});if(!r.ok)throw Error('Download unavailable. Refresh the list and try again.');const blob=await r.blob();if(!valid(m)||m.selected!==a)return;const url=URL.createObjectURL(blob),anchor=node('a');anchor.href=url;anchor.download=a.artifact_id+(m.kind==='backup'?'.sqlite':'.json');anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);result($('file-result'),'Download started.',a);}catch(e){if(valid(m))result($('file-result'),e.message);}finally{if(active===m){m.busy=false;controls();}}};
 window.addEventListener('beforeunload',e=>{if(active?.busy){e.preventDefault();e.returnValue='';}});
 return {open,close,result,isBusy:()=>!!active?.busy,reauthenticated:()=>{if(active){active.busy=false;load();}}};
}
