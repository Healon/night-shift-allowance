from __future__ import annotations

from copy import copy
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.classifier import ShiftCount
from src.config import (
    DEFAULT_OUTPUT_DIR,
    RATES,
    TEMPLATE_PATH,
    TEMPLATE_STAFF_CAPACITY,
    TEMPLATE_TOTAL_ROW,
)
from src.parser import ScheduleData

BLOCK_ROWS = 10
FIRST_STAFF_ROW = 4
DATE_COL_START = 7   # G
DATE_COL_END = 16    # P (G..P = 10 columns per row)

_SHIFT_TYPES = (
    # (offset, span, label, rate_key)
    (0, 3, '小夜', 'E_full'),
    (3, 2, '小夜半', 'E_half'),
    (5, 3, '大夜', 'N_full'),
    (8, 2, '大夜半', 'N_half'),
)


def build_roster(
    schedule: ScheduleData,
    shift_counts: list[ShiftCount],
    template_path: Path = TEMPLATE_PATH,
    output_path: Path | None = None,
    rates: dict | None = None,
) -> Path:
    rates = rates or RATES
    if len(shift_counts) != len(schedule.staff):
        raise ValueError('shift_counts 與 schedule.staff 長度不一致')

    wb = load_workbook(template_path, data_only=False)
    ws = wb.active

    _write_header(ws, schedule)
    _reset_template_blocks(ws, rates)

    n = len(schedule.staff)
    if n > TEMPLATE_STAFF_CAPACITY:
        _extend_blocks(ws, extra=n - TEMPLATE_STAFF_CAPACITY, rates=rates)

    _fill_staff(ws, schedule, shift_counts)
    _rewrite_totals_row(ws, n)

    out_dir = Path(output_path) if output_path else DEFAULT_OUTPUT_DIR
    if out_dir.suffix.lower() == '.xlsx':
        out_file = out_dir
        out_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / _output_filename(schedule)

    wb.save(out_file)
    return out_file


def _output_filename(schedule: ScheduleData) -> str:
    ym = f'{schedule.year:03d}{schedule.month:02d}'
    return f'{ym}-{schedule.ward_code}_夜班費清冊_{schedule.ward_name}.xlsx'


def _write_header(ws: Worksheet, schedule: ScheduleData) -> None:
    ws['A1'] = (
        f'國軍花蓮總醫院急性一般病床護理人員夜班獎勵人員清冊({schedule.month}月)'
    )
    ws['A2'] = f'單位：{schedule.ward_name}'
    ws['E2'] = None
    ws['L2'] = None
    ws['AA2'] = None


def _reset_template_blocks(ws: Worksheet, rates: dict) -> None:
    """清空原 22 人區塊的序號/姓名/身分證/日期，並覆寫費率公式。"""
    for idx in range(TEMPLATE_STAFF_CAPACITY):
        r = FIRST_STAFF_ROW + idx * BLOCK_ROWS
        ws.cell(r, 1).value = None
        ws.cell(r, 2).value = None
        ws.cell(r, 3).value = None
        for rr in range(r, r + BLOCK_ROWS):
            for col in range(DATE_COL_START, DATE_COL_END + 1):
                ws.cell(rr, col).value = None
        _set_block_formulas(ws, r, rates)


def _set_block_formulas(ws: Worksheet, r: int, rates: dict) -> None:
    """寫入 D/E/F 班別標籤、COUNT、費率公式，以及 Q 小計。"""
    for offset, span, label, rate_key in _SHIFT_TYPES:
        start = r + offset
        end = start + span - 1
        ws.cell(start, 4).value = label
        ws.cell(start, 5).value = f'=COUNT(G{start}:P{end})'
        ws.cell(start, 6).value = f'=E{start}*{rates[rate_key]}'
    ws.cell(r, 17).value = f'=SUM(F{r}:F{r + BLOCK_ROWS - 1})'


def _extend_blocks(ws: Worksheet, extra: int, rates: dict) -> None:
    """在合計列前插入 extra * 10 列，重建樣式與合併，填入公式。"""
    amount = extra * BLOCK_ROWS
    insert_at = TEMPLATE_TOTAL_ROW
    ws.insert_rows(insert_at, amount=amount)

    new_first = insert_at
    new_last = insert_at + amount - 1
    _clean_stray_merges(ws, new_first, new_last)

    # Source block to copy styling from = the original 22nd staff's 10 rows,
    # which are now sitting right above the insertion point.
    src_first = insert_at - BLOCK_ROWS
    for offset in range(amount):
        dst_r = insert_at + offset
        src_r = src_first + (offset % BLOCK_ROWS)
        _copy_row_styles(ws, src_r, dst_r)

    # Apply merges & formulas for each new staff block.
    for blk_idx in range(extra):
        r = insert_at + blk_idx * BLOCK_ROWS
        _apply_block_merges(ws, r)
        _set_block_formulas(ws, r, rates)


def _clean_stray_merges(ws: Worksheet, row_lo: int, row_hi: int) -> None:
    """移除 insert_rows 殘留的異常合併儲存格。

    `insert_rows` 會把原本跨越插入點的合併範圍拉伸或重複放入 ranges 串列，
    openpyxl 的 unmerge_cells 對重複項目只能處理一次，剩下的必須直接從底層
    container 清掉。
    """
    overlaps = [
        mr for mr in list(ws.merged_cells.ranges)
        if mr.min_row <= row_hi and mr.max_row >= row_lo
    ]
    targets = {str(mr) for mr in overlaps}
    # Rebuild ranges list without any merged cell that overlaps.
    kept = [mr for mr in ws.merged_cells.ranges if str(mr) not in targets]
    ws.merged_cells.ranges = kept  # type: ignore[assignment]


def _copy_row_styles(ws: Worksheet, src_r: int, dst_r: int) -> None:
    for col in range(1, ws.max_column + 1):
        sc = ws.cell(src_r, col)
        dc = ws.cell(dst_r, col)
        if sc.has_style:
            dc.font = copy(sc.font)
            dc.border = copy(sc.border)
            dc.fill = copy(sc.fill)
            dc.alignment = copy(sc.alignment)
            dc.number_format = sc.number_format
            dc.protection = copy(sc.protection)
    ws.row_dimensions[dst_r].height = ws.row_dimensions[src_r].height


def _apply_block_merges(ws: Worksheet, r: int) -> None:
    # Full-height merges (A, B, C, Q, R)
    for col_letter in ('A', 'B', 'C', 'Q', 'R'):
        ws.merge_cells(f'{col_letter}{r}:{col_letter}{r + BLOCK_ROWS - 1}')
    # Shift-type sub-block merges (D, E, F × 4 rows)
    for offset, span, _, _ in _SHIFT_TYPES:
        start = r + offset
        end = start + span - 1
        for col_letter in ('D', 'E', 'F'):
            ws.merge_cells(f'{col_letter}{start}:{col_letter}{end}')


def _fill_staff(
    ws: Worksheet,
    schedule: ScheduleData,
    shift_counts: list[ShiftCount],
) -> None:
    for idx, (staff, counts) in enumerate(zip(schedule.staff, shift_counts)):
        r = FIRST_STAFF_ROW + idx * BLOCK_ROWS
        ws.cell(r, 1).value = idx + 1
        ws.cell(r, 2).value = staff.name
        # C (身分證) left blank per DECISION_LOG D004
        _write_days(ws, r + 0, r + 2, counts.E_full_days)
        _write_days(ws, r + 3, r + 4, counts.E_half_days)
        _write_days(ws, r + 5, r + 7, counts.N_full_days)
        _write_days(ws, r + 8, r + 9, counts.N_half_days)


def _write_days(ws: Worksheet, row_start: int, row_end: int, days: list[int]) -> None:
    if not days:
        return
    capacity = (row_end - row_start + 1) * (DATE_COL_END - DATE_COL_START + 1)
    if len(days) > capacity:
        raise ValueError(
            f'班數 {len(days)} 超過 rows {row_start}~{row_end} 容量 {capacity}'
        )
    for i, day in enumerate(sorted(days)):
        rr = row_start + i // (DATE_COL_END - DATE_COL_START + 1)
        cc = DATE_COL_START + i % (DATE_COL_END - DATE_COL_START + 1)
        ws.cell(rr, cc).value = int(day)


def _rewrite_totals_row(ws: Worksheet, staff_count: int) -> None:
    # 合計 row location depends on whether we inserted rows:
    #   staff_count <= 22 → template untouched, 合計 still at row 224
    #   staff_count >  22 → 合計 shifted down by (n-22)*10 rows
    if staff_count <= TEMPLATE_STAFF_CAPACITY:
        total_row = TEMPLATE_TOTAL_ROW
    else:
        total_row = FIRST_STAFF_ROW + staff_count * BLOCK_ROWS
    last_data_row = total_row - 1

    # Defensive sanity check: 合計 label should be at col N (14) of total_row.
    # If not (e.g. template changed), scan a wider window.
    if ws.cell(total_row, 14).value != '合計':
        for r in range(max(1, total_row - 15), min(ws.max_row, total_row + 15) + 1):
            if ws.cell(r, 14).value == '合計':
                total_row = r
                last_data_row = r - 1
                break
        else:
            raise RuntimeError(
                '找不到合計列。請確認範本未被修改，'
                f'預期 row {total_row} col N 為「合計」'
            )

    range_ref = f'$D$4:$D${last_data_row}'
    e_range = f'$E$4:$E${last_data_row}'
    f_range = f'$F$4:$F${last_data_row}'

    # Template rows (relative to 合計 row):
    # row+0: 小夜8小時 (criteria D4)
    # row+1: 小夜未滿8 (D7)
    # row+2: 大夜8小時 (D9)
    # row+3: 大夜未滿8 (D12)
    criteria_cells = ['D4', 'D7', 'D9', 'D12']
    for i, crit in enumerate(criteria_cells):
        r = total_row + i
        ws.cell(r, 5).value = f'=SUMIF({range_ref},{crit},{e_range})'
        ws.cell(r, 6).value = f'=SUMIF({range_ref},{crit},{f_range})'

    ws.cell(total_row, 17).value = f'=SUM(Q4:Q{last_data_row})'
