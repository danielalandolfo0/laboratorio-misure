"use strict";

/*
 * Test vero in Chromium + Pyodide con QUATTRO percorsi nello stesso CSV.
 * Nessuna impostazione interna del sito viene iniettata: ogni valore
 * passa dai controlli HTML visibili, come farebbe una persona.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {chromium} = require("playwright");

const OUT = path.resolve("test-results/browser");
fs.mkdirSync(OUT, {recursive: true});
const INPUT = fs.readFileSync(
  path.resolve("examples/collaudo/test_integrato_gower_gruppi_mancanti.csv"),
  "utf8"
);
const approx = (actual, wanted, eps=1e-5) => {
  assert.ok(Number.isFinite(actual) && Math.abs(actual - wanted) <= eps,
    "Distanza attesa " + wanted + ", ottenuta " + actual);
};
const parseValue = value => Number(String(value).trim().replace(",", "."));

async function main() {
  const browser = await chromium.launch({headless:true, args:["--no-sandbox"]});
  const context = await browser.newContext({
    viewport: {width:1366, height:900},
    locale:"it-IT", acceptDownloads:true
  });
  const page = await context.newPage();
  page.setDefaultTimeout(16000);
  const errors = [];
  const phases = [];
  page.on("pageerror", err => errors.push("JS: " + err.message));
  page.on("requestfailed", req =>
    errors.push("Request: " + req.url() + " - " + req.failure()?.errorText));
  page.on("console", msg => {
    if (msg.type() === "error") errors.push("Console: " + msg.text());
  });

  async function snapshot(name) {
    const info = {
      phase:name, phases, errors,
      alert:await page.locator("#csv-error").innerText().catch(()=>""),
      planText:await page.locator("#comparison-plan-intro").innerText().catch(()=>""),
      warnings:await page.locator("#comparison-plan-warnings").innerText().catch(()=>""),
      planVisible:await page.locator("#comparison-plan").isVisible().catch(()=>false),
      calculateVisible:await page.locator("#gower-actions").isVisible().catch(()=>false),
      adaptiveSelections:await page.locator("#adaptive-questions select").evaluateAll(
        nodes=>nodes.map(n=>({label:n.labels?.[0]?.textContent?.slice(0,100),
          className:n.className,value:n.value,
          answer:n.dataset.answer,groupId:n.dataset.groupId}))
      ).catch(()=>[]),
      gowerInputs:await page.locator("#adaptive-questions .gower-setting").evaluateAll(
        nodes=>nodes.map(n=>({key:n.dataset.gowerKey,col:n.dataset.gowerColumn,value:n.value}))
      ).catch(()=>[])
    };
    fs.writeFileSync(path.join(OUT,"four-block-"+name+".json"),JSON.stringify(info,null,2));
    await page.screenshot({
      path:path.join(OUT,"four-block-"+name+".png"),fullPage:true
    }).catch(()=>{});
  }
  const checkpoint = name => {phases.push(name); console.log("[Quattro percorsi] "+name);};
  async function choose(css, value) {
    const node=page.locator(css);
    await node.selectOption(value);
    assert.equal(await page.locator(css).inputValue(),value,
      "Selezione persa: "+css);
  }
  async function enter(css,value,triggerChange=false) {
    const node=page.locator(css);
    await node.fill(value);
    if(triggerChange) await node.dispatchEvent("change");
  }
  async function answer(key,value) {
    await choose('#adaptive-questions [data-answer="'+key+'"]',value);
  }
  async function assign(name,groupId) {
    await choose('.group-assignment[data-group-column="'+name+'"]',groupId);
  }
  async function gowerField(key,col,value) {
    const css='.gower-setting[data-gower-key="'+key+'"][data-gower-column="'+col+'"]';
    const node=page.locator(css);
    const tag=await node.evaluate(el=>el.tagName.toLowerCase());
    if(tag==="select") await choose(css,value);
    else await enter(css,value,true);
  }
  async function setPlanInput(css,value) {
    const node=page.locator(css);
    await node.fill(value);
    await node.dispatchEvent("change");
    // La risposta causa un nuovo piano; deve tornare visibile e
    // contenere l'input aggiornato prima di passare al controllo seguente.
    await page.locator("#comparison-plan").waitFor({state:"visible"});
    await page.waitForFunction(([selector,wanted]) => {
      const x=document.querySelector(selector);
      return x && x.value===wanted;
    },[css,value]);
  }

  try {
    await page.goto("http://127.0.0.1:8765/",{waitUntil:"domcontentloaded"});
    await page.waitForFunction(()=>!!window.Preprocessing?.ready);
    await page.evaluate(async()=>await window.Preprocessing.ready);
    await page.locator("#csv-file").setInputFiles({
      name:"test_integrato_gower_gruppi_mancanti.csv",
      mimeType:"text/csv", buffer:Buffer.from(INPUT)
    });
    await page.locator("#csv-output").waitFor({state:"visible"});
    assert.match(await page.locator("#comparison-guide-phase").innerText(),/Indica che cosa rappresenta una riga/);
    await page.locator("#comparison-guide-next").click();
    assert.equal(await page.locator("#row-meaning").evaluate(e=>e===document.activeElement),true);
    await choose("#row-meaning","oggetto");
    checkpoint("CSV caricato con Pyodide: 6 righe, 9 colonne");

    const names=["livello","categoria","c1","c2","p1","p2","p3","codice","id"];
    const roles=["livello","categoria","quantita","quantita","quantita","quantita",
      "quantita","testo","identificativo"];
    for(let i=0;i<names.length;i++){
      await choose('.semantic-role[data-semantic-column="'+i+'"]',roles[i]);
    }
    // Il ruolo "testo" e' inizialmente escluso per prudenza:
    // l'utente deve riabilitare esplicitamente il suo confronto.
    const textUsed=page.locator('.semantic-use[data-semantic-column="7"]');
    assert.equal(await textUsed.isChecked(),false,
      "Una colonna appena dichiarata testo deve richiedere inclusione esplicita");
    await textUsed.check();
    const idUsed=page.locator('.semantic-use[data-semantic-column="8"]');
    if(await idUsed.isChecked())await idUsed.uncheck();

    // Prima si conferma quali colonne formano blocchi.
    await page.locator("#add-column-group").click();
    await page.locator("#add-column-group").click();
    for(const col of ["c1","c2"])await assign(col,"gruppo-1");
    for(const col of ["p1","p2","p3"])await assign(col,"gruppo-2");
    await choose('.group-config[data-group-id="gruppo-1"] .group-type',"coordinate");
    await choose('.group-config[data-group-id="gruppo-2"] .group-type',"distribuzione");
    checkpoint("Riconosciuti due gruppi e tre colonne standard indipendenti");

    // Interpretazione di Gower e della distribuzione: decisioni esplicite.
    await answer("significatoMancanti","sconosciuto");
    const outlier=page.locator('[data-answer="significatoEstremi"]');
    if(await outlier.count())await answer("significatoEstremi","reali");
    await answer("ordineLivelli","si");
    await gowerField("ordiniLivelliGower","livello","basso; medio; alto");
    await gowerField("modalitaIntervalliGower","livello","personalizzati");
    await gowerField("passiOrdinaliGower","livello","1; 3");
    await gowerField("pesiGower","livello","2");
    await gowerField("modalitaCategorieGower","categoria","personalizzata");

    const nominal={
      "0:1":"0,4", "0:2":"0,8", "1:2":"0,6"
    };
    for(const [pair,value] of Object.entries(nominal)){
      await enter('.gower-nominal-pair[data-gower-nominal-column="categoria"][data-gower-pair="'+pair+'"]',value);
    }
    await choose('.text-measure-setting[data-text-measure-column="codice"]',"hamming");
    await answer("naturaDistribuzione-gruppo-2","probabilita");
    await answer("misuraDistribuzione-gruppo-2","hellinger");
    checkpoint("Gower personalizzata, Hamming e Hellinger confermate");

    // Coordinate: non si usa un'euclidea arbitraria.
    await choose('.group-measure-setting[data-group-id="gruppo-1"]',"weighted_minkowski");
    await enter('.group-measure-parameter[data-group-id="gruppo-1"][data-parameter="q"]',"2",true);
    await enter('.group-measure-parameter[data-group-id="gruppo-1"][data-parameter="pesi"]',"1; 4",true);
    await answer("mancanti-gruppo-gruppo-1","pairwise");
    checkpoint("Minkowski pesata pairwise, q=2, pesi 1;4");

    // Trasformazioni esplicite, non applicate alle distribuzioni.
    await page.locator("#scaling-wrap").waitFor({state:"visible"});
    await choose('#scaling-body .column-choice[data-column="2"][data-choice="metodo"]',"nessuno");
    await choose('#scaling-body .column-choice[data-column="3"][data-choice="metodo"]',"log1p");
    await page.locator("#confirm-numeric-scaling").click();
    checkpoint("Conferma riscalamento c1 originale, c2 log(1+x)");

    // Le due conferme di compatibilità non sono scelte dal sito.
    const confirmMixed='.group-preprocessing-confirmation[data-group-id="gruppo-1"][data-kind="misti"]';
    const confirmOriginal='.group-preprocessing-confirmation[data-group-id="gruppo-2"][data-kind="originali"]';
    assert.equal(await page.locator(confirmMixed).count(),1,
      "Manca la domanda sulle trasformazioni differenti");
    assert.equal(await page.locator(confirmOriginal).count(),1,
      "Manca la domanda sull'uso dei valori originali");
    await page.locator("#prepare-comparison-plan").click();
    await page.locator("#comparison-plan").waitFor({state:"visible"});
    assert.equal(await page.locator("#gower-actions").isVisible(),false,
      "Senza le conferme il calcolo deve essere bloccato");
    assert.match(await page.locator("#comparison-guide-phase").innerText(),/Completa una domanda/);
    await page.locator("#comparison-guide-next").click();
    assert.equal(await page.locator(confirmMixed).evaluate(
      el => el === document.activeElement), true,
      "La guida deve raggiungere la conferma ancora mancante");
    checkpoint("Piano incompleto blocca correttamente il calcolo");
    await choose(confirmMixed,"si");
    await choose(confirmOriginal,"si");

    await page.locator("#prepare-comparison-plan").click();
    await page.locator("#comparison-plan").waitFor({state:"visible"});
    const cards=page.locator("#comparison-plan-paths .plan-path");
    assert.equal(await cards.count(),4,
      "Servono quattro percorsi, nessun blocco deve scomparire");
    const pathText=await cards.allTextContents();
    for(const expected of ["Gower","Hamming","Minkowski","Hellinger"]){
      assert.ok(pathText.some(text=>text.includes(expected)),
        "Percorso non configurato: "+expected);
    }
    checkpoint("Piano con quattro percorsi");

    // Pesi locali indipendenti, default non equivalente ai pesi richiesti.
    for(const [id,value] of [
      ["percorso-1","2"],["percorso-2","1"],
      ["percorso-3","3"],["percorso-4","4"]
    ]) await setPlanInput('.path-weight[data-path-id="'+id+'"]',value);

    await choose('.path-normalization-method[data-path-id="percorso-3"]',"robusta");
    await page.locator("#comparison-plan").waitFor({state:"visible"});
    assert.equal(await page.locator("#gower-actions").isVisible(),false,
      "Le righe anomale vanno confermate prima di procedere");
    await setPlanInput('.path-robust-rows[data-path-id="percorso-3"]',"4; 5");
    assert.equal(await page.locator("#gower-actions").isVisible(),true,
      "Il piano deve diventare calcolabile dopo tutte le conferme. "+
      await page.locator("#comparison-plan-warnings").innerText());
    checkpoint("Pesi 2,1,3,4 e scala robusta sulle righe 4;5");

    await page.locator("#calculate-gower").click();
    await page.locator("#gower-result").waitFor({state:"visible"});
    assert.match(await page.locator("#gower-result-caption").innerText(),/6 × 6/);
    assert.equal(await page.locator("#gower-matrix-body tr").count(),6);
    const tableRows=page.locator("#gower-matrix-body tr");
    const ab=parseValue(await tableRows.nth(0).locator("td").nth(1).innerText());
    const ae=parseValue(await tableRows.nth(0).locator("td").nth(4).innerText());
    const scale=Math.sqrt((4+4*Math.log(18/11)**2)/5);
    const coordinateAB=Math.sqrt((1+4*Math.log(13/11)**2)/5)/scale;
    const expectedAB=(2*.3+1/3+3*coordinateAB+4*1)/10;
    approx(ab,expectedAB);
    approx(ae,19/21);
    checkpoint("Matrice 6×6: A/B e A/E coincidono con le formule");

    const pending=page.waitForEvent("download");
    await page.locator("#download-gower").click();
    const download=await pending;
    const csv=fs.readFileSync(await download.path(),"utf8");
    const clean=csv.replace(/^\uFEFF/,"").trim().split(/\r?\n/).map(r=>r.split(";"));
    assert.equal(clean.length,7);
    assert.deepEqual(clean[0],["Riga","A","B","C","D","E","F"]);
    assert.deepEqual(clean.slice(1).map(r=>r[0]),["A","B","C","D","E","F"]);
    for(let i=1;i<=6;i++){
      assert.equal(clean[i].length,7);
      approx(parseValue(clean[i][i]),0);
      for(let j=1;j<=6;j++){
        const x=parseValue(clean[i][j]);
        assert.ok(Number.isFinite(x) && x>=0 && x<=1);
        approx(x,parseValue(clean[j][i]));
      }
    }
    approx(parseValue(clean[1][2]),expectedAB,1e-9);
    approx(parseValue(clean[1][5]),19/21,1e-9);
    fs.writeFileSync(path.join(OUT,"four-block-export.csv"),csv);
    assert.match(await page.locator("#comparison-guide-phase").innerText(),/La matrice è pronta/);
    await snapshot("success");
    checkpoint("Esportazione CSV: matrice completa, simmetrica e valida");
  }catch(error){
    await snapshot("failure");
    error.message+="\nFase: "+phases.at(-1)+
      "\nEventi browser: "+JSON.stringify(errors);
    throw error;
  }finally{
    await context.close();
    await browser.close();
  }
}

main().catch(error=>{
  console.error(error);
  process.exitCode=1;
});
