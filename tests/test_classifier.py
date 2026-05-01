import pytest

from src.classifier import ShiftCount, classify_shifts
from src.parser import StaffRecord, parse_schedule


def _make_staff(codes: dict[int, str], notes: dict[int, str] | None = None) -> StaffRecord:
    return StaffRecord(
        emp_id='TEST001',
        name='測試',
        daily_codes=dict(codes),
        below_notes=dict(notes or {}),
    )


def test_N_counts_as_full_night():
    staff = _make_staff({1: 'N', 2: 'N'})
    result = classify_shifts(staff)
    assert result.N_full_days == [1, 2]
    assert result.E_full_days == []
    assert result.E_half_days == []
    assert result.N_half_days == []


def test_rest_N_counts_as_full_night():
    staff = _make_staff({3: '休;N'})
    assert classify_shifts(staff).N_full_days == [3]


def test_E_counts_as_full_evening():
    staff = _make_staff({5: 'E'})
    assert classify_shifts(staff).E_full_days == [5]


def test_rest_E_counts_as_full_evening():
    staff = _make_staff({6: '休;E'})
    assert classify_shifts(staff).E_full_days == [6]


def test_national_N_counts_as_full_night():
    staff = _make_staff({4: '國;N'})
    assert classify_shifts(staff).N_full_days == [4]


def test_national_E_counts_as_full_evening():
    staff = _make_staff({9: '國;E'})
    assert classify_shifts(staff).E_full_days == [9]


def test_N_national_reversed_counts_as_full_night():
    staff = _make_staff({5: 'N;國'})
    assert classify_shifts(staff).N_full_days == [5]


def test_N_rest_reversed_counts_as_full_night():
    staff = _make_staff({6: 'N;休'})
    assert classify_shifts(staff).N_full_days == [6]


def test_E_national_reversed_counts_as_full_evening():
    staff = _make_staff({7: 'E;國'})
    assert classify_shifts(staff).E_full_days == [7]


def test_E_rest_reversed_counts_as_full_evening():
    staff = _make_staff({8: 'E;休'})
    assert classify_shifts(staff).E_full_days == [8]


def test_reversed_N_also_honors_full_leave_marker():
    staff = _make_staff(
        {15: 'N;休'},
        notes={15: '休假8(00:00~08:00)'},
    )
    assert classify_shifts(staff).N_full_days == []


def test_N_with_full_leave_marker_is_excluded():
    # 大夜 N 但下列同欄有 00:00~08:00 代表整班請假 → 不計
    staff = _make_staff(
        {16: 'N'},
        notes={16: '休假8(00:00~08:00)'},
    )
    assert classify_shifts(staff).N_full_days == []


def test_rest_N_with_full_leave_marker_is_excluded():
    staff = _make_staff(
        {10: '休;N'},
        notes={10: '休假8(00:00~08:00)'},
    )
    assert classify_shifts(staff).N_full_days == []


def test_national_N_with_full_leave_marker_is_excluded():
    staff = _make_staff(
        {11: '國;N'},
        notes={11: '休假8(00:00~08:00)'},
    )
    assert classify_shifts(staff).N_full_days == []


def test_N_without_00_08_marker_still_counts():
    staff = _make_staff(
        {12: 'N'},
        notes={12: '補假8(08:00~17:00)'},  # different marker, irrelevant
    )
    assert classify_shifts(staff).N_full_days == [12]


# --- D012: JD 班視為小夜半班 ---

def test_JD_counts_as_half_evening():
    staff = _make_staff({1: 'JD'})
    result = classify_shifts(staff)
    assert result.E_half_days == [1]
    assert result.E_full_days == []
    assert result.N_full_days == []


def test_rest_JD_counts_as_half_evening():
    staff = _make_staff({2: '休;JD'})
    assert classify_shifts(staff).E_half_days == [2]


def test_national_JD_counts_as_half_evening():
    staff = _make_staff({3: '國;JD'})
    assert classify_shifts(staff).E_half_days == [3]


def test_JD_rest_reversed_counts_as_half_evening():
    staff = _make_staff({4: 'JD;休'})
    assert classify_shifts(staff).E_half_days == [4]


def test_JD_national_reversed_counts_as_half_evening():
    staff = _make_staff({5: 'JD;國'})
    assert classify_shifts(staff).E_half_days == [5]


# --- D013: ED 班視為小夜半班 ---

def test_ED_counts_as_half_evening():
    staff = _make_staff({1: 'ED'})
    result = classify_shifts(staff)
    assert result.E_half_days == [1]
    assert result.E_full_days == []
    assert result.N_full_days == []


def test_rest_ED_counts_as_half_evening():
    staff = _make_staff({2: '休;ED'})
    assert classify_shifts(staff).E_half_days == [2]


def test_national_ED_counts_as_half_evening():
    staff = _make_staff({3: '國;ED'})
    assert classify_shifts(staff).E_half_days == [3]


def test_ED_rest_reversed_counts_as_half_evening():
    staff = _make_staff({4: 'ED;休'})
    assert classify_shifts(staff).E_half_days == [4]


def test_ED_national_reversed_counts_as_half_evening():
    staff = _make_staff({5: 'ED;國'})
    assert classify_shifts(staff).E_half_days == [5]


def test_E_qing_with_marker_is_half_evening():
    staff = _make_staff(
        {7: 'E(請)'},
        notes={7: '補假3(21:00~24:00)'},
    )
    result = classify_shifts(staff)
    assert result.E_half_days == [7]
    assert result.E_full_days == []


def test_E_qing_without_marker_is_not_counted():
    staff = _make_staff(
        {8: 'E(請)'},
        notes={8: '補假8(08:00~17:00)'},
    )
    result = classify_shifts(staff)
    assert result.E_half_days == []
    assert result.E_full_days == []
    assert result.N_full_days == []


@pytest.mark.parametrize('code', [
    'D', 'C', 'AD', 'DD', 'BE', 'AE', 'P8', 'U', '國', '休', '例', '請',
    '08/請', '休;D', '休;BE', '休;AD', '8-12/1-5', '',
])
def test_other_codes_are_ignored(code):
    staff = _make_staff({10: code})
    result = classify_shifts(staff)
    assert result.N_full_days == []
    assert result.E_full_days == []
    assert result.E_half_days == []
    assert result.N_half_days == []


def test_N_half_always_empty_in_v1():
    # N(請) + 21:00~24:00 → per DECISION_LOG D008, explicitly unsupported
    staff = _make_staff(
        {11: 'N(請)'},
        notes={11: '補假3(21:00~24:00)'},
    )
    assert classify_shifts(staff).N_half_days == []


def test_days_are_sorted_ascending():
    staff = _make_staff({5: 'N', 2: 'N', 10: 'N'})
    result = classify_shifts(staff)
    assert result.N_full_days == [2, 5, 10]


def test_integration_with_fixture(fixture_xls_path):
    """比對 CLAUDE.md 驗收基準表關鍵幾人"""
    schedule = parse_schedule(fixture_xls_path)
    by_name = {s.name: classify_shifts(s) for s in schedule.staff}

    # 陳淑靜: 0 / 0 / 1
    assert len(by_name['陳淑靜'].E_full_days) == 0
    assert len(by_name['陳淑靜'].E_half_days) == 0
    assert len(by_name['陳淑靜'].N_full_days) == 1

    # 陳芳瑜: 2 / 1 / 3
    assert len(by_name['陳芳瑜'].E_full_days) == 2
    assert len(by_name['陳芳瑜'].E_half_days) == 1
    assert len(by_name['陳芳瑜'].N_full_days) == 3

    # 蕭雅慧: 0 / 0 / 18
    assert len(by_name['蕭雅慧'].E_full_days) == 0
    assert len(by_name['蕭雅慧'].E_half_days) == 0
    assert len(by_name['蕭雅慧'].N_full_days) == 18

    # 蘇心柔: 14 / 2 / 4
    assert len(by_name['蘇心柔'].E_full_days) == 14
    assert len(by_name['蘇心柔'].E_half_days) == 2
    assert len(by_name['蘇心柔'].N_full_days) == 4

    # 丁煒哲: 15 / 0 / 4
    assert len(by_name['丁煒哲'].E_full_days) == 15
    assert len(by_name['丁煒哲'].E_half_days) == 0
    assert len(by_name['丁煒哲'].N_full_days) == 4

    # 莊雅婷: 0 / 0 / 0
    assert len(by_name['莊雅婷'].E_full_days) == 0
    assert len(by_name['莊雅婷'].E_half_days) == 0
    assert len(by_name['莊雅婷'].N_full_days) == 0


def test_grand_totals_match_baseline(fixture_xls_path):
    schedule = parse_schedule(fixture_xls_path)
    counts = [classify_shifts(s) for s in schedule.staff]
    total_e_full = sum(len(c.E_full_days) for c in counts)
    total_e_half = sum(len(c.E_half_days) for c in counts)
    total_n_full = sum(len(c.N_full_days) for c in counts)
    total_n_half = sum(len(c.N_half_days) for c in counts)
    assert total_e_full == 80
    assert total_e_half == 12
    assert total_n_full == 88
    assert total_n_half == 0
    total_amount = total_e_full * 400 + total_e_half * 200 + total_n_full * 600 + total_n_half * 300
    assert total_amount == 87_200


# 三個月份總額迴歸測試 — Lin 已親自驗證的基線，未來任何規則改動都必須
# 保持這三個數字不變（若真的要變，必須同步更新 DECISION_LOG + 測試）
@pytest.mark.parametrize('fixture_name, expected_e_full, expected_e_half, expected_n_full, expected_total', [
    ('11501-N19W01排班表.xls', 66, 21, 96, 88_200),
    ('11502-N19W01排班表.xls', 56,  6, 78, 70_400),
    ('11503-N19W01排班表.xls', 80, 12, 88, 87_200),
    ('11504-N18W01排班表.xls', 49, 11, 30, 39_800),
])
def test_monthly_baselines(
    fixture_name, expected_e_full, expected_e_half, expected_n_full, expected_total
):
    from tests.conftest import PROJECT_ROOT
    path = PROJECT_ROOT / 'tests' / 'fixtures' / fixture_name
    schedule = parse_schedule(path)
    counts = [classify_shifts(s) for s in schedule.staff]
    e_full = sum(len(c.E_full_days) for c in counts)
    e_half = sum(len(c.E_half_days) for c in counts)
    n_full = sum(len(c.N_full_days) for c in counts)
    n_half = sum(len(c.N_half_days) for c in counts)
    total = e_full * 400 + e_half * 200 + n_full * 600 + n_half * 300
    assert (e_full, e_half, n_full, total) == \
        (expected_e_full, expected_e_half, expected_n_full, expected_total)
