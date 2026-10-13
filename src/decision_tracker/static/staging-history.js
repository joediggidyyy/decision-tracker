// Local copied content only. These commands never write to a project or Library.
export class StagingHistory {
 constructor({maxItems=500,maxBytes=10*1024*1024,maxCommands=100,maxHistoryBytes=32*1024*1024}={}){
  Object.assign(this,{maxItems,maxBytes,maxCommands,maxHistoryBytes});this.items=new Map();this.undoStack=[];this.redoStack=[];
 }
 bytes(value){return new TextEncoder().encode(JSON.stringify(value)).length;}
 validate(items){if(items.size>this.maxItems||this.bytes({decisions:[...items.values()]})>this.maxBytes)throw Error('Staging exceeds 500 decisions or the 10MiB preparation limit. Remove items before trying again.');}
 change(next){
  this.validate(next);const before=this.items,ids=new Set([...before.keys(),...next.keys()]);
  const changes=[...ids].filter(id=>JSON.stringify(before.get(id))!==JSON.stringify(next.get(id))).map(id=>({id,before:before.has(id)?structuredClone(before.get(id)):null,after:next.has(id)?structuredClone(next.get(id)):null}));
  if(!changes.length)return false;
  const command={changes,beforeOrder:[...before.keys()],afterOrder:[...next.keys()]};
  this.items=new Map([...next].map(([id,value])=>[id,structuredClone(value)]));this.redoStack=[];this.undoStack.push(command);
  let evicted=false;while(this.undoStack.length&&(this.undoStack.length>this.maxCommands||this.bytes(this.undoStack)>this.maxHistoryBytes)){this.undoStack.shift();evicted=true;}return evicted?'evicted':true;
 }
 add(items,{replace=false}={}){const next=new Map(this.items);for(const {id,content} of items)if(replace||!next.has(id))next.set(id,content);return this.change(next);}
 remove(ids){const next=new Map(this.items);for(const id of ids)next.delete(id);return this.change(next);}
 replay(command,side){const next=new Map(this.items);for(const change of command.changes){if(change[side]===null)next.delete(change.id);else next.set(change.id,structuredClone(change[side]));}this.items=new Map(command[side+'Order'].map(id=>[id,next.get(id)]));}
 undo(){const command=this.undoStack.pop();if(!command)return false;this.replay(command,'before');this.redoStack.push(command);return true;}
 redo(){const command=this.redoStack.pop();if(!command)return false;this.replay(command,'after');this.undoStack.push(command);return true;}
 boundary(){this.undoStack=[];this.redoStack=[];}
 clear(){this.items.clear();this.boundary();}
}
