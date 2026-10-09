const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PROOF_BROWSER_EXECUTABLE});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],checks=[];
 const [url,out]=process.argv.slice(2);page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(url+'/#project=legacy-test&decision=D000001');await page.locator('#token').fill('Synthetic action form test password');await page.locator('#login-submit').click();await page.locator('#detail[data-loaded=true]').waitFor();
  assert.ok((await page.locator('#detail').innerText()).includes('Unknown in source.'));
  const source=page.locator('.legacy-history');assert.ok((await source.innerText()).includes('legacy-test · SOURCE-1'));
  await source.getByRole('button',{name:'Source references',exact:true}).click();await source.getByText('planning/source.json',{exact:false}).waitFor();
  await source.getByRole('button',{name:'Source history',exact:true}).click();await source.getByRole('button',{name:'View source',exact:true}).first().click();
  await page.waitForFunction(()=>document.querySelector('.legacy-history pre')?.textContent.includes('1.2300'));
  const raw=await source.locator('pre').first().textContent();assert.ok(raw.includes('1E+02')&&raw.includes('-0')&&raw.includes('🧭'));checks.push('Original numeric tokens, ordered events and source references remain readable without fabricated approval');
  await page.locator('#detail').getByRole('button',{name:'History',exact:true}).click();assert.equal(await page.locator('#detail').getByRole('button',{name:'View snapshot',exact:true}).count(),0);checks.push('Initial source history is distinct from native transactions');
  await page.screenshot({path:out+'/source-wide.png'});await page.setViewportSize({width:320,height:780});await page.screenshot({path:out+'/source-mobile.png'});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  fs.writeFileSync(out+'/observations.json',JSON.stringify({checks,pageerrors:errors},null,2));
 }catch(e){await page.screenshot({path:out+'/failure.png'});fs.writeFileSync(out+'/failure.json',JSON.stringify({error:e.stack,checks,pageerrors:errors},null,2));throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
