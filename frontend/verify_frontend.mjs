import { chromium } from 'playwright';

const browser = await chromium.launch({ args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1400, height: 1400 } });

const errors = [];
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(`console.error: ${msg.text()}`);
});

await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' });
await page.waitForSelector('text=Detected Patterns', { timeout: 15000 });
await page.waitForTimeout(1200);

const outBase = process.argv[2] ?? '/tmp/frontend_screenshot';

await page.screenshot({ path: `${outBase}_1Y.png`, fullPage: true });

for (const tf of ['3M', '1M', '1D']) {
  await page.click(`button:has-text("${tf}")`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${outBase}_${tf}.png`, fullPage: true });
}

// Also drive a ticker change to confirm the full round trip works.
await page.fill('input[placeholder="Ticker, e.g. AAPL"]', 'NVDA');
await page.click('button:has-text("Analyze")');
await page.waitForTimeout(2000);
await page.screenshot({ path: `${outBase}_NVDA.png`, fullPage: true });

// And an invalid ticker, to check the error path renders sanely.
await page.fill('input[placeholder="Ticker, e.g. AAPL"]', 'ZZZZZZ');
await page.click('button:has-text("Analyze")');
await page.waitForTimeout(2000);
await page.screenshot({ path: `${outBase}_invalid.png`, fullPage: true });

console.log('ERRORS:', JSON.stringify(errors, null, 2));
await browser.close();
