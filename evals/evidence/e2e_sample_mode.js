// E2E (demo mode, no Gemini key on the server): the Council shows the free-API notice and
// "Showing sample replies", a chat reply carries the sample label, and a demo-control
// nudge on the dashboard carries it too. Never presents a sample as live.
// Usage: node evals/evidence/e2e_sample_mode.js <out_dir> [frontend_url]
const { chromium } = require('playwright');
const out = process.argv[2]; const base = process.argv[3] || 'http://localhost:3000';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1366, height: 900 } });
  const p = await ctx.newPage(); const errors = []; p.on('pageerror', e => errors.push(e.message));

  await p.goto(base + '/council', { waitUntil: 'networkidle' }); await p.waitForTimeout(1500);
  const body = await p.innerText('body');
  console.log('council budget line:', (body.match(/Showing sample replies[^\n]*|Live replies left: \d+ of \d+/) || ['(none)'])[0]);
  console.log('free-API notice shown:', body.includes("Live replies use a free Google API; don't enter personal information. This demo uses sample data."));
  await p.getByPlaceholder(/Message Freya/).fill('How is my day going?');
  await p.keyboard.press('Enter');
  await p.getByText('Sample reply (pre-written, not live)').first().waitFor({ timeout: 30000 });
  const bubble = await p.locator('div.fade-in').filter({ hasText: 'Sample reply (pre-written, not live)' }).last().innerText();
  console.log('chat reply (Freya):', bubble.replace(/\s+/g, ' ').slice(0, 260));
  await p.screenshot({ path: `${out}/sample_mode_council.png` });

  await p.goto(base + '/', { waitUntil: 'networkidle' });
  await p.getByRole('button', { name: /Mark a task as missed/ }).click();
  await p.getByRole('status').waitFor({ timeout: 30000 });
  console.log('demo control result:', await p.getByRole('status').innerText());
  await p.waitForTimeout(1500);
  const nudges = await p.locator('div.glass').filter({ has: p.getByText('Council nudges', { exact: true }) }).last().innerText();
  console.log('nudges panel:', nudges.replace(/\s+/g, ' ').slice(0, 300));
  await p.screenshot({ path: `${out}/sample_mode_dashboard_nudge.png` });
  console.log('page errors:', errors.length ? errors : 'none');
  await b.close();
})();
