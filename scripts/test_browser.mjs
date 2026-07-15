// Headless-browser acceptance test for the built dist/ (AC3/AC4/AC5/AC6
// local edition): serves dist, drives the real UI in Chromium, audits that
// every network request is same-origin, and verifies the downloaded xlsx.
// Usage: python3 scripts/build_webapp.py && node scripts/test_browser.mjs
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PORT = 8791;
const BASE = `http://127.0.0.1:${PORT}`;
const FIXTURE = path.join(ROOT, 'tests', 'fixtures', '11503-N19W01排班表.xls');
const EXPECT_NAME = '11503-N19W01_夜班費清冊_11病房.xlsx';

const fail = (msg) => {
  console.error('FAIL:', msg);
  process.exit(1);
};

// -- static server --------------------------------------------------------
const server = spawn(process.execPath, [path.join(ROOT, 'scripts', 'serve_dist.mjs'), String(PORT)], {
  stdio: ['ignore', 'pipe', 'pipe'],
});
process.on('exit', () => server.kill());
await new Promise((resolve, reject) => {
  const t0 = Date.now();
  const poll = async () => {
    try {
      const r = await fetch(`${BASE}/version.json`);
      if (r.ok) return resolve(null);
    } catch (_) { /* not up yet */ }
    if (Date.now() - t0 > 15000) return reject(new Error('serve_dist 未在 15 秒內就緒'));
    setTimeout(poll, 200);
  };
  poll();
});
console.log('[ok] 本機伺服器就緒 ' + BASE);

// -- browser ---------------------------------------------------------------
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const externalRequests = [];
const pageErrors = [];
page.on('request', (req) => {
  const url = req.url();
  if (!url.startsWith(BASE) && !url.startsWith('data:') && !url.startsWith('blob:')) {
    externalRequests.push(url);
  }
});
page.on('pageerror', (err) => pageErrors.push(String(err)));

await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
// .done hides the loader (display:none), so wait on the class, not visibility
await page.waitForFunction(() => {
  const el = document.querySelector('#loader');
  if (el.classList.contains('error')) throw new Error('載入失敗：' + el.textContent);
  return el.classList.contains('done');
}, { timeout: 120000 });
console.log('[ok] 引擎載入完成，上傳區已開放');

// AC3 (local): upload fixture → preview
await page.setInputFiles('#file-input', FIXTURE);
await page.waitForSelector('#preview.show', { timeout: 60000 });
const title = await page.textContent('#preview-title');
if (!title.includes('115 年 3 月') || !title.includes('11病房') || !title.includes('23 位人員')) {
  fail(`預覽標題不符：${title}`);
}
const rowCount = await page.locator('#preview-body tr').count();
if (rowCount !== 23) fail(`預覽人數列 ${rowCount} != 23`);
const foot = await page.textContent('#preview-foot');
if (!foot.includes('NT$ 87,200')) fail(`合計列缺 87,200：${foot}`);
console.log('[ok] 預覽：23 人、合計 NT$ 87,200');

// AC5: change E_full rate to 500 → live total 95,200
await page.fill('#rate-e-full', '500');
await page.waitForFunction(() =>
  document.querySelector('#preview-foot').textContent.includes('NT$ 95,200'));
console.log('[ok] 費率 400→500 即時重算：合計 NT$ 95,200');

// download with the adjusted rate and verify the workbook formulas
const [download] = await Promise.all([
  page.waitForEvent('download', { timeout: 60000 }),
  page.click('#download-btn'),
]);
if (download.suggestedFilename() !== EXPECT_NAME) {
  fail(`下載檔名不符：${download.suggestedFilename()}`);
}
const saved = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'nsa-dl-')), EXPECT_NAME);
await download.saveAs(saved);
const check = spawnSync(path.join(ROOT, '.venv', 'bin', 'python'), ['-c', `
import sys
from openpyxl import load_workbook
ws = load_workbook(sys.argv[1]).active
assert ws['F4'].value == '=E4*500', ws['F4'].value
assert ws['F9'].value == '=E9*600', ws['F9'].value
assert '3月' in str(ws['A1'].value), ws['A1'].value
assert str(ws['A2'].value).endswith('11病房'), ws['A2'].value
assert len(ws.merged_cells.ranges) > 300
print('xlsx-ok')
`, saved], { encoding: 'utf-8' });
if (!check.stdout.includes('xlsx-ok')) fail(`下載檔驗證失敗：${check.stdout} ${check.stderr}`);
console.log(`[ok] 下載檔驗證通過（F4 =E4*500、標題、合併儲存格）：${download.suggestedFilename()}`);

// AC6: wrong file type → plain-language error, then recover without reload
const badFile = path.join(path.dirname(saved), 'not-excel.txt');
fs.writeFileSync(badFile, 'not an excel file');
await page.setInputFiles('#file-input', badFile);
await page.waitForFunction(() =>
  document.querySelector('#status').textContent.includes('只支援 .xls 或 .xlsx'));
await page.setInputFiles('#file-input', FIXTURE);
await page.waitForSelector('#preview.show', { timeout: 60000 });
await page.waitForFunction(() =>
  document.querySelector('#preview-foot').textContent.includes('NT$'));
console.log('[ok] 錯誤路徑：白話提示後不需重新整理即可重試');

// AC4: zero external requests
if (externalRequests.length) fail('出現外部請求：\n' + externalRequests.join('\n'));
console.log('[ok] 網路稽核：全程僅同源請求（AC4）');

if (pageErrors.length) fail('頁面 JS 錯誤：\n' + pageErrors.join('\n'));

await browser.close();
console.log('PASS: 瀏覽器驗收全數通過');
process.exit(0);
