// usage: node measure.js <name>::<route> ...   (site served at :8090). Prints words, visible controls and page height at 390 px and 1440 px as JSON.
const { chromium } = require('playwright');
(async () => {
  const [,, ...pairs] = process.argv;
  const b = await chromium.launch();
  const out = {};
  for (const [w, h, tag] of [[390, 844, 'm390'], [1440, 1000, 'd1440']]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    const p = await ctx.newPage();
    for (const pair of pairs) {
      const i = pair.indexOf('::'), name = pair.slice(0, i), route = pair.slice(i + 2);
      await p.goto('http://127.0.0.1:8090/index.html' + route, { waitUntil: 'networkidle' });
      await p.reload({ waitUntil: 'networkidle' });
      await p.waitForTimeout(300);
      const m = await p.evaluate(() => {
        const app = document.getElementById('app');
        const closed = (el) => { for (let e = el.parentElement; e && e !== app; e = e.parentElement) if (e.tagName === 'DETAILS' && !e.open && !(el.tagName === 'SUMMARY' && el.parentElement === e)) return true; return false; };
        const vis = (el) => !!(el.offsetWidth || el.offsetHeight);
        const text = app.innerText.split(/\s+/).filter(Boolean).length;
        const hidden = Array.from(app.querySelectorAll('details:not([open]) > *:not(summary)')).reduce((n, e) => n + e.textContent.split(/\s+/).filter(Boolean).length, 0);
        const controls = Array.from(app.querySelectorAll('button, select, input, summary')).filter((e) => vis(e) && !closed(e) && !e.closest('nav.mobile') && !e.closest('header.top')).length;
        return { words: text, hiddenWords: hidden, controls, height: document.documentElement.scrollHeight };
      });
      (out[name] = out[name] || {})[tag] = m;
    }
    await ctx.close();
  }
  console.log(JSON.stringify(out, null, 1));
  await b.close();
})();
