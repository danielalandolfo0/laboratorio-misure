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
    await page.locator("#papila-options").waitFor({state:"visible"});
    assert.match(await page.locator("#papila-count").innerText(),/244 pazienti/);
    assert.ok(await page.locator("#papila-features label").count()>=10);
    assert.ok(await page.locator("#papila-measures select").count()>=4);
    assert.equal(await page.locator("input[type=file]").count(),0);
    await page.locator("#papila-start").click();
    assert.equal(await page.locator(".candidate-card").count(),3);
    assert.equal(await page.locator(".candidate-card img").count(),6);
    await page.waitForFunction(() => [...document.querySelectorAll('.candidate-card img')].some(img => img.complete && img.naturalWidth > 0),null,{timeout:30000});
    assert.equal(await page.locator(".candidate-card").first().innerText().then(t => /Diagnos/i.test(t)),false);
    for (let i=0;i<10;i++) {
      await page.locator(".candidate-card").nth(0).click();
      await page.locator(".candidate-card").nth(1).click();
      await page.locator("#papila-next").click();
    }
    assert.equal(await page.locator("#papila-completion").isVisible(),true);
    assert.ok(await page.locator("#papila-weights tr").count()>=4);
    assert.equal(await page.locator("#papila-nearest li").count(),10);
    await page.locator("#papila-nearest li button").first().click();
    assert.equal(await page.locator("#papila-nearest-card .candidate-card").count(),1);
    assert.deepEqual(errors,[]);
    console.log("Linnerud conservato; percorso PAPILA verificato in Chromium.");
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
