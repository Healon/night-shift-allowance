# CLAUDE.md

> 此檔案供 Claude Code 在此專案中作為跨 session 的長期記憶。
> 開工前請先完整讀過 `SPEC.md` 與本檔。

---

## 專案一句話

護理長上傳**當月排班表 Excel**，系統**自動產出**符合衛福部格式的**夜班獎勵人員清冊 Excel**。

---

## 工作流程（六步法）

依照 Lin 既有的 Claude Code 工作流：

1. **Brainstorm**：先讀 `SPEC.md`、`DECISION_LOG.md`，寫下對需求的理解與疑問
2. **Plan**：列出 Sprint 任務分解（已有 Sprint 01~03 建議）
3. **Implement**：先寫測試、再寫實作，一次只改一個模組
4. **Review 1**：自己檢查程式碼品質（命名、抽象、錯誤處理）
5. **Review 2**：重讀 SPEC 確認功能齊全、端到端驗收測試通過
6. **Report**：更新本檔的「目前進度」區塊

---

## 當前狀態

- **Sprint**：03 已完成（2026-07-15）— 靜態網頁上線
- **網頁版**：<https://night-shift-roster.netlify.app>（Netlify site id `ea169e5c-d053-4f7c-b1de-96b5450feaf8`）
- **下一步**：無進行中 Sprint。v1.1 候選 — 去 pandas 瘦身、未知班別代碼警告
- **維護 SOP**：見 README「維護 SOP」節（改 src → pytest → test_wasm → build → test_browser → deploy）
- **已驗證基線**：
  - 11501 / 115年1月 → NT$ 88,200
  - 11502 / 115年2月 → NT$ 70,400
  - 11503 / 115年3月 → NT$ 87,200
  - 11504 / 115年4月 → NT$ 39,800（含 D012 JD + D013 ED 規則；D014 HD / D015 ND 引入後總額不變，因 N18W01 該月無 HD/ND 出現）
- **端到端（CLI）**：`python -m src.main tests/fixtures/11503-N19W01排班表.xls`
- **端到端（本機 Web）**：`uvicorn web.app:app --port 8000` → `http://localhost:8000` 拖放排班表自動下載
- **端到端（網頁版）**：`node scripts/test_browser.mjs [網址]`（省略網址則自動起本機 dist 伺服器）
- **測試**：本機 pytest 106/106 綠（parser 9 / classifier 74 / builder 14 / web 9）；WASM 97/97 綠（`node scripts/test_wasm.mjs`，不含 web 那 9 條 FastAPI 測試）

---

## 絕對不要做的事

1. **不要硬編碼費率**：費率寫在 F 欄公式，不要在 Python 端先乘好再寫入儲存格
2. **不要用 `data_only=True` 開啟後再存檔**：會把所有公式變成死值，永久遺失
3. **不要從零建立清冊 Excel**：一定要**以範本為基底**，保留原有樣式與合併儲存格
4. **不要只處理有夜班的人**：**全部人員都要列入**，班數為 0 也要
5. **不要忽略 `*;N` / `N;*` 的前後綴變體**：`休;N`、`國;N`、`N;休`、`N;國` 都算大夜整班；`休;E`、`國;E`、`E;休`、`E;國` 都算小夜整班（D011）；`JD`、`休;JD`、`國;JD`、`JD;休`、`JD;國` 都**無條件**算小夜半班（D012）；`ED`、`休;ED`、`國;ED`、`ED;休`、`ED;國` 都**無條件**算小夜半班（D013）
6. **不要忽略 HD / ND**：`HD`（含 `休;HD`、`國;HD`、`HD;休`、`HD;國`）**無條件**算小夜半班（D014）；`ND`（含 `休;ND`、`國;ND`、`ND;休`、`ND;國`）**當日**算小夜半班、**隔日**算大夜整班（D015）；月底 ND 因 day+1 已超出本月，本月清冊**不外溢**到下個月
7. **不要把 `E(請)` 一律算半班**：必須先檢查**下方一列同欄**是否有 `21:00~24:00`、`20:00~24:00` 或 `16:00~20:00` 任一字串（D017）；都沒有代表整班沒上，不計入
8. **不要忽略大夜整班的 `00:00~08:00` 標記**：`N`/`休;N`/`國;N` 若下方同欄有 `00:00~08:00` 代表整班請假，**不列入計算**
9. **不要忽略小夜整班的 `16:00~24:00` 標記**：`E`/`休;E`/`國;E`/`E;休`/`E;國` 若下方同欄有 `16:00~24:00` 代表整班請假，**不列入計算**（D016）
10. **不要讓 `insert_rows` 自己處理合併儲存格**：會殘留異常，必須主動清理
11. **不要把 `dist/` 的資產改成從 CDN 抓**：執行期必須零外部請求（院方封鎖 CDN 也要能用），`scripts/test_browser.mjs` 的同源稽核會擋
12. **不要把 `scripts/build_webapp.py` 的版本釘點改成浮動**（`latest`、`>=`）：會重演 LESSONS L-2026-07-11-002／005 的「重新部署默默升版」漂移。升級是顯式動作，升完必跑 `node scripts/test_wasm.mjs`
13. **不要讓 `tests/fixtures`（含真實姓名）進 `dist/`**：build 腳本有白名單檢查，不要為了方便繞過它

---

## 關鍵業務規則速查

### 班別代碼分類

```python
# 注意：實際 classifier 為 day-by-day iter（src/classifier.py），
# 下方為單格規則速查；ND 跨日邏輯靠呼叫端維護 nd_carryover_days set
def classify(code: str, below_note: str) -> tuple[str | None, int]:
    if code in ('N', '休;N', '國;N', 'N;休', 'N;國'):
        if '00:00~08:00' in (below_note or ''):
            return (None, 0)  # 整班請假不計
        return ('N_full', 1)
    if code in ('E', '休;E', '國;E', 'E;休', 'E;國'):
        # D016：整班請假（下列標 16:00~24:00）→ 不計
        if '16:00~24:00' in (below_note or ''):
            return (None, 0)
        return ('E_full', 1)
    if code == 'E(請)':
        # D017：三個半班 marker 任一命中即 E_half
        if any(m in (below_note or '') for m in ('21:00~24:00', '20:00~24:00', '16:00~20:00')):
            return ('E_half', 1)
        return (None, 0)
    if code in ('JD', '休;JD', '國;JD', 'JD;休', 'JD;國'):
        return ('E_half', 1)  # D012：JD 班 09-13/17-21，後段 4 小時屬小夜半
    if code in ('ED', '休;ED', '國;ED', 'ED;休', 'ED;國'):
        return ('E_half', 1)  # D013：ED 班 08-12/16-20，後段 4 小時屬小夜半
    if code in ('HD', '休;HD', '國;HD', 'HD;休', 'HD;國'):
        return ('E_half', 1)  # D014：HD 車班 08-20，17-20 屬小夜時段
    if code in ('ND', '休;ND', '國;ND', 'ND;休', 'ND;國'):
        # D015：當日小夜半 + 隔日大夜整；隔日 N_full 須由呼叫端透過
        # nd_carryover_days set 在 day+1 補上，月底自然不外溢
        return ('E_half', 1)
    return (None, 0)
```

### 費率

```python
RATES = {
    'E_full': 400,   # 小夜整班
    'E_half': 200,   # 小夜半班
    'N_full': 600,   # 大夜整班
    'N_half': 300,   # 大夜半班（目前全 0）
}
```

### 範本結構（每人 10 列）

| 相對列 | D 欄 | E 欄公式 | F 欄公式 |
|---:|---|---|---|
| +0 | 小夜 | `=COUNT(G{r}:P{r+2})` | `=E{r}*400` |
| +3 | 小夜半 | `=COUNT(G{r+3}:P{r+4})` | `=E{r+3}*200` |
| +5 | 大夜 | `=COUNT(G{r+5}:P{r+7})` | `=E{r+5}*600` |
| +8 | 大夜半 | `=COUNT(G{r+8}:P{r+9})` | `=E{r+8}*300` |

第 N 位人員起始列 = `4 + (N-1) × 10`

---

## 排班表結構速查

```
col 4: 員工編號（如 CNU80500401）
col 5: 姓名
col 7~37: 日期 1~31 的班別代碼

row 0: [年, '年', 月, '月', '排班表', '－', 病房名稱]
row 1: 表頭
row 2: 星期列
row 3, 5, 7, 9, ...: 人員的主班別列
row 4, 6, 8, 10, ...: 對應人員的補休備註列
```

**`21:00~24:00` 字串只會出現在偶數 row（補休備註列）**，代表「補假 3 小時 21:00~24:00」，是判斷小夜半班的關鍵。

---

## 測試驗收基準

用 `tests/fixtures/11503-N19W01排班表.xls` 跑端到端，以下為標準答案：

| 姓名 | 小夜 | 小夜半 | 大夜 | 總額 |
|---|---:|---:|---:|---:|
| 陳淑靜 | 0 | 0 | 1 | 600 |
| 陳芳瑜 | 2 | 1 | 3 | 2,800 |
| 蕭雅慧 | 0 | 0 | 18 | 10,800 |
| 陳佩君 | 0 | 0 | 0 | 0 |
| 莊淨雅 | 0 | 0 | 17 | 10,200 |
| 曾郁翎 | 0 | 0 | 7 | 4,200 |
| 蘇心柔 | 14 | 2 | 4 | 8,400 |
| 丁煒哲 | 15 | 0 | 4 | 8,400 |
| 何語馨 | 14 | 3 | 3 | 8,000 |
| 陳資晴 | 4 | 0 | 0 | 1,600 |
| 黃崴 | 1 | 1 | 18 | 11,400 |
| 莊雅婷 | 0 | 0 | 0 | 0 |
| 邱子桓 | 1 | 0 | 3 | 2,200 |
| 劉芳榕 | 15 | 2 | 3 | 8,200 |
| 葉子瑜 | 14 | 3 | 1 | 6,800 |
| 卓玲 | 0 | 0 | 0 | 0 |
| 陳緯 | 0 | 0 | 5 | 3,000 |
| 陳庭逸 | 0 | 0 | 0 | 0 |
| 丁麗美 | 0 | 0 | 0 | 0 |
| 陳秀怡 | 0 | 0 | 0 | 0 |
| 韓譯賢 | 0 | 0 | 1 | 600 |
| 邱漢珍 | 0 | 0 | 0 | 0 |
| 林仲康 | 0 | 0 | 0 | 0 |

**合計**：
- 小夜整班 80、小夜半 12、大夜整班 88、大夜半 0
- 小夜費 32,000 + 小夜半費 2,400 + 大夜費 52,800 = **NT$ 87,200**

---

## 技術棧建議

- Python 3.10+
- `pandas` + `xlrd` 讀 .xls、`openpyxl` 讀寫 .xlsx
- `fastapi` + `uvicorn` 作 Web UI
- `pytest` 測試
- `ruff` lint、`mypy` 型別檢查（可選）

---

## 檔案清單

- `SPEC.md` — 完整需求與技術規格
- `CLAUDE.md` — 本檔（工作指南）
- `DECISION_LOG.md` — 決策記錄（班別規則、費率確認）
- `docs/superpowers/specs/2026-07-15-web-static-pyodide-design.md` — 網頁版部署設計（AC1~AC7）
- `src/` — 計算核心（CLI／本機 Web／網頁版三者共用）
- `webapp/` — 網頁版前端與 `bridge.py`；`scripts/build_webapp.py` 組成 `dist/` 部署
- `tests/fixtures/11503-N19W01排班表.xls` — 測試用排班表
- `templates/衛生福利部夜班津貼示範.xlsx` — 清冊範本
- `samples/SAMPLE_OUTPUT.xlsx` — 驗證過的產出範例

---

## 對話接力摘要模板

在每個 Sprint 結束前，請在此檔**新增**以下區塊：

```markdown
## Sprint 0X 接力摘要（YYYY-MM-DD）

**完成**：
- ...

**未完成**：
- ...

**下次接力重點**：
- ...

**關鍵決策**：
- ...
```

---

## Sprint 01 接力摘要（2026-04-17）

**完成**：
- 專案骨架：`src/`（config、parser、classifier、builder、main）、`tests/`、`requirements.txt`、`output/`
- TDD 完成三核心模組，46/46 測試綠：
  - `test_parser.py` 7 題（metadata、23 人、蕭雅慧 18 大夜、陳芳瑜 codes/notes、12 個 `21:00~24:00` 標記）
  - `test_classifier.py` 28 題（含 17 個「不算」雜項代碼 parametrize + 整合基準表驗證）
  - `test_builder.py` 11 題（輸出檔命名、表頭、23 人區塊公式、費率覆寫、SUMIF 範圍、合併儲存格、模擬重算 = 87,200）
- 端到端：`python -m src.main tests/fixtures/11503-N19W01排班表.xls` → `11503-N19W01_夜班費清冊_11病房.xlsx`，模擬重算總額 **NT$ 87,200**

**未完成**：
- Sprint 02（FastAPI Web UI）尚未開始
- Sprint 03（錯誤訊息白話化、RWD、部署文件）尚未開始
- 開發機器無 LibreOffice，未用 `soffice --calc` 實際重算；測試內以模擬計算替代

**下次接力重點**：
- Sprint 02 起點：沿用 `src/main.py` 的 `parse → classify → build_roster` 三步鏈，包成 `POST /upload` 回傳 FileResponse
- `build_roster()` 的 `output_path` 參數若傳 `.xlsx` 完整路徑會直接存檔，方便與 `tempfile.NamedTemporaryFile` 整合
- 需注意中文檔名 `Content-Disposition` URL encode

**關鍵決策**：
- **解決 insert_rows 殘留合併** ([src/builder.py:124](src/builder.py)) 採「直接重建 `ws.merged_cells.ranges` 串列」而非逐個 unmerge（openpyxl 對重複 range 的 unmerge 會拋 KeyError）
- **費率覆寫時機**：在清空 22 人原始資料後立即覆寫全部 F 欄公式（`_reset_template_blocks`），新插入人員也共用 `_set_block_formulas()`，確保 400/200/600/300 一致
- **民國年換算**：`calendar.monthrange(year + 1911, month)` 得到當月天數，於 parser 限制只取到 `day=days_in_month`，避免 4/6/9/11 月讀進空欄
- **身分證欄**照 DECISION_LOG D004 留空；`C` 欄清空後由人工填寫

---

## Sprint 02 接力摘要（2026-04-17）

**完成**：
- `web/app.py` — FastAPI app，三個路由：`GET /`（回 HTML）、`GET /health`、`POST /upload`（驗副檔名 → tempfile 暫存 → parse/classify/build → `FileResponse`）
- `web/templates/index.html` — 單檔前端（純 HTML + CSS + 原生 JS，無外部套件），拖放 / 點擊上傳、loading spinner、成功/失敗訊息、RWD
- `tests/test_web.py` — 9 題 FastAPI `TestClient` E2E：首頁、健康檢查、三個月份上傳比對 88,200 / 70,400 / 87,200、副檔名錯誤、壞檔、缺檔
- 測試總數 55 → **64/64 綠**
- `requirements.txt` 追加 fastapi、uvicorn[standard]、python-multipart、httpx（TestClient 依賴）
- 手動端到端：`uvicorn web.app:app --port 8765` 跑真伺服器，`curl` 三個月份都下載到正確 xlsx、錯誤訊息為白話中文
- README.md、CLAUDE.md 同步更新

**未完成**：
- Sprint 03（身分驗證、Docker、歷史紀錄、費率 UI）
- `output/` 資料夾累積產出檔的清理機制（目前需人工刪）
- 行動裝置的實機測試（iPhone Safari）尚未由 Lin 驗過

**下次接力重點**：
- Sprint 03 起點：目前 `web/app.py` 的 `upload` endpoint 是無狀態、可並發，可作為後續加驗證/紀錄層的掛載點
- 若要部署成常駐服務，先用 `systemd --user` 或 `launchd`（Mac），再討論 Docker
- 若未來要讓 `/upload` 回傳 JSON 統計預覽（先看總額再決定是否下載），可改為回 `{total, breakdown, download_url}`，builder 已支援 output_path 任意路徑

**關鍵決策**：
- **前端零依賴**（純原生 HTML/CSS/JS）— 維護最低、任何瀏覽器直接能跑；若未來 UI 複雜度爆炸再考慮 HTMX
- **檔名保留原始輸入**（tempfile 用 `mkdtemp` + 原檔名複製）— 因為 `parse_schedule` 從檔名 stem 擷取 ward_code（`11503-N19W01` 格式），不能被 tempfile 的隨機檔名蓋掉
- **錯誤訊息分級**：副檔名錯 → 400 固定訊息；`ValueError` → 400 包含 parser 具體訊息；其他 Exception → 400 包含訊息但標註「請確認 Excel」，避免暴露 traceback
- **`TestClient` 需要 httpx**（FastAPI 0.110+），已加入 requirements 避免跑 pytest 時缺依賴

---

## Sprint 03 接力摘要（2026-07-15）

**完成**：
- **靜態網頁上線**：<https://night-shift-roster.netlify.app>，Pyodide（WASM 版 CPython）在使用者瀏覽器內跑**同一份 `src/`**，計算程式零修改
- `scripts/build_webapp.py` — 組裝 `dist/`：釘死 Pyodide 314.0.2 與所有 wheel（sha256 驗證）、把 openpyxl／et_xmlfile 補進 vendored lockfile、產 `src.zip`＋`version.json`、dist 白名單檢查
- `webapp/` — `bridge.py`（JSON 介面）＋ module worker ＋ 前端（分階段載入進度、統計預覽表、費率即時重算、Blob 下載）
- `scripts/test_wasm.mjs` — 用 **dist 實體資產**跑 97 條 pytest ＋出貨版 bridge 端到端（87,200）
- `scripts/test_browser.mjs` — 無頭 Chromium 驗收：預覽、費率改 500、下載檔公式、錯誤路徑、**全程同源稽核**；可帶網址測線上站台
- 設計文件 `docs/superpowers/specs/2026-07-15-web-static-pyodide-design.md`（AC1~AC7 全數通過，AC7 待 Lin 在非開發機人工確認）
- 實測（線上）：冷啟動就緒 10.4 秒、快取後 3.0 秒、傳輸約 13.5MB、解析加預覽 0.1 秒

**未完成**：
- **AC7 人工驗收**：Lin 在非開發機（院內電腦或手機）實跑一次上傳到下載
- v1.1 候選：去 pandas 瘦身（13.5MB → 約 6.6MB）、未知班別代碼警告
- repo 仍為 local-only，無 git remote（雙機同步與備份待辦）

**下次接力重點**：
- 規則變更（D018）走 README「維護 SOP」六步，網頁版與 CLI 共用 `src/`，改一次同步生效
- 升級 Pyodide 或套件版本前先看 `scripts/build_webapp.py` 頂端釘版常數，升完必跑 `test_wasm.mjs`
- 部署指令：`netlify deploy --dir dist --site ea169e5c-d053-4f7c-b1de-96b5450feaf8 --prod --no-build`（本機 Netlify CLI 已登入）

**關鍵決策**：
- **不採 GAS**：Lin 確認不需帳號與歷史紀錄後，GAS 的伺服器端優勢無用武之地，只剩「三模組全部重寫 JS＋74 條 classifier 測試重建＋規則月月演化雙軌維護」的成本。Pyodide 路線讓 `src/` 零修改（DECISION_LOG 三個月改六次，這是決定性理由）
- **資產全自託管、版本釘死、執行期零外部請求**：院方若封鎖 CDN 不受影響；杜絕 LESSONS L-2026-07-11-002／005 的「重新部署默默升版」漂移
- **module worker**：Pyodide 314 已移除 classic worker（`importScripts`）支援，worker 必須是 `type: 'module'`＋`import { loadPyodide } from './vendor/pyodide/pyodide.mjs'`
- **Netlify MCP 的 deploy 代理不能用**（14MB 上傳一律 400，疑似函式 payload 上限），改用**本機已登入的 Netlify CLI** 直接部署
- **`test_wasm.mjs` 的 openpyxl／et_xmlfile 走 `micropip emfs:` 裝 dist 實體 wheel**：Node 版 loader 不從 `indexURL` 取 lockfile 之外的 wheel（瀏覽器才走該路徑，已由 `test_browser.mjs` 實證），但仍確保測到的就是出貨的那份 bytes

