// Read-only source history stays visibly separate from native mutation history.
export function installLegacyHistory({box,record,base,api,node,button,current}) {
 if(!record.legacy_origin)return;
 const section=node('section',undefined,'legacy-history');box.append(section);
 section.append(node('h3','Source','section-title'),node('p',record.legacy_origin.namespace+' · '+record.legacy_origin.source_id));
 const attribution=node('dl');
 for(const field of record.legacy_origin.fields){
  if(field.known_state==='exact_source')continue;
  const summary=field.selector?.endsWith('/gain')?'Attributed source benefit':'Attributed source summary';
  attribution.append(node('dt',field.field),node('dd',field.known_state==='explicit_source_unknown'?'Unknown in source':field.projection_kind==='attributed-summary'?summary:field.projection_kind==='import-provenance'?'Import provenance':'Not projected'));
 }
 section.append(attribution);
 const sources=node('div');section.append(sources);
 button('Source references',async()=>{
  sources.replaceChildren();let cursor=null,revision=null;
  do{
   const r=await api(base()+'/legacy/records/source_anchors?key='+record.key+'&limit=20'+(cursor?'&cursor='+encodeURIComponent(cursor):''));
   if(!current())return;if(revision!==null&&revision!==r.revision)throw new Error('Source references changed. Reload this decision.');revision=r.revision;
   for(const source of r.data.rows)sources.append(node('p',source.original_locator+' · '+source.selector+' · '+source.incorporation_state));
   cursor=r.next_cursor;
  }while(cursor);
 },section);
 const content=node('div');section.append(content);let cursor=null,revision=null,open=false;
 async function page(){
  const response=await api(base()+'/decisions/'+record.key+'/legacy?limit=20'+(cursor?'&cursor='+encodeURIComponent(cursor):''));
  if(!current())return;
  if(revision!==null&&revision!==response.revision)throw new Error('Source history changed. Reload this decision.');
  revision=response.revision;
  for(const member of response.data.members){
   const row=node('article',undefined,'child-card');row.append(node('p',member.subject_kind+' · '+member.selector),node('small','Source version '+member.version_id));
   const text=node('pre');row.append(text);
   button('View source',async()=>{
    const chunks=[];let offset=0,total=null;
    do{
     const r=await api(base()+'/decisions/'+record.key+'/legacy/payload/'+member.payload_sha256+'?offset='+offset+'&limit=16384');
     if(!current())return;
     if(r.revision!==revision)throw new Error('Source history changed. Reload this decision.');
     const p=r.data;if(total!==null&&total!==p.encoded_bytes)throw new Error('Source payload changed.');total=p.encoded_bytes;
     const chunk=Uint8Array.from(atob(p.chunk_base64),c=>c.charCodeAt(0));chunks.push(chunk);offset=p.next_offset;
    }while(offset!==null);
    const bytes=new Uint8Array(total);let position=0;for(const chunk of chunks){bytes.set(chunk,position);position+=chunk.length;}
    if(position!==total)throw new Error('Source payload is incomplete.');
    const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
    if(hash!==member.payload_sha256)throw new Error('Source payload integrity check failed.');
    if(current())text.textContent=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
   },row);content.append(row);
  }
  cursor=response.next_cursor;more.hidden=response.complete;
 }
 const toggle=button('Source history',async()=>{open=!open;toggle.setAttribute('aria-expanded',String(open));content.replaceChildren();more.hidden=true;if(!open)return;cursor=null;revision=null;await page();},section);
 toggle.setAttribute('aria-expanded','false');const more=button('More source history',page,section);more.hidden=true;
}
