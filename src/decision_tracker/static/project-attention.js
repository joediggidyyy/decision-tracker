export function validAttention(r,p){
 const a=r?.data?.attention,R=r?.revision;
 if(r?.project_id!==p.project_id||r?.ledger_uuid!==p.ledger_uuid||!Number.isSafeInteger(R)||R<0||a?.version!==1||!Number.isSafeInteger(a.open_count)||a.open_count<0||!(a.open_count===0?a.latest_open_revision===null:Number.isSafeInteger(a.latest_open_revision)&&a.latest_open_revision>=0&&a.latest_open_revision<=R))throw Error('Decision attention unavailable');
 return {revision:R,...a};
}
export function parseAcknowledgement(raw){try{const v=JSON.parse(raw);return v?.version===1&&Object.keys(v).length===2&&Number.isSafeInteger(v.acknowledged_revision)&&v.acknowledged_revision>=0?v.acknowledged_revision:null;}catch{return null;}}
export function needsAttention(data,ack){return data.open_count>0&&(ack===null||data.latest_open_revision>ack);}
export function installProjectAttention({$,state,read}){
 const cache=new Map(),memory=new Map();let epoch=0,controllers=new Set(),active=0,waiters=[],degraded=false;
 const current=p=>state.csrf&&state.principal&&state.projects.some(x=>x.project_id===p.project_id&&x.ledger_uuid===p.ledger_uuid&&x.enabled);
 const storageKey=p=>'decision-tracker:project-attention:v1:'+encodeURIComponent(state.principal)+':'+p.ledger_uuid;
 function storageFailure(){degraded=true;let n=$('project-attention-notice');if(!n){n=document.createElement('p');n.id='project-attention-notice';n.className='muted';$('project-admin').before(n);}n.textContent='Attention acknowledgements will not persist in this browser.';}
 function acknowledgement(p){const key=storageKey(p);try{if(!degraded)return parseAcknowledgement(localStorage.getItem(key));}catch{storageFailure();}return memory.get(key)??null;}
 function put(p,value){const key=storageKey(p);memory.set(key,value);try{if(!degraded){if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,JSON.stringify({version:1,acknowledged_revision:value}));}}catch{storageFailure();}}
 function align(){for(const row of $('project-admin').querySelectorAll('.project-row')){const button=row.querySelector('.project-name'),marker=row.querySelector('.project-attention-dot');if(!button||!marker)continue;const range=document.createRange();range.selectNodeContents(button);const first=range.getClientRects()[0];if(first)marker.style.top=(first.top-row.getBoundingClientRect().top+first.height/2-3)+'px';}}
 function paint(){
  for(const row of $('project-admin').querySelectorAll('.project-row')){
   const p=state.projects.find(x=>x.project_id===row.dataset.project),button=row.querySelector('.project-name');if(!p||!button)continue;
   const value=cache.get(p.ledger_uuid);let label='',kind='clear';
   if(p.enabled){if(!value){kind='checking';label='Checking decision attention';}else if(value.error){kind='unknown';label='Decision attention unavailable; Refresh to retry';}else if(needsAttention(value,acknowledgement(p))){kind='unviewed';label='Unviewed open decisions';}}
   row.dataset.attention=kind;let marker=row.querySelector('.project-attention-dot');if(!marker){marker=document.createElement('i');marker.className='project-attention-dot';marker.setAttribute('aria-hidden','true');row.append(marker);}marker.hidden=kind==='clear';
   button.title=label;let description=row.querySelector('.project-attention-description');if(!description){description=document.createElement('span');description.className='sr-only project-attention-description';description.id='project-attention-'+p.project_id;row.append(description);}description.textContent=label;if(label)button.setAttribute('aria-describedby',description.id);else button.removeAttribute('aria-describedby');
  }align();
 }
 function cancel(){epoch++;for(const c of controllers)c.abort();controllers.clear();}
 function session(){cancel();cache.clear();memory.clear();degraded=false;$('project-attention-notice')?.remove();paint();}
 function begin(){const c=new AbortController();controllers.add(c);const timer=setTimeout(()=>c.abort(),20000);return {c,ticket:epoch,finish(){clearTimeout(timer);controllers.delete(c);}};}
 async function collect(p,operation){
  const {c,ticket}=operation;while(active>=2){await new Promise(resolve=>{waiters.push(resolve);c.signal.addEventListener('abort',resolve,{once:true});});c.signal.throwIfAborted();}
  c.signal.throwIfAborted();active++;let timer;const request=new AbortController(),abort=()=>request.abort();c.signal.addEventListener('abort',abort,{once:true});
  try{timer=setTimeout(abort,5000);const r=await read(p,request.signal);c.signal.throwIfAborted();if(ticket!==epoch||!current(p))throw Error('Attention binding changed');const value=validAttention(r,p),old=cache.get(p.ledger_uuid);if(!old||old.error||old.revision<=value.revision){cache.set(p.ledger_uuid,value);if(acknowledgement(p)>value.revision)put(p,null);}paint();return value;}
  finally{clearTimeout(timer);c.signal.removeEventListener('abort',abort);active--;const pending=waiters;waiters=[];pending.forEach(resolve=>resolve());}
 }
 async function sweep(selectedOnly=false){
  if(!state.csrf||!state.principal||state.view!=='projects-view'||document.hidden)return;
  cancel();const operation=begin(),rows=state.projects.filter(p=>p.enabled&&(!selectedOnly||p.ledger_uuid===state.project?.ledger_uuid)).sort((a,b)=>(b.ledger_uuid===state.project?.ledger_uuid)-(a.ledger_uuid===state.project?.ledger_uuid)||a.project_id.localeCompare(b.project_id));
  for(const p of rows)cache.delete(p.ledger_uuid);paint();
  const worker=async()=>{while(rows.length&&!operation.c.signal.aborted){const p=rows.shift();try{await collect(p,operation);}catch{if(operation.ticket===epoch&&current(p))cache.set(p.ledger_uuid,{error:true});}}};
  try{await Promise.all([worker(),worker()]);if(operation.ticket===epoch){for(const p of rows)cache.set(p.ledger_uuid,{error:true});paint();}}finally{operation.finish();}
 }
 async function acknowledge(p,expected=null,reload=null){
  if(!p?.enabled||!current(p))return;const operation=begin();
  try{for(let attempt=0;attempt<2;attempt++){const value=await collect(p,operation);if(expected!==null&&value.revision!==expected){if(attempt||!reload)return;expected=await reload(operation.c.signal);continue;}if(operation.ticket!==epoch||!current(p))return;put(p,Math.max(acknowledgement(p)??0,value.revision));paint();return;}}
  catch{/* Attention is optional. Existing navigation/session handling remains available. */}finally{operation.finish();}
 }
 if(globalThis.ResizeObserver)new ResizeObserver(align).observe($('project-admin'));
 window.addEventListener('storage',e=>{if(e.key===null||e.key.startsWith('decision-tracker:project-attention:v1:'))paint();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)cancel();});
 return {paint,cancel,session,sweep,acknowledge};
}
