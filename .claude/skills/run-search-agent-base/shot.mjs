// Usage: [CLICK='text=Market Discovery Radar'] node shot.mjs [url] [out.png]   (uses the globally installed playwright)
// Loads the dashboard in headless Chromium, prints console errors/failed requests, saves a screenshot.
import { createRequire } from 'module';
import { execSync } from 'child_process';
const require = createRequire(execSync('npm root -g').toString().trim() + '/');
const { chromium } = require('playwright');
const url = process.argv[2] || 'http://localhost:8000/';
const out = process.argv[3] || '/tmp/shots/dashboard.png';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const problems = [];
page.on('console', m => m.type() === 'error' && problems.push('console: ' + m.text()));
page.on('requestfailed', r => problems.push('failed: ' + r.url()));
page.on('response', r => r.status() >= 400 && problems.push(`${r.status()}: ${r.url()}`));
await page.goto(url, { waitUntil: 'networkidle' });
if (process.env.CLICK) { await page.click(process.env.CLICK); await page.waitForTimeout(800); }
await page.screenshot({ path: out, fullPage: !!process.env.CLICK });
console.log('title:', await page.title());
console.log('screenshot:', out);
console.log(problems.length ? problems.join('\n') : 'no console errors');
await browser.close();
