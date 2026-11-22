// Baseline browser pass: screenshots of each page (desktop + phone) and console errors.
// Usage: node evals/evidence/baseline_browser.js <out_dir> [frontend_url]
const { chromium, devices } = require('playwright');
const out = process.argv[2]; const base = process.argv[3] || 'http://localhost:3000';
(async () => {
  const browser = await chromium.launch();
  const log = [];
  for (const [label, opts] of [['desktop', { viewport: { width: 1366, height: 900 }, deviceScaleFactor: 1 }], ['phone', devices['iPhone 13']]]) {
    const ctx = await browser.newContext(opts); const page = await ctx.newPage();
    page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') log.push(`[${label}] console.${m.type()}: ${m.text()}`); });
    page.on('pageerror', e => log.push(`[${label}] pageerror: ${e.message}`));
    for (const p of ['/', '/analytics', '/council', '/settings']) {
      const r = await page.goto(base + p, { waitUntil: 'networkidle' }).catch(e => ({ status: () => 'ERR ' + e.message }));
      await page.waitForTimeout(1500);
      const name = `baseline_${label}_${p === '/' ? 'home' : p.slice(1)}.png`;
      await page.screenshot({ path: `${out}/${name}`, fullPage: true });
      const sw = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      log.push(`[${label}] ${p} status=${r.status()} scrollWidth=${sw[0]} innerWidth=${sw[1]} -> ${name}`);
    }
    await ctx.close();
  }
  await browser.close();
  console.log(log.join('\n'));
})();
