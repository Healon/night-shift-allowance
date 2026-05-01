# 夜班費清冊產生器

讓護理長上傳排班表 Excel 後，自動產出符合衛福部格式的夜班獎勵人員清冊。

---

## 目前狀態

**尚未實作**，本資料夾為 **Claude Code 實作起點**。

---

## 文件閱讀順序

1. **`README.md`**（本檔）— 專案總覽
2. **`CLAUDE.md`** — Claude Code 工作指南（含絕對不要做的事、規則速查、測試驗收基準）
3. **`SPEC.md`** — 完整需求與技術規格
4. **`DECISION_LOG.md`** — 業務規則決策記錄
5. **`SPRINT_01.md`** — 當前 Sprint 任務清單

---

## 專案檔案結構

```
夜班費清冊專案/
├── README.md                                  ← 你在這裡
├── CLAUDE.md                                  ← Claude Code 長期記憶
├── SPEC.md                                    ← 完整規格
├── DECISION_LOG.md                            ← 決策記錄
├── SPRINT_01.md                               ← 當前 Sprint
├── templates/
│   └── 衛生福利部夜班津貼示範.xlsx                ← 清冊範本
├── tests/
│   └── fixtures/
│       └── 11503-N19W01排班表.xls               ← 測試用排班表（115年3月）
└── samples/
    └── SAMPLE_OUTPUT.xlsx                      ← 已驗證的產出範例（總額 87,200）
```

---

## Claude Code 啟動提示（Prompt）

把此資料夾放到你的工作區後，在 Claude Code 開啟第一次對話時貼：

```
我要依照 CLAUDE.md 與 SPEC.md 開始實作夜班費清冊產生器。
請先完整讀過 README.md、CLAUDE.md、SPEC.md、DECISION_LOG.md、SPRINT_01.md，
然後依照六步法執行 Sprint 01：
  Brainstorm → Plan → Implement → Review 1 → Review 2 → Report

實作策略：
  1. 用 TDD：先寫測試再寫實作
  2. 一次只做一個模組（Parser → Classifier → Builder → main）
  3. 每個模組完成後跑對應測試
  4. Sprint 01 完成後，用 tests/fixtures/11503-N19W01排班表.xls 跑端到端驗收，
     對照 samples/SAMPLE_OUTPUT.xlsx 的標準答案（總額 NT$ 87,200）

請先讀文件，確認沒有疑問後開始 Brainstorm 階段。
```

---

## 驗收標準摘要

用 `tests/fixtures/11503-N19W01排班表.xls` 跑端到端，應產出：

- **23 位人員**全部列入清冊
- **單位**：11病房
- **月份**：3月
- **小夜整班 80 × 400 = 32,000**
- **小夜半班 12 × 200 = 2,400**
- **大夜整班 88 × 600 = 52,800**
- **大夜半班 0 × 300 = 0**
- **總獎勵金額 = NT$ 87,200**

完整每人班數對照見 `CLAUDE.md` 驗收基準表。

---

## 使用情境流程（完成後）

```
[ 護理長 ]
    │
    │ 1. 開啟網頁（http://院區IP:8000）
    │ 2. 拖放排班表 Excel 到網頁上
    │
    ▼
[ 系統 ]
    │
    │ 1. 讀取排班表
    │ 2. 統計每人大夜/小夜班數
    │ 3. 以範本為基底產出清冊 Excel
    │
    ▼
[ 護理長 ]
    │
    │ 4. 自動下載清冊 Excel
    │ 5. 手動填入身分證字號、填表人、電話（留空部分）
    │ 6. 交給會計請款
```

---

## 使用方式

### 方法一：命令列（CLI）

```bash
pip install -r requirements.txt
python -m src.main tests/fixtures/11503-N19W01排班表.xls
# 產出 output/11503-N19W01_夜班費清冊_11病房.xlsx
```

### 方法二：Web UI（瀏覽器拖放）

啟動：
```bash
pip install -r requirements.txt
uvicorn web.app:app --port 8000
# 瀏覽器打開 http://localhost:8000
# 把排班表 Excel 拖進網頁 → 自動下載清冊
```

內網分享（讓同院區其他護理長也能用）：
```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
# 查自己 IP: ifconfig en0 | grep 'inet '
# 給同事：http://<你的IP>:8000
```

**注意**：全程本機運算、不連外部 API、不需要網路。

---

## 後續 Sprint

- ✅ **Sprint 01**：CLI 端到端（已完成，三個月份驗證通過）
- ✅ **Sprint 02**：FastAPI Web UI（已完成，拖放上傳 + 自動下載）
- **Sprint 03**：易用性與穩健性（身分驗證、歷史紀錄、Docker 部署）

---

## 聯絡與決策

所有規則變更請更新 `DECISION_LOG.md` 並註記決策者與日期。
