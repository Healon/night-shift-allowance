# 夜班費清冊產生器

讓護理長上傳排班表 Excel 後，自動產出符合衛福部格式的夜班獎勵人員清冊。

**網頁版（推薦，免安裝）**：<https://night-shift-roster.netlify.app>

---

## 目前狀態

**已上線**。Sprint 01（CLI）、02（本機 Web UI）、03（靜態網頁部署）皆已完成。

- 網頁版全程在使用者瀏覽器內運算，**排班表不會上傳到任何伺服器**
- 四個月份基線通過：11501 → 88,200、11502 → 70,400、11503 → 87,200、11504 → 40,000
- 測試：本機 pytest 111 條、WASM 環境 102 條、瀏覽器端到端驗收（本機與線上）皆綠

---

## 文件閱讀順序

1. **`README.md`**（本檔）— 專案總覽與使用方式
2. **`CLAUDE.md`** — Claude Code 工作指南（含絕對不要做的事、規則速查、測試驗收基準）
3. **`SPEC.md`** — 完整需求與技術規格
4. **`DECISION_LOG.md`** — 業務規則決策記錄（D001~D018）
5. **`docs/superpowers/specs/2026-07-15-web-static-pyodide-design.md`** — 網頁版部署設計
6. **`SPRINT_03.md`** — 最近一次 Sprint 任務清單

---

## 專案檔案結構

```
night-shift-allowance/
├── README.md                                  ← 你在這裡
├── CLAUDE.md                                  ← Claude Code 長期記憶
├── SPEC.md / DECISION_LOG.md                  ← 規格與決策記錄
├── SPRINT_01.md / SPRINT_03.md                ← Sprint 任務清單
├── docs/superpowers/specs/                    ← 設計文件
├── src/                                       ← 計算核心（CLI、本機 Web、網頁版共用）
│   ├── parser.py / classifier.py / builder.py / config.py / main.py
├── web/                                       ← 本機版 FastAPI（開發與備援用）
├── webapp/                                    ← 網頁版前端（index.html / app.js / worker.js / bridge.py）
├── scripts/
│   ├── build_webapp.py                        ← 組裝 dist（釘版、自託管、白名單檢查）
│   ├── test_wasm.mjs                          ← WASM 冒煙測試
│   ├── test_browser.mjs                       ← 瀏覽器驗收（本機或線上）
│   └── serve_dist.mjs                         ← 本機靜態伺服器
├── templates/
│   └── 衛生福利部夜班津貼示範.xlsx                ← 清冊範本
├── tests/                                     ← pytest（含 fixtures，含真實姓名，不對外發布）
└── dist/                                      ← 建置產物（不進 git，部署上傳的就是它）
```

---

## 使用情境流程

```
[ 護理長 ]
    │
    │ 1. 開啟 https://night-shift-roster.netlify.app
    │ 2. 拖放排班表 Excel 到網頁上
    │
    ▼
[ 瀏覽器內運算（資料不外傳） ]
    │
    │ 1. 讀取排班表
    │ 2. 統計每人大夜/小夜班數 → 顯示預覽表與總額
    │ 3. 以範本為基底產出清冊 Excel
    │
    ▼
[ 護理長 ]
    │
    │ 4. 核對預覽（必要時調整費率）→ 按下載
    │ 5. 手動填入身分證字號、填表人、電話（留空部分）
    │ 6. 交給會計請款
```

---

## 使用方式

### 方法一：網頁版（推薦，給所有護理長）

開 <https://night-shift-roster.netlify.app> 即可，免安裝、免帳號。

- 首次開啟需下載計算引擎（約 13.5MB，實測約 10 秒），之後瀏覽器快取，再開約 3 秒
- 排班表全程留在自己電腦，不上傳
- 需近三年內的 Chrome、Edge 或 Safari

### 方法二：命令列（CLI）

```bash
pip install -r requirements.txt
python -m src.main tests/fixtures/11503-N19W01排班表.xls
# 產出 output/11503-N19W01_夜班費清冊_11病房.xlsx
```

### 方法三：本機 FastAPI（開發與備援）

```bash
uvicorn web.app:app --port 8000     # 瀏覽器打開 http://localhost:8000
```

---

## 維護 SOP（規則變更時，例如新增 D018 班別代碼）

```bash
# 1. 改 src/classifier.py 等，補對應測試
.venv/bin/python -m pytest -q                 # 2. 本機測試全綠
node scripts/test_wasm.mjs                    # 3. WASM 環境全綠（防「本機綠、瀏覽器炸」）
python3 scripts/build_webapp.py               # 4. 重建 dist
node scripts/test_browser.mjs                 # 5. 本機瀏覽器驗收
netlify deploy --dir dist --site ea169e5c-d053-4f7c-b1de-96b5450feaf8 --prod --no-build
node scripts/test_browser.mjs https://night-shift-roster.netlify.app   # 6. 線上複驗
```

網頁版與 CLI **共用同一份 `src/`**，改一次規則三種用法同步生效。

**維護要點**：

- Pyodide 與各套件版本**釘死在 `scripts/build_webapp.py`**，升級是顯式動作，升完必跑 `test_wasm.mjs`
- 執行期**零外部請求**（引擎與套件全部自託管於 dist），`test_browser.mjs` 每次驗這條
- `dist/` 有白名單檢查，`tests/fixtures`（含真實姓名）**絕不會**被打包發布

---

## 驗收標準摘要

用 `tests/fixtures/11503-N19W01排班表.xls` 跑端到端，應產出：

- **23 位人員**全部列入清冊
- **單位**：11病房　**月份**：3月
- **小夜整班 80 × 400 = 32,000**
- **小夜半班 12 × 200 = 2,400**
- **大夜整班 88 × 600 = 52,800**
- **大夜半班 0 × 300 = 0**
- **總獎勵金額 = NT$ 87,200**

完整每人班數對照見 `CLAUDE.md` 驗收基準表。

---

## Sprint 歷程

- ✅ **Sprint 01**：CLI 端到端（三個月份驗證通過）
- ✅ **Sprint 02**：FastAPI Web UI（拖放上傳 + 自動下載）
- ✅ **Sprint 03**：靜態網頁部署（Pyodide 在瀏覽器內跑同一份 Python，公開網址、免安裝、資料不外傳）

**v1.1 候選**：去 pandas 瘦身（13.5MB → 約 6.6MB）、未知班別代碼警告。

---

## 聯絡與決策

所有規則變更請更新 `DECISION_LOG.md` 並註記決策者與日期。
