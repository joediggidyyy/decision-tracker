const assert=require('node:assert/strict'),fs=require('node:fs');

module.exports=async function decideContext(page,out,{zoom=false}={}){
 const editor=page.locator('#editor'),context=page.locator('#edit-context');
 const settle=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const edit=async text=>{
  await page.locator('#context .control-primary').getByRole('button',{name:'Edit',exact:true}).click();
  await editor.waitFor();
  const question=page.locator('#edit-fields [name=question]');
  if(text===undefined){const value=await question.inputValue();await page.locator('#cancel-edit').click();await editor.waitFor({state:'hidden'});return value;}
  await question.fill(text);await page.locator('#save-edit').click();await editor.waitFor({state:'hidden'});
  await page.waitForFunction(text=>document.querySelector('#detail').textContent.includes(text),text.slice(0,100));
 };
 const retained=await edit();
 const question=Array.from({length:8},(_,i)=>`Context sentence ${i+1}: Which approach preserves project boundaries, complete evidence and reachable controls as the decision form scrolls?`).join(' ');
 const observations=[];
 const capture=async name=>{
  await page.bringToFront();await settle();const session=await page.context().newCDPSession(page);
  try{const shot=await session.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});fs.writeFileSync(`${out}/${name}.png`,Buffer.from(shot.data,'base64'));}
  finally{await session.detach();}
 };
 const geometry=()=>editor.evaluate(n=>{
  const c=n.querySelector('#edit-context'),legend=n.querySelector('#edit-fields legend'),r=c.getBoundingClientRect();
  return {viewport:innerWidth,dialog:n.getBoundingClientRect().toJSON(),frameTop:n.getBoundingClientRect().top+n.clientTop,context:r.toJSON(),position:getComputedStyle(c).position,
   scrollTop:n.scrollTop,maxScroll:n.scrollHeight-n.clientHeight,legendTop:legend.getBoundingClientRect().top,
   contextScrollHeight:c.scrollHeight,contextClientHeight:c.clientHeight,shadow:getComputedStyle(c).boxShadow,border:getComputedStyle(c).borderTopWidth};
 });
 const cancel=async()=>{await page.keyboard.press('Escape');await editor.waitFor({state:'hidden'});};
 try{
  await edit(question);
  for(const width of zoom?[null]:[1440,601,600,320]){
   if(width)await page.setViewportSize({width,height:900});
   await page.locator('.closure-slot button').click();await editor.waitFor();
   await editor.evaluate(n=>n.scrollTop=0);await settle();
   assert.equal(await context.locator('#edit-project').count(),1);
   assert.equal(await context.locator('.resolution-question').innerText(),question);
   const body=await editor.innerText();
   assert.equal(body.includes('Choose a proposal or write your answer.'),false);
   assert.equal(body.includes('Switching choices replaces'),false);
   const top=await geometry(),wide=top.viewport>600;
   assert.equal(top.position,wide?'sticky':'static');assert.equal(top.shadow,'none');assert.equal(top.border,'0px');
   assert.ok(top.maxScroll>100);
   await capture(`decide-context-${zoom?'zoom-200':width}-top`);
   await editor.evaluate(n=>n.scrollTop=(n.scrollHeight-n.clientHeight)*.75);await settle();const middle=await geometry();
   await editor.evaluate(n=>n.scrollTop=(n.scrollHeight-n.clientHeight)*.95);await settle();const end=await geometry();
   if(wide){
    assert.ok(Math.abs(end.context.top-middle.context.top)<=1,'Wide question context stays pinned');
    assert.ok(Math.abs(end.context.top-end.frameTop)<=1,'Pinned context meets the inner frame edge without a gap');
    assert.ok(end.context.bottom<end.dialog.bottom-100,'Form retains usable reading space');
    assert.deepEqual(await context.evaluate(n=>{
     const r=n.getBoundingClientRect(),blocked=[];
     for(let y=r.top+2;y<r.bottom-1;y+=8)for(let x=r.left+8;x<r.right-8;x+=40){const top=document.elementFromPoint(x,y);if(!n.contains(top))blocked.push(top?.tagName||'outside');}
     return blocked;
    }),[],'Question context must paint above scrolling fields and legends');
   }else{
    assert.ok(Math.abs((top.context.top-end.context.top)-end.scrollTop)<=1,'Mobile context scrolls with the form');
   }
   assert.ok(end.legendTop<top.legendTop-100,'Choice content continues to scroll');
   await capture(`decide-context-${zoom?'zoom-200':width}-scrolled`);
   await page.locator('#edit-fields [name=answer]').focus();await settle();
   if(wide){const field=await page.locator('#edit-fields [name=answer]').boundingBox(),pinned=await context.boundingBox();assert.ok(field.y>=pinned.y+pinned.height-1,'Focused answer stays below pinned context');}
   observations.push({width:width||'actual-200-percent',top,middle,end});await cancel();
  }
  if(!zoom){
   // An unusually long question remains readable without trapping the rest of the form.
   await page.setViewportSize({width:1440,height:900});await edit(question.repeat(6));
   await page.locator('.closure-slot button').click();await editor.waitFor();await settle();
   assert.ok(await context.evaluate(n=>n.clientHeight<=innerHeight*.45+1&&n.scrollHeight>n.clientHeight));
   await context.evaluate(n=>n.scrollTop=n.scrollHeight);assert.ok(await context.evaluate(n=>n.scrollTop>0));
   await page.locator('#edit-fields [name=answer]').focus();await settle();
   const field=await page.locator('#edit-fields [name=answer]').boundingBox(),pinned=await context.boundingBox();assert.ok(field.y>=pinned.y+pinned.height-1);
   await capture('decide-context-long-question');await cancel();
  }
  await edit(retained);
  await page.locator('#context .control-primary').getByRole('button',{name:'Edit',exact:true}).click();await editor.waitFor();
  assert.equal(await editor.evaluate(n=>n.classList.contains('decision-editor')),false);
  assert.equal(await context.locator('.resolution-question').count(),0);assert.equal(await context.evaluate(n=>getComputedStyle(n).position),await page.evaluate(()=>innerWidth>600)?'sticky':'static');await cancel();
  fs.writeFileSync(`${out}/decide-context-${zoom?'zoom-200':'wide-mobile'}-observations.json`,JSON.stringify({observations,questionRestored:true},null,2));
 }catch(error){await capture(`decide-context-${zoom?'zoom-200':'wide-mobile'}-failure`);throw error;}
};
