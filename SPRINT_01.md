# Sprint 01 — 核心解析與產出

> 目標：建立最小可用的命令列版本，能讀排班表 → 產出清冊，不含 Web UI。

---

## 驗收條件

執行：
```bash
python -m src.main tests/fixtures/11503-N19W01排班表.xls
```
應產出檔案在 `output/11503-N19W01_夜班費清冊_11病房.xlsx`，且：
- 所有公式可在 Excel 中正確重算
- 總獎勵金額 = **NT$ 87,200**
- 每位人員班數與 `CLAUDE.md` 驗收基準表一致
- 23 人全部列入

---

## 任務分解

### Task 1.1：專案骨架
- [ ] `requirements.txt`：`pandas`, `openpyxl`, `xlrd>=2.0.1`, `pytest`
- [ ] `src/` 結構（見 SPEC 第 7 節）
- [ ] `config.py`：費率、班別代碼常數
- [ ] `templates/` 放範本
- [ ] `tests/fixtures/` 放測試排班表
- [ ] `samples/` 放標準答案清冊

### Task 1.2：Parser
- [ ] `src/parser.py`
  - `parse_schedule(xls_path) -> ScheduleData`
  - 資料類別：`ScheduleData`、`StaffRecord`
  - 抓取 year、month、ward_name
  - 逐人取編號、姓名、日期代碼、下方備註
- [ ] `tests/test_parser.py`
  - 資料類別欄位正確
  - 23 位人員全部抓到
  - 蕭雅慧的 3 月班別序列正確（驗證 31 個代碼）
  - 備註列能對應到正確日期

### Task 1.3：Classifier
- [ ] `src/classifier.py`
  - `classify_shifts(staff: StaffRecord) -> ShiftCount`
  - 純函數、無副作用
- [ ] `tests/test_classifier.py`
  - 每個代碼都有單元測試
  - `E(請)` 雙邊情況（有/無 `21:00~24:00`）

### Task 1.4：Builder
- [ ] `src/builder.py`
  - `build_roster(schedule, shift_counts, template_path, output_path, rates) -> Path`
  - 以範本為基底
  - 動態插入列的邏輯（> 22 人時）
  - 修正合計列 SUMIF 範圍
- [ ] `tests/test_builder.py`
  - 產出檔案可被重新開啟
  - 23 人區塊都有完整 D/E/F 欄
  - 合計列 SUMIF 範圍正確
  - Q{r} 總計公式存在

### Task 1.5：主流程
- [ ] `src/main.py`
  - CLI 入口：`python -m src.main <input.xls> [--output DIR]`
  - 呼叫 parser → classifier → builder
  - 錯誤訊息友善化

### Task 1.6：端到端驗收
- [ ] 用 `11503-N19W01排班表.xls` 跑一次
- [ ] 比對 `samples/SAMPLE_OUTPUT.xlsx`（班數與總額一致）
- [ ] 用 LibreOffice 重算後檢查 0 錯誤

---

## 實作提示

### Parser

排班表 row 0 的抓法：
```python
row0 = df.iloc[0].dropna().tolist()
# ['年份int', '年', '月份int', '月', '排班表', '－', '病房名稱']
year = int(row0[0])
month = int(row0[2])
ward_name = row0[6]
```

人員列的識別：
```python
for i in range(3, len(df)):
    emp_id = df.iloc[i, 4]
    name = df.iloc[i, 5]
    if pd.notna(emp_id) and pd.notna(name) and str(name).strip() not in ('', '*'):
        # 這是一位人員的主班別列，下一列 i+1 是對應的備註列
        ...
```

### Builder 的關鍵順序

**必須照以下順序**，否則合併儲存格會亂掉：

1. 載入範本
2. 修改表頭（A1、A2、E2、L2、AA2）
3. 清空 22 人原有的姓名/身分證/日期（保留班別標籤與公式）
4. **更新所有 22 人的費率公式**（F 欄）
5. 若人數 > 22：
   - 5a. `insert_rows({合計列位置}, amount=10 * (超出人數))`
   - 5b. 清理殘留合併儲存格
   - 5c. 複製第 22 人樣式到新列
   - 5d. 為新列加上標準合併儲存格
   - 5e. 為新列加上班別標籤 + COUNT 公式 + 費率公式 + Q 合計公式
6. 填入所有人員的姓名與日期
7. 更新合計列的 SUMIF 範圍（涵蓋全部人員）
8. 存檔

### 驗證工具

```python
def verify_output(output_path: Path) -> dict:
    """快速驗證產出正確性"""
    from openpyxl import load_workbook
    wb = load_workbook(output_path, data_only=False)
    ws = wb.active

    checks = {
        '人員數': 0,
        '班別標籤完整': True,
        '公式完整': True,
        '合計列正確': False,
    }
    # ... 各項檢查
    return checks
```

---

## 開發順序建議

1. 先寫 **Parser + test_parser**（純讀取，容易測）
2. 再寫 **Classifier + test_classifier**（純邏輯，容易測）
3. 再寫 **Builder + test_builder**（最複雜，但前兩步資料已可信）
4. 最後 **main.py** 串起來
5. 端到端驗收

每個階段的測試**先寫再實作**，TDD 風格。

---

## 完成後

更新 `CLAUDE.md`：
- 當前狀態 → Sprint 02
- 下一步 → Web UI
- 新增 Sprint 01 接力摘要
