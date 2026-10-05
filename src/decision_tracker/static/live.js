/* Latest-state notifications never mutate displayed records or editor revisions. */
export function freshness(connected,latest,loaded){
 if(!connected||!latest)return 'gray';
 if(loaded.key&&(!latest.selected_exists||latest.decision_revision!==loaded.decisionRevision))return 'red';
 if(latest.ledger_revision!==loaded.listRevision||(loaded.key&&latest.context_fingerprint!==loaded.contextFingerprint))return 'yellow';
 return 'green';
}
export class LiveMonitor{
 constructor(loaded,render){this.loaded=loaded;this.render=render;this.generation=0;this.latest=null;this.connected=false;this.binding=null;}
 update(){this.render(freshness(this.connected,this.latest,this.loaded()),this.label);}
 stop(label='Disconnected'){this.generation++;this.controller?.abort();clearTimeout(this.timer);clearTimeout(this.watchdog);this.binding=null;this.latest=null;this.connected=false;this.label=label;this.update();}
 start(project,key){this.stop(project?'Connecting':'Select project');if(!project)return;this.binding={project:project.project_id,uuid:project.ledger_uuid,key};this.attempt=0;this.connect(this.generation);}
 async connect(generation){
  if(generation!==this.generation||!this.binding)return;
  const bound=this.binding;const controller=this.controller=new AbortController();let terminal=false,retryAfter=0;
  const heartbeat=()=>{clearTimeout(this.watchdog);this.watchdog=setTimeout(()=>controller.abort(),45000);};
  try{
   heartbeat();
   const q=bound.key?'?decision_key='+encodeURIComponent(bound.key):'';
   const response=await fetch('/api/v1/projects/'+encodeURIComponent(bound.project)+'/events'+q,{headers:{'X-Ledger-UUID':bound.uuid},credentials:'same-origin',signal:controller.signal});
   if(!response.ok){terminal=[400,401,403,404,409,422].includes(response.status);this.label=response.status===401?'Sign in required':terminal?'Unavailable':'Disconnected';retryAfter=Math.min(60,Math.max(0,Number(response.headers.get('Retry-After'))||0))*1000;throw Error('Live connection unavailable');}
   if(!response.headers.get('content-type')?.startsWith('text/event-stream'))throw Error('Invalid live response');
   const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});let buffer='';
   while(true){
    const {value,done}=await reader.read();if(done)break;
    if(generation!==this.generation)return;
    buffer+=decoder.decode(value,{stream:true});if(new TextEncoder().encode(buffer).length>16384)throw Error('Live buffer limit');
    let match;
    while((match=/\r?\n\r?\n/.exec(buffer))){
     const frame=buffer.slice(0,match.index);buffer=buffer.slice(match.index+match[0].length);
     if(new TextEncoder().encode(frame).length>8192)throw Error('Live event limit');
     heartbeat();let type='message',data=[];
     for(const line of frame.split(/\r?\n/)){if(line.startsWith('event:'))type=line.slice(6).trim();if(line.startsWith('data:'))data.push(line.slice(5).trimStart());}
     if(type==='service-stopping'){terminal=true;this.label='Service stopped';throw Error('Service stopped');}
     if(type==='unavailable'){terminal=true;this.label='Unavailable';throw Error('Live access changed');}
     if(type!=='state')continue;
     const state=JSON.parse(data.join('\n'));
     if(state.version!==1||state.project_id!==bound.project||state.ledger_uuid!==bound.uuid||state.decision_key!==bound.key||!Number.isSafeInteger(state.ledger_revision)||state.ledger_revision<0)throw Error('Invalid live identity');
     if(this.latest&&state.ledger_revision<this.latest.ledger_revision)continue;
     this.latest=state;this.connected=true;this.attempt=0;this.label=null;this.update();
    }
   }
  }catch(error){/* Visible state below; no automatic record reload. */}
  finally{controller.abort();if(generation===this.generation)clearTimeout(this.watchdog);}
  if(generation!==this.generation)return;
  this.connected=false;this.label=this.label||'Disconnected';this.update();
  if(!terminal){const delay=Math.max(retryAfter,Math.min(30000,1000*2**Math.min(this.attempt++,5))*(.8+Math.random()*.4));this.timer=setTimeout(()=>this.connect(generation),delay);}
 }
}
