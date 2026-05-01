from pathlib import Path

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from src.builder import build_roster
from src.classifier import classify_shifts
from src.parser import parse_schedule

EXPECTED_BLOCK_ROWS = 10
FIRST_STAFF_ROW = 4
STAFF_COUNT = 23
TOTAL_ROW = FIRST_STAFF_ROW + STAFF_COUNT * EXPECTED_BLOCK_ROWS  # = 234
LAST_DATA_ROW = TOTAL_ROW - 1  # 233


@pytest.fixture(scope='module')
def roster_path(tmp_path_factory, fixture_xls_path, template_xlsx_path) -> Path:
    schedule = parse_schedule(fixture_xls_path)
    counts = [classify_shifts(s) for s in schedule.staff]
    out_dir = tmp_path_factory.mktemp('roster')
    return build_roster(
        schedule,
        counts,
        template_path=template_xlsx_path,
        output_path=out_dir,
    )


@pytest.fixture(scope='module')
def roster_ws(roster_path):
    wb = load_workbook(roster_path, data_only=False)
    return wb.active


def test_output_path_naming(roster_path):
    assert roster_path.exists()
    assert roster_path.name == '11503-N19W01_夜班費清冊_11病房.xlsx'


def test_output_reopenable(roster_path):
    # Load twice — once formulas, once values — both must work
    wb_f = load_workbook(roster_path, data_only=False)
    assert wb_f.active.max_row >= TOTAL_ROW
    wb_v = load_workbook(roster_path, data_only=True)
    assert wb_v.active.max_row >= TOTAL_ROW


def test_header_substitution(roster_ws):
    assert '(3月)' in str(roster_ws['A1'].value)
    assert '11病房' in str(roster_ws['A2'].value)
    assert roster_ws['E2'].value in (None, '')
    assert roster_ws['L2'].value in (None, '')
    assert roster_ws['AA2'].value in (None, '')


def test_all_23_blocks_have_labels_and_count_formulas(roster_ws):
    for idx in range(STAFF_COUNT):
        r = FIRST_STAFF_ROW + idx * EXPECTED_BLOCK_ROWS
        assert roster_ws[f'D{r}'].value == '小夜'
        assert roster_ws[f'D{r + 3}'].value == '小夜半'
        assert roster_ws[f'D{r + 5}'].value == '大夜'
        assert roster_ws[f'D{r + 8}'].value == '大夜半'
        assert roster_ws[f'E{r}'].value == f'=COUNT(G{r}:P{r + 2})'
        assert roster_ws[f'E{r + 3}'].value == f'=COUNT(G{r + 3}:P{r + 4})'
        assert roster_ws[f'E{r + 5}'].value == f'=COUNT(G{r + 5}:P{r + 7})'
        assert roster_ws[f'E{r + 8}'].value == f'=COUNT(G{r + 8}:P{r + 9})'


def test_rate_overridden_to_400_200_600_300(roster_ws):
    for idx in range(STAFF_COUNT):
        r = FIRST_STAFF_ROW + idx * EXPECTED_BLOCK_ROWS
        assert roster_ws[f'F{r}'].value == f'=E{r}*400'
        assert roster_ws[f'F{r + 3}'].value == f'=E{r + 3}*200'
        assert roster_ws[f'F{r + 5}'].value == f'=E{r + 5}*600'
        assert roster_ws[f'F{r + 8}'].value == f'=E{r + 8}*300'


def test_subtotal_Q_formula(roster_ws):
    for idx in range(STAFF_COUNT):
        r = FIRST_STAFF_ROW + idx * EXPECTED_BLOCK_ROWS
        assert roster_ws[f'Q{r}'].value == f'=SUM(F{r}:F{r + 9})'


def test_staff_names_filled_in_order(roster_ws, fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    for idx, staff in enumerate(schedule.staff):
        r = FIRST_STAFF_ROW + idx * EXPECTED_BLOCK_ROWS
        assert roster_ws[f'A{r}'].value == idx + 1
        assert roster_ws[f'B{r}'].value == staff.name
        # C-column (ID) left blank per DECISION_LOG D004
        assert roster_ws[f'C{r}'].value in (None, '')


def test_chenfangyu_dates_filled(roster_ws, fixture_xls_path):
    # 陳芳瑜 is staff index 1 → row 14
    schedule = parse_schedule(fixture_xls_path)
    counts = [classify_shifts(s) for s in schedule.staff]
    fangyu = next(c for c in counts if c.name == '陳芳瑜')
    r = FIRST_STAFF_ROW + 1 * EXPECTED_BLOCK_ROWS  # = 14

    def cells_in(row_start: int, row_end: int) -> list:
        vals = []
        for rr in range(row_start, row_end + 1):
            for col in range(7, 17):  # G..P
                v = roster_ws.cell(rr, col).value
                if v is not None and v != '':
                    vals.append(v)
        return vals

    e_full_cells = cells_in(r, r + 2)
    e_half_cells = cells_in(r + 3, r + 4)
    n_full_cells = cells_in(r + 5, r + 7)
    n_half_cells = cells_in(r + 8, r + 9)

    assert sorted(e_full_cells) == sorted(fangyu.E_full_days)
    assert sorted(e_half_cells) == sorted(fangyu.E_half_days)
    assert sorted(n_full_cells) == sorted(fangyu.N_full_days)
    assert n_half_cells == []


def test_totals_row_position_and_sumif_range(roster_ws):
    # 合計 label at col N of TOTAL_ROW
    assert roster_ws.cell(TOTAL_ROW, 14).value == '合計'
    expected_sumif_E = f'=SUMIF($D$4:$D${LAST_DATA_ROW},D4,$E$4:$E${LAST_DATA_ROW})'
    expected_sumif_F = f'=SUMIF($D$4:$D${LAST_DATA_ROW},D4,$F$4:$F${LAST_DATA_ROW})'
    assert roster_ws[f'E{TOTAL_ROW}'].value == expected_sumif_E
    assert roster_ws[f'F{TOTAL_ROW}'].value == expected_sumif_F
    # D7/D9/D12 references for the other three breakdown rows
    assert roster_ws[f'E{TOTAL_ROW + 1}'].value == \
        f'=SUMIF($D$4:$D${LAST_DATA_ROW},D7,$E$4:$E${LAST_DATA_ROW})'
    assert roster_ws[f'E{TOTAL_ROW + 2}'].value == \
        f'=SUMIF($D$4:$D${LAST_DATA_ROW},D9,$E$4:$E${LAST_DATA_ROW})'
    assert roster_ws[f'E{TOTAL_ROW + 3}'].value == \
        f'=SUMIF($D$4:$D${LAST_DATA_ROW},D12,$E$4:$E${LAST_DATA_ROW})'
    # Grand total Q formula
    assert roster_ws[f'Q{TOTAL_ROW}'].value == f'=SUM(Q4:Q{LAST_DATA_ROW})'


def test_23rd_staff_block_has_correct_merges(roster_ws):
    # 23rd person starts at row 224
    r = FIRST_STAFF_ROW + 22 * EXPECTED_BLOCK_ROWS  # = 224
    expected_merges = {
        f'A{r}:A{r + 9}',
        f'B{r}:B{r + 9}',
        f'C{r}:C{r + 9}',
        f'Q{r}:Q{r + 9}',
        f'R{r}:R{r + 9}',
        f'D{r}:D{r + 2}', f'E{r}:E{r + 2}', f'F{r}:F{r + 2}',
        f'D{r + 3}:D{r + 4}', f'E{r + 3}:E{r + 4}', f'F{r + 3}:F{r + 4}',
        f'D{r + 5}:D{r + 7}', f'E{r + 5}:E{r + 7}', f'F{r + 5}:F{r + 7}',
        f'D{r + 8}:D{r + 9}', f'E{r + 8}:E{r + 9}', f'F{r + 8}:F{r + 9}',
    }
    actual_merges = {str(m) for m in roster_ws.merged_cells.ranges}
    missing = expected_merges - actual_merges
    assert not missing, f'missing merges on 23rd staff block: {missing}'


@pytest.mark.parametrize('staff_n', [1, 10, 22])
def test_build_roster_handles_below_capacity(
    tmp_path, fixture_xls_path, template_xlsx_path, staff_n
):
    """範本本身容量 22 人。<= 22 時不應插入列，合計列保持在 row 224。"""
    from src.parser import parse_schedule
    from src.classifier import classify_shifts
    schedule = parse_schedule(fixture_xls_path)
    schedule.staff = schedule.staff[:staff_n]
    counts = [classify_shifts(s) for s in schedule.staff]
    out = build_roster(
        schedule, counts,
        template_path=template_xlsx_path,
        output_path=tmp_path,
    )
    wb = load_workbook(out, data_only=False)
    ws = wb.active
    # 合計 must still be at the template's original row 224
    assert ws.cell(224, 14).value == '合計'
    assert ws['E224'].value == '=SUMIF($D$4:$D$223,D4,$E$4:$E$223)'
    assert ws['Q224'].value == '=SUM(Q4:Q223)'


def test_grand_totals_computed_when_recalculated(roster_path, tmp_path):
    """
    Re-create formulas values by populating E/F cells in-memory
    (simulates what Excel does when opening the file).
    Confirms that formulas end up producing the expected NT$87,200.
    """
    wb = load_workbook(roster_path, data_only=False)
    ws = wb.active
    # Manually evaluate by counting G:P entries per shift row and multiplying
    total = 0
    for idx in range(STAFF_COUNT):
        r = FIRST_STAFF_ROW + idx * EXPECTED_BLOCK_ROWS
        ranges = [
            (r, r + 2, 400),
            (r + 3, r + 4, 200),
            (r + 5, r + 7, 600),
            (r + 8, r + 9, 300),
        ]
        for rs, re, rate in ranges:
            count = 0
            for rr in range(rs, re + 1):
                for col in range(7, 17):
                    if ws.cell(rr, col).value not in (None, ''):
                        count += 1
            total += count * rate
    assert total == 87_200
