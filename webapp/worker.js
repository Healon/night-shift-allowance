/* Module Web Worker: hosts Pyodide and runs the pipeline off the main thread.
 * (Pyodide 314 dropped classic-worker support.) All assets are same-origin
 * (vendor/) — no external requests at runtime. */
import { loadPyodide } from './vendor/pyodide/pyodide.mjs';

const post = (msg, transfer) => self.postMessage(msg, transfer || []);

let pyodide = null;
let bridge = null;

const INIT = (async () => {
  post({ type: 'progress', stage: 'engine' });
  pyodide = await loadPyodide({
    indexURL: new URL('./vendor/pyodide/', import.meta.url).href,
  });

  post({ type: 'progress', stage: 'packages' });
  await pyodide.loadPackage(['pandas', 'xlrd', 'openpyxl'], { messageCallback: () => {} });

  post({ type: 'progress', stage: 'app' });
  const [srcZip, template] = await Promise.all([
    fetch('./vendor/src.zip').then((r) => {
      if (!r.ok) throw new Error('src.zip HTTP ' + r.status);
      return r.arrayBuffer();
    }),
    fetch('./vendor/template.xlsx').then((r) => {
      if (!r.ok) throw new Error('template.xlsx HTTP ' + r.status);
      return r.arrayBuffer();
    }),
  ]);
  ['/app', '/work', '/out'].forEach((d) => pyodide.FS.mkdirTree(d));
  pyodide.unpackArchive(srcZip, 'zip', { extractDir: '/app' });
  pyodide.FS.writeFile('/app/template.xlsx', new Uint8Array(template));
  pyodide.runPython("import sys; sys.path.insert(0, '/app')");
  bridge = pyodide.pyimport('bridge');
  post({ type: 'ready' });
})().catch((err) => {
  post({ type: 'fatal', message: String((err && err.message) || err) });
  throw err;
});

self.onmessage = async (e) => {
  const msg = e.data || {};
  try {
    await INIT;
  } catch (_) {
    return; // fatal already reported
  }
  try {
    if (msg.cmd === 'parse') {
      // Keep the original basename: parser derives ward_code from it.
      const filename = String(msg.filename).split('/').pop().split('\\').pop();
      pyodide.FS.writeFile('/work/' + filename, new Uint8Array(msg.buffer));
      const res = JSON.parse(bridge.parse_and_classify(filename));
      post({ type: 'parsed', ...res });
    } else if (msg.cmd === 'build') {
      const res = JSON.parse(bridge.build(JSON.stringify(msg.rates)));
      if (!res.ok) {
        post({ type: 'built', ...res });
        return;
      }
      const bytes = pyodide.FS.readFile(res.path);
      pyodide.FS.unlink(res.path);
      post({ type: 'built', ok: true, filename: res.filename, bytes: bytes.buffer }, [bytes.buffer]);
    }
  } catch (err) {
    post({ type: 'error', message: String((err && err.message) || err) });
  }
};
