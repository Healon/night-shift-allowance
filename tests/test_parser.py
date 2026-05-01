from pathlib import Path

import pytest

from src.parser import ScheduleData, StaffRecord, parse_schedule


def test_parse_metadata(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    assert isinstance(schedule, ScheduleData)
    assert schedule.year == 115
    assert schedule.month == 3
    assert schedule.ward_name == '11病房'
    assert schedule.ward_code == 'N19W01'


def test_staff_count(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    assert len(schedule.staff) == 23


def test_first_and_last_staff(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    first = schedule.staff[0]
    assert isinstance(first, StaffRecord)
    assert first.emp_id == 'CNU80500401'
    assert first.name == '陳淑靜'

    last = schedule.staff[-1]
    assert last.emp_id == 'CNA80500326'
    assert last.name == '林仲康'


def test_shift_sequence_xiaoya(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    xiaoya = next(s for s in schedule.staff if s.name == '蕭雅慧')
    # 31 days in March
    assert len(xiaoya.daily_codes) == 31
    assert all(day in xiaoya.daily_codes for day in range(1, 32))

    # 17 N + 1 休;N = 18 大夜
    n_days = [d for d, code in xiaoya.daily_codes.items() if code == 'N']
    xiu_n_days = [d for d, code in xiaoya.daily_codes.items() if code == '休;N']
    assert len(n_days) == 17
    assert len(xiu_n_days) == 1


def test_chenfangyu_codes_and_notes(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    fangyu = next(s for s in schedule.staff if s.name == '陳芳瑜')
    assert fangyu.daily_codes[1] == '休;E'
    assert fangyu.daily_codes[14] == 'E'
    assert fangyu.daily_codes[15] == 'E(請)'
    assert fangyu.daily_codes[11] == 'N'
    # day 15 below-note contains 21:00~24:00 (half-shift marker)
    assert '21:00~24:00' in fangyu.below_notes[15]
    # day 1 below-note is empty
    assert fangyu.below_notes.get(1, '') == ''


def test_half_shift_marker_count(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    total_markers = sum(
        1
        for staff in schedule.staff
        for note in staff.below_notes.values()
        if '21:00~24:00' in note
    )
    assert total_markers == 12


def test_staff_order_matches_schedule_order(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    names = [s.name for s in schedule.staff]
    expected_first_five = ['陳淑靜', '陳芳瑜', '蕭雅慧', '陳佩君', '莊淨雅']
    assert names[:5] == expected_first_five


def test_parse_xlsx_format(fixture_xls_path, tmp_path):
    """parser 必須同時支援 .xls 與 .xlsx（透過 openpyxl 引擎）。"""
    import pandas as pd
    # 將 .xls 轉成 .xlsx（保留檔名主幹，避免 ward_code 擷取失敗）
    df = pd.read_excel(fixture_xls_path, sheet_name=0, header=None, engine='xlrd')
    xlsx_path = tmp_path / '11503-N19W01排班表.xlsx'
    with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, header=False)

    schedule = parse_schedule(xlsx_path)
    assert schedule.year == 115
    assert schedule.month == 3
    assert schedule.ward_name == '11病房'
    assert len(schedule.staff) == 23


def test_unsupported_extension_raises():
    from src.parser import _pick_engine
    with pytest.raises(ValueError, match='不支援'):
        _pick_engine(Path('foo.csv'))
