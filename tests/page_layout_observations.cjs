const assert=require('node:assert/strict'),fs=require('node:fs');
module.exports=async function(page,out,kind){
 const projects=kind==='projects',root=projects?'#projects-view':'#workspace',divider=projects?'#project-divider':'#workspace-divider',search=projects?'#project-search':'#search',count=projects?'#project-count':'#result-count',storage=projects?'dt.projectsBrowseWidth':'dt.decisionsBrowseWidth';
 const settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));const observations=[];
 await page.setViewportSize({width:1440,height:1000});await settle();
 assert.equal(await page.locator('.local-sidebar').isVisible(),false);
 await page.locator(divider).focus();await page.keyboard.press('Home');await settle();assert.equal(await page.locator(divider).getAttribute('aria-valuenow'),'280');
 await page.keyboard.press(projects?'ArrowRight':'ArrowLeft');assert.equal(await page.locator(divider).getAttribute('aria-valuenow'),'295');assert.equal(await page.evaluate(k=>localStorage.getItem(k),storage),'295');
 await page.keyboard.press(projects?'Shift+ArrowRight':'Shift+ArrowLeft');assert.equal(await page.locator(divider).getAttribute('aria-valuenow'),'345');
 await page.keyboard.press('End');await settle();const max=Number(await page.locator(divider).getAttribute('aria-valuemax'));assert.ok(max<=500);assert.equal(Number(await page.locator(divider).getAttribute('aria-valuenow')),max);
 const selected=await page.locator(projects?'#project-data':'#decision-record').boundingBox();assert.ok(selected.width>=480-1);
 for(const width of [1920,1690,1440,1009,1008,981,980,600,320]){
  await page.setViewportSize({width,height:900});await settle();const wide=await page.locator(root).evaluate(e=>e.classList.contains('tracker-wide'));
  assert.equal(wide,await page.locator(root).evaluate(e=>innerWidth>980&&e.clientWidth>960));
  if(!projects&&!wide){await page.locator('#back-decisions').click();await page.locator(search).waitFor();}
  const s=await page.locator(search).boundingBox(),c=await page.locator(count).boundingBox();assert.ok(s&&c);if(projects){assert.ok(Math.abs(s.y+s.height/2-c.y-c.height/2)<=2);assert.ok(c.x>=s.x+s.width-1);}else {assert.equal(await page.locator(count).evaluate(e=>e.closest('.tracker-region').id),'decision-browse');const results=await page.locator('#decision-browse-body').boundingBox();assert.ok(c.y+c.height<=results.y+1);}
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if(!projects&&wide){const bounds=await page.locator(root).boundingBox();assert.ok(width-bounds.x-bounds.width<=49);const help=await page.locator('#context>.panel-info').boundingBox(),primary=await page.locator('#context>.control-primary').boundingBox();assert.ok(Math.abs(help.y+help.height/2-primary.y-primary.height/2)<=2);const nav=await page.locator('.page-nav button').evaluateAll(nodes=>nodes.map(n=>({border:getComputedStyle(n).borderTopWidth,background:getComputedStyle(n).backgroundColor})));assert.ok(nav.every(n=>n.border==='0px'&&n.background==='rgba(0, 0, 0, 0)'));}
  assert.equal(await page.locator(divider).isVisible(),wide);
  if(!projects){assert.equal(await page.locator('#filters').evaluate(e=>e.parentElement.id),'workspace');const filters=await page.locator('#filters').boundingBox(),frame=await page.locator('#decision-columns').boundingBox();assert.ok(filters.y+filters.height<=frame.y+1);}
  if(!projects&&wide){const record=await page.locator('#decision-record').boundingBox(),browse=await page.locator('#decision-browse').boundingBox(),controls=await page.locator('#context').boundingBox(),body=await page.locator('#decision-browse-body').boundingBox();assert.ok(record.x+record.width<=browse.x);assert.equal(await page.locator('#decision-columns').evaluate(e=>e.firstElementChild.id),'decision-record');assert.equal(await page.locator('#context').evaluate(e=>e.closest('.tracker-region').id),'decision-browse');assert.ok(controls.x>=browse.x&&controls.y+controls.height<=body.y+1);}
  if(projects&&!wide)assert.ok(await page.locator('#project-columns').evaluate(e=>e.firstElementChild.id==='project-data'));
  observations.push({width,wide,search:s,count:c});await page.screenshot({path:`${out}/layout-${kind}-${width}.png`});
  if(!projects&&!wide){await page.locator('#results button').first().click();await page.locator('#detail[data-loaded=true]').waitFor();assert.equal(await page.locator('#decision-browse').isVisible(),false);assert.equal(await page.locator('#record-identity').evaluate(e=>e===document.activeElement),true);await page.screenshot({path:`${out}/layout-record-${width}.png`});}
 }
 await page.setViewportSize({width:1440,height:1000});await settle();assert.equal(Number(await page.locator(divider).getAttribute('aria-valuenow')),max);
 const boundary=await page.locator(divider).boundingBox();await page.mouse.move(boundary.x+4,boundary.y+40);await page.mouse.down();await page.mouse.move(boundary.x+(projects?-80:80),boundary.y+40);await page.mouse.up();await settle();assert.ok(Number(await page.locator(divider).getAttribute('aria-valuenow'))<max);assert.ok(Number(await page.locator(divider).getAttribute('aria-valuenow'))>=280);
 await page.setViewportSize({width:1440,height:400});await settle();assert.ok((await page.locator(projects?'#project-data-body':'#record-body').boundingBox()).height>=64);await page.screenshot({path:`${out}/layout-${kind}-short.png`});await page.setViewportSize({width:1440,height:1000});await settle();
 if(projects){await page.locator(search).fill('no matching project');assert.equal(await page.locator(count).textContent(),'0');await page.locator('#project-admin').getByText('No matching projects.').waitFor();await page.locator(search).fill('');assert.ok(Number(await page.locator(count).textContent())>=1);}
 else {const text=await page.locator(search).inputValue();await page.locator(search).fill('explicit-submit-fixture');await page.waitForTimeout(350);assert.ok(await page.locator('#results button').count());await page.locator(search).fill(text);}
 fs.writeFileSync(`${out}/layout-${kind}-observations.json`,JSON.stringify(observations,null,2));
};
module.exports.captureRegions=async function(page,out,kind,label){
 const root=kind==='projects'?'#projects-view':'#workspace';
 for(const fraction of [0,.5,1]){if(fraction===0)await page.locator(root+'>.workspace-heading,'+root+'>.admin-heading').evaluate(e=>e.scrollTop=0);await page.evaluate(({root,fraction})=>{const p=document.querySelector(root),main=document.querySelector('#main-content'),wide=p.classList.contains('tracker-wide');const surfaces=wide?[...p.querySelectorAll('.region-body')]:[getComputedStyle(main).overflowY==='auto'?main:document.scrollingElement];for(const surface of surfaces)surface.scrollTop=(surface.scrollHeight-surface.clientHeight)*fraction;},{root,fraction});await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await page.bringToFront();const session=await page.context().newCDPSession(page);try{const pixels=await session.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});fs.writeFileSync(`${out}/layout-${kind}-${label}-${fraction}.png`,Buffer.from(pixels.data,'base64'));}finally{await session.detach();}}
 await page.evaluate(()=>{document.querySelector('#main-content').scrollTop=0;window.scrollTo(0,0);});
};
