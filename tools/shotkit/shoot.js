// usage: node shoot.js <out dir> name::route ...   (site served at :8090). Writes <name>-<desktop|mobile>-<light|dark>.png and overflow.json
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [,, out, ...pairs] = process.argv;
  const b = await chromium.launch();
  const report = [];
  for (const scheme of ['light', 'dark']) for (const [w, h, tag] of [[1440, 1000, 'desktop'], [390, 844, 'mobile']]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, deviceScaleFactor: tag === 'mobile' ? 2 : 1.25 });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => console.log('PAGEERROR', e.message));
    p.on('console', (m) => { if (m.type() === 'error') console.log('CONSOLE', m.text(), m.location().url); });
    for (const pair of pairs) {
      const i = pair.indexOf('::'), name = pair.slice(0, i), route = pair.slice(i + 2);
      await p.goto('http://127.0.0.1:8090/index.html' + route, { waitUntil: 'networkidle' });
      await p.reload({ waitUntil: 'networkidle' });
      await p.waitForTimeout(600);
      const wide = await p.evaluate((vw) => {
        const bad = [];
        const clipped = (el) => { for (let e = el.parentElement; e; e = e.parentElement) { const o = getComputedStyle(e).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') return true; } return false; };
        document.querySelectorAll('body *').forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.width && r.right > vw + 1 && !clipped(el) && getComputedStyle(el).position !== 'fixed') bad.push(el.tagName.toLowerCase() + '.' + String(el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className).split(' ')[0] + ' ' + Math.round(r.right));
        });
        return { scrollWidth: document.documentElement.scrollWidth, bad: bad.slice(0, 6) };
      }, w);
      report.push({ name, tag, scheme, vw: w, scrollWidth: wide.scrollWidth, overflow: wide.scrollWidth > w + 1 || wide.bad.length > 0, bad: wide.bad });
      await p.screenshot({ path: `${out}/${name}-${tag}-${scheme}.png`, fullPage: true });
    }
    await ctx.close();
  }
  fs.writeFileSync(`${out}/overflow.json`, JSON.stringify(report, null, 1));
  const bad = report.filter((r) => r.overflow && r.tag === 'mobile');
  console.log(bad.length ? 'OVERFLOW:\n' + bad.map((r) => `${r.name} ${r.scheme} scrollWidth=${r.scrollWidth} ${r.bad.join('; ')}`).join('\n') : 'no mobile overflow');
  await b.close();
})();
