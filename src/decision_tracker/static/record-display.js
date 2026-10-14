// Presentation only: retained values stay literal and attribution stays explicit.
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export function recordSection(label,cls=''){
 const section=node('section',undefined,'record-section '+cls),heading=node('div',undefined,'record-section-heading');
 heading.append(node('h3',label,'section-title'));section.append(heading);return {section,heading};
}
export function metadata(){return node('dl',undefined,'record-metadata');}
export function metadataValue(list,label,value){
 const row=node('div',undefined,'record-metadata-row'),dd=node('dd');row.append(node('dt',label),dd);
 dd.append(value instanceof Node?value:node('span',value));list.append(row);return dd;
}
export function displayTime(value,dateOnly=false){
 if(!value)return node('span','Unknown','muted');
 const t=node('time');t.dateTime=value;t.title=value;
 if(dateOnly||!Number.isFinite(Date.parse(value)))t.textContent=value;
 else t.textContent=new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'long'}).format(new Date(value));
 return t;
}
export function approvalMetadata(approval,dateLabel='Decision date'){
 const list=metadata(),mode=approval?.mode;
 const approver=mode==='authenticated_now'?approval.recorded_by:mode==='reported'?approval.reported_approver:null;
 metadataValue(list,'Approver',approver||'Unknown');
 metadataValue(list,'Method',mode==='authenticated_now'?'Authenticated':mode==='reported'?'Reported':approval?'Legacy references':'Unavailable');
 metadataValue(list,dateLabel,displayTime(approval?.occurred_at||approval?.occurred_date,!approval?.occurred_at));
 metadataValue(list,'Recorded by',approval?.recorded_by||'Unknown');metadataValue(list,'Recorded at',displayTime(approval?.recorded_at));return list;
}
export function evidenceDisplay(state){
 const list=metadata();
 for(const [key,label] of [['implementation','Implementation'],['verification','Verification'],['acceptance','Acceptance']]){
  const entry=state?.[key],content=node('div',undefined,'record-evidence-value');
  content.append(node('span',entry?.status||'Not recorded',entry?.status?'':'muted'));
  if(entry?.responsible_role||entry?.evidence_refs?.length){const details=metadata();
   if(entry.responsible_role)metadataValue(details,'Responsible role',entry.responsible_role);
   if(entry.evidence_refs?.length){const refs=node('ul',undefined,'record-evidence-sources');for(const text of entry.evidence_refs)refs.append(node('li',text));metadataValue(details,'Evidence sources',refs);}
   content.append(details);
  }
  metadataValue(list,label,content);
 }
 return list;
}
const labels={description:'Description',benefit:'Benefit',cost:'Cost',disposition:'Disposition',reason:'Reason',locator:'Locator',kind:'Kind',availability:'Availability',authenticity:'Authenticity',limitations:'Limitations',impact:'Impact',baseline_disposition:'Baseline handling'};
const enums={'relates_to':'Related to','depends_on':'Depends on','supersedes':'Supersedes','amends':'Amends','unselected':'Unselected','selected':'Selected','rejected':'Rejected','retired':'Retired','evidence':'Evidence','authority':'Authority','external-decision':'External decision','known':'Known','unavailable':'Unavailable','unknown':'Unknown','verified':'Verified','unverified':'Unverified','continue':'Continue','pause':'Pause'};
function locatorValue(value){
 // DocDoc will provide destinations; arbitrary locators are never launched here.
 if(/^[a-z][a-z0-9+.-]*:/i.test(value)&&!(/^[a-z]:[\\/]/i.test(value)))return node('span',value);
 if(!/[\\/]/.test(value)&&! /\.[a-z0-9]{1,10}(?:[#?].*)?$/i.test(value))return node('span',value);
 const name=value.split(/[\\/]/).filter(Boolean).pop();if(!name)return node('span',value);
 const link=node('a',name,'record-source-inactive');link.setAttribute('role','link');link.setAttribute('aria-disabled','true');link.tabIndex=-1;return link;
}
export function supportingEntry(family,child,decisionLink){
 const card=node('article',undefined,'child-card'),title=node('h4',undefined,'record-entry-title');
 if(family==='links'){title.append(node('span',(enums[child.type]||child.type)+' · '),decisionLink(child.source_key),node('span',' → '),decisionLink(child.target_key));}
 else title.textContent=child.title||child.label;
 card.append(title);const list=metadata();
 for(const key of family==='alternatives'?['description','benefit','cost','disposition','reason']:family==='references'?['locator','kind','availability','authenticity','limitations']:['reason','impact','baseline_disposition']){
  if(child[key])metadataValue(list,labels[key],key==='locator'?locatorValue(child[key]):['disposition','kind','availability','authenticity','baseline_disposition'].includes(key)?enums[child[key]]||child[key]:child[key]);
 }
 card.append(list);return card;
}
