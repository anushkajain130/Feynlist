// E2E (demo mode): two browser sessions get separate seeded data; demo controls work;
// a change in one session never appears in the other. Run against a DEMO_MODE=true backend.
// Usage: node evals/evidence/e2e_demo_mode.js <out_dir> [frontend_url]
const { chromium, devices } = require('playwright');
const out = process.argv[2]; const base = process.argv[3] || 'http://localhost:3000';
const log = (...a) => console.log(...a);
(async () => {
  const browser = await chromium.launch();
  const a = await (await browser.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
  const b = await (await browser.newContext(devices['iPhone 13'])).newPage();
  const errors = []; for (const p of [a, b]) p.on('pageerror', e => errors.push(e.message));

  await a.goto(base + '/', { waitUntil: 'networkidle' });
  await a.getByText('How to evaluate in 3 minutes').waitFor({ timeout: 30000 });
  log('A: demo panel visible:', await a.getByText('Sample data', { exact: true }).count() > 0);
  log('A: progress text:', (await a.getByText(/\d+\/\d+ tasks/).first().innerText()));
  log('A: Aura card:', (await a.getByText(/consistency streak · Info|Starts after your first counted day/).first().innerText()));
  await a.screenshot({ path: `${out}/demo_desktop_dashboard.png` });

  // Demo control: complete a task
  const before = await a.getByText(/\d+\/\d+ tasks/).first().innerText();
  await a.getByRole('button', { name: /Complete a task/ }).click();
  await a.getByRole('status').waitFor({ timeout: 30000 });
  log('A: complete-task result:', await a.getByRole('status').innerText());
  await a.waitForTimeout(1000);
  const after = await a.getByText(/\d+\/\d+ tasks/).first().innerText();
  log(`A: progress ${before} -> ${after}`);

  // Session B (phone) must not see A's change
  await b.goto(base + '/', { waitUntil: 'networkidle' });
  await b.getByText('How to evaluate in 3 minutes').waitFor({ timeout: 30000 });
  log('B: progress text (should equal A before):', await b.getByText(/\d+\/\d+ tasks/).first().innerText());
  await b.screenshot({ path: `${out}/demo_phone_dashboard.png` });

  // Reset A
  await a.getByRole('button', { name: /Reset demo/ }).click();
  await a.getByText('Demo reset to the starting sample data.').waitFor({ timeout: 30000 });
  await a.waitForTimeout(800);
  log('A after reset:', await a.getByText(/\d+\/\d+ tasks/).first().innerText());

  await a.goto(base + '/analytics', { waitUntil: 'networkidle' }); await a.waitForTimeout(1500);
  log('A analytics shows charts (no "No data yet"):', await a.getByText('No data yet').count() === 0);
  await a.screenshot({ path: `${out}/demo_desktop_analytics.png` });
  log('page errors:', errors.length ? errors : 'none');
  await browser.close();
})();
