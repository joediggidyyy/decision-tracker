/* Collect first, commit later. Every participating response must share a revision. */
export async function collectWorkspace(read,base,query,key,signal,minimumRows=0){
 let revision=null,stage='results';
 const checked=async path=>{signal.throwIfAborted();const r=await read(path,signal);signal.throwIfAborted();if(revision===null)revision=r.revision;if(r.revision!==revision){const e=Error('The project changed during refresh.');e.code='REFRESH_CHANGED';throw e;}return r;};
 const expand=async value=>{if(!value?.chunks_url)return value;let text='',offset=0;do{const r=await checked(value.chunks_url+'&offset='+offset);text+=r.data.text;offset=r.data.next_offset;}while(offset!==null);return text;};
 const all=async url=>{let cursor=null,items=[];do{const r=await checked(url+(cursor?(url.includes('?')?'&':'?')+'cursor='+encodeURIComponent(cursor):''));items.push(...r.data);cursor=r.next_cursor;}while(cursor);for(const item of items)for(const field of Object.keys(item))item[field]=await expand(item[field]);return items;};
 try{
  const list=await checked(base+'/decisions?'+query);const cursors=new Set();
  while(list.next_cursor&&list.data.length<minimumRows){const cursor=list.next_cursor;if(cursors.has(cursor))throw Error('Repeated results cursor');cursors.add(cursor);const page=await checked(base+'/decisions?'+query+'&cursor='+encodeURIComponent(cursor));list.data.push(...page.data);list.next_cursor=page.next_cursor;}
  let record=null,context=null,targets={};
  if(key){stage='selected decision';const r=await checked(base+'/decisions/'+key);record=r.data;for(const field of Object.keys(record))record[field]=await expand(record[field]);
   stage='decision collections';for(const family of ['alternatives','references','links'])record[family]=await all(record.collections[family].url);
   for(const link of record.links.filter(l=>l.active&&(l.source_key===key||l.type==='relates_to')&&['relates_to','depends_on'].includes(l.type))){const other=link.source_key===key?link.target_key:link.source_key;targets[other]=(await checked(base+'/decisions/'+other)).data;}
   stage='decision context';context=(await checked(base+'/decisions/'+key+'/context')).data;
  }
  return {list,record,context,targets,revision};
 }catch(error){error.stage=stage;throw error;}
}

export async function collectProjectRegions(read,project,signal){
 const base='/api/v1/projects/'+encodeURIComponent(project.project_id);let stage='Summary',summary;
 const checked=async path=>{signal.throwIfAborted();const r=await read(path,signal);signal.throwIfAborted();if(r.project_id!==project.project_id||r.ledger_uuid!==project.ledger_uuid){const e=Error('Project response identity changed.');e.code='LEDGER_IDENTITY_MISMATCH';throw e;}return r;};
 try{
  summary=await checked(base+'/summary');stage='Sources';const entries=[],seen=new Set();let cursor=null,roots=[];
  do{const r=await checked(base+'/planning-documents?limit=200'+(cursor?'&cursor='+encodeURIComponent(cursor):''));if(r.revision!==summary.revision){const e=Error('Project changed during refresh.');e.code='REFRESH_CHANGED';throw e;}roots=r.data.roots||[];entries.push(...r.data.entries.filter(x=>x.kind==='document'));cursor=r.next_cursor;if(!cursor&&!r.complete)throw Error('Source inventory incomplete');if(cursor&&seen.has(cursor))throw Error('Source cursor repeated');seen.add(cursor);}while(cursor);
  return {summary,sources:{roots,entries},revision:summary.revision};
 }catch(e){
  // A new standalone project has no registered planning roots. This is an
  // explicit configuration state, not a failed inventory or permission bypass.
  if(stage==='Sources'&&e.code==='PLANNING_ACCESS_REQUIRED'){
   const confirm=await checked(base+'/summary');if(confirm.revision!==summary.revision){const changed=Error('Project changed during refresh.');changed.code='REFRESH_CHANGED';throw changed;}
   return {summary,sources:{roots:[],entries:[],unconfigured:true},revision:summary.revision};
  }
  e.stage=stage;throw e;
 }
}

export async function collectProjects(read,identity,signal,validateCatalog=()=>{}){
 let stage='Catalog';try{
  const catalog=await read('/api/v1/projects',signal);signal.throwIfAborted();validateCatalog(catalog);
  const selected=identity&&catalog.data.find(p=>p.project_id===identity.project_id&&p.ledger_uuid===identity.ledger_uuid);
  const regions=selected?.enabled?await collectProjectRegions(read,selected,signal):null;
  stage='Catalog';const confirm=await read('/api/v1/projects',signal);signal.throwIfAborted();validateCatalog(confirm);
  if(confirm.catalog_revision!==catalog.catalog_revision){const e=Error('Catalog changed during refresh.');e.code='REFRESH_CHANGED';throw e;}
  return {catalog,selected,regions};
 }catch(e){e.stage=e.stage||stage;throw e;}
}
