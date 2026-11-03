// WASM smoke test: run the full pytest suite AND the shipped bridge against
// the assets actually deployed in dist/. Guards against "green locally,
// broken in the browser". Usage: python3 scripts/build_webapp.py && node scripts/test_wasm.mjs
import { loadPyodide } from 'pyodide';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST_PYODIDE = path.join(ROOT, 'dist', 'vendor', 'pyodide');
const FIXTURE = '11503-N19W01排班表.xls';

const fail = (msg) => {
  console.error('FAIL:', msg);
  process.exit(1);
};
process.on('uncaughtException', (e) => fail((e && e.message) || e));
process.on('unhandledRejection', (e) => fail((e && e.message) || e));

if (!fs.existsSync(path.join(DIST_PYODIDE, 'pyodide-lock.json'))) {
  fail('找不到 dist/vendor/pyodide，請先跑 python3 scripts/build_webapp.py');
}

const npmVersion = createRequire(import.meta.url)('pyodide/package.json').version;
const lock = JSON.parse(fs.readFileSync(path.join(DIST_PYODIDE, 'pyodide-lock.json'), 'utf-8'));
for (const name of ['pandas', 'xlrd', 'openpyxl', 'et-xmlfile']) {
  if (!lock.packages[name]) fail(`dist lockfile 缺 ${name}`);
  if (!fs.existsSync(path.join(DIST_PYODIDE, lock.packages[name].file_name))) {
    fail(`dist 缺 wheel：${lock.packages[name].file_name}`);
  }
}
// every wheel shipped in dist must match its lockfile sha256 (this is what
// the browser will integrity-check when serving from dist)
let verified = 0;
for (const pkg of Object.values(lock.packages)) {
  const p = path.join(DIST_PYODIDE, pkg.file_name);
  if (!fs.existsSync(p)) continue; // only the runtime closure is vendored
  const h = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
  if (h !== pkg.sha256) fail(`sha256 不符：${pkg.file_name}`);
  verified += 1;
}
console.log(`[ok] dist 資產齊全（${verified} 顆 wheel sha256 全數相符）`);

const t0 = performance.now();
// The repo lives under a path with a space ("MAC SSD"): Node's loadPackage
// percent-encodes such paths and then misses local wheels, silently falling
// back to the CDN (symlinks get resolved back to the real path, so they do
// not help). Run against a byte-identical copy in a space-free temp dir.
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nsa-wasm-'));
const indexDir = path.join(tmpDir, 'pyodide');
fs.cpSync(DIST_PYODIDE, indexDir, { recursive: true });
process.on('exit', () => {
  try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch (_) { /* best effort */ }
});
const pyodide = await loadPyodide({
  indexURL: indexDir + path.sep, // trailing slash is required for local wheel resolution
  packageCacheDir: path.join(ROOT, '.vendor-cache', 'test-packages'),
});
// dist core must match the npm loader version (both pinned).
if (pyodide.version !== npmVersion) {
  fail(`版本不一致：dist 核心=${pyodide.version} npm pyodide=${npmVersion}（兩處都要釘同版）`);
}
console.log(`[ok] 以 dist 核心開機 ${(performance.now() - t0).toFixed(0)} ms（pyodide ${pyodide.version}）`);

// pytest closure is NOT vendored in dist (production never needs it); the
// first run fetches it from the CDN into .vendor-cache/test-packages.
// Node's loader sources lockfile wheels from its own cache/CDN — indexURL
// wheel serving is a browser-only path (verified in the real-browser E2E).
// dist wheel bytes are sha256-verified statically below; the two PyPI wheels
// that do not exist on the CDN are installed from the dist copies via emfs,
// so the exact shipped bytes are what runs in this test.
await pyodide.loadPackage(['pandas', 'xlrd', 'pytest', 'micropip'], { messageCallback: () => {} });
pyodide.FS.mkdirTree('/dist-wheels');
const extraWheels = ['et-xmlfile', 'openpyxl'].map((key) => lock.packages[key].file_name);
for (const fn of extraWheels) {
  pyodide.FS.writeFile('/dist-wheels/' + fn, new Uint8Array(fs.readFileSync(path.join(DIST_PYODIDE, fn))));
}
await pyodide.runPythonAsync(`
import micropip
await micropip.install([${extraWheels.map((f) => `'emfs:/dist-wheels/${f}'`).join(', ')}], deps=False)
`);
console.log('[ok] 套件載入（openpyxl / et_xmlfile 來自 dist 實體 wheel）');

// mount the repo test bed
const MOUNT = [
  'src/__init__.py', 'src/builder.py', 'src/classifier.py', 'src/config.py', 'src/main.py', 'src/parser.py',
  'src/shift_hours.py',
  'tests/__init__.py', 'tests/conftest.py', 'tests/test_parser.py', 'tests/test_classifier.py', 'tests/test_builder.py',
  'tests/test_shift_hours.py',
  `tests/fixtures/${FIXTURE}`, 'tests/fixtures/11501-N19W01排班表.xls',
  'tests/fixtures/11502-N19W01排班表.xls', 'tests/fixtures/11504-N18W01排班表.xls',
  'tests/fixtures/11510-N08W01排班表.xlsx',
  'templates/衛生福利部夜班津貼示範.xlsx',
];
for (const dir of ['/proj/src', '/proj/tests/fixtures', '/proj/templates', '/app', '/work']) {
  pyodide.FS.mkdirTree(dir);
}
for (const f of MOUNT) {
  pyodide.FS.writeFile(`/proj/${f}`, new Uint8Array(fs.readFileSync(path.join(ROOT, f))));
}

// phase 1: full pytest suite (repo code) in WASM
const rc = await pyodide.runPythonAsync(`
import os, sys, pytest
os.chdir('/proj')
sys.path.insert(0, '/proj')
pytest.main(['-q', '--no-header', '-p', 'no:cacheprovider',
             'tests/test_parser.py', 'tests/test_classifier.py', 'tests/test_builder.py',
             'tests/test_shift_hours.py'])
`);
if (rc !== 0) fail(`pytest exit code ${rc}`);
console.log('[ok] pytest 全綠（WASM）');

// phase 2: the SHIPPED bridge + src.zip + template from dist
pyodide.unpackArchive(new Uint8Array(fs.readFileSync(path.join(ROOT, 'dist', 'vendor', 'src.zip'))), 'zip', { extractDir: '/app' });
pyodide.FS.writeFile('/app/template.xlsx',
  new Uint8Array(fs.readFileSync(path.join(ROOT, 'dist', 'vendor', 'template.xlsx'))));

const summary = await pyodide.runPythonAsync(`
import json, shutil, sys
# drop repo modules so imports re-resolve to the shipped copies under /app
for m in [m for m in list(sys.modules) if m == 'src' or m.startswith('src.')]:
    del sys.modules[m]
sys.path.remove('/proj')
sys.path.insert(0, '/app')
import bridge  # noqa: F401

shutil.copy('/proj/tests/fixtures/${FIXTURE}', '/work/${FIXTURE}')
r = json.loads(bridge.parse_and_classify('${FIXTURE}'))
assert r['ok'], r
staff = r['preview']['staff']
tot = {k: sum(s[k] for s in staff) for k in ('E_full', 'E_half', 'N_full', 'N_half')}
assert len(staff) == 23, len(staff)
assert (tot['E_full'], tot['E_half'], tot['N_full'], tot['N_half']) == (80, 12, 88, 0), tot
amount = tot['E_full']*400 + tot['E_half']*200 + tot['N_full']*600 + tot['N_half']*300
assert amount == 87200, amount
assert r['preview']['review_flags'] == [], r['preview']['review_flags']

# D020／D021：11510 含 E(請) 16-17:40／16-19、N( 請) 04-08；整班 E 部分請假不足 4h 不計；1 筆需確認班次
D020 = '11510-N08W01排班表.xlsx'
shutil.copy(f'/proj/tests/fixtures/{D020}', f'/work/{D020}')
r20 = json.loads(bridge.parse_and_classify(D020))
assert r20['ok'], r20
t20 = {k: sum(s[k] for s in r20['preview']['staff']) for k in ('E_full', 'E_half', 'N_full', 'N_half')}
assert (t20['E_full'], t20['E_half'], t20['N_full'], t20['N_half']) == (69, 3, 90, 1), t20
assert [(f['name'], f['day']) for f in r20['preview']['review_flags']] == \
    [('人員M', 12)], r20['preview']['review_flags']
# 回復 11503 狀態供下方 build 驗證
r = json.loads(bridge.parse_and_classify('${FIXTURE}'))
assert r['ok'], r

b = json.loads(bridge.build(json.dumps({'E_full': 500, 'E_half': 200, 'N_full': 600, 'N_half': 300})))
assert b['ok'], b
from openpyxl import load_workbook
ws = load_workbook(b['path']).active
assert ws['F4'].value == '=E4*500', ws['F4'].value
assert '3月' in str(ws['A1'].value), ws['A1'].value
json.dumps({'staff': len(staff), **tot, 'baseline': amount, 'filename': b['filename']}, ensure_ascii=False)
`);
console.log('[ok] 出貨版 bridge 端到端：' + summary);
console.log('PASS: WASM 冒煙測試全數通過');
