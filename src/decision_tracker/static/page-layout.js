export function placeControlHelp(help,tip){
 const r=help.getBoundingClientRect(),below=Math.max(0,innerHeight-r.bottom-24),above=Math.max(0,r.top-24);
 const down=below>=above;tip.style.maxHeight=Math.max(44,down?below:above)+'px';
 const b=tip.getBoundingClientRect();tip.style.left=Math.max(18,Math.min(r.left,innerWidth-b.width-18))+'px';tip.style.top=(down?r.bottom+6:Math.max(18,r.top-b.height-6))+'px';
}
// Browser-only presentation. Bind caches to ledger identity, never to a display name.
export function installPageLayouts($){
 const workspace=$('workspace'),projects=$('projects-view'),detail=$('detail');$('workspace-divider').remove();
 const decisionFrame=document.createElement('div');decisionFrame.className='tracker-regions';decisionFrame.id='decision-columns';
 decisionFrame.innerHTML='<section id="decision-browse" class="tracker-region tracker-browse" aria-label="Decisions"><div class="region-head"></div><div id="decision-browse-body" class="region-body"></div></section><div id="workspace-divider" class="tracker-divider" role="separator" aria-label="Resize decision browsing" aria-orientation="vertical" tabindex="0"></div><section id="decision-record" class="tracker-region tracker-selected" aria-label="Selected decision"><div id="record-head" class="region-head"><button id="back-decisions" type="button">Back to decisions</button><div id="record-identity" tabindex="-1"></div></div><div id="record-body" class="region-body"></div></section>';
 decisionFrame.prepend(decisionFrame.querySelector('#decision-record'),decisionFrame.querySelector('#workspace-divider'));
 $('decision-columns').remove();workspace.append(decisionFrame);
 const filters=$('filters');workspace.insertBefore(filters,decisionFrame);
 const searchRow=document.createElement('div');searchRow.className='tracker-search-row';searchRow.append(filters.querySelector('label'));filters.prepend(searchRow);
 const resultsHeading=document.createElement('div');resultsHeading.className='results-heading decision-results-heading';const resultsTitle=document.createElement('h2');resultsTitle.textContent='Decisions';resultsHeading.append(resultsTitle,$('result-count'));$('decision-browse').querySelector('.region-head').append(resultsHeading);
 const advanced=document.createElement('div');advanced.className='tracker-filter-actions';for(const child of [...filters.children].filter(n=>n!==searchRow))advanced.append(child);filters.append(advanced);
 const actions=document.createElement('div');actions.className='tracker-heading-actions';actions.append($('new-decision'));
 const refresh=document.createElement('button');refresh.id='decisions-refresh';refresh.type='button';refresh.textContent='↻ Refresh';actions.append(refresh);workspace.querySelector('.workspace-heading').append(actions);
 $('decision-browse-body').append($('results'),$('load-more'));$('record-head').append($('context'));$('record-body').append(detail);
 const frame=document.createElement('div');frame.className='tracker-regions';frame.id='project-columns';
 frame.innerHTML='<section id="project-browse" class="tracker-region tracker-browse" aria-label="Projects"><div class="region-head"><div class="tracker-search-row"><label>Search project names<input id="project-search" type="search" autocomplete="off"></label><span id="project-count" class="muted" aria-live="polite"></span></div></div><div id="project-browse-body" class="region-body"></div></section><div id="project-divider" class="tracker-divider" role="separator" aria-label="Resize project browsing" aria-orientation="vertical" tabindex="0"></div><section id="project-data" class="tracker-region tracker-selected" aria-label="Project data" tabindex="-1"><div class="region-head"><div id="project-data-identity"></div><div id="project-data-actions" class="tracker-heading-actions"></div></div><div id="project-data-body" class="region-body"></div></section>';
 projects.append(frame);$('project-browse-body').append($('project-admin'));$('project-data-body').append($('maintenance'));
 for(const section of [...projects.querySelectorAll(':scope>section')])if(section!==frame&&section.id!=='maintenance')section.remove();
 const projectActions=document.createElement('div');projectActions.className='tracker-heading-actions';projectActions.append($('new-project'),$('add-existing'));
 const catalogRefresh=document.createElement('button');catalogRefresh.id='projects-refresh';catalogRefresh.type='button';catalogRefresh.textContent='↻ Refresh';projectActions.append(catalogRefresh);$('projects-heading').append(projectActions);
 $('project-data-actions').append($('backups-button'),$('exports-button'),$('verify-button'),$('admin-info'),$('admin-help'));
 document.querySelector('.local-sidebar').hidden=true;$('admin-watermark').hidden=true;
 const links=document.createElement('nav');links.className='tracker-region-links';links.setAttribute('aria-label','Project regions');links.innerHTML='<button type="button" data-target="project-data">Project data</button><button type="button" data-target="project-search">Projects</button>';projects.insertBefore(links,frame);
 links.onclick=e=>{const id=e.target.dataset.target;if(id){$(id).focus();$(id).scrollIntoView({block:'start'});}};
 let compact=true,mode='browse',focused=false,active=null,activeRecord=null;const cache=new Map(),recordScroll=new Map();
 const key=p=>p&&p.project_id+'\0'+p.ledger_uuid;
 const snapshot=()=>({search:$('search').value,status:$('status').value,work:$('work').value,browse:$('decision-browse-body').scrollTop,record:$('record-body').scrollTop,key:activeRecord,mode});
 function remember(){if(active){cache.set(active,snapshot());if(activeRecord)recordScroll.set(active+'\0'+activeRecord,$('record-body').scrollTop);}}
 function project(p){remember();active=key(p);const held=cache.get(active);activeRecord=held?.key||null;for(const id of ['search','status','work'])$(id).value=held?.[id]||'';mode='browse';focused=false;sync();restore(held);return activeRecord;}
 function restore(held=cache.get(active)){if(held)requestAnimationFrame(()=>{$('decision-browse-body').scrollTop=held.browse;$('record-body').scrollTop=held.record;});}
 function sync(){workspace.classList.toggle('record-open',mode==='record');workspace.classList.toggle('tracker-focus',focused&&!compact);const controls=$('context'),parent=(focused&&!compact)||(compact&&mode==='record')?$('record-head'):$('decision-browse').querySelector('.region-head');if(controls.parentElement!==parent){const focus=document.activeElement;parent=== $('record-head')?parent.append(controls):parent.insertBefore(controls,resultsHeading);if(focus&&controls.contains(focus))focus.focus();}$('focus-toggle').hidden=compact||workspace.hidden;$('focus-toggle').setAttribute('aria-pressed',String(focused));$('focus-toggle').setAttribute('aria-label',focused?'Show decisions':'Focus decision');$('focus-toggle').title=focused?'Show decisions':'Focus decision';}
 function record({focus=false,key=null}={}){if(key&&key!==activeRecord){activeRecord=key;$('record-body').scrollTop=recordScroll.get(active+'\0'+key)||0;}mode='record';sync();if(focus&&compact)$('record-identity').focus();}
 function browse({focus=true}={}){mode='browse';sync();const selected=$('results').querySelector('[aria-current=true]');if(focus)(selected||$('search')).focus();restore();}
 $('focus-toggle').onclick=()=>{focused=!focused;sync();};
 function setup(page,frame,divider,storage){
  let preferred=null;try{const raw=localStorage.getItem(storage),n=Number(raw);if(raw!==null&&Number.isFinite(n)&&n>=280&&n<=500)preferred=n;}catch{}
  let current=280,maximum=500;
  const update=()=>{const wide=innerWidth>980&&page.clientWidth>960;page.classList.toggle('tracker-wide',wide);const available=frame.clientWidth-10;maximum=Math.min(500,available-480);current=Math.max(280,Math.min(maximum,preferred??available*.35));frame.style.setProperty('--browse-width',current+'px');divider.setAttribute('aria-valuenow',String(Math.round(current)));divider.setAttribute('aria-valuemin','280');divider.setAttribute('aria-valuemax',String(Math.round(Math.max(280,maximum))));divider.setAttribute('aria-valuetext',Math.round(current)+' pixels browsing');if(page===workspace){const before=compact;compact=!wide;if(before!==compact){const selected=$('detail').dataset.loaded==='true';if(compact&&selected)mode='record';sync();}else sync();}else {const browse=$('project-browse'),selected=$('project-data');const focusedNode=document.activeElement;const order=wide?[browse,divider,selected]:[selected,browse,divider];if(order.some((item,index)=>frame.children[index]!==item))frame.prepend(...order);if(focusedNode&&page.contains(focusedNode)&&focusedNode!==document.activeElement)focusedNode.focus();}};
  const resize=(value,persist=false)=>{preferred=Math.max(280,Math.min(maximum,value));update();if(persist)try{localStorage.setItem(storage,String(preferred));}catch{}};
  divider.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();divider.focus();divider.setPointerCapture(e.pointerId);};
  const browseRight=page===workspace;
  divider.onpointermove=e=>{if(divider.hasPointerCapture(e.pointerId)){const bounds=frame.getBoundingClientRect();resize(browseRight?bounds.right-e.clientX-10:e.clientX-bounds.left);}};
  for(const type of ['pointerup','pointercancel'])divider.addEventListener(type,e=>{if(!divider.hasPointerCapture(e.pointerId))return;divider.releasePointerCapture(e.pointerId);resize(current,true);});
  divider.onkeydown=e=>{const step=(e.shiftKey?50:15)*(browseRight?-1:1),values={ArrowLeft:current-step,ArrowRight:current+step,Home:280,End:maximum};if(e.key in values){e.preventDefault();resize(values[e.key],true);}};
  new ResizeObserver(update).observe(page);window.addEventListener('resize',update);update();
 }
 setup(workspace,decisionFrame,$('workspace-divider'),'dt.decisionsBrowseWidth');setup(projects,frame,$('project-divider'),'dt.projectsBrowseWidth');
 new ResizeObserver(()=>workspace.style.setProperty('--decision-filters-height',filters.getBoundingClientRect().height+'px')).observe(filters);
 for(const page of [workspace,projects]){page.classList.add('tracker-page');const head=page.querySelector(':scope>.workspace-heading,:scope>.admin-heading');new ResizeObserver(()=>page.style.setProperty('--page-heading-height',head.getBoundingClientRect().height+'px')).observe(head);}
 return {project,remember,restore,record,browse,sync,get selectedKey(){return activeRecord;},get compact(){return compact;},get mode(){return mode;}};
}
