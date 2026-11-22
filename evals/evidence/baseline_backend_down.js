// Backend-down pass: load pages with the API stopped and record what the user sees.
const { chromium } = require('playwright');
const out = process.argv[2]; const base = process.argv[3] || 'http://localhost:3000';
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
  const errs = []; p.on('console', m => m.type() === 'error' && errs.push(m.text()));
  for (const path of ['/', '/analytics', '/council']) {
    const r = await p.goto(base + path, { waitUntil: 'networkidle' }); await p.waitForTimeout(2000);
    const name = `baseline_backend_down_${path === '/' ? 'home' : path.slice(1)}.png`;
    await p.screenshot({ path: `${out}/${name}` });
    const text = (await p.innerText('body')).replace(/\s+/g, ' ').slice(0, 300);
    console.log(`${path} status=${r.status()} -> ${name}\n  visible text: ${text}`);
  }
  console.log('console errors:', errs.slice(0, 5).join(' | '));
  await b.close();
})();
