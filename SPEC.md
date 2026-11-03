# 夜班費清冊產生器 — 實作規格

> 給 Claude Code 的實作文件
> 版本：v1.0 · 日期：2026-04-17

---

## 1. 專案目的

讓護理長**上傳一份排班表 Excel**，系統**自動產出**符合衛福部格式的**夜班獎勵人員清冊** Excel，免去人工統計與填表。

**使用者**：護理長 / 護理行政人員（非工程背景）
**使用情境**：每月結束後，上傳該月排班表，下載清冊交給會計。

---

## 2. 功能範圍（v1.0）

### In-Scope
- 單月份、單一病房的排班表處理
- 從排班表統計：大夜整班、小夜整班、小夜半班
- 依費率計算夜班費
- 依範本樣式產出清冊 Excel（含樣式、邊框、合併儲存格、動態公式）

### Out-of-Scope（未來版本再考慮）
- 跨月份、多病房合併處理
- 大夜半班（目前規則未使用）
- 非 `N/E/D` 以外的院區班別代碼
- 使用者身分驗證
- 歷史紀錄保存

---

## 3. 輸入規格

### 3.1 排班表 Excel（.xls 或 .xlsx）

**檔名範例**：`11503-N19W01排班表.xls`
（`11503` = 115年3月、`N19W01` = 病房代碼）

**結構**：
- 第 1 個工作表即為排班資料
- **Row 0**（第 1 列）：`[年份, '年', 月份, '月', '排班表', '－', 病房名稱]`
  - 範例：`[115, '年', 3, '月', '排班表', '－', '11病房']`
- **Row 1**（第 2 列）：表頭（col 4 = `編號`、col 5 = `姓名`、col 7~37 = 日期 1~31）
- **Row 2**（第 3 列）：星期列（可忽略）
- **Row 3 起**：每位人員**佔 2 列**
  - 第 1 列（奇數 row）：主班別代碼（欄位 col 7~col 37，對應每月 1~31 日）
  - 第 2 列（偶數 row）：補休備註（含 `21:00~24:00` 等時間字串）
- **Col 4**：員工編號（如 `CNU80500401`）
- **Col 5**：姓名
- **Col 7~37**：日期 1~31 的班別代碼

> 若該月不足 31 天（2/4/6/9/11 月），col 37 以後可能為空，需容錯處理。

### 3.2 班別代碼規則

| 原始代碼 | 歸類 | 班數計算 |
|---|---|---:|
| `N` **且下方列同欄不含** `00:00~08:00` | 大夜整班 | 1 |
| `N` **且下方列同欄含** `00:00~08:00` | 不算（整班請假） | 0 |
| `休;N` / `N;休` **且下方列同欄不含** `00:00~08:00` | 大夜整班 | 1 |
| `休;N` / `N;休` **且下方列同欄含** `00:00~08:00` | 不算（整班請假） | 0 |
| `國;N` / `N;國` **且下方列同欄不含** `00:00~08:00` | 大夜整班 | 1 |
| `國;N` / `N;國` **且下方列同欄含** `00:00~08:00` | 不算（整班請假） | 0 |
| `E` | 小夜整班 | 1 |
| `休;E` / `E;休` | 小夜整班 | 1 |
| `國;E` / `E;國` | 小夜整班 | 1 |
| `E(請)` **且** 16:00–24:00 扣除下方請假時段後實際工時 ≥ 4 小時 | 小夜半班 | 0.5 |
| `E(請)` **且**實際工時 < 4 小時（或下方無請假時段） | 不算 | 0 |
| `N(請)`（含 `N( 請)`）**且** 00:00–08:00 扣除請假後實際工時 ≥ 4 小時 | 大夜半班 | 0.5 |
| `N(請)` **且**實際工時 < 4 小時（或下方無請假時段） | 不算 | 0 |
| `D`、`C`、`AD`、`DD`、`BE`、`AE`、`P8`、`8-12/1-5`、`U`、`國`、`休`、`例`、`請`、`08/請`、`休;D`、`休;BE`、`休;AD` 等 | 不算 | 0 |

> **D020（2026-11-03）**：半班一律以「班別時段 − 請假時段 = 實際工時 ≥ 4 小時」判定，取代舊版固定字串比對，計算規格見 `src/shift_hours.py` 與 DECISION_LOG D020。**D021**：整班代碼（`E`／`N` 系列）也依實際工時判定，滿 8 小時整班、≥ 4 小時半班、未滿 4 小時不計。請假時段超出班別、標示時數不符等規則外情況才列入「需要確認」提醒；提醒不影響計數。

### 3.3 判斷 `E(請)` 半班的實作邏輯

```
for each 人員列 i (從 row 3 起，每 2 列一位):
    for each 日期欄位 c (col 7 ~ col 37):
        code = df[i, c]
        if code == 'E(請)':
            below_cell = df[i+1, c]
            if '21:00~24:00' in str(below_cell):
                → 小夜半班 +1 （該日期記錄）
            else:
                → 不算夜班
```

### 3.4 判斷大夜整班整日請假的實作邏輯（D010）

```
for each 人員列 i (從 row 3 起，每 2 列一位):
    for each 日期欄位 c (col 7 ~ col 37):
        code = df[i, c]
        if code in ('N', '休;N', '國;N'):
            below_cell = df[i+1, c]
            if '00:00~08:00' in str(below_cell):
                → 不算（整班請假，該日期不列入大夜）
            else:
                → 大夜整班 +1
```

> **範例**（11501 排班表 W9）：蕭雅慧第 16 天 `N` 下方寫 `休假8(00:00~08:00)`，表示大夜整班 8 小時全部請假，當日不計入大夜班。

---

## 4. 輸出規格

### 4.1 範本檔案

- 檔名：`衛生福利部夜班津貼示範.xlsx`
- 放在 `templates/` 資料夾
- **以範本為基底**產出，**不另外從零建立**，以保留表頭樣式、字型、邊框、合併儲存格、欄寬

### 4.2 範本結構

#### 表頭（row 1~3）
| 位置 | 內容 | 動態修改 |
|---|---|---|
| A1 | `國軍花蓮總醫院急性一般病床護理人員夜班獎勵人員清冊(X月)` | X 隨月份變動 |
| A2 | `單位：XXX` | 隨病房變動 |
| E2 | `填表人：` | 留空待手填 |
| L2 | `連絡電話：` | 留空待手填 |
| AA2 | （密碼欄） | 清空 |
| Row 3 | 欄位標題（序號、姓名、身分證字號、班別、班數、分項獎勵金額、備考(值班日期)、總獎勵金額、簽章） | 不動 |

#### 人員區塊（每人佔 10 列）

起始列計算：**第 N 位人員起始列 = 4 + (N-1) × 10**
（第 1 人 row 4、第 2 人 row 14、第 23 人 row 224）

每人區塊結構：

| 相對列 | D 欄（班別） | E 欄（班數公式） | F 欄（金額公式） |
|---:|---|---|---|
| +0 | 小夜 | `=COUNT(G{r}:P{r+2})` | `=E{r}*400` |
| +1 | — | — | — |
| +2 | — | — | — |
| +3 | 小夜半 | `=COUNT(G{r+3}:P{r+4})` | `=E{r+3}*200` |
| +4 | — | — | — |
| +5 | 大夜 | `=COUNT(G{r+5}:P{r+7})` | `=E{r+5}*600` |
| +6 | — | — | — |
| +7 | — | — | — |
| +8 | 大夜半 | `=COUNT(G{r+8}:P{r+9})` | `=E{r+8}*300` |
| +9 | — | — | — |

其他欄位：
- **A 欄**（序號）：填在起始列，合併 A{r}:A{r+9}
- **B 欄**（姓名）：填在起始列，合併 B{r}:B{r+9}
- **C 欄**（身分證字號）：**留空**，合併 C{r}:C{r+9}
- **G~P 欄**（備考/值班日期）：填入整數日期，每列最多 10 格
  - 小夜整班：3 列可容納 30 天（G{r}~P{r+2}）
  - 小夜半班：2 列可容納 20 天（G{r+3}~P{r+4}）
  - 大夜整班：3 列可容納 30 天（G{r+5}~P{r+7}）
  - 大夜半班：2 列可容納 20 天（G{r+8}~P{r+9}）
- **Q 欄**（總獎勵金額）：`=SUM(F{r}:F{r+9})`，合併 Q{r}:Q{r+9}
- **R 欄**（簽章）：留空，合併 R{r}:R{r+9}

#### 合計列（人員區塊之後）

| 位置 | 內容 |
|---|---|
| C（小夜8小時） | 文字 `小夜8小時`、E=`=SUMIF($D$4:$D$X,D4,$E$4:$E$X)`、F 同理 |
| C（小夜未滿8） | 同上，條件改為 D7 |
| C（大夜8小時） | 同上，條件改為 D9 |
| C（大夜未滿8） | 同上，條件改為 D12 |
| N（合計標籤） | 文字 `合計` |
| Q（總計） | `=SUM(Q4:Q{X})` |

其中 `X` = 最後一位人員的最後列 = 4 + (人數) × 10 - 1

### 4.3 費率

| 班別 | 金額/班 |
|---:|---:|
| 小夜整班 | 400 |
| 小夜半班 | 200 |
| 大夜整班 | 600 |
| 大夜半班 | 300 |

> 費率**寫在 F 欄公式**中（如 `=E4*400`），不硬編碼數值。若未來費率調整，改公式即可。
> 建議把費率常數抽到設定檔（`config.py` 或 `.env`），產出時注入。

### 4.4 輸出檔名

`{年月}-{病房代碼}_夜班費清冊_{病房名稱}.xlsx`
範例：`11503-N19W01_夜班費清冊_11病房.xlsx`

---

## 5. 人員處理規則

1. **全部人員列入**：即使該月份無夜班（班數皆 0）的人員，**也要列入清冊**
2. **序號依排班表順序**：由上至下、從 1 開始
3. **身分證字號一律留空**，待使用者手填
4. **若人員數超過範本原有數量（22 人）**：需**動態插入列**，並正確延伸合計列的 `SUMIF` 範圍

---

## 6. 技術實作重點（踩過的坑）

### 6.1 讀取 .xls 舊格式
- 需要 `xlrd >= 2.0.1`
- `pd.read_excel(path, sheet_name=0, header=None)` 讀全部，再用 iloc 切

### 6.2 動態插入人員列
- 用 `ws.insert_rows({合計列位置}, amount=10)` 在合計列之前插入
- **`insert_rows` 會殘留異常的合併儲存格**，必須主動清理：
  ```python
  for mr in list(ws.merged_cells.ranges):
      if 新插入範圍 overlap 該 merged range:
          try:
              ws.unmerge_cells(str(mr))
          except KeyError:
              ws.merged_cells.ranges.remove(mr)
  ```
- 清理後**重新合併成標準規格**（A、B、C、D、E、F、Q、R 欄的縱向合併）

### 6.3 複製樣式
- openpyxl 沒有「複製整列樣式」API，要逐格複製：
  ```python
  from copy import copy
  dc.font = copy(sc.font)
  dc.border = copy(sc.border)
  dc.fill = copy(sc.fill)
  dc.number_format = sc.number_format
  dc.alignment = copy(sc.alignment)
  ```

### 6.4 修正合計列 SUMIF 範圍
- `insert_rows` 會自動調整被推下的儲存格中的公式，**但有時會漏**
- 穩妥作法：產出完成後**主動覆寫**合計列 SUMIF 的範圍：
  ```python
  ws['E234'] = '=SUMIF($D$4:$D$233,D4,$E$4:$E$233)'
  ```

### 6.5 公式重新計算
- openpyxl 存檔後**公式值為空**，需用 LibreOffice 重算：
  ```bash
  python scripts/recalc.py output.xlsx 150
  ```
- 若使用者直接在 Excel 開啟，Excel 會自動重算，不需此步

### 6.6 中文檔名
- Python 端檔名可用中文，但**需確認 web 框架的 `Content-Disposition` 正確 URL encode**

---

## 7. 建議架構

```
night_shift_payroll/
├── README.md
├── requirements.txt
├── config.py                      # 費率、班別代碼對照
├── templates/
│   └── 衛生福利部夜班津貼示範.xlsx       # 清冊範本
├── src/
│   ├── __init__.py
│   ├── parser.py                  # 解析排班表
│   ├── classifier.py              # 班別分類邏輯
│   ├── builder.py                 # 產出清冊（以範本為基底）
│   └── main.py                    # 主流程
├── web/                           # Web UI（見下節）
│   ├── app.py                     # FastAPI
│   ├── static/
│   └── templates/
│       └── index.html
└── tests/
    ├── fixtures/
    │   └── 11503-N19W01排班表.xls  # 測試用
    ├── test_parser.py
    ├── test_classifier.py
    └── test_builder.py
```

### 核心模組 API 設計

```python
# src/parser.py
def parse_schedule(xls_path: Path) -> ScheduleData:
    """讀取排班表，回傳結構化資料"""
    return ScheduleData(
        year=115, month=3, ward_name='11病房', ward_code='N19W01',
        staff=[
            StaffRecord(emp_id='CNU80500401', name='陳淑靜',
                        daily_codes={1:'例', 2:'C', ...},
                        below_notes={1:'', 2:'', ...}),
            ...
        ]
    )

# src/classifier.py
def classify_shifts(staff: StaffRecord) -> ShiftCount:
    """依班別規則分類，回傳整班/半班日期清單"""
    return ShiftCount(
        E_full_days=[1, 14],
        E_half_days=[15],
        N_full_days=[11, 29, 30],
        N_half_days=[],
    )

# src/builder.py
def build_roster(
    schedule: ScheduleData,
    shift_counts: list[ShiftCount],
    template_path: Path,
    output_path: Path,
    rates: dict = None,   # 預設 {'E_full':400, 'E_half':200, 'N_full':600, 'N_half':300}
) -> Path:
    """以範本為基底產出清冊，回傳輸出路徑"""
```

---

## 8. Web UI 設計

### 8.1 最小可用原型（MVP）

用 **FastAPI + 一頁式 HTML**：

**`web/app.py`**：
```python
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
import tempfile, shutil
from pathlib import Path
from src.main import generate_roster

app = FastAPI()

@app.get('/', response_class=HTMLResponse)
def index():
    return open('web/templates/index.html', encoding='utf-8').read()

@app.post('/upload')
async def upload(file: UploadFile = File(...)):
    # 儲存上傳檔
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xls') as f:
        shutil.copyfileobj(file.file, f)
        input_path = Path(f.name)

    # 產出清冊
    output_path = generate_roster(input_path)

    # 回傳下載
    return FileResponse(
        output_path,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename=output_path.name,
    )
```

**`web/templates/index.html`**：
單檔 HTML，含：
- 標題：「夜班費清冊產生器」
- 說明：支援檔案格式、輸出格式範例
- 拖放上傳區（`<input type="file" accept=".xls,.xlsx">`）
- 處理中動畫（loading spinner）
- 錯誤訊息顯示區（上傳格式錯誤、解析失敗等）
- 成功後自動下載 + 顯示成功訊息

### 8.2 UI/UX 要點（護理長使用）

- **拖放 + 點擊上傳**兩種都要支援
- **上傳後即刻處理**，不要再按「送出」按鈕
- **檔案格式檢查**：副檔名不對就立刻提示
- **錯誤訊息要白話**：
  - ❌「KeyError: '編號'」
  - ✅「排班表格式不符，請確認第 2 列的欄位包含『編號』『姓名』」
- **支援中文檔名下載**
- **手機/平板可用**（RWD）

### 8.3 進階選項（v1.1 再加）

- 可選擇費率（整合未來薪資調整）
- 可自訂病房名稱、填表人
- 可預覽統計結果，再確認下載
- 歷史紀錄查詢

---

## 9. 測試

### 9.1 單元測試

- **`test_parser.py`**：
  - 正確讀取 year/month/ward_name
  - 正確抓到 23 位人員、編號、姓名
  - 正確讀取每位人員每日班別代碼
  - 下方備註列（補休）能正確對應

- **`test_classifier.py`**：
  - `N` / `休;N` → N_full_days
  - `E` / `休;E` → E_full_days
  - `E(請)` + `21:00~24:00` → E_half_days
  - `E(請)` 無 `21:00~24:00` → 不算
  - 所有不相關代碼 → 不算

- **`test_builder.py`**：
  - 產出的 Excel 可被 openpyxl 重開、公式無錯
  - 關鍵人員的總獎勵金額正確
  - 合計列 SUMIF 範圍涵蓋所有人員
  - 23 人（超過範本 22 人）能正確處理

### 9.2 驗收測試（端到端）

用 `tests/fixtures/11503-N19W01排班表.xls` 跑一次，比對：

| 姓名 | 小夜 | 小夜半 | 大夜 | 總額 |
|---|---:|---:|---:|---:|
| 陳淑靜 | 0 | 0 | 1 | 600 |
| 陳芳瑜 | 2 | 1 | 3 | 2,800 |
| 蕭雅慧 | 0 | 0 | 18 | 10,800 |
| 莊淨雅 | 0 | 0 | 17 | 10,200 |
| 曾郁翎 | 0 | 0 | 7 | 4,200 |
| 蘇心柔 | 14 | 2 | 4 | 8,400 |
| 丁煒哲 | 15 | 0 | 4 | 8,400 |
| 何語馨 | 14 | 3 | 3 | 8,000 |
| 陳資晴 | 4 | 0 | 0 | 1,600 |
| 黃崴 | 1 | 1 | 18 | 11,400 |
| 邱子桓 | 1 | 0 | 3 | 2,200 |
| 劉芳榕 | 15 | 2 | 3 | 8,200 |
| 葉子瑜 | 14 | 3 | 1 | 6,800 |
| 陳緯 | 0 | 0 | 5 | 3,000 |
| 韓譯賢 | 0 | 0 | 1 | 600 |
| 其他 8 人 | 0 | 0 | 0 | 0 |
| **合計** | **80** | **12** | **88** | **87,200** |

- 小夜8小時：80 班 = 32,000
- 小夜未滿8：12 班 = 2,400
- 大夜8小時：88 班 = 52,800
- **總獎勵金額：87,200**

---

## 10. 部署建議

### 本機單機版（推薦 v1.0 起點）
```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
```
同院區內網用 `http://<你的電腦IP>:8000` 提供給其他護理長使用。

### 院區伺服器部署（未來）
- Docker 化
- 加 HTTPS、身分驗證（串接院區 AD）
- 與 HIS 整合（未來可直接從班表系統拉資料，免上傳）

---

## 11. 開發路徑建議

### Sprint 01：核心解析與產出
- [ ] 建立專案結構
- [ ] `parser.py` + 單元測試
- [ ] `classifier.py` + 單元測試
- [ ] `builder.py` + 單元測試
- [ ] 端到端驗收測試通過（與第 9.2 節數字一致）

### Sprint 02：Web UI
- [ ] FastAPI 框架
- [ ] 上傳 + 下載流程
- [ ] 錯誤處理
- [ ] RWD

### Sprint 03：易用性與穩健性
- [ ] 檔案格式容錯（.xls / .xlsx、31 天以下月份）
- [ ] 未預期班別代碼的警告訊息（跳出提示但不中斷）
- [ ] 統計預覽頁面
- [ ] 部署文件

---

## 12. 參考附件

- `SAMPLE_INPUT.xls` — 115 年 3 月 N19W01 排班表
- `SAMPLE_TEMPLATE.xlsx` — 衛福部清冊範本
- `SAMPLE_OUTPUT.xlsx` — 已驗證的產出範例（總額 87,200）
- `DECISION_LOG.md` — 規則決策記錄（班別代碼歸類討論、費率確認）
