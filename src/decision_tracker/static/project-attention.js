export function validAttention(r,p){
 const count=r?.data?.counts?.open,R=r?.revision;
 if(r?.project_id!==p.project_id||r?.ledger_uuid!==p.ledger_uuid||!Number.isSafeInteger(R)||R<0||!Number.isSafeInteger(count)||count<0)throw Error('Open decision count unavailable');
 return {revision:R,open_count:count};
}
export function needsAttention(data){return data.open_count>0;}
export function installProjectAttention({$,state,read}){
 const cache=new Map();let epoch=0,controllers=new Set(),active=0,waiters=[];
 const current=p=>state.csrf&&state.projects.some(x=>x.project_id===p.project_id&&x.ledger_uuid===p.ledger_uuid&&x.enabled);
 function align(){for(const row of $('project-admin').querySelectorAll('.project-row')){const button=row.querySelector('.project-name'),marker=row.querySelector('.project-attention-dot');if(!button||!marker)continue;const range=document.createRange();range.selectNodeContents(button);const first=range.getClientRects()[0];if(first)marker.style.top=(first.top-row.getBoundingClientRect().top+first.height/2-3)+'px';}}
 function paint(){
  for(const row of $('project-admin').querySelectorAll('.project-row')){
   const p=state.projects.find(x=>x.project_id===row.dataset.project),button=row.querySelector('.project-name');if(!p||!button)continue;
   const value=cache.get(p.ledger_uuid);let label='',kind='clear';
   if(p.enabled){if(!value){kind='checking';label='Checking open decision count';}else if(value.error){kind='unknown';label='Open decision count unavailable; Refresh to retry';}else if(needsAttention(value)){kind='open';label='Open decisions';}}
   row.dataset.attention=kind;let marker=row.querySelector('.project-attention-dot');if(!marker){marker=document.createElement('i');marker.className='project-attention-dot';marker.setAttribute('aria-hidden','true');row.append(marker);}marker.hidden=kind!=='open';
   button.title=label;let description=row.querySelector('.project-attention-description');if(!description){description=document.createElement('span');description.className='sr-only project-attention-description';description.id='project-attention-'+p.project_id;row.append(description);}description.textContent=label;if(label)button.setAttribute('aria-describedby',description.id);else button.removeAttribute('aria-describedby');
  }align();
 }
 function cancel(){epoch++;for(const c of controllers)c.abort();controllers.clear();}
 function session(){cancel();cache.clear();paint();}
 function begin(){const c=new AbortController();controllers.add(c);const timer=setTimeout(()=>c.abort(),20000);return {c,ticket:epoch,finish(){clearTimeout(timer);controllers.delete(c);}};}
 async function collect(p,operation){
  const {c,ticket}=operation;while(active>=2){await new Promise(resolve=>{waiters.push(resolve);c.signal.addEventListener('abort',resolve,{once:true});});c.signal.throwIfAborted();}
  c.signal.throwIfAborted();active++;let timer;const request=new AbortController(),abort=()=>request.abort();c.signal.addEventListener('abort',abort,{once:true});
  try{timer=setTimeout(abort,5000);const r=await read(p,request.signal);c.signal.throwIfAborted();if(ticket!==epoch||!current(p))throw Error('Attention binding changed');const value=validAttention(r,p),old=cache.get(p.ledger_uuid);if(!old||old.error||old.revision<=value.revision){cache.set(p.ledger_uuid,value);}paint();return value;}
  finally{clearTimeout(timer);c.signal.removeEventListener('abort',abort);active--;const pending=waiters;waiters=[];pending.forEach(resolve=>resolve());}
 }
 async function sweep(selectedOnly=false){
  if(!state.csrf||state.view!=='projects-view'||document.hidden)return;
  cancel();const operation=begin(),rows=state.projects.filter(p=>p.enabled&&(!selectedOnly||p.ledger_uuid===state.project?.ledger_uuid)).sort((a,b)=>(b.ledger_uuid===state.project?.ledger_uuid)-(a.ledger_uuid===state.project?.ledger_uuid)||a.project_id.localeCompare(b.project_id));
  // Keep the displayed count while a newer summary is collected.
  paint();
  const worker=async()=>{while(rows.length&&!operation.c.signal.aborted){const p=rows.shift();try{await collect(p,operation);}catch{if(operation.ticket===epoch&&current(p))cache.set(p.ledger_uuid,{error:true});}}};
  try{await Promise.all([worker(),worker()]);if(operation.ticket===epoch){for(const p of rows)cache.set(p.ledger_uuid,{error:true});paint();}}finally{operation.finish();}
 }
 if(globalThis.ResizeObserver)new ResizeObserver(align).observe($('project-admin'));

 document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
 return {paint,cancel,session,sweep};
}
