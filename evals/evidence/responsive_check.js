// Phone-width check (390px, iPhone 13 profile) + desktop, with screenshots.
// Reports elements whose box extends past the viewport (clipped/unreachable content).
// Seeds today's plan with frontend/src/lib/dayTemplate.json via the API first
// (replaces today's tasks in whatever DB the backend uses: run it on a scratch DB).
// Usage: node evals/evidence/responsive_check.js <out_dir> <prefix> [frontend_url] [api_url]
const { chromium, devices } = require('playwright');
const path = require('path');
const out = process.argv[2]; const prefix = process.argv[3]; const base = process.argv[4] || 'http://localhost:3000';
const api = process.argv[5] || 'http://127.0.0.1:8000';
const template = require(path.join(__dirname, '..', '..', 'frontend', 'src', 'lib', 'dayTemplate.json'));
async function overflow(page) {
  return page.evaluate(() => {
    const W = window.innerWidth; const bad = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') continue;
      if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
      if (r.right > W + 1 || r.left < -1) bad.push(`${el.tagName.toLowerCase()}${el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''} [${Math.round(r.left)}..${Math.round(r.right)}] "${(el.innerText || '').trim().slice(0, 30)}"`);
    }
    return { W, count: bad.length, sample: bad.slice(0, 5) };
  });
}
(async () => {
  const seed = await fetch(`${api}/api/tasks/schedule`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tasks: template }) });
  if (!seed.ok) throw new Error(`seeding failed: HTTP ${seed.status}`);
  const browser = await chromium.launch();
  const results = [];
  for (const [label, opts] of [['phone', devices['iPhone 13']], ['desktop', { viewport: { width: 1366, height: 900 }, deviceScaleFactor: 1 }]]) {
    const ctx = await browser.newContext(opts); const page = await ctx.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.status() >= 500) errors.push(`HTTP ${r.status()} ${r.url()}`); });
    const shots = [
      ['home', '/', null],
      ['home_task_expanded', '/', async p => { await p.getByText('Study: hardest subject first').first().click(); }],
      ['home_planner', '/', async p => { await p.getByRole('button', { name: /Modify Schedule|Plan Today/ }).click(); }],
      ...(process.env.SKIP_CHECKIN ? [] : [['home_checkin', '/', async p => { await p.getByRole('button', { name: /Daily Check-In/ }).click(); }]]),
      ['home_aura_info', '/', async p => { await p.getByText(/Aura \(Click for Info\)/).click(); }],
      ['analytics', '/analytics', null],
      ['council', '/council', null],
      ['about', '/about', null],
    ];
    for (const [name, path, act] of shots) {
      await page.goto(base + path, { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
      if (act) { await act(page); await page.waitForTimeout(500); }
      const o = await overflow(page);
      const broken = (await page.innerText('body')).includes("This page couldn’t load");
      const errs = errors.splice(0); if (broken) errs.push('error page rendered');
      const file = `${prefix}_${label}_${name}.png`;
      await page.screenshot({ path: `${out}/${file}`, fullPage: true });
      results.push(`[${label}] ${name}: elements past viewport (${o.W}px) = ${o.count}${o.count ? ' e.g. ' + o.sample.join(' | ') : ''}; page errors = ${errs.length}${errs.length ? ' (' + errs.slice(0, 2).join('; ') + ')' : ''} -> ${file}`);
    }
    await ctx.close();
  }
  await browser.close();
  console.log(results.join('\n'));
})();
