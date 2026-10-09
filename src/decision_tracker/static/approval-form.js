// Shared approval controls for resolution and deprecation.
import {activeControl} from './form-controls.js';
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
export function installApprovalForm(container,idPrefix='resolution-'){
 function input(label,name,value='',type='textarea',required=false,parent=container){const wrap=el('label',label),n=el(type==='textarea'?'textarea':'input');if(type!=='textarea')n.type=type;n.name=name;n.id=idPrefix+name;n.value=value;n.required=required;wrap.htmlFor=n.id;wrap.append(n);parent.append(wrap);return n;}
 const approval=el('fieldset'),approvalNotice=el('p','Approval will be recorded as Operator when you save.');approval.append(el('legend','Approval'),approvalNotice);container.append(approval);
 const report=input('Record an earlier or external approval','reported','','checkbox',false,approval);
 const history=el('div');history.hidden=true;approval.append(history);
 const approver=input('Who approved?','approver','','text',false,history);approver.maxLength=160;
 const sources=el('div');history.append(sources);const sourceFields=[];
 let sourceSerial=0;
 const addSource=()=>{const n=input('Approval source','source_'+sourceSerial++,'','text',false,sources);n.maxLength=1024;sourceFields.push(n);const remove=el('button','Remove this source');remove.type='button';remove.onclick=()=>{if(sourceFields.length>1){sourceFields.splice(sourceFields.indexOf(n),1);n.closest('label').remove();remove.remove();sourceFields[0].focus();}};sources.append(remove);return n;};addSource();
 history.append(el('p','Identify the message, document or note that records the approval. A document path, link or descriptive note is accepted.'));
 const add=el('button','Add another source');add.type='button';add.onclick=()=>{if(sourceFields.length<32){addSource().focus();sync();}};history.append(add);
 const pl=el('label','When was the decision made?'),precision=el('select');precision.name='precision';precision.id=idPrefix+'precision';pl.htmlFor=precision.id;
 for(const [v,t] of [['','Choose what is known'],['exact','Date and time known'],['date','Date known, time unknown'],['unknown','Date unknown']]){const o=el('option',t);o.value=v;precision.append(o);}pl.append(precision);history.append(pl);
 const date=input('Date of decision','approval_date','','date',false,history),time=input('Time of decision','approval_time','','time',false,history);time.step=1;
 const offsetLabel=el('label','UTC offset'),offset=el('select');offset.name='offset';offset.id=idPrefix+'offset';offsetLabel.htmlFor=offset.id;
 for(let m=-720;m<=840;m+=15){const o=el('option',(m>=0?'+':'-')+String(Math.floor(Math.abs(m)/60)).padStart(2,'0')+':'+String(Math.abs(m)%60).padStart(2,'0'));o.value=m;offset.append(o);}offsetLabel.append(offset);history.append(offsetLabel);
 const zone=Intl.DateTimeFormat().resolvedOptions().timeZone;history.append(el('p','Local timezone: '+zone+'. Choose the recorded UTC offset if the approval occurred elsewhere.'));
 const confirm=input('This is the date of the original decision','date_confirm','','checkbox',false,history);
 function sync(){const active=report.checked,known=precision.value==='exact'||precision.value==='date';history.hidden=!active;for(const n of history.querySelectorAll('input,select,button'))n.disabled=!active;approver.required=active;precision.required=active;sourceFields.forEach(n=>n.required=active);for(const n of [date,offset,confirm]){n.closest('label').hidden=!known;n.disabled=!active||!known;}time.closest('label').hidden=precision.value!=='exact';time.disabled=!active||precision.value!=='exact';date.required=active&&known;time.required=active&&precision.value==='exact';confirm.required=active&&known;}
 report.onchange=()=>{approvalNotice.textContent=report.checked?'You are recording an approval made earlier or outside this application. The approver below is reported, not authenticated.':'Approval will be recorded as Operator when you save.';sync();};precision.onchange=()=>{const n=new Date(),pad=x=>String(x).padStart(2,'0');date.value=n.getFullYear()+'-'+pad(n.getMonth()+1)+'-'+pad(n.getDate());time.value=pad(n.getHours())+':'+pad(n.getMinutes())+':'+pad(n.getSeconds());offset.value=-n.getTimezoneOffset();confirm.checked=false;explicitOffset=false;sync();};
 let explicitOffset=false;offset.onchange=()=>explicitOffset=true;
 date.oninput=time.oninput=()=>{confirm.checked=true;explicitOffset=false;if(date.value&&time.value)offset.value=-new Date(date.value+'T'+time.value).getTimezoneOffset();};sync();
 return {showError(error,box){
 const map={approver,sources:sourceFields.find(n=>activeControl(n,container)),occurred_at:date,occurred_date:date,precision,utc_offset_minutes:offset};
 const inferred={APPROVAL_DATE_FUTURE:'occurred_date',APPROVAL_DATE_INVALID:'precision',APPROVER_REQUIRED:'approver',APPROVAL_SOURCE_REQUIRED:'sources'};
 for(const item of error.details?.fields||[{field:inferred[error.code]}]){const name=item.field?.split(/[/.]/).filter(x=>x&&!/^\d+$/.test(x)).pop(),target=map[name];if(!activeControl(target,container))continue;target.setAttribute('aria-invalid','true');const b=el('button',item.message||('Review '+name.replaceAll('_',' ')));b.type='button';b.onclick=()=>target.focus();box.append(b);}
 },read(){const data={};
  if(!report.checked)data.approval={mode:'authenticated_now'};
  else{const a={mode:'reported',approver:approver.value.trim(),sources:sourceFields.filter(n=>activeControl(n,container)).map(n=>n.value.trim()).filter(Boolean),precision:precision.value};
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
 return data.approval;}};
}
