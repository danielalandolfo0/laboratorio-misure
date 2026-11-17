"use strict";
// E2E Chromium + DOM + Pyodide reali. Serve un server HTTP su localhost:8765.
const assert=require("node:assert/strict");
const crypto=require("node:crypto");
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
  await page.locator("#csv-import-stage").waitFor({state:"visible"});
  assert.equal(await page.locator("#csv-output").isVisible(),false,
    "Il CSV non deve essere tipizzato prima della conferma.");
  await page.locator("#confirm-csv-import").click();
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
    await role(page,0,"categoria");await role(page,1,"categoria");await role(page,2,"identificativo");
    assert.equal(await page.locator("#phase-selection").isVisible(),false);
    assert.equal(await page.locator("#phase-measures").isVisible(),false);
    await page.locator("#confirm-semantic-types").click();
    assert.equal(await page.locator("#phase-preprocessing").isVisible(),true);
    await page.locator("#confirm-preprocessing-phase").click();
    await omit(page,2);
    await page.locator("#confirm-selection-phase").click();
    assert.equal(await page.locator("#phase-measures").isVisible(),true);
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
    await rows.nth(0).click();
    await page.locator("#nearest-ranking").waitFor({state:"visible"});
    const vicini=page.locator("#nearest-ranking-list li");
    assert.equal(await vicini.count(),3);
    assert.match(await page.locator("#nearest-ranking-title").innerText(),/A/);
    assert.match(await vicini.nth(0).innerText(),/B/);
    assert.match(await vicini.nth(2).innerText(),/C/);
    const pending=page.waitForEvent("download");
    await page.locator("#download-gower").click();
    const download=await pending;
    const csv=fs.readFileSync(await download.path(),"utf8");
    const m=csv.trim().split(/\r?\n/).map(l=>l.split(";"));
    assert.deepEqual(m[0],["Riga","A","B","C","D"]);
    assert.equal(m.length,5);assert.ok(m.every(row=>row.length===5));
    equal(number(m[1][2]),.5);equal(number(m[1][3]),1);
    fs.writeFileSync(path.join(OUT,"gower-export.csv"),csv);
    // Il bridge Pyodide conserva il rapporto delle coppie mancanti
    // senza sostituirle con zero e senza rendere disponibile una matrice.
    const erroreCoppie = await page.evaluate(async () => {
      const risposte = {
        riga: "oggetto", significatoMancanti: "sconosciuto",
        colonne: {
          flag1: {ruolo: "presenza", usa: true},
          flag2: {ruolo: "presenza", usa: true}
        },
        gruppi: [{id: "bin", nome: "Presenze", tipo: "vettore_binario"}],
        assegnazioni: {flag1: "bin", flag2: "bin"},
        "misuraBinaria-bin": "jaccard",
        "mancanti-gruppo-bin": "pairwise"
      };
      try {
        await window.Preprocessing.calcolaMatrice(
          "flag1,flag2\n1,NA\nNA,1\n1,1", [], risposte
        );
        return {errore: "Il calcolo non doveva avere esito positivo"};
      } catch (e) {
        return {messaggio: e.message, rapporto: e.rapportoProblemi};
      }
    });
    assert.match(erroreCoppie.messaggio,/non hanno alcun contributo valido/);
    assert.equal(erroreCoppie.rapporto.fase,"calcolo");
    assert.equal(erroreCoppie.rapporto.numeroCoppieNonConfrontabili,1);
    assert.deepEqual(erroreCoppie.rapporto.coppieNonConfrontabili,[[1,2]]);
    assert.equal(erroreCoppie.rapporto.analisiCopertura.numeroCoppie,1);
    assert.equal(erroreCoppie.rapporto.analisiCopertura.perBlocco.length,1);
    assert.equal(
      erroreCoppie.rapporto.analisiCopertura.perBlocco[0].coppieLocalmenteIndefinite,1
    );

    // Due percorsi con copertura insufficiente: il bridge distingue
    // dissimilarità locale indefinita da zero valido, senza fallback.
    const coperturaMista = await page.evaluate(async () => {
      const opzioni = {
        riga: "oggetto", significatoMancanti: "sconosciuto",
        colonne: {
          id: {ruolo:"identificativo",usa:false},
          flag1: {ruolo:"presenza",usa:true},
          flag2: {ruolo:"presenza",usa:true},
          categoria: {ruolo:"categoria",usa:true}
        },
        gruppi: [{id:"bin",nome:"Presenze",tipo:"vettore_binario"}],
        assegnazioni: {flag1:"bin",flag2:"bin"},
        "misuraBinaria-bin":"jaccard",
        "mancanti-gruppo-bin":"pairwise"
      };
      const csvScoperto = "id,flag1,flag2,categoria\nA,1,NA,NA\nB,NA,1,NA\nC,1,1,x\nD,0,0,y";
      const csvRecuperato = "id,flag1,flag2,categoria\nA,1,NA,x\nB,NA,1,x\nC,1,1,x\nD,0,0,y";
      let errore;
      try {
        await window.Preprocessing.calcolaMatrice(csvScoperto, [], opzioni);
      } catch (e) {
        errore = e.rapportoProblemi;
      }
      const matrice = await window.Preprocessing.calcolaMatrice(
        csvRecuperato, [], opzioni
      );
      return {
        errore,
        recuperata: matrice.matrice,
        parziali: matrice.diagnosticaFinale.coppieCoperturaParziale
      };
    });
    assert.deepEqual(coperturaMista.errore.coppieNonConfrontabili, [[1,2]]);
    assert.equal(coperturaMista.errore.analisiCopertura.perBlocco.length, 2);
    assert.equal(coperturaMista.errore.analisiCopertura.numeroCoppie, 1);
    assert.equal(coperturaMista.recuperata[0][1], 0);
    assert.ok(coperturaMista.parziali > 0);

    // Stress numerico end-to-end: due pesi globali 1e308 producono
    // la STESSA media di due pesi unitari; l'API non restituisce NaN.
    const pesiEstremiBrowser = await page.evaluate(async () => {
      const csv = "x,y,categoria\n0,0,a\n3,0,b\n0,4,a";
      const scelte = [
        {tipo:"auto",metodo:"nessuno"},
        {tipo:"auto",metodo:"nessuno"},
        {tipo:"auto",metodo:"auto"}
      ];
      const base = {
        riga:"oggetto",
        comparabilitaScale:"comparabili",
        confrontoQuantitativo:"assoluto",
        aggregazioneScarti:"quadratica",
        importanzaCoordinate:"uguale",
        dipendenzaCoordinate:"no",
        gestioneDipendenzaLineare:"mantieni",
        riscalamentoConfermato:true,
        gestioneQuantitativeMiste:"separato",
        colonne:{
          x:{ruolo:"quantita",usa:true},
          y:{ruolo:"quantita",usa:true},
          categoria:{ruolo:"categoria",usa:true}
        }
      };
      const standard = await window.Preprocessing.calcolaMatrice(
        csv,scelte,base
      );
      const pesato = await window.Preprocessing.calcolaMatrice(
        csv,scelte,{
          ...base,modalitaPesiPercorsi:"personalizzati",
          pesiPercorsi:{"percorso-1":"1e308","percorso-2":"1e308"}
        }
      );
      return {
        standard:standard.matrice,
        pesato:pesato.matrice,
        pesi:pesato.contributi.map(c=>c.peso),
        sensibilita:pesato.diagnosticaFinale.sensibilitaPesi
      };
    });
    assert.deepEqual(pesiEstremiBrowser.pesi,[1e308,1e308]);
    for(let i=0;i<3;i++)for(let j=0;j<3;j++){
      assert.ok(Number.isFinite(pesiEstremiBrowser.pesato[i][j]));
      assert.ok(Math.abs(
        pesiEstremiBrowser.pesato[i][j]-pesiEstremiBrowser.standard[i][j]
      )<1e-10);
    }
    assert.equal(pesiEstremiBrowser.sensibilita.numeroBlocchi,2);
    assert.ok(
      pesiEstremiBrowser.sensibilita.perBlocco.every(
        c=>Number.isFinite(c.fattoreDoppio.variazioneMassimaAssoluta)
      )
    );

    // Collaudo del contratto Bray–Curtis 0/0 con il VERO motore Pyodide.
    // Il piano deve chiedere la decisione; la scelta "indefinita"
    // deve mantenere la coppia priva di contributo e bloccare la matrice.
    const brayZeroNelBrowser = await page.evaluate(async () => {
      const csv = "x,y\n0,0\n0,0\n3,2";
      const opzioni = {
        riga: "oggetto", confrontoQuantitativo: "abbondanza",
        gestioneDipendenzaLineare: "mantieni",
        colonne: {
          x: {ruolo: "quantita", usa: true},
          y: {ruolo: "quantita", usa: true}
        }
      };
      const nonConfermato = await window.Preprocessing.creaPiano(csv, [], opzioni);
      const confermato = await window.Preprocessing.creaPiano(csv, [], {
        ...opzioni, convenzioneBrayCurtisZero: "zero"
      });
      const matrice = await window.Preprocessing.calcolaMatrice(csv, [], {
        ...opzioni, convenzioneBrayCurtisZero: "zero"
      });
      let nonDefinito;
      try {
        await window.Preprocessing.calcolaMatrice(csv, [], {
          ...opzioni, convenzioneBrayCurtisZero: "indefinita"
        });
        nonDefinito = {errore: false};
      } catch (errore) {
        nonDefinito = {errore: true, rapporto: errore.rapportoProblemi};
      }
      return {
        attende: !nonConfermato.completo,
        misura: nonConfermato.percorsi[0].idMisura,
        coppie: nonConfermato.percorsi[0].coppieBrayDoppioZero,
        confermato: confermato.completo,
        matrice: matrice.matrice,
        nonDefinito
      };
    });
    assert.equal(brayZeroNelBrowser.attende, true);
    assert.equal(brayZeroNelBrowser.misura, "bray_curtis");
    assert.equal(brayZeroNelBrowser.coppie, 1);
    assert.equal(brayZeroNelBrowser.confermato, true);
    equal(brayZeroNelBrowser.matrice[0][1], 0);
    equal(brayZeroNelBrowser.matrice[0][2], 1);
    assert.equal(brayZeroNelBrowser.nonDefinito.errore, true);
    assert.deepEqual(
      brayZeroNelBrowser.nonDefinito.rapporto.coppieNonConfrontabili, [[1,2]]
    );


    // Cambiando il significato di una coppia categoriale, la misura
    // locale deve cambiare davvero: blu/rosso passa da 1 a 0.2.
    await page.locator(
      '#adaptive-questions select.gower-setting[data-gower-key="modalitaCategorieGower"][data-gower-column="colore"]'
    ).selectOption("personalizzata");
    await page.locator(
      '#adaptive-questions input.gower-nominal-pair[data-gower-nominal-column="colore"]'
    ).fill("0,2");
    await page.locator("#prepare-comparison-plan").click();
    await page.locator("#comparison-plan").waitFor({state:"visible"});
    assert.equal(await page.locator("#gower-actions").isVisible(),true,
      "Gower personalizzata non pronta: " +
      await page.locator("#comparison-plan-warnings").innerText());
    await page.locator("#calculate-gower").click();
    await page.locator("#gower-result").waitFor({state:"visible"});
    const customized=page.locator("#gower-matrix-body tr");
    equal(number(await customized.nth(0).locator("td").nth(1).innerText()),.1);
    await capture("success");
  }catch(e){await capture("failure");e.message+="\n"+JSON.stringify(errors);throw e}
  finally{await ctx.close()}
}
async function importaCsv(browser){
  const {ctx,page,capture,errors}=await newPage(browser,"importazione-csv",1000);
  try{
    await init(page);
    const csv="id;quantita;categoria\nA;1;NA\nB;2;rosso\nC;3;NA";
    await page.locator("#csv-file").setInputFiles({
      name:"separatore-punto-virgola.csv", mimeType:"text/csv",
      buffer:Buffer.from(csv)
    });
    await page.locator("#csv-import-stage").waitFor({state:"visible"});
    assert.equal(await page.locator("#csv-output").isVisible(),false);
    assert.equal(await page.locator("#import-separator").inputValue(),";");
    assert.match(await page.locator("#import-preview-caption").innerText(),/3 righe/);
    const checkbox=page.locator('.import-marker-choice[value="na"]');
    assert.equal(await checkbox.isChecked(),true);
    await checkbox.uncheck();
    await page.locator("#confirm-csv-import").click();
    await page.locator("#csv-output").waitFor({state:"visible"});
    assert.equal(await page.locator("#csv-import-stage").isVisible(),false);
    await page.locator("#row-meaning").selectOption("oggetto");
    await role(page,0,"identificativo");
    await role(page,1,"quantita");
    await role(page,2,"categoria");
    await page.locator("#confirm-semantic-types").click();
    assert.equal(await page.locator("#phase-preprocessing").isVisible(),true);
    assert.equal(await page.locator("#confirm-preprocessing-phase").isDisabled(),true);
    // Una sola colonna quantitativa richiede comunque la conferma
    // della trasformazione prima di selezionare le colonne.
    assert.equal(await page.locator("#scaling-wrap").isVisible(),true);
    await page.locator("#confirm-numeric-scaling").click();
    await page.locator("#confirm-preprocessing-phase").click();
    assert.equal(await page.locator("#phase-selection").isVisible(),true);
    await page.locator("#confirm-selection-phase").click();
    assert.equal(await page.locator("#phase-measures").isVisible(),true);
    assert.equal(await page.locator("#prepare-comparison-plan").isVisible(),true);
    const risultati=await page.evaluate(async csv=>{
      const interpretazione={
        riga:"oggetto", significatoMancanti:"sconosciuto",
        colonne:{
          id:{ruolo:"identificativo",usa:false},
          quantita:{ruolo:"quantita",usa:true},
          categoria:{ruolo:"categoria",usa:true}
        }
      };
      const literal={separatore:";",marcatoriMancanti:["","?","null","n/a"]};
      const absent={separatore:";",marcatoriMancanti:["","?","null","n/a","na"]};
      const a=await window.Preprocessing.preparaTabella(csv,[],literal);
      const b=await window.Preprocessing.preparaTabella(csv,[],absent);
      const d1=await window.Preprocessing.calcolaMatrice(csv,[],interpretazione,literal);
      const d2=await window.Preprocessing.calcolaMatrice(csv,[],interpretazione,absent);
      const report=await window.Preprocessing.creaRapporto(
        csv,[],interpretazione,"mio.csv",literal
      );
      return {
        missingLiteral:a.colonne[2].mancanti,
        missingAbsent:b.colonne[2].mancanti,
        distanceLiteral:d1.matrice[0][2],
        distanceAbsent:d2.matrice[0][2],
        orig:report.sorgente.csvOriginale,
        reportConfig:report.configurazione.importazioneCSV
      };
    },csv);
    assert.equal(risultati.missingLiteral,0);
    assert.equal(risultati.missingAbsent,2);
    equal(risultati.distanceLiteral,0.5);
    equal(risultati.distanceAbsent,1);
    assert.equal(risultati.orig,csv);
    assert.equal(risultati.reportConfig.separatore,";");
    assert.equal(risultati.reportConfig.marcatoriMancanti.includes("na"),false);
    await page.locator("#edit-csv-import").click();
    await page.locator("#csv-import-stage").waitFor({state:"visible"});
    assert.equal(await page.locator("#csv-output").isVisible(),false);
    assert.equal(await checkbox.isChecked(),false);
    await checkbox.check();
    await page.locator("#confirm-csv-import").click();
    await page.locator("#csv-output").waitFor({state:"visible"});
    await capture("success");
  }catch(e){await capture("failure");e.message+="\n"+JSON.stringify(errors);throw e}
  finally{await ctx.close()}
}

async function mobile(browser){
  const {ctx,page,capture,errors}=await newPage(browser,"numerico-mobile",390);
  try{
    await init(page);
    await upload(page,"x,y,id\n0,1,A\n1,4,B\n2,2,C\n3,3,D","numerico.csv");
    await page.locator("#row-meaning").selectOption("oggetto");
    await role(page,0,"quantita");await role(page,1,"quantita");await role(page,2,"identificativo");
    await page.locator("#confirm-semantic-types").click();
    assert.equal(await page.locator("#scaling-wrap").isVisible(),true);
    assert.equal(await page.locator("#prepare-comparison-plan").isVisible(),false);
    await page.locator('#scaling-body select[data-column="0"][data-choice="metodo"]').selectOption("nessuno");
    await page.locator('#scaling-body select[data-column="1"][data-choice="metodo"]').selectOption("log1p");
    await page.locator("#confirm-numeric-scaling").click();
    assert.equal(await page.locator("#prepare-comparison-plan").isVisible(),false);
    await page.locator("#confirm-preprocessing-phase").click();
    await omit(page,2);
    await page.locator("#confirm-selection-phase").click();
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
    // Qui la scelta della misura deve appartenere all'utente.
    await page.locator("#numeric-measure-choice").selectOption("euclidean");
    await page.locator("#apply-numeric-measure").click();
    await page.locator("#gower-actions").waitFor({state:"visible"});
    await page.locator("#calculate-gower").click();
    await page.locator("#gower-result").waitFor({state:"visible"});
    assert.equal(await page.locator("#gower-matrix-body tr").count(),4);
    const mobileExport=page.waitForEvent("download");
    await page.locator("#download-gower").click();
    const downloaded=await mobileExport;
    const matrix=fs.readFileSync(await downloaded.path(),"utf8").trim().split(/\r?\n/);
    assert.equal(matrix.length,5);
    fs.writeFileSync(path.join(OUT,"numerico-mobile-export.csv"),matrix.join("\n"));
    const layout = await page.evaluate(() => {
      const root = document.documentElement;
      const visible = [...document.querySelectorAll(
        ".data-prep input, .data-prep select, .data-prep textarea"
      )].filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== "hidden");
      const withoutLabel = visible.filter(el =>
        !(el.labels?.length || el.closest("label") ||
          el.getAttribute("aria-label") || el.getAttribute("aria-labelledby"))
      ).map(el => el.id || el.className);
      return {
        innerWidth: window.innerWidth,
        pageWidth: root.scrollWidth,
        visibleControls: visible.length,
        withoutLabel
      };
    });
    fs.writeFileSync(path.join(OUT,"mobile-layout.json"), JSON.stringify(layout,null,2));
    assert.ok(layout.pageWidth <= layout.innerWidth + 2,
      "La pagina non deve avere uno scorrimento orizzontale globale: " +
      JSON.stringify(layout));
    assert.deepEqual(layout.withoutLabel, [],
      "Controlli visibili senza nome accessibile: " + JSON.stringify(layout));
    await capture("success");
  }catch(e){await capture("failure");e.message+="\n"+JSON.stringify(errors);throw e}
  finally{await ctx.close()}
}
(async()=>{
  const b=await chromium.launch({headless:true,args:["--no-sandbox"]});
  try{await importaCsv(b);await gower(b);await mobile(b);console.log("E2E Chromium e Pyodide superato")}
  finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
