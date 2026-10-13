const assert=require('node:assert/strict');
const fs=require('node:fs');

// Real browser interactions on disposable application data. No replacement DOM or CSS scaling.
module.exports=async function stickyHeading(page,out,{zoom=false}={}){
 const heading=page.locator('#workspace>.workspace-heading');
 const edit=async question=>{
  await page.locator('#context .control-primary').getByRole('button',{name:'Edit',exact:true}).click();
  await page.locator('#edit-fields [name=question]').fill(question);
  await page.locator('#save-edit').click();await page.locator('#editor').waitFor({state:'hidden'});
  await page.waitForFunction(text=>document.querySelector('#detail').textContent.includes(text),question.slice(0,100));
 };
 // Read the original value through the supported edit form, not a guessed detail selector.
 await page.locator('#context .control-primary').getByRole('button',{name:'Edit',exact:true}).click();
 const retained=await page.locator('#edit-fields [name=question]').inputValue();
 await page.locator('#cancel-edit').click();await page.locator('#editor').waitFor({state:'hidden'});
 const longQuestion=Array.from({length:36},(_,i)=>`Sticky heading reading paragraph ${i+1}. Project context must remain available while the record scrolls. Keyboard navigation and project selection must remain usable.`).join('\n\n');
 const observations=[];
 const settle=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const scroll=async fraction=>{
  await page.evaluate(f=>{
   const main=document.querySelector('.local-content'),pane=getComputedStyle(main).overflowY==='auto';
   const node=pane?main:document.scrollingElement,frameTop=pane?main.getBoundingClientRect().top:0;
   // Compact layout puts the independent sidebar after the record. Exercise the record's scroll extent.
   const recordEnd=node.scrollTop+document.querySelector('#workspace').getBoundingClientRect().bottom-frameTop-node.clientHeight;
   node.scrollTop=Math.max(0,Math.min(node.scrollHeight-node.clientHeight,recordEnd))*f;
  },fraction);await settle();
 };
 const geometry=()=>page.evaluate(()=>{
  const heading=document.querySelector('#workspace>.workspace-heading'),main=document.querySelector('.local-content');
  const pane=getComputedStyle(main).overflowY==='auto',node=pane?main:document.scrollingElement;
  const style=getComputedStyle(heading),h=heading.getBoundingClientRect();
  return {viewport:{width:innerWidth,height:innerHeight},heading:h.toJSON(),scrollTop:node.scrollTop,
   maxScroll:node.scrollHeight-node.clientHeight,frameTop:pane?main.getBoundingClientRect().top:0,workspaceBottom:document.querySelector('#workspace').getBoundingClientRect().bottom,
   filters:document.querySelector('#filters').getBoundingClientRect().toJSON(),
   title:document.querySelector('#workspace-title').textContent,project:document.querySelector('#project').value,
   position:style.position,background:style.backgroundColor,border:style.borderTopWidth,shadow:style.boxShadow,
   horizontalOverflow:document.documentElement.scrollWidth>innerWidth,headingCount:document.querySelectorAll('#workspace>.workspace-heading').length};
 });
 const capture=async name=>{
  await page.bringToFront();await settle();
  const session=await page.context().newCDPSession(page);
  try{const shot=await session.send('Page.captureScreenshot',{format:'png',fromSurface:true});fs.writeFileSync(`${out}/${name}.png`,Buffer.from(shot.data,'base64'));}
  finally{await session.detach();}
 };
 try{
  await edit(longQuestion);
  const sizes=zoom?[null]:[1440,981,980,600,320];
  for(const width of sizes){
   if(width)await page.setViewportSize({width,height:900});
   await scroll(0);const top=await geometry();
   assert.equal(top.position,'sticky');assert.equal(top.headingCount,1);assert.equal(top.horizontalOverflow,false);
   assert.equal(top.border,'0px');assert.equal(top.shadow,'none');assert.notEqual(top.background,'rgba(0, 0, 0, 0)');
   assert.ok(top.maxScroll>top.heading.height*2,'Synthetic record must exercise downward scrolling');
   await capture(`sticky-${zoom?'zoom-200':width}-top`);
   for(const fraction of [.45,.95]){
    await scroll(fraction);const pinned=await geometry();
    assert.ok(Math.abs(pinned.heading.top-pinned.frameTop)<=1,JSON.stringify(pinned));
    assert.ok(pinned.filters.top<top.filters.top-50,'Filters must scroll separately from heading');
    assert.ok(pinned.heading.bottom<pinned.viewport.height-100,'Retain a reading area');
    assert.ok(await page.locator('#project').evaluate(n=>{const r=n.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}));
    observations.push({width:width||'actual-200-percent',fraction,...pinned});
   }
   await capture(`sticky-${zoom?'zoom-200':width}-scrolled`);
   // The existing status control is clickable above the scrolling record and opens its real dialog.
   await page.locator('#freshness').click();await page.locator('#live-review').waitFor();
   assert.ok(await page.locator('#live-review').evaluate(n=>{const r=n.getBoundingClientRect();return n.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}));
   await page.locator('#close-live-review').click();await page.locator('#live-review').waitFor({state:'hidden'});
   await page.locator('#project').focus();await page.keyboard.press('Tab');assert.equal(await page.locator('#freshness').evaluate(n=>n===document.activeElement),true);
   await page.keyboard.press('Tab');assert.equal(await page.locator('#search').evaluate(n=>n===document.activeElement),true);
   const focus=await page.locator('#search').boundingBox(),sticky=await heading.boundingBox();
   assert.ok(focus.y>=sticky.y+sticky.height-1,'Tab target cannot hide behind sticky heading');
   await page.keyboard.press('Shift+Tab');assert.equal(await page.locator('#freshness').evaluate(n=>n===document.activeElement),true);
   await scroll(.5);const route=page.url(),selected=await page.locator('#detail>.eyebrow').innerText();
   await page.locator('.skip-link').focus();await page.keyboard.press('Enter');await settle();
   assert.ok(await page.locator('#main-content').evaluate(n=>n===document.activeElement));
   assert.equal(page.url(),route,'Skip link must preserve the application route');
   assert.equal(await page.locator('#detail>.eyebrow').innerText(),selected,'Skip link must preserve the selected record');
   await scroll(0);const returned=await geometry();assert.ok(Math.abs(returned.heading.top-top.heading.top)<=1);
  }
  if(!zoom){
   await page.setViewportSize({width:1440,height:900});await scroll(.5);
   await page.locator('#focus-toggle').click();await settle();const focused=await geometry();assert.ok(Math.abs(focused.heading.top-focused.frameTop)<=1);
   await page.locator('#focus-toggle').click();
   await page.locator('#projects-button').click();await page.locator('#projects-view').waitFor();
   assert.equal(await page.locator('#projects-heading #project-picker').count(),1);
   assert.equal(await page.locator('#projects-heading').evaluate(n=>getComputedStyle(n).position),'static');
   await page.locator('#saved-button').click();await page.locator('#library-view').waitFor();assert.equal(await page.locator('#project-picker').isVisible(),false);
   await page.locator('#decisions-button').click();await page.locator('#detail[data-loaded=true]').waitFor();
   assert.equal(await heading.locator('#project-picker').count(),1);await scroll(.5);
   assert.ok(Math.abs((await geometry()).heading.top-(await geometry()).frameTop)<=1);
  }
  await scroll(0);await edit(retained);
  fs.writeFileSync(`${out}/sticky-${zoom?'zoom-200':'heading'}-observations.json`,JSON.stringify({observations,questionRestored:true},null,2));
 }catch(error){await capture(`sticky-${zoom?'zoom-200':'heading'}-failure`);throw error;}
};
