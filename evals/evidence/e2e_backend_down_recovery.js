// E2E: backend down -> banner shown -> backend starts -> page recovers by itself.
// Usage: node evals/evidence/e2e_backend_down_recovery.js <out_dir> <start_backend_cmd>
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const out = process.argv[2]; const startCmd = process.argv[3];
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1366, height: 900 } })).newPage();
  await p.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
  const banner = await p.getByRole('alert').filter({ hasText: /Waking the server|Can't reach/ }).innerText().catch(() => '');
  await p.screenshot({ path: `${out}/e2e_backend_down_banner.png` });
  console.log('down: banner =', JSON.stringify(banner.replace(/\s+/g, ' ').slice(0, 160)));
  console.log('down: shows empty-account text?', await p.getByText(/No tasks scheduled for today|No data yet/).count() > 0);
  const srv = spawn('bash', ['-c', startCmd], { detached: true, stdio: 'ignore' });
  const t0 = Date.now();
  await p.getByRole('alert').filter({ hasText: /Waking the server|Can't reach/ }).waitFor({ state: 'detached', timeout: 60000 });
  console.log(`up: banner gone after ${Math.round((Date.now() - t0) / 1000)}s without manual reload`);
  await p.waitForTimeout(1000);
  await p.screenshot({ path: `${out}/e2e_backend_recovered.png` });
  console.log('up: dashboard loaded with progress:', await p.getByText(/\d+\/\d+ tasks/).first().innerText());
  await b.close(); process.kill(-srv.pid);
})();
