import {installApprovalForm} from './approval-form.js';
import {activeControl} from './form-controls.js';
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
 const approvalControls=installApprovalForm(container);
 const details=el('details');details.append(el('summary','Optional details'));container.append(details);
 const reason=input('Change note','reason',(editing?'Updated':'Recorded')+' a written decision.','textarea',true,details);reason.maxLength=8192;reason.oninput=()=>reasonDirty=true;
 function markSelection(){for(const r of radios)r.checked=r.value===selected;}
 function choose(id){if(id===selected)return;notice.textContent='';selected=id;markSelection();const p=proposals.find(p=>p.id===id),v=p?defaults(p,editing):{answer:'',rationale:'',reason:(editing?'Updated':'Recorded')+' a written decision.'};answer.value=v.answer;rationale.value=v.rationale;reason.value=v.reason;reasonDirty=false;}
 answer.oninput=()=>{if(selected){const p=proposals.find(p=>p.id===selected);if(normalize(answer.value)!==normalize(defaults(p,editing).answer)){selected='';markSelection();notice.textContent='Your edited answer will be saved as a written decision, not as the selected proposal.';if(!reasonDirty)reason.value=(editing?'Updated':'Recorded')+' a written decision.';}}};
 return {asWritten(){selected='';markSelection();if(!reasonDirty)reason.value=(editing?'Updated':'Recorded')+' a written decision.';},showError(error,box){
  for(const n of container.querySelectorAll('[aria-invalid]'))n.removeAttribute('aria-invalid');
  approvalControls.showError(error,box);
  const map={answer,rationale,selected_option:radios[0],expected_option_revision:radios[0]};
  const inferred={APPROVAL_DATE_FUTURE:'occurred_date',APPROVAL_DATE_INVALID:'precision',PROPOSAL_CHANGED:'selected_option',ANSWER_PROPOSAL_MISMATCH:'answer'};
  const fields=error.details?.fields||[{field:inferred[error.code]}];
  for(const item of fields){const name=item.field?.split(/[/.]/).filter(x=>x&&!/^\d+$/.test(x)).pop(),target=map[name];if(!activeControl(target,container))continue;target.setAttribute('aria-invalid','true');const b=el('button',item.message||('Review '+name.replaceAll('_',' ')));b.type='button';b.onclick=()=>{target.closest('details')?.setAttribute('open','');target.focus();};box.append(b);}
 },read(){
  const data={answer:answer.value,rationale:rationale.value,selected_option:selected||null};
  if(selected)data.expected_option_revision=proposals.find(p=>p.id===selected).revision;
  data.approval=approvalControls.read();
  return {data,reason:reason.value,authority_refs:[]};
 }};
}
