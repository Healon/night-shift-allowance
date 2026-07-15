# 夜班費清冊產生器：靜態網頁化（Pyodide）設計文件

> 日期：2026-07-15
> 狀態：**已核可**（Lin 於 2026-07-15 brainstorming 對談中逐項確認）
> 前置文件：`SPEC.md`（核心功能規格）、`DECISION_LOG.md`（D001~D017 業務規則）
> 本文件範圍：部署形態改造（本機 uvicorn 改為公開網址的靜態網頁）。業務規則、計算邏輯完全不變。

---

## 1. 背景、目標與非目標

### 1.1 現況與痛點

現行系統為本機執行：`uvicorn web.app:app` 起 FastAPI，瀏覽器連 localhost 使用。Lin 確認的三項痛點：

1. **要給其他護理長用**：多病房各自上傳自己的排班表（11504 已出現 N03、N04、N05 多病房檔案）。
2. **不綁定開發機**：任何電腦開瀏覽器就能用，不用裝 Python。
3. **不依賴個人電腦開機**：隨時在線的網址，開發機關機也能用。

### 1.2 目標

一個永遠在線的網址，護理長開瀏覽器、拖入排班表、預覽統計、下載清冊。零安裝、零帳號、多人同時各自使用。

### 1.3 非目標（Lin 於需求釐清時明確排除）

- **不做**帳號與存取控制：網址不對外公告，工具本身不含資料，知道網址即可使用。
- **不做**歷史紀錄：無伺服器端儲存需求。
- **不做** GAS 改寫（決策理由見第 2 節）。
- 手機非主要場景：版面響應式可用即可，運算效能不為手機最佳化。

### 1.4 需求釐清時確認的環境事實

- 院方可接受行政資料上第三方雲端（因此本設計的「資料不出瀏覽器」是加分而非硬約束）。
- 院內工作電腦可連外部網站。
- 清冊格式為院內自訂，可修正調整（格式保真為軟約束；本方案實際上完全保真）。

---

## 2. 方案決策

| 面向 | **B 靜態＋Pyodide（採用）** | A GAS | C 雲端主機跑 FastAPI |
|---|---|---|---|
| 改寫成本 | 近零 | parser、classifier、builder 全部重寫為 JS | 零 |
| 規則月月演化的維護 | 現有 Python＋pytest 流程不變 | JS 雙軌維護、測試基礎薄弱 | 現有流程不變 |
| 排班表資料落點 | 不離開使用者瀏覽器 | Google 雲端 | 第三方主機 |
| 永遠在線 | 是（靜態託管無休眠） | 是 | 免費層休眠、冷啟動約一分鐘 |
| 格式保真 | openpyxl 原樣輸出，零漂移 | xlsx 轉 Sheets 再轉回，會漂移 | 原樣輸出 |
| 費用 | 0 | 0 | 0（休眠）或月費 |

**選 B 的決定性理由**：DECISION_LOG 顯示 classifier 三個月內演化六次（D012~D017），未來必有 D018。方案 B 是唯一「規則維護流程與今天完全相同」的網頁化路徑；106 條測試與整套開發流程原樣保留。

**GAS 出局理由**：Lin 已確認不需要帳號、不需要伺服器端儲存，GAS 僅存的優勢（伺服器端能力）無用武之地，剩下全是重寫與雙軌維護成本。

**方案 C 定位**：退路。若靜態方案在院內實測遇到不可解的瀏覽器或政策問題，現有 FastAPI 可零改寫上雲。

---

## 3. PoC 證據（2026-07-15 實測）

以 Node 版 Pyodide（與瀏覽器同一 WASM 引擎）掛載現有程式實跑，**一行程式碼未改**：

| 驗證項目 | 結果 |
|---|---|
| 端到端（11503 fixture） | 23 人，E_full 80、E_half 12、N_full 88、N_half 0，總額 NT$ 87,200，與驗收基準一致 |
| 產出檔完整性 | 標題含「(3月)」、`F4="=E4*400"`、`Q4="=SUM(F4:F13)"`、396 個合併儲存格 |
| 測試套件 | parser 9＋classifier 74＋builder 14 = **97/97 綠**，3.8 秒 |
| 執行環境 | WASM 內 Python 3.14.2、pandas 3.0.2（比本機開發環境新，全綠，相容餘裕充足） |
| 傳輸量（gzip 實測） | 核心約 6.2MB；pandas＋numpy 約 6.9MB；openpyxl＋xlrd 約 0.35MB；**合計約 14MB**。去 pandas 可壓至約 6.6MB |
| 運算耗時 | pipeline 約 2 秒（桌機） |

PoC 腳本位於 session scratchpad（`poc.mjs`、`fetch-dist.mjs`），實作階段收編為 `scripts/test_wasm.mjs`。

---

## 4. 架構

### 4.1 總覽

純靜態網站，零伺服器、零資料庫。頁面載入 Pyodide（WebAssembly 版 CPython）後，現有 `src/` 三模組在**使用者瀏覽器內**原樣執行。排班表全程不離開使用者電腦；託管平台只負責遞送程式資產。運算跑在 Web Worker，主執行緒介面不卡頓。

```
使用者瀏覽器
├─ index.html + app.js（UI：上傳、進度、預覽表、費率欄、下載鍵）
└─ worker.js（Web Worker）
    └─ Pyodide 引擎（vendor/ 自帶）
        ├─ src/parser.py     ← 原樣
        ├─ src/classifier.py ← 原樣
        ├─ src/builder.py    ← 原樣
        └─ 範本 xlsx（vendor/ 自帶）
```

### 4.2 目錄結構（新增部分）

```
webapp/                 # 前端原始碼（進 git）
├── index.html          # 單頁 UI，沿用現行 web/templates/index.html 的拖放體驗
├── app.js              # 主執行緒：UI 狀態機、與 worker 通訊
└── worker.js           # 載入 pyodide、掛載 src 與範本、執行 pipeline
dist/                   # 建置產物（不進 git；部署上傳的就是它）
├── （webapp/ 靜態檔複製）
└── vendor/
    ├── pyodide/        # 核心（pyodide.asm.wasm、stdlib、lock 等）
    ├── wheels/         # pandas、numpy、openpyxl、xlrd 等 wheel
    ├── src.zip         # src/*.py 打包
    └── template.xlsx   # 清冊範本（改英文檔名避免 URL 編碼問題；builder 吃參數，與檔名無關）
scripts/
├── build_webapp.py     # 組裝 dist：抓齊 vendor、注入版本號、白名單檢查
└── test_wasm.mjs       # WASM 冒煙測試（97 條核心測試＋87,200 基線）
```

### 4.3 資料流

1. 開頁：worker 依序載入 pyodide 核心、wheels、`src.zip`、範本，主頁顯示分階段進度；完成後開放上傳區。
2. 使用者拖放 `.xls`/`.xlsx`：File 讀成 bytes 傳入 worker，寫入 WASM 虛擬檔案系統。
3. worker 跑 `parse_schedule` 與 `classify_shifts`，回傳統計 JSON（各人 E_full、E_half、N_full 班數與日期）。
4. 主頁渲染**統計預覽表**：各人班數、金額、全月總額。金額 = 班數 × 費率，在 JS 端以目前費率欄位值計算，**費率調整即時重算不需重跑 Python**。
5. 使用者按「下載清冊」：worker 以目前費率呼叫 `build_roster(schedule, counts, template, output, rates)`，讀回 bytes，主頁以 Blob 觸發下載。檔名沿用現行規則（含中文；瀏覽器 download 屬性原生支援，無 Content-Disposition 編碼問題）。
6. 同一次 parse 結果供預覽與產檔共用；重新拖檔即重跑。

### 4.4 資產自託管與版本釘死（關鍵決策）

Pyodide 核心、全部 wheels、src、範本**全部隨站自帶，執行期零外部請求**（不連 CDN、不連 PyPI）。理由：

1. 院方未來若封鎖外部 CDN，本站不受影響。
2. 版本永久釘死。杜絕「重新部署默默升版」（LESSONS L-2026-07-11-002、L-2026-07-11-005 的教訓）；升級 Pyodide 或套件是顯式動作，必過 `test_wasm.mjs` 才部署。

### 4.5 費率調整

預覽區四欄位，預設 `RATES`（400/200/600/300）。改動即時反映預覽金額；產檔時傳入 `build_roster` 既有的 `rates` 參數，F 欄公式隨之改變。僅影響本次產出，不持久化。

### 4.6 錯誤處理

沿用現行 `web/app.py` 的白話分級語意：

| 情境 | 行為 |
|---|---|
| 副檔名非 .xls/.xlsx | 立即提示，不進 worker |
| parser `ValueError` | 顯示 parser 的具體白話訊息（如格式不符指引） |
| 其他例外 | 顯示訊息並標註「請確認 Excel 檔案」，不暴露 traceback |
| 瀏覽器不支援 WASM／過舊 | 開頁偵測，顯示明確說明與最低版本需求（以所釘 Pyodide 版本的官方支援矩陣為準，實作時載明） |
| worker 崩潰 | catch-all 提示重新整理頁面（唯一需要重新整理的情境） |

除 worker 崩潰外，任何錯誤後頁面可直接重試，不需重新整理（載入好的引擎不受影響）。

### 4.7 資安與隱私

- 排班表資料不離開使用者瀏覽器，頁面上明文聲明此事。
- `dist` **禁止**含 `tests/fixtures`（真實姓名）與任何個資檔案；`build_webapp.py` 內建部署清單檢查，比對白名單才放行。
- repo 維持私有；Netlify 只收 dist。
- 頁腳顯示版本號（git short hash＋build 日期），使用者可回報版本、確認用到新版。

---

## 5. 維護與更新流程

規則演化（例如未來 D018）的 SOP，前三步與今天完全相同：

1. 改 `src/classifier.py` 等，補測試。
2. `pytest` 本機全綠。
3. `node scripts/test_wasm.mjs` WASM 全綠（防「本機綠、瀏覽器炸」）。
4. `python scripts/build_webapp.py` 產 dist。
5. Netlify 部署（一條指令）。

現有 `web/`（FastAPI）與 CLI 入口**保留不動**：本機開發、測試與備援用途。

---

## 6. 驗收條件（AC）

- **AC1**：`python scripts/build_webapp.py` 成功產出 dist，且 dist 檔案清單通過白名單檢查（不含 fixtures、不含任何含真實姓名的檔案）。
- **AC2**：`node scripts/test_wasm.mjs` 於 WASM 環境跑 parser／classifier／builder 共 97 條測試全綠，且 11503 端到端總額 = 87,200。
- **AC3**：真瀏覽器手動驗收：上傳 `11503-N19W01排班表.xls`，預覽顯示 23 人、總額 87,200；下載檔以 openpyxl 檢核與現行 CLI 產出等值（人數區塊、公式、合併儲存格、標題）。
- **AC4**：DevTools Network 檢視：頁面載入與操作全程僅同源請求，零外部網域請求。
- **AC5**：費率欄改 500 後，預覽金額即時重算，產出檔 F 欄公式為 `=E{r}*500`。
- **AC6**：錯誤路徑：上傳非 Excel 檔顯示白話訊息，頁面不需重新整理即可再次上傳正確檔案。
- **AC7**：部署後從非開發機（他台電腦或手機）開啟公開網址，完成一次上傳到下載的完整流程。

---

## 7. 風險與退路

| 風險 | 對策 |
|---|---|
| 院內瀏覽器過舊或政策擋 WASM | 開頁偵測與明確訊息；退路為方案 C（FastAPI 上雲），零改寫可走 |
| 首次載入約 14MB，院內網速慢時等待久 | 分階段進度條管理預期；v1.1 去 pandas 可壓至約 6.6MB |
| 範本改版 | 換範本檔重新 build 部署，流程與現行相同 |
| 未知班別代碼靜默略過 | 與現行行為一致；v1.1 於預覽加警告（需 classifier 小改） |
| Netlify 免費方案政策變動 | 純靜態資產無平台綁定，dist 可原樣搬至 Cloudflare Pages 等任何靜態託管 |

---

## 8. 本次決策記錄

| 決策 | 內容 | 決策者與日期 |
|---|---|---|
| 部署形態 | 方案 B：靜態網頁＋Pyodide | Lin，2026-07-15 |
| 部署平台 | Netlify（工具鏈已接入；repo 私有、dist-only 上傳） | Lin，2026-07-15 |
| pandas 去留 | v1 保留（零改動優先）；瘦身列 v1.1 | Lin，2026-07-15 |
| 存取控制 | 不做（網址不公告；工具無資料，風險可接受） | Lin，2026-07-15 |
| 歷史紀錄 | 不做（無伺服器端儲存） | Lin，2026-07-15 |
| 資產策略 | 全自託管、版本釘死、執行期零外部請求 | 設計決策，Lin 核可 |

## 9. v1.1 候選（不在本次範圍）

- 去 pandas 瘦身：parser 改 xlrd 直讀，首載約 14MB 降至約 6.6MB（既有 9 條 parser 測試保護）。
- 未知班別代碼警告：統計預覽列出被略過的未知代碼，護理長可即時發現漏算（對應 SPEC Sprint 03 待辦）。
