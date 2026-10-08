/* Collect first, commit later. Every participating response must share a revision. */
export async function collectWorkspace(read,base,query,key,signal){
 let revision=null,stage='results';
 const checked=async path=>{signal.throwIfAborted();const r=await read(path,signal);signal.throwIfAborted();if(revision===null)revision=r.revision;if(r.revision!==revision){const e=Error('The project changed during refresh.');e.code='REFRESH_CHANGED';throw e;}return r;};
 const expand=async value=>{if(!value?.chunks_url)return value;let text='',offset=0;do{const r=await checked(value.chunks_url+'&offset='+offset);text+=r.data.text;offset=r.data.next_offset;}while(offset!==null);return text;};
 const all=async url=>{let cursor=null,items=[];do{const r=await checked(url+(cursor?(url.includes('?')?'&':'?')+'cursor='+encodeURIComponent(cursor):''));items.push(...r.data);cursor=r.next_cursor;}while(cursor);for(const item of items)for(const field of Object.keys(item))item[field]=await expand(item[field]);return items;};
 try{
  const list=await checked(base+'/decisions?'+query);let record=null,context=null,targets={};
  if(key){stage='selected decision';const r=await checked(base+'/decisions/'+key);record=r.data;for(const field of Object.keys(record))record[field]=await expand(record[field]);
   stage='decision collections';for(const family of ['alternatives','references','links'])record[family]=await all(record.collections[family].url);
   for(const link of record.links.filter(l=>l.active&&l.source_key===key&&['relates_to','depends_on'].includes(l.type)))targets[link.target_key]=(await checked(base+'/decisions/'+link.target_key)).data;
   stage='decision context';context=(await checked(base+'/decisions/'+key+'/context')).data;
  }
  return {list,record,context,targets,revision};
 }catch(error){error.stage=stage;throw error;}
}
