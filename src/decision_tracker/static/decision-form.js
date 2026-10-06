// Resolution form: explicit choice, generated defaults, and honest approval dates.
export const normalize=s=>(s||'').replaceAll('\r\n','\n').trim();
export function defaults(p,editing=false){return {answer:p.description?.trim()?p.description:p.title,rationale:[p.benefit?.trim()?'Expected benefit: '+p.benefit:'',p.cost?.trim()?'Cost or tradeoff: '+p.cost:''].filter(Boolean).join('\n\n'),reason:(editing?'Updated':'Recorded')+' decision using proposal: '+p.title+'.'};}
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
export function installDecisionForm(container,d,editing=false){
 const notice=el('p');notice.setAttribute('role','status');
 container.append(el('h3',d.question),el('p',editing?'Update the recorded answer. Saving keeps this decision closed; it does not perform the work.':'Choose a proposal or write your answer. Saving closes this question; it does not perform the work.'));
 const choices=el('fieldset');choices.append(el('legend','Which proposed solution do you choose?'),el('p','Switching choices replaces the Decision, Why this choice and Change note fields. Choose a proposal to fill them, or Write a different answer to clear them.'));container.append(choices);
 const proposals=(d.alternatives||[]).filter(p=>p.disposition!=='retired').sort((a,b)=>a.position-b.position||a.id.localeCompare(b.id));
 let selected=editing?proposals.find(p=>p.disposition==='selected')?.id||'':(d.answer||d.rationale?'':null);
 const radios=[];
 function input(label,name,value='',type='textarea',required=false,parent=container){const wrap=el('label',label),n=el(type==='textarea'?'textarea':'input');if(type!=='textarea')n.type=type;n.name=name;n.id='resolution-'+name;n.value=value;n.required=required;wrap.htmlFor=n.id;wrap.append(n);parent.append(wrap);return n;}
 function radio(id,title,disabled=false){const label=el('label'),n=el('input');n.type='radio';n.name='proposal_choice';n.value=id;n.required=true;n.disabled=disabled;n.checked=selected===id;label.append(n,document.createTextNode(title));choices.append(label);radios.push(n);return n;}
 for(const p of proposals){const r=radio(p.id,p.title,p.disposition==='rejected');if(r.disabled)choices.append(el('p','Previously rejected. Reconsider this proposal before selecting it.'));
  for(const [label,text] of [['Proposal',p.description],['Expected benefit',p.benefit],['Cost or tradeoff',p.cost]])if(text){if(text.length>600){const det=el('details');det.append(el('summary',label+': '+text.slice(0,600)+'… Show full proposal'),el('p',text));choices.append(det);}else choices.append(el('p',label+': '+text));}
  r.onchange=()=>choose(p.id);
 }
 const manual=radio('','Write a different answer');manual.onchange=()=>choose('');if(!proposals.some(p=>p.disposition!=='rejected')&&!editing){selected='';manual.checked=true;}
 const answer=input('Decision','answer',d.answer||'','textarea',true);answer.maxLength=32768;
 const answerHint=el('p','State the answer to the question above.');answerHint.id='resolution-answer-hint';answer.setAttribute('aria-describedby',answerHint.id);container.append(answerHint);
 const rationale=input('Why this choice?','rationale',d.rationale||'','textarea',true);rationale.maxLength=32768;
 const rationaleHint=el('p','Explain why this answer is appropriate, including important tradeoffs.');rationaleHint.id='resolution-rationale-hint';rationale.setAttribute('aria-describedby',rationaleHint.id);container.append(rationaleHint);
 container.append(notice);
 let reasonDirty=false;
 const approval=el('fieldset'),approvalNotice=el('p','Approval will be recorded as Operator when you save.');approval.append(el('legend','Approval'),approvalNotice);container.append(approval);
 const report=input('Record an earlier or external approval','reported','','checkbox',false,approval);
 const history=el('div');history.hidden=true;approval.append(history);
 const approver=input('Who approved?','approver','','text',false,history);approver.maxLength=160;
 const sources=el('div');history.append(sources);const sourceFields=[];
 let sourceSerial=0;
 const addSource=()=>{const n=input('Approval source','source_'+sourceSerial++,'','text',false,sources);n.maxLength=1024;sourceFields.push(n);const remove=el('button','Remove this source');remove.type='button';remove.onclick=()=>{if(sourceFields.length>1){sourceFields.splice(sourceFields.indexOf(n),1);n.closest('label').remove();remove.remove();sourceFields[0].focus();}};sources.append(remove);return n;};addSource();
 history.append(el('p','Identify the message, document or note that records the approval. A document path, link or descriptive note is accepted.'));
 const add=el('button','Add another source');add.type='button';add.onclick=()=>{if(sourceFields.length<32){addSource().focus();sync();}};history.append(add);
 const pl=el('label','When was the decision made?'),precision=el('select');precision.name='precision';precision.id='resolution-precision';pl.htmlFor=precision.id;
 for(const [v,t] of [['','Choose what is known'],['exact','Date and time known'],['date','Date known, time unknown'],['unknown','Date unknown']]){const o=el('option',t);o.value=v;precision.append(o);}pl.append(precision);history.append(pl);
 const date=input('Date of decision','approval_date','','date',false,history),time=input('Time of decision','approval_time','','time',false,history);time.step=1;
 const offsetLabel=el('label','UTC offset'),offset=el('select');offset.name='offset';offset.id='resolution-offset';offsetLabel.htmlFor=offset.id;
 for(let m=-720;m<=840;m+=15){const o=el('option',(m>=0?'+':'-')+String(Math.floor(Math.abs(m)/60)).padStart(2,'0')+':'+String(Math.abs(m)%60).padStart(2,'0'));o.value=m;offset.append(o);}offsetLabel.append(offset);history.append(offsetLabel);
 const zone=Intl.DateTimeFormat().resolvedOptions().timeZone;history.append(el('p','Local timezone: '+zone+'. Choose the recorded UTC offset if the approval occurred elsewhere.'));
 const confirm=input('This is the date of the original decision','date_confirm','','checkbox',false,history);
 const details=el('details');details.append(el('summary','Optional details'));container.append(details);
 const reason=input('Change note','reason',(editing?'Updated':'Recorded')+' a written decision.','textarea',true,details);reason.maxLength=8192;reason.oninput=()=>reasonDirty=true;
 function markSelection(){for(const r of radios)r.checked=r.value===selected;}
 function choose(id){if(id===selected)return;notice.textContent='';selected=id;markSelection();const p=proposals.find(p=>p.id===id),v=p?defaults(p,editing):{answer:'',rationale:'',reason:(editing?'Updated':'Recorded')+' a written decision.'};answer.value=v.answer;rationale.value=v.rationale;reason.value=v.reason;reasonDirty=false;}
 answer.oninput=()=>{if(selected){const p=proposals.find(p=>p.id===selected);if(normalize(answer.value)!==normalize(defaults(p,editing).answer)){selected='';markSelection();notice.textContent='Your edited answer will be saved as a written decision, not as the selected proposal.';if(!reasonDirty)reason.value=(editing?'Updated':'Recorded')+' a written decision.';}}};
 function sync(){const active=report.checked,known=precision.value==='exact'||precision.value==='date';history.hidden=!active;for(const n of history.querySelectorAll('input,select,button'))n.disabled=!active;approver.required=active;precision.required=active;sourceFields.forEach(n=>n.required=active);for(const n of [date,offset,confirm]){n.closest('label').hidden=!known;n.disabled=!active||!known;}time.closest('label').hidden=precision.value!=='exact';time.disabled=!active||precision.value!=='exact';date.required=active&&known;time.required=active&&precision.value==='exact';confirm.required=active&&known;}
 report.onchange=()=>{approvalNotice.textContent=report.checked?'You are recording an approval made earlier or outside this application. The approver below is reported, not authenticated.':'Approval will be recorded as Operator when you save.';sync();};precision.onchange=()=>{const n=new Date(),pad=x=>String(x).padStart(2,'0');date.value=n.getFullYear()+'-'+pad(n.getMonth()+1)+'-'+pad(n.getDate());time.value=pad(n.getHours())+':'+pad(n.getMinutes())+':'+pad(n.getSeconds());offset.value=-n.getTimezoneOffset();confirm.checked=false;explicitOffset=false;sync();};
 let explicitOffset=false;offset.onchange=()=>explicitOffset=true;
 date.oninput=time.oninput=()=>{confirm.checked=true;explicitOffset=false;if(date.value&&time.value)offset.value=-new Date(date.value+'T'+time.value).getTimezoneOffset();};sync();
 return {asWritten(){selected='';markSelection();if(!reasonDirty)reason.value=(editing?'Updated':'Recorded')+' a written decision.';},showError(error,box){
  for(const n of container.querySelectorAll('[aria-invalid]'))n.removeAttribute('aria-invalid');
  const map={approver,sources:sourceFields[0],occurred_at:date,occurred_date:date,precision,utc_offset_minutes:offset,answer,rationale,selected_option:radios[0],expected_option_revision:radios[0]};
  const inferred={APPROVAL_DATE_FUTURE:'occurred_date',APPROVAL_DATE_INVALID:'precision',PROPOSAL_CHANGED:'selected_option',ANSWER_PROPOSAL_MISMATCH:'answer'};
  const fields=error.details?.fields||[{field:inferred[error.code]}];
  for(const item of fields){const name=item.field?.split(/[/.]/).filter(x=>x&&!/^\d+$/.test(x)).pop(),target=map[name];if(!target)continue;target.setAttribute('aria-invalid','true');const b=el('button',item.message||('Review '+name.replaceAll('_',' ')));b.type='button';b.onclick=()=>{target.closest('details')?.setAttribute('open','');target.focus();};box.append(b);}
 },read(){
  const data={answer:answer.value,rationale:rationale.value,selected_option:selected||null};
  if(selected)data.expected_option_revision=proposals.find(p=>p.id===selected).revision;
  if(!report.checked)data.approval={mode:'authenticated_now'};
  else{const a={mode:'reported',approver:approver.value.trim(),sources:sourceFields.map(n=>n.value.trim()).filter(Boolean),precision:precision.value};
   if(a.precision!=='unknown'){
    if(!confirm.checked)throw new Error('Confirm the date of the original decision.');a.utc_offset_minutes=Number(offset.value);a.timezone_label=explicitOffset?'Reported offset '+offset.selectedOptions[0].textContent:zone;
    if(a.precision==='date')a.occurred_date=date.value;
    else{const local=date.value+'T'+time.value,chosen=new Date(local),parts=local.split(/[-T:]/).map(Number);
     if(!explicitOffset&&(chosen.getFullYear()!==parts[0]||chosen.getMonth()+1!==parts[1]||chosen.getDate()!==parts[2]||chosen.getHours()!==parts[3]||chosen.getMinutes()!==parts[4]))throw new Error('This local time does not exist. Choose a valid time or an explicit external offset.');
     const wall=Date.UTC(parts[0],parts[1]-1,parts[2],parts[3],parts[4],parts[5]||0),offsets=[];
     for(let m=-720;m<=840;m+=15){const t=new Date(wall-m*60000);if(t.getFullYear()===parts[0]&&t.getMonth()+1===parts[1]&&t.getDate()===parts[2]&&t.getHours()===parts[3]&&t.getMinutes()===parts[4])offsets.push(m);}
     if(offsets.length>1&&!explicitOffset)throw new Error('This local time occurs twice. Choose its UTC offset explicitly.');
     a.occurred_at=local+(time.value.length===5?':00':'')+offset.selectedOptions[0].textContent;
    }
   }data.approval=a;
  }
  return {data,reason:reason.value,authority_refs:[]};
 }};
}
