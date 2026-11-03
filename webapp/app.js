/* Main-thread UI state machine. Heavy lifting happens in worker.js. */
'use strict';

(function () {
  const loader = document.getElementById('loader');
  const loaderText = document.getElementById('loader-text');
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const status = document.getElementById('status');
  const preview = document.getElementById('preview');
  const previewTitle = document.getElementById('preview-title');
  const previewBody = document.getElementById('preview-body');
  const previewFoot = document.getElementById('preview-foot');
  const review = document.getElementById('review');
  const reviewTitle = document.getElementById('review-title');
  const reviewList = document.getElementById('review-list');
  const downloadBtn = document.getElementById('download-btn');
  const versionFooter = document.getElementById('version-footer');

  const DEFAULT_RATES = { E_full: 400, E_half: 200, N_full: 600, N_half: 300 };
  const rateInputs = {
    E_full: document.getElementById('rate-e-full'),
    E_half: document.getElementById('rate-e-half'),
    N_full: document.getElementById('rate-n-full'),
    N_half: document.getElementById('rate-n-half'),
  };

  const STAGE_TEXT = {
    engine: '下載計算引擎（首次約 14MB，之後瀏覽器會快取，開啟即用）…',
    packages: '載入試算表元件…',
    app: '載入計算程式與清冊範本…',
  };

  let ready = false;
  let busy = false;
  let staffRows = []; // [{name, E_full, E_half, N_full, N_half}]

  function setStatus(type, html) {
    status.className = 'status show ' + type;
    status.innerHTML = html;
  }
  function clearStatus() {
    status.className = 'status';
    status.innerHTML = '';
  }
  function setBusy(b) {
    busy = b;
    dropzone.classList.toggle('disabled', b || !ready);
    downloadBtn.disabled = b || staffRows.length === 0;
  }
  function fatal(message) {
    loader.classList.add('error');
    loaderText.textContent = message;
  }

  if (typeof WebAssembly === 'undefined' || typeof Worker === 'undefined') {
    fatal('這個瀏覽器版本過舊，無法執行本工具。請改用近三年內的 Chrome、Edge 或 Safari。');
    return;
  }

  const worker = new Worker('./worker.js', { type: 'module' });
  worker.onerror = (e) => fatal('計算引擎啟動失敗：' + (e.message || '未知錯誤') + '，請重新整理頁面。');
  worker.onmessage = (e) => {
    const msg = e.data || {};
    if (msg.type === 'progress') {
      loaderText.textContent = STAGE_TEXT[msg.stage] || '載入中…';
    } else if (msg.type === 'ready') {
      ready = true;
      loader.classList.add('done');
      dropzone.classList.remove('disabled');
    } else if (msg.type === 'fatal') {
      fatal('載入失敗：' + msg.message + '（請重新整理頁面重試）');
    } else if (msg.type === 'parsed') {
      onParsed(msg);
    } else if (msg.type === 'built') {
      onBuilt(msg);
    } else if (msg.type === 'error') {
      setBusy(false);
      setStatus('error', '❌ 處理失敗：' + msg.message + '（可直接重新上傳重試）');
    }
  };

  function currentRates() {
    const rates = {};
    for (const key of Object.keys(rateInputs)) {
      const v = Number.parseInt(rateInputs[key].value, 10);
      if (!Number.isFinite(v) || v < 0) return null;
      rates[key] = v;
    }
    return rates;
  }

  const money = (n) => 'NT$ ' + n.toLocaleString('zh-TW');
  const amountOf = (row, rates) =>
    row.E_full * rates.E_full + row.E_half * rates.E_half +
    row.N_full * rates.N_full + row.N_half * rates.N_half;

  function renderPreview(meta) {
    previewTitle.textContent =
      meta.year + ' 年 ' + meta.month + ' 月 · ' + meta.ward_name +
      '（' + meta.ward_code + '）· ' + staffRows.length + ' 位人員';
    previewBody.replaceChildren();
    for (const row of staffRows) {
      const tr = document.createElement('tr');
      for (const val of [row.name, row.E_full, row.E_half, row.N_full, row.N_half, '']) {
        const td = document.createElement('td');
        td.textContent = String(val);
        tr.appendChild(td);
      }
      previewBody.appendChild(tr);
    }
    recalcAmounts();
    preview.classList.add('show');
  }

  // D020：需護理長人工確認的班次（不影響計數，只提醒）
  function renderReview(meta) {
    const flags = meta.review_flags || [];
    reviewList.replaceChildren();
    review.classList.toggle('show', flags.length > 0);
    if (flags.length === 0) return;
    reviewTitle.textContent = '⚠️ 有 ' + flags.length + ' 筆班次需要確認';
    for (const f of flags) {
      const li = document.createElement('li');
      const head = document.createElement('span');
      head.className = 'review-head';
      head.textContent = meta.month + '/' + f.day + ' ' + f.name + '　班別 ' + f.code + '　';
      const note = document.createElement('span');
      note.className = 'review-note';
      note.textContent = f.note || '（無備註）';
      const msg = document.createElement('span');
      msg.className = 'review-msg';
      msg.textContent = f.message;
      li.append(head, note, msg);
      reviewList.appendChild(li);
    }
  }

  function recalcAmounts() {
    const rates = currentRates();
    downloadBtn.disabled = busy || staffRows.length === 0 || !rates;
    if (!rates) {
      previewFoot.replaceChildren();
      setStatus('error', '❌ 費率必須是 0 以上的整數');
      return;
    }
    if (staffRows.length === 0) return;
    clearStatus();
    let totals = { E_full: 0, E_half: 0, N_full: 0, N_half: 0, amount: 0 };
    const rows = previewBody.children;
    staffRows.forEach((row, i) => {
      const amount = amountOf(row, rates);
      rows[i].lastElementChild.textContent = money(amount);
      totals.E_full += row.E_full;
      totals.E_half += row.E_half;
      totals.N_full += row.N_full;
      totals.N_half += row.N_half;
      totals.amount += amount;
    });
    const tr = document.createElement('tr');
    for (const val of ['合計', totals.E_full, totals.E_half, totals.N_full, totals.N_half, money(totals.amount)]) {
      const td = document.createElement('td');
      td.textContent = String(val);
      tr.appendChild(td);
    }
    previewFoot.replaceChildren(tr);
  }

  Object.values(rateInputs).forEach((input) => input.addEventListener('input', recalcAmounts));

  async function handleFile(file) {
    if (!file || !ready || busy) return;
    const name = (file.name || '').toLowerCase();
    if (!name.endsWith('.xls') && !name.endsWith('.xlsx')) {
      setStatus('error', '❌ 只支援 .xls 或 .xlsx 格式，請確認檔案類型');
      return;
    }
    setBusy(true);
    preview.classList.remove('show');
    staffRows = [];
    setStatus('loading', '<span class="spinner"></span><span>正在解析排班表…</span>');
    const buffer = await file.arrayBuffer();
    worker.postMessage({ cmd: 'parse', filename: file.name, buffer }, [buffer]);
  }

  function onParsed(msg) {
    setBusy(false);
    if (!msg.ok) {
      setStatus('error', '❌ ' + msg.message);
      return;
    }
    staffRows = msg.preview.staff;
    clearStatus();
    renderPreview(msg.preview);
    renderReview(msg.preview);
  }

  downloadBtn.addEventListener('click', () => {
    const rates = currentRates();
    if (!rates || busy) return;
    setBusy(true);
    setStatus('loading', '<span class="spinner"></span><span>正在產出清冊…</span>');
    worker.postMessage({ cmd: 'build', rates });
  });

  function onBuilt(msg) {
    setBusy(false);
    if (!msg.ok) {
      setStatus('error', '❌ ' + msg.message);
      return;
    }
    const blob = new Blob([msg.bytes], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = msg.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setStatus('success', '✅ 產出完成，已開始下載「' + msg.filename + '」');
  }

  fileInput.addEventListener('change', (e) => {
    const f = e.target.files && e.target.files[0];
    handleFile(f);
    fileInput.value = ''; // allow re-uploading the same file
  });
  ['dragenter', 'dragover'].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });
  dropzone.addEventListener('drop', (e) => {
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) handleFile(f);
  });

  fetch('./version.json')
    .then((r) => (r.ok ? r.json() : null))
    .then((v) => {
      if (v) versionFooter.textContent = '版本 ' + v.version + ' · ' + v.built;
    })
    .catch(() => {});
})();
