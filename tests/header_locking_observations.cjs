const assert=require('node:assert/strict'),fs=require('node:fs');
module.exports=async function(page,out,kind,{zoom=false}={}){
 const observations=[],settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 async function check(scroll,header,sticky,label){
  await settle();
  await page.locator(scroll).evaluate(e=>e.scrollTop=0);await settle();
  const before=await page.locator(header).boundingBox();
  await page.locator(scroll).evaluate(e=>e.scrollTop=350);await settle();
  const data=await page.locator(header).evaluate((h,selector)=>{const s=document.querySelector(selector),r=h.getBoundingClientRect(),f=s.getBoundingClientRect();return {top:r.top,frame:f.top+s.clientTop,position:getComputedStyle(h).position,scroll:s.scrollTop,height:r.height};},scroll);
  assert.ok(data.scroll>100,label+' scroll fixture');
  if(sticky){assert.equal(data.position,'sticky');assert.ok(Math.abs(data.top-data.frame)<=1,JSON.stringify({label,...data}));}
  else {assert.notEqual(data.position,'sticky');assert.ok(data.top<before.y-100);}
  observations.push({label,sticky,...data});
  if(sticky){
   for(const target of [700,1200]){
    await page.locator(scroll).evaluate((e,t)=>e.scrollTop=t,target);await settle();
    const further=await page.locator(header).evaluate((h,selector)=>{const s=document.querySelector(selector);return {top:h.getBoundingClientRect().top,frame:s.getBoundingClientRect().top+s.clientTop,scroll:s.scrollTop};},scroll);
    assert.ok(Math.abs(further.top-further.frame)<=1,JSON.stringify({label,target,...further}));observations.push({label,target,...further});
   }
   await page.locator(scroll).evaluate(e=>e.scrollTop=350);await settle();
   const control=page.locator(header).locator('button,select').first();
   if(await control.count()){
    await control.focus();await settle();
    assert.ok(await control.evaluate(e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return e===document.activeElement&&(hit===e||e.contains(hit));}),label+' pinned control focus/hit target');
   }
  }
  if(sticky){const session=await page.context().newCDPSession(page);try{const shot=await session.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});fs.writeFileSync(`${out}/header-${label}.png`,Buffer.from(shot.data,'base64'));}finally{await session.detach();}}
  await page.locator(scroll).evaluate(e=>e.scrollTop=0);
 }
 const fixture=async selector=>page.locator(selector).evaluate(e=>{const n=document.createElement('div');n.dataset.headerFixture='';n.style.height='1800px';n.textContent='Synthetic long scrolling content for header geometry.';e.append(n);});
 const cleanup=()=>page.evaluate(()=>document.querySelectorAll('[data-header-fixture]').forEach(n=>n.remove()));
 const size=page.viewportSize();
 try{
  if(kind==='actions'){
   await page.locator('#context .control-primary').getByRole('button',{name:'Edit',exact:true}).click();
   await fixture('#edit-fields');
   for(const width of zoom?[null]:[1440,601,600,320]){if(width)await page.setViewportSize({width,height:1000});await check('#editor','#edit-context',zoom?await page.evaluate(()=>innerWidth>600):width>600,`action-${zoom?'zoom':width}`);}
   await cleanup();await page.locator('#cancel-edit').click();
   await page.evaluate(()=>document.querySelector('#live-review').showModal());await fixture('#live-review-content');
   for(const width of zoom?[null]:[1440,600]){if(width)await page.setViewportSize({width,height:1000});await check('#live-review','#live-review>.dialog-heading',zoom?await page.evaluate(()=>innerWidth>600):width>600,`updates-${zoom?'zoom':width}`);}
   await cleanup();await page.locator('#close-live-review').click();
  }else if(kind==='projects'){
   await fixture('#projects-view');
   for(const width of [1440,981]){await page.setViewportSize({width,height:1000});await check('#main-content','#projects-heading',true,`projects-${width}`);}
   await page.setViewportSize({width:980,height:1000});assert.notEqual(await page.locator('#projects-heading').evaluate(e=>getComputedStyle(e).position),'sticky');
  }else if(kind==='library'){
   await fixture('#saved-list');
   for(const width of [1440,1009,1008,981,980,600,320]){
    await page.setViewportSize({width,height:1000});await settle();
    const wide=await page.locator('#library-view').evaluate(e=>innerWidth>980&&e.clientWidth>960);
    assert.equal(await page.locator('.library-header-locked').count(),wide?1:0);
    if(wide){await check('#main-content','.library-header-locked',true,`library-${width}`);const header=await page.locator('.library-header-locked').boundingBox();const stage=await page.locator('#library-staging').boundingBox();if(stage)assert.ok(stage.y>=header.y+header.height);}
    else assert.equal(await page.locator('.library-filters #saved-view-toggle').count(),1);
   }
   await cleanup();await page.setViewportSize({width:1440,height:1000});
   await page.locator('#saved-new').click();await fixture('#saved-fields');
   for(const width of [1440,600,320]){await page.setViewportSize({width,height:1000});await check('#saved-editor','#saved-editor .locked-dialog-heading',width>600,`library-editor-${width}`);}
   await cleanup();await page.locator('#saved-cancel').click();await page.setViewportSize({width:1440,height:1000});
   await page.locator('#saved-management-open').click();await page.locator('#saved-manage-groups').click();await fixture('#saved-group-list');
   for(const width of [1440,600]){await page.setViewportSize({width,height:1000});await check('#saved-group-dialog','#saved-group-dialog .locked-dialog-heading',width>600,`groups-${width}`);}
   await cleanup();await page.locator('#saved-group-close').click();
  }
 }finally{await cleanup();if(size)await page.setViewportSize(size);await page.evaluate(()=>{document.querySelector('#main-content').scrollTop=0;window.scrollTo(0,0);});}
 fs.writeFileSync(`${out}/header-${kind}${zoom?'-zoom':''}-observations.json`,JSON.stringify(observations,null,2));
};
