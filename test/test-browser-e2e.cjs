"use strict";
// E2E Chromium + DOM + Pyodide reali. Serve un server HTTP su localhost:8765.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {chromium}=require("playwright");
const OUT="test-results/browser";
fs.mkdirSync(OUT,{recursive:true});
const equal=(a,b)=>assert.ok(Math.abs(a-b)<1e-5,"Atteso "+b+", trovato "+a);
const number=t=>Number(t.trim().replace(",","."));
async function newPage(browser,name,width){
  const ctx=await browser.newContext({viewport:{width,height:900},acceptDownloads:true,locale:"it-IT"});
  const page=await ctx.newPage();page.setDefaultTimeout(120000);
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  page.on("requestfailed",r=>errors.push(r.url()+": "+r.failure()?.errorText));
  async function capture(suffix){
    await page.screenshot({path:path.join(OUT,name+"-"+suffix+".png"),fullPage:true}).catch(()=>{});
    fs.writeFileSync(path.join(OUT,name+"-"+suffix+".json"),JSON.stringify({errors,url:page.url()},null,2));
  }
  return {ctx,page,capture,errors};
}
async function init(page){
  await page.goto("http://127.0.0.1:8765/",{waitUntil:"domcontentloaded"});
  await page.waitForFunction(()=>!!window.Preprocessing?.ready,null,{timeout:120000});
  await page.evaluate(async()=>await window.Preprocessing.ready);
}
async function upload(page,csv,name){
  await page.locator("#csv-file").setInputFiles({name,mimeType:"text/csv",buffer:Buffer.from(csv)});
  await page.locator("#csv-output").waitFor({state:"visible"});
  assert.equal((await page.locator("#csv-file-name").innerText()).trim(),name);
}
async function role(page,index,value){
  await page.locator('.semantic-role[data-semantic-column="'+index+'"]').selectOption(value);
}
async function omit(page,index){
  const input=page.locator('.semantic-use[data-semantic-column="'+index+'"]');
  if(await input.isChecked())await input.uncheck();
}
async function gower(browser){
  const {ctx,page,capture,errors}=await newPage(browser,"gower",1280);
  try{
    await init(page);
    await upload(page,"colore,forma,id\nrosso,tondo,A\nblu,tondo,B\nblu,quadro,C\nrosso,quadro,D","categorie.csv");
    await page.locator("#row-meaning").selectOption("oggetto");
    await role(page,0,"categoria");await role(page,1,"categoria");await role(page,2,"identificativo");await omit(page,2);
    await page.locator("#prepare-comparison-plan").click();
    await page.locator("#comparison-plan").waitFor({state:"visible"});
    assert.equal(await page.locator("#gower-actions").isVisible(),true,
      await page.locator("#comparison-plan-warnings").innerText());
    await page.locator("#calculate-gower").click();
    await page.locator("#gower-result").waitFor({state:"visible"});
    const rows=page.locator("#gower-matrix-body tr");
    assert.equal(await rows.count(),4);
    equal(number(await rows.nth(0).locator("td").nth(1).innerText()),.5);
    equal(number(await rows.nth(0).locator("td").nth(2).innerText()),1);
    const pending=page.waitForEvent("download");
    await page.locator("#download-gower").click();
    const download=await pending;
    const csv=fs.readFileSync(await download.path(),"utf8");
    const m=csv.trim().split(/\r?\n/).map(l=>l.split(";"));
    assert.deepEqual(m[0],["Riga","A","B","C","D"]);
    assert.equal(m.length,5);assert.ok(m.every(row=>row.length===5));
    equal(number(m[1][2]),.5);equal(number(m[1][3]),1);
    fs.writeFileSync(path.join(OUT,"gower-export.csv"),csv);
    await capture("success");
  }catch(e){await capture("failure");e.message+="\n"+JSON.stringify(errors);throw e}
  finally{await ctx.close()}
}
async function mobile(browser){
  const {ctx,page,capture,errors}=await newPage(browser,"numerico-mobile",390);
  try{
    await init(page);
    await upload(page,"x,y,id\n0,1,A\n1,2,B\n2,3,C\n3,4,D","numerico.csv");
    await page.locator("#row-meaning").selectOption("oggetto");
    await role(page,0,"quantita");await role(page,1,"quantita");await role(page,2,"identificativo");await omit(page,2);
    assert.equal(await page.locator("#scaling-wrap").isVisible(),true);
    assert.equal(await page.locator("#prepare-comparison-plan").isVisible(),false);
    await page.locator('#scaling-body select[data-column="0"][data-choice="metodo"]').selectOption("nessuno");
    await page.locator('#scaling-body select[data-column="1"][data-choice="metodo"]').selectOption("log1p");
    await page.locator("#confirm-numeric-scaling").click();
    assert.equal(await page.locator("#prepare-comparison-plan").isVisible(),true);
    const answer=async(id,value)=>{
      const input=page.locator('[data-answer="'+id+'"]');
      if(await input.count())await input.selectOption(value);
    };
    await answer("confrontoQuantitativo","assoluto");
    await answer("dipendenzaCoordinate","no");
    await answer("aggregazioneScarti","quadratica");
    await answer("importanzaCoordinate","uguale");
    await page.locator("#prepare-comparison-plan").click();
    await page.locator("#comparison-plan").waitFor({state:"visible"});
    assert.match(await page.locator("#comparison-plan-paths").innerText(),/numeriche|euclidea|Minkowski/i);
    assert.equal(await page.locator("#download-work").isEnabled(),true);
    await capture("success");
  }catch(e){await capture("failure");e.message+="\n"+JSON.stringify(errors);throw e}
  finally{await ctx.close()}
}
(async()=>{
  const b=await chromium.launch({headless:true,args:["--no-sandbox"]});
  try{await gower(b);await mobile(b);console.log("E2E Chromium e Pyodide superato")}
  finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
