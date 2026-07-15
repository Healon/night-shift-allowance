# Sprint 03 — 靜態網頁化（Pyodide）

> 目標：把工具部署為永遠在線的靜態網址，護理長開瀏覽器即用。現有 Python 計算程式**零修改**，在使用者瀏覽器內以 WebAssembly 執行。
> 依據：`docs/superpowers/specs/2026-07-15-web-static-pyodide-design.md`（已核可）。
> 註：本 Sprint 取代 CLAUDE.md 原排定的 Sprint 03 範圍（身分驗證、Docker、歷史紀錄）。該三項經 2026-07-15 需求釐清由 Lin 明確排除，不再實作。

---

## 驗收條件

即設計文件第 6 節 AC1~AC7，摘要：

1. **AC1** `python scripts/build_webapp.py` 產出 `dist/`，檔案清單通過白名單檢查（絕不含 fixtures 與任何真實姓名檔案）。
2. **AC2** `node scripts/test_wasm.mjs` 以 `dist/vendor` 的資產跑 parser／classifier／builder 97 條測試全綠，11503 端到端 = 87,200。
3. **AC3** 真瀏覽器：上傳 11503 fixture，預覽 23 人、總額 87,200，下載檔與現行 CLI 產出等值。
4. **AC4** 執行期零外部請求（DevTools Network 僅同源）。
5. **AC5** 費率改 500：預覽即時重算、產出 F 欄公式 `=E{r}*500`。
6. **AC6** 錯誤路徑白話提示，不需重新整理可重試。
7. **AC7** 非開發機開公開網址完成完整流程。

---

## 任務分解

### Task 3.1：建置腳本 `scripts/build_webapp.py`
- [ ] 釘死版本常數：Pyodide 314.0.2；openpyxl／et_xmlfile 釘 PyPI 版本
- [ ] 下載器：CDN 核心檔＋依 lock 計算 `pandas`、`xlrd` 依賴閉包的 wheels；PyPI 兩顆純 Python wheel；一律 sha256 驗證，快取於 `.vendor-cache/`（gitignore）
- [ ] lock 補丁：把 openpyxl、et_xmlfile 以標準 entry 寫入 vendored `pyodide-lock.json`（此後執行期一律 `loadPackage(['pandas','xlrd','openpyxl'])`，單一機制）
- [ ] 組裝 `dist/`：webapp 靜態檔＋`vendor/pyodide/`（核心＋lock＋全部 wheels）＋`vendor/src.zip`（`src/*.py`＋`webapp/bridge.py`）＋`vendor/template.xlsx`（範本改英文檔名）＋`version.json`（git short hash＋日期）
- [ ] 白名單檢查：dist 每個檔案必須在允許清單內；另外硬性禁止 `.xls`、路徑含 `fixtures`、檔名含「排班表」
- [ ] `.gitignore` 增補：`dist/`、`.vendor-cache/`、`node_modules/`

### Task 3.2：Python 橋接 `webapp/bridge.py`
- [ ] `parse_and_classify(filename) -> json`：讀 `/work/<原始檔名>`（保留檔名，parser 從檔名抽 ward_code）、回預覽資料（各人四類班數）或 `{ok:false, kind, message}`
- [ ] `build(rates_json) -> json`：以暫存的 schedule/counts 呼叫 `build_roster(..., rates)`，輸出至 `/out/`，回檔名
- [ ] 錯誤分級沿用 `web/app.py` 語意：`ValueError` → format（白話）、其他 → unknown（帶訊息）

### Task 3.3：前端 `webapp/index.html`＋`app.js`＋`worker.js`
- [ ] worker：分階段初始化（引擎 → 套件 → 程式與範本 → 就緒），每階段回報進度；`parse`／`build` 指令；崩潰 catch-all
- [ ] UI 沿用現行 index.html 視覺；新增：載入進度、統計預覽表（姓名／小夜／小夜半／大夜／大夜半／金額＋合計）、四個費率欄（預設 400/200/600/300，改動即時以 JS 重算金額）、「下載清冊」鍵
- [ ] 下載：worker 回傳 bytes，Blob＋`a[download]`（中文檔名原生支援）
- [ ] WASM 不支援偵測與明確訊息；頁腳顯示 version.json 內容
- [ ] 錯誤後不需重新整理即可重試；重新拖檔即重跑

### Task 3.4：WASM 冒煙測試 `scripts/test_wasm.mjs`
- [ ] 收編 PoC：`indexURL` 指向 `dist/vendor/pyodide/`（**測部署資產本身**）
- [ ] 掛載 repo 的 `src/`、`tests/`（不含 test_web）、`templates/`、`fixtures/` 進 MEMFS
- [ ] `loadPackage(['pandas','xlrd','openpyxl','pytest'])`（pytest 閉包經 CDN 首跑後快取於 `.vendor-cache/`，不進 dist）
- [ ] 斷言：97 條測試全綠＋11503 端到端 87,200＋產出檔公式抽查
- [ ] root `package.json`（pyodide dev 依賴）進 git

### Task 3.5：本機驗收
- [ ] AC1、AC2 指令實跑
- [ ] 本機起靜態伺服器載入 dist，實測上傳 11503：預覽、費率改 500、下載、錯誤路徑（AC3、AC5、AC6 的本機版）
- [ ] 產出檔與 `python -m src.main` 的 CLI 產出用 openpyxl 逐項比對

### Task 3.6：部署與文件
- [ ] Netlify 建站（中性站名，不含醫院識別）、上傳 dist、取得公開網址
- [ ] 線上驗 AC4（Network 僅同源）；AC7 與 AC3 線上版請 Lin 在非開發機做最終人工驗收
- [ ] 更新 `README.md`（新增網頁版使用與維護 SOP）、`CLAUDE.md`（當前狀態、Sprint 03 接力摘要）

---

## 實作提示

- **檔名保留**：與 `web/app.py` 同理，上傳檔必須以原始檔名寫入 MEMFS `/work/`，否則 `_extract_ward_code` 會失敗。
- **範本路徑**：一律顯式傳 `template_path=/app/template.xlsx`，不依賴 `config.TEMPLATE_PATH`（其 `PROJECT_ROOT` 推導在 MEMFS 不成立）。
- **輸出**：`build_roster(output_path=Path('/out'))` 傳目錄，讓 `_output_filename` 派生標準檔名，回傳值的 `.name` 即下載檔名。
- **費率即時重算**：預覽金額＝JS 端 `班數 × 費率欄位值`；只有按「下載」才重跑 Python（`build_roster` 吃 `rates`）。
- **維護 SOP**（規則演化時）：改 `src/` → `pytest` → `node scripts/test_wasm.mjs` → `python scripts/build_webapp.py` → Netlify 部署。

---

## 開發順序

1. Task 3.1（build 腳本先行，產出 dist 供後續所有測試）
2. Task 3.2 ＋ 3.4（橋接與 WASM 測試，先於 UI 拿到綠燈）
3. Task 3.3（UI）
4. Task 3.5 → 3.6（驗收、部署、文件）

---

## 完成後

更新 `CLAUDE.md`：
- 當前狀態 → Sprint 03 已完成（網頁版網址、維護 SOP 位置）
- 新增 Sprint 03 接力摘要（完成、未完成、下次接力重點、關鍵決策）
