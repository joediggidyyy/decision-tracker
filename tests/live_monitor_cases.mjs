import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(process.argv[2],'utf8');
const {freshness,LiveMonitor}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const loaded={key:'D000001',decisionRevision:1,listRevision:1,contextFingerprint:'abc'};
const latest={version:1,project_id:'alpha',ledger_uuid:'uuid',ledger_revision:1,decision_key:'D000001',decision_revision:1,selected_exists:true,context_fingerprint:'abc'};
assert.equal(freshness(false,latest,loaded),'gray');
assert.equal(freshness(true,latest,loaded),'green');
assert.equal(freshness(true,{...latest,ledger_revision:2},loaded),'yellow');
assert.equal(freshness(true,{...latest,decision_revision:2},loaded),'red');
assert.equal(freshness(true,{...latest,context_fingerprint:'changed'},loaded),'yellow');
assert.equal(freshness(true,{...latest,selected_exists:false},loaded),'red');
const encoder=new TextEncoder();
async function observe(chunks,ok=true,status=200){
 let accepted=false;
 globalThis.fetch=async(url,options)=>{
  assert.equal(url,'/api/v1/projects/alpha/events?decision_key=D000001');assert.equal(options.headers['X-Ledger-UUID'],'uuid');assert.equal(options.credentials,'same-origin');
  if(!ok)return {ok:false,status,headers:new Headers()};
  return new Response(new ReadableStream({start(controller){for(const chunk of chunks)controller.enqueue(chunk);options.signal.addEventListener('abort',()=>{try{controller.error(new Error('aborted'));}catch{}});}}),{headers:{'Content-Type':'text/event-stream'}});
 };
 const monitor=new LiveMonitor(()=>loaded,color=>{if(color==='green')accepted=true;});
 monitor.start({project_id:'alpha',ledger_uuid:'uuid'},'D000001');
 await new Promise(resolve=>setTimeout(resolve,30));
 const result={accepted,connected:monitor.connected,latest:monitor.latest,label:monitor.label};monitor.stop();await new Promise(resolve=>setTimeout(resolve,0));return result;
}
const frame=encoder.encode(': \u2665\r\n\r\nevent: state\r\ndata: '+JSON.stringify(latest)+'\r\n\r\n');
assert.equal((await observe([...frame].map(byte=>Uint8Array.of(byte)))).accepted,true);
assert.equal((await observe([encoder.encode('event: state\ndata: broken\n\n')])).accepted,false);
assert.equal((await observe([encoder.encode('event: state\ndata: '+JSON.stringify({...latest,ledger_uuid:'wrong'})+'\n\n')])).accepted,false);
assert.equal((await observe([encoder.encode('x'.repeat(17000))])).accepted,false);
assert.equal((await observe([],false,401)).label,'Sign in required');
const missing=encoder.encode('event: unavailable\ndata: {}\n\n');assert.equal((await observe([missing])).label,'Unavailable');
const backwards=encoder.encode('event: state\ndata: '+JSON.stringify({...latest,ledger_revision:0})+'\n\n');assert.equal((await observe([frame,backwards])).latest.ledger_revision,1);
console.log('monitor cases passed');
