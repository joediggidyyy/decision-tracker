// Human fields become the bounded shared API operation; no JSON entry control.
export function installApplicationForm(container,decision,{api,base,prefill=null,onPrefilled=()=>{}}){
 const label=document.createElement('label');label.textContent='Planning document';
 const documentField=document.createElement('input');documentField.name='planning_document';documentField.maxLength=1024;documentField.required=true;label.append(documentField);container.append(label);
 const sectionLabel=document.createElement('label');sectionLabel.textContent='Section';
 const section=document.createElement('select');section.name='planning_section';section.required=true;section.add(new Option('Choose a section',''));sectionLabel.append(section);container.append(sectionLabel);
 const error=document.createElement('p');error.className='error';error.hidden=true;error.setAttribute('role','alert');container.append(error);
 let doc=null,policyRevision=decision.application_policy_revision,resolutionId=decision.planning_application?.resolution_id,anchorRequired=true,serial=0,edited=false;
 for(const field of [documentField,section])field.addEventListener('input',()=>{edited=true;});
 function fail(e){error.textContent=e.message;error.hidden=false;}
 async function load(){const current=++serial,locator=documentField.value.trim(),old=section.value;doc=null;section.replaceChildren(new Option('Choose a section',''));error.hidden=true;
  if(!locator)return;
  try{const anchors=[];let cursor=null,result;do{result=await api(base()+'/planning-document?'+new URLSearchParams({locator,...(cursor?{cursor}:{})}));if(current!==serial||!documentField.isConnected)return;anchors.push(...result.data.anchors);cursor=result.next_cursor;}while(cursor);doc={...result.data,anchors};for(const a of doc.anchors)section.add(new Option(a.heading,a.id));if(doc.anchors.some(a=>a.id===old))section.value=old;}
  catch(e){if(current===serial&&documentField.isConnected)fail(e);}
 }
 documentField.addEventListener('input',()=>{serial++;doc=null;section.replaceChildren(new Option('Choose a section',''));section.required=anchorRequired||Boolean(documentField.value.trim());});
 documentField.addEventListener('change',load);
 api(base()+'/policy').then(r=>{if(!documentField.isConnected)return;anchorRequired=r.data.anchor_required;policyRevision=r.data.policy_revision;documentField.required=anchorRequired;section.required=anchorRequired||Boolean(documentField.value.trim());}).catch(fail);
 if(prefill?.document){documentField.value=prefill.document;load().then(()=>{if(edited||!doc||!documentField.isConnected||documentField.value!==prefill.document)return;if(doc.anchors.some(a=>a.id===prefill.section))section.value=prefill.section;if(prefill.sha256&&prefill.sha256!==doc.sha256)fail(new Error('Document changed. Review the refreshed section before applying.'));onPrefilled();});}
 return {submit:'Apply',read(){
  const locator=documentField.value.trim();
  if(locator&&(!doc||!section.value))throw new Error(error.hidden?'Select a section in this document.':error.textContent);
  if(anchorRequired&&!locator)throw new Error('Select a planning document and section.');
  return {data:{expected_policy_revision:policyRevision,expected_resolution_id:resolutionId,
    ...(locator?{planning_document:locator,planning_section:section.value,expected_document_sha256:doc.sha256,...(doc.projection?{expected_projection_sha256:doc.projection.sha256}:{})}:{})},reason:'Applied decision to authoritative planning.',authority_refs:[]};
 },showError(e){if(e.code==='DOCUMENT_CHANGED')load();if(e.code==='POLICY_CHANGED')api(base()+'/policy').then(r=>{policyRevision=r.data.policy_revision;anchorRequired=r.data.anchor_required;documentField.required=anchorRequired;section.required=anchorRequired||Boolean(documentField.value.trim());}).catch(fail);},rebase(d){resolutionId=d.planning_application?.resolution_id;policyRevision=d.application_policy_revision;}};
}
