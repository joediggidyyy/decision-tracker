import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const load=async name=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(new URL('../src/decision_tracker/static/'+name,import.meta.url),'utf8')).toString('base64'));
const {collectProjects,collectWorkspace}=await load('refresh.js'),{YellowSync}=await load('yellow-sync.js');
const project={project_id:'alpha',ledger_uuid:'uuid',enabled:true},signal=new AbortController().signal;
let catalogRevision=1,drift=false,reads=[];
const read=async path=>{reads.push(path);if(path==='/api/v1/projects')return {catalog_revision:catalogRevision++,data:[project]};throw Error('Unexpected project read');};
await assert.rejects(()=>collectProjects(read,null,signal),e=>e.code==='REFRESH_CHANGED');
let page=0;
const coherent=async path=>{
 if(path==='/api/v1/projects')return {catalog_revision:1,data:[project]};
 if(path.endsWith('/summary'))return {project_id:'alpha',ledger_uuid:'uuid',revision:8,data:{counts:{open:1,closed:0,deprecated:0}}};
 return {project_id:'alpha',ledger_uuid:drift?'wrong':'uuid',revision:8,next_cursor:page++%2===0?'next':null,complete:true,data:{roots:[],entries:[{kind:'document',path:path}]}};
};
const candidate=await collectProjects(coherent,project,signal);assert.equal(candidate.regions.sources.entries.length,2);assert.equal(candidate.regions.revision,8);
drift=true;await assert.rejects(()=>collectProjects(coherent,project,signal),e=>e.code==='LEDGER_IDENTITY_MISMATCH');drift=false;
const disabled={...project,enabled:false};let calls=0;await collectProjects(async path=>{calls++;assert.equal(path,'/api/v1/projects');return {catalog_revision:1,data:[disabled]};},disabled,signal);assert.equal(calls,2);
let listCalls=0;const list=await collectWorkspace(async()=>({revision:3,data:[{key:'D'+(++listCalls)}],next_cursor:listCalls<3?'c'+listCalls:null}),'/projects/alpha','q=',null,signal,3);assert.equal(list.list.data.length,3);assert.equal(list.revision,3);
let now=0,timers=new Map(),serial=0,color='yellow',binding='workspace\0alpha\0uuid',hidden=false,allowed=true,attempts=0,fail=false,hold=false,resolveRun,errors=0;
const sync=new YellowSync({snapshot:()=>({color,binding,hidden}),eligible:()=>allowed,now:()=>now,timer:(fn,delay)=>{timers.set(++serial,{fn,at:now+delay});return serial;},cancel:id=>timers.delete(id),failure:()=>errors++,run:async signal=>{attempts++;if(fail)throw Error('Offline');if(hold)await new Promise(resolve=>{resolveRun=resolve;signal.addEventListener('abort',resolve,{once:true});});else color='green';}});
const advance=async ms=>{const until=now+ms;for(let n=0;n<500;n++){const next=[...timers.entries()].filter(([,t])=>t.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;timers.delete(next[0]);now=next[1].at;next[1].fn();for(let j=0;j<5;j++)await Promise.resolve();}now=until;};
sync.observe('one');await advance(999);assert.equal(attempts,0);await advance(1);assert.equal(attempts,1);assert.equal(color,'green');
color='yellow';sync.observe('two');allowed=false;await advance(5000);assert.equal(attempts,1);allowed=true;sync.activity();await advance(1000);assert.equal(attempts,2);
color='yellow';fail=true;sync.observe('three');await advance(5000);assert.equal(attempts,3);assert.equal(errors,1);await advance(20000);assert.equal(attempts,3);
binding='projects\0alpha\0uuid';sync.observe('four');await advance(1000);assert.equal(attempts,4);binding='workspace\0alpha\0uuid';sync.observe('five');await advance(5000);assert.equal(attempts,4); // navigation cannot reset suspension
fail=false;sync.recovered(binding);await advance(1000);assert.equal(attempts,5);
color='yellow';hold=true;sync.observe('six');await advance(5000);assert.equal(attempts,6);sync.activity();await advance(500);assert.equal(errors,2);hold=false;resolveRun?.();color='red';sync.observe('red');await advance(10000);assert.equal(attempts,6);
color='yellow';hidden=true;sync.observe('hidden');await advance(10000);assert.equal(attempts,6);sync.stop();
console.log('browser update cases passed');
