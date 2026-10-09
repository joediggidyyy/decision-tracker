// Browser-owned controls: removed rows, disabled sections and visible recovery.
module.exports=async page=>{
 const result=await page.evaluate(async()=>{
  const {installActionForm}=await import('/static/action-form.js');
  const {activeControl}=await import('/static/form-controls.js');
  const owner=document.createElement('form');document.body.append(owner);
  try{
   const form=installActionForm(owner,'decision.reopen',{key:'D000099',answer:'Retained'},null,{decide:true,findDecisions:async()=>[]});
   const input=name=>owner.querySelector(`[name="${name}"]`),button=text=>[...owner.querySelectorAll('button')].find(n=>n.textContent===text);
   input('impact').value='Review';input('reason').value='Correct';input('authority_0').value=' ';
   let error;try{form.read();}catch(e){error=e;}
   if(!error)throw Error('Attached whitespace required source must fail.');
   const box=document.createElement('div');form.showError(error,box);box.querySelector('button').click();
   if(document.activeElement!==input('authority_0'))throw Error('Recovery must focus the attached source.');
   button('Add source').click();input('authority_1').value='Actual approval';
   const removed=input('authority_0');removed.parentElement.parentElement.querySelector('button').click();
   if(activeControl(removed,owner)||JSON.stringify(form.read().authority_refs)!=='["Actual approval"]')throw Error('Detached required source entered validation.');
   const staleBox=document.createElement('div');form.showError(error,staleBox);if(staleBox.children.length)throw Error('Detached source received an error target.');
   button('Add source').click();if(!input('authority_2'))throw Error('Source serial must not be reused.');
   input('authority_2').parentElement.parentElement.querySelector('button').click();
   input('authority_1').parentElement.parentElement.querySelector('button').click();
   if(!input('authority_1')||input('authority_1').value)throw Error('Last source row must remain available.');
   input('authority_1').value='Corrected';form.read();
   input('authority_1').disabled=true;input('authority_1').value='';form.read();
   owner.replaceChildren();const option=installActionForm(owner,'option.add',{key:'D000099'},null,{decide:true,findDecisions:async()=>[]});
   input('title').value='Proposal';const refs=input('authority_0');if(!refs.closest('details')||refs.closest('details').open)throw Error('Optional approval should be collapsed.');
   if(!activeControl(refs,owner))throw Error('Collapsed optional details must remain applicable.');
   refs.value='Optional evidence';if(option.read().authority_refs[0]!=='Optional evidence')throw Error('Optional evidence was lost.');
   owner.replaceChildren();const edit=installActionForm(owner,'decision.edit',{key:'D000099',title:'Title',question:'Question?',status:'open'},null,{decide:true,findDecisions:async()=>[]});
   if(activeControl(input('implementation_status'),owner))throw Error('Disabled hidden evidence must be ignored.');edit.read();
   const other=document.createElement('input');other.required=true;document.body.append(other);if(activeControl(other,owner))throw Error('Foreign control entered this form.');other.remove();
   return true;
  }finally{owner.remove();}
 });
 if(!result)throw Error('Control applicability observations failed.');
};
