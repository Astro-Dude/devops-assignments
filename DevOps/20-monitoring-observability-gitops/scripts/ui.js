// usage: node ui.js <grafana|argocd|none> <url> <out.png> [--wait=ms] [--width=] [--height=] [--full] [--click=css] [--type=css::text]
const puppeteer = require('/tmp/cdp/node_modules/puppeteer-core');
(async () => {
  const [kind, url, out, ...rest] = process.argv.slice(2);
  const opt = {}; for (const a of rest) { const i = a.indexOf('='); const k = a.slice(2, i < 0 ? undefined : i); const v = i < 0 ? true : a.slice(i + 1); (opt[k] = opt[k] || []).push(v); }
  const one = k => opt[k] && opt[k][0];
  const browser = await puppeteer.connect({ browserURL: 'http://127.0.0.1:9222', defaultViewport: null });
  const page = await browser.newPage();
  await page.setViewport({ width: +(one('width') || 1600), height: +(one('height') || 1000) });
  const origin = new URL(url).origin;
  try {
    if (kind === 'grafana') {
      await page.goto(origin + '/login', { waitUntil: 'domcontentloaded' });
      const r = await page.evaluate(async () => (await fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user: 'admin', password: 'hw-s20-admin' }) })).status);
      console.log('grafana login', r);
    } else if (kind === 'argocd') {
      await page.goto(origin + '/login', { waitUntil: 'domcontentloaded' });
      const pw = process.env.ARGO_PW;
      const r = await page.evaluate(async (pw) => { const res = await fetch('/api/v1/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: 'admin', password: pw }) }); const j = await res.json(); document.cookie = 'argocd.token=' + j.token + '; path=/'; return res.status; }, pw);
      console.log('argocd login', r);
    }
    try { await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 }); } catch (e) { console.error('goto:', e.message); }
    for (const t of opt.type || []) { const [sel, text] = t.split('::'); await page.waitForSelector(sel, { timeout: 15000 }); await page.click(sel); await page.keyboard.type(text); }
    for (const c of opt.click || []) { await page.waitForSelector(c, { timeout: 15000 }); await page.click(c); await new Promise(r => setTimeout(r, 1500)); }
    await new Promise(r => setTimeout(r, +(one('wait') || 3000)));
    await page.screenshot({ path: out, fullPage: !!one('full') });
    console.log('saved', out);
  } finally { await page.close(); browser.disconnect(); }
})().catch(e => { console.error(e); process.exit(1); });
