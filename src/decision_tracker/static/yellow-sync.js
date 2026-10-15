/* One scheduler per document. Notifications request reads, never mutations. */
export class YellowSync{
 constructor({snapshot,eligible,run,failure,now=()=>performance.now(),timer=(fn,delay)=>setTimeout(fn,delay),cancel=id=>clearTimeout(id)}){Object.assign(this,{snapshot,eligible,run,failure,now,timer,cancel});this.suspended=new Set();this.lastStart=-Infinity;this.activityAt=now();this.eventAt=now();}
 observe(token){const s=this.snapshot();if(s.binding!==this.binding){this.controller?.abort();this.binding=s.binding;this.token=null;}if(token!==this.token){this.token=token;this.eventAt=this.now();}this.wake();}
 activity(){this.activityAt=this.now();this.controller?.abort();this.wake();}
 recovered(binding){this.suspended.delete(binding);this.wake();}
 wake(){this.cancel(this.timeout);const s=this.snapshot();if(this.controller||!s.binding||s.color!=='yellow'||s.hidden||this.suspended.has(s.binding))return;const delay=Math.max(0,1000-(this.now()-this.activityAt),1000-(this.now()-this.eventAt),5000-(this.now()-this.lastStart));this.timeout=this.timer(()=>this.attempt(),Math.max(50,delay));}
 async attempt(){const s=this.snapshot();if(s.color!=='yellow'||s.hidden||!s.binding||this.suspended.has(s.binding))return;if(!this.eligible()){this.timeout=this.timer(()=>this.wake(),250);return;}const binding=s.binding,controller=this.controller=new AbortController();this.lastStart=this.now();try{await this.run(controller.signal);}catch(e){if(!controller.signal.aborted&&e.code!=='AUTO_DEFERRED'){this.suspended.add(binding);this.failure(e);}}finally{if(this.controller===controller)this.controller=null;this.wake();}}
 stop(){this.cancel(this.timeout);this.controller?.abort();}
}
