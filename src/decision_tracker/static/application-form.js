// Select existing planning content; application remains a separate attestation.
export function installApplicationForm(container,decision,{api,base,prefill=null,onPrefilled=()=>{},onReady=()=>{}}){
 const make=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const label=make('label','Planning document'),documentField=make('select');documentField.name='planning_document';documentField.required=true;documentField.add(new Option('Loading documents…',''));label.append(documentField);container.append(label);
 const picker=make('div');picker.className='planning-browser';picker.hidden=true;container.append(picker);
 const heading=make('h3','Select document'),folder=make('select');folder.setAttribute('aria-label','Planning folder');
 const toolbar=make('div');toolbar.className='planning-browser-toolbar';
 const up=make('button','Up'),cancel=make('button','Cancel');for(const b of [up,cancel])b.type='button';toolbar.append(folder,up,cancel);
 const files=make('div');files.className='planning-files';files.setAttribute('aria-label','Planning files');
 const pathLabel=make('label','File path'),pathField=make('input');pathField.maxLength=1024;pathLabel.append(pathField);
 const use=make('button','Use path');use.type='button';picker.append(heading,toolbar,files,pathLabel,use);
 const sectionLabel=make('label','Section'),section=make('select');section.name='planning_section';section.required=true;section.disabled=true;section.add(new Option('Choose a document first',''));sectionLabel.append(section);container.append(sectionLabel);
 const error=make('p');error.className='error';error.hidden=true;error.setAttribute('role','alert');container.append(error);
 let doc=null,policyRevision=decision.application_policy_revision,resolutionId=decision.planning_application?.resolution_id,anchorRequired=true,policyLoaded=false,serial=0,browseSerial=0,edited=false,selected='',parent=null,roots=[];
 const ready=()=>policyLoaded&&picker.hidden&&(!selected&&!anchorRequired||Boolean(doc&&section.value));
 const sync=()=>onReady(ready());
 function fail(e){if(!documentField.isConnected)return;error.textContent=e.message;error.hidden=false;sync();}
 function add(path){if(![...documentField.options].some(o=>o.value===path))documentField.add(new Option(path.split(/[\\/]/).pop(),path),documentField.options[documentField.options.length-1]);}
 function setRoots(items){roots=items;const previous=folder.value;folder.replaceChildren();for(const r of roots)folder.add(new Option(r.name,r.path));if(roots.some(r=>r.path===previous))folder.value=previous;}
 async function inventory(directory=null){const entries=[];let cursor=null,result;do{result=await api(base()+'/planning-documents?'+new URLSearchParams({...directory?{directory}:{},...cursor?{cursor}:{}}));entries.push(...result.data.entries);cursor=result.next_cursor;}while(cursor);return {...result.data,entries};}
 async function load(path,old=''){
  const current=++serial;selected=path;doc=null;section.disabled=true;section.required=anchorRequired||Boolean(path);section.replaceChildren(new Option(path?'Loading sections…':'Choose a document first',''));error.hidden=true;sync();
  if(!path)return;
  try{const anchors=[];let cursor=null,result;do{result=await api(base()+'/planning-document?'+new URLSearchParams({locator:path,...cursor?{cursor}:{}}));if(current!==serial||!documentField.isConnected)return;anchors.push(...result.data.anchors);cursor=result.next_cursor;}while(cursor);
   doc={...result.data,anchors};section.replaceChildren(new Option('Choose a section',''));for(const a of anchors)section.add(new Option(a.heading,a.id));if(anchors.some(a=>a.id===old))section.value=old;section.disabled=false;
  }catch(e){if(current===serial&&documentField.isConnected){section.replaceChildren(new Option('Document unavailable',''));fail(e);}}
  sync();
 }
 async function browse(directory){const current=++browseSerial;files.replaceChildren(make('p','Loading files…'));files.setAttribute('aria-busy','true');up.disabled=true;error.hidden=true;
  try{const listing=await inventory(directory);if(current!==browseSerial||picker.hidden||!documentField.isConnected)return;parent=listing.parent;up.disabled=!parent;folder.value=roots.filter(r=>directory===r.path||directory.startsWith(r.path+'/')||directory.startsWith(r.path+'\\')).sort((a,b)=>b.path.length-a.path.length)[0]?.path||'';
   files.replaceChildren(make('p',listing.directory));for(const f of listing.entries){const b=make('button',(f.kind==='folder'?'▸ ':'')+f.path.split(/[\\/]/).pop());b.type='button';b.title=f.path;b.onclick=()=>{if(f.kind==='folder')browse(f.path);else choose(f.path);};files.append(b);}if(!listing.entries.length)files.append(make('p','No documents or folders.'));
  }catch(e){if(current===browseSerial){files.replaceChildren();fail(e);}}finally{if(current===browseSerial)files.setAttribute('aria-busy','false');}
 }
 function closePicker(){picker.hidden=true;++browseSerial;sync();documentField.focus();}
 function choose(path){edited=true;add(path);documentField.value=path;picker.hidden=true;++browseSerial;load(path);documentField.focus();}
 documentField.onchange=()=>{if(documentField.value==='__add__'){documentField.value=selected;picker.hidden=false;pathField.value='';sync();if(roots.length)browse(folder.value||roots[0].path);pathField.focus();}else{edited=true;load(documentField.value);}};
 section.onchange=()=>{edited=true;sync();};folder.onchange=()=>browse(folder.value);up.onclick=()=>parent&&browse(parent);cancel.onclick=closePicker;
 use.onclick=()=>{const path=pathField.value.trim();if(path)choose(path);};pathField.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();use.click();}};
 const getPolicy=()=>api(base()+'/policy').then(r=>{if(!documentField.isConnected)return;anchorRequired=r.data.anchor_required;policyRevision=r.data.policy_revision;policyLoaded=true;setRoots(r.data.planning_roots.map(path=>({path,name:path.split(/[\\/]/).pop()})));documentField.required=anchorRequired;section.required=anchorRequired||Boolean(selected);sync();});
 getPolicy().catch(fail);
 inventory().then(r=>{if(!documentField.isConnected)return;setRoots(r.roots);const value=documentField.value;documentField.replaceChildren(new Option('Choose a document',''));for(const f of r.entries.filter(f=>f.kind==='document')){const o=new Option(f.path.split(/[\\/]/).pop(),f.path);o.title=f.path;documentField.add(o);}documentField.add(new Option('Add document…','__add__'));
  if(value&&value!=='__add__'){add(value);documentField.value=value;}if(!picker.hidden&&roots.length)browse(folder.value||roots[0].path);
 }).catch(e=>{if(!documentField.isConnected)return;documentField.replaceChildren(new Option('Choose a document',''),new Option('Add document…','__add__'));if(selected){add(selected);documentField.value=selected;}fail(e);});
 if(prefill?.document){add(prefill.document);documentField.value=prefill.document;load(prefill.document,prefill.section).then(()=>{if(edited||!doc||!documentField.isConnected||selected!==prefill.document)return;if(prefill.sha256&&prefill.sha256!==doc.sha256)fail(new Error('Document changed. Review the refreshed section before applying.'));onPrefilled();});}
 sync();
 return {submit:'Apply',ready,read(){
  if(!ready())throw new Error('Select a planning document and section.');
  return {data:{expected_policy_revision:policyRevision,expected_resolution_id:resolutionId,...selected?{planning_document:selected,planning_section:section.value,expected_document_sha256:doc.sha256,...doc.projection?{expected_projection_sha256:doc.projection.sha256}:{}}:{}},reason:'Applied decision to authoritative planning.',authority_refs:[]};
 },showError(e){if(e.code==='DOCUMENT_CHANGED')load(selected);if(e.code==='POLICY_CHANGED')getPolicy().catch(fail);},rebase(d){resolutionId=d.planning_application?.resolution_id;policyRevision=d.application_policy_revision;}};
}
