"use strict";
const assert = require("node:assert/strict");
const {chromium} = require("playwright");

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("http://127.0.0.1:8765/");
    await page.locator('a[href="apprendimento.html"]').click();
    assert.equal(await page.locator("#learning-title").innerText(), "Linnerud di scikit-learn");
    assert.equal(await page.locator("#learning-group-assignment-body tr").count(), 6);
    await page.goto("http://127.0.0.1:8765/");
    await page.locator('a[href="papila.html"]').click();
    const lines = ["patient_id,Age_OD,Age_OS,Pneumatic_OD,Pneumatic_OS,Diagnosis_OD,Diagnosis_OS,image_OD,image_OS"];
    for (let i = 1; i <= 7; i++) lines.push(`RET${String(i).padStart(3,"0")},${30+i},${30+i},${10+i},${12+i},0,1,RET${String(i).padStart(3,"0")}OD.png,RET${String(i).padStart(3,"0")}OS.png`);
    await page.locator("#papila-csv").setInputFiles({name:"papila.csv",mimeType:"text/csv",buffer:Buffer.from(lines.join("\r\n"))});
    await page.locator("#papila-options").waitFor({state:"visible"});
    assert.equal(await page.locator("#papila-features label").count(),4);
    assert.equal(await page.locator("#papila-measures select").count(),2);
    const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/fZkAAAAASUVORK5CYII=","base64");
    await page.locator("#papila-images").setInputFiles([{name:"RET001OD.png",mimeType:"image/png",buffer:png},{name:"RET001OS.png",mimeType:"image/png",buffer:png}]);
    await page.locator("#papila-start").click();
    assert.equal(await page.locator(".candidate-card").count(),3);
    assert.equal(await page.locator(".candidate-card").first().innerText().then(t => /Diagnos/i.test(t)),false);
    for (let i=0;i<10;i++) {
      await page.locator(".candidate-card").nth(0).click();
      await page.locator(".candidate-card").nth(1).click();
      await page.locator("#papila-next").click();
    }
    assert.equal(await page.locator("#papila-completion").isVisible(),true);
    assert.equal(await page.locator("#papila-weights tr").count(),2);
    assert.equal(await page.locator("#papila-nearest li").count(),6);
    await page.locator("#papila-nearest li button").first().click();
    assert.equal(await page.locator("#papila-nearest-card .candidate-card").count(),1);
    assert.deepEqual(errors,[]);
    console.log("Linnerud conservato; percorso PAPILA verificato in Chromium.");
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
