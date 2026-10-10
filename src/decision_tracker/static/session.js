/* Central session recovery covers API, downloads and live connections. */
let recover=()=>{},probe=null;
export function onSessionExpired(callback){recover=callback;}
export async function sessionFetch(path,options={}){
 let response;
 try{response=await fetch(path,options);}
 catch(error){
  if(error.name==='TypeError'&&!options.signal?.aborted)await checkSession();
  throw error;
 }
 if(response.status===401||response.status===403){
  if(path==='/api/v1/session'&&(!options.method||options.method==='GET')||String(path).includes('/events')){
   if(response.status===401)recover();
  }else await checkSession();
 }
 return response;
}
export async function checkSession(){
 if(!probe)probe=(async()=>{
  try{const response=await fetch('/api/v1/session',{credentials:'same-origin',signal:AbortSignal.timeout(5000)});if(response.status===401)recover();}
  catch{/* An outage is not evidence of an expired session. */}
 })().finally(()=>{probe=null;});
 await probe;
}
