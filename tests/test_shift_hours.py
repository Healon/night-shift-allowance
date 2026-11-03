"""D020：班別時段扣除請假時段後的實際工時計算（規格測試）。"""
import pytest

from src.shift_hours import (
    HALF_SHIFT_MIN_MINUTES,
    SHIFT_WINDOWS,
    assess_leave,
    parse_leave_ranges,
)


# --- 時段字串解析 ---

@pytest.mark.parametrize('note, expected', [
    ('補假3(21:00~24:00)', [(21 * 60, 24 * 60)]),
    ('休假4(16:00~17:40)', [(16 * 60, 17 * 60 + 40)]),
    ('補假4(04:00~08:00)', [(4 * 60, 8 * 60)]),
    ('休假（1600-1740）', [(16 * 60, 17 * 60 + 40)]),   # 無冒號、全形括號、連字號
    ('補假3(16:00～19:00)', [(16 * 60, 19 * 60)]),       # 全形波浪號
    ('補假1(00:00~01:00)補假2(06:00~08:00)', [(0, 60), (6 * 60, 8 * 60)]),
    ('', []),
    ('公差', []),
])
def test_parse_leave_ranges(note, expected):
    assert parse_leave_ranges(note) == expected


@pytest.mark.parametrize('note', ['補假(25:00~26:00)', '補假(16:70~17:00)', '補假(20:00~18:00)'])
def test_parse_leave_ranges_skips_impossible_times(note):
    assert parse_leave_ranges(note) == []


# --- 實際工時 = 班別時段 − 與請假時段重疊的部分 ---

def test_windows_and_threshold():
    assert SHIFT_WINDOWS['E'] == (16 * 60, 24 * 60)
    assert SHIFT_WINDOWS['N'] == (0, 8 * 60)
    assert HALF_SHIFT_MIN_MINUTES == 4 * 60


@pytest.mark.parametrize('note, worked_hours', [
    ('補假3(21:00~24:00)', 5),        # 既有 D001
    ('補假4(20:00~24:00)', 4),        # 既有 D017
    ('補假4(16:00~20:00)', 4),        # 既有 D017
    ('補假3(16:00~19:00)', 5),        # 11510 人員K 10/31
    ('休假4(16:00~17:40)', 6 + 20 / 60),  # 11510 人員M 10/12（S29）
    ('補假5(16:00~21:00)', 3),
    ('補假8(16:00~24:00)', 0),
    ('補假8(08:00~17:00)', 7),        # 只有 16-17 跟小夜重疊
    ('補假8(08:00~16:00)', 8),        # 與小夜無重疊
])
def test_evening_worked_minutes(note, worked_hours):
    assert assess_leave('E', note).worked_minutes == round(worked_hours * 60)


@pytest.mark.parametrize('note, worked_hours', [
    ('補假4(04:00~08:00)', 4),
    ('補假1(00:00~01:00)', 7),
    ('休假8(00:00~08:00)', 0),
])
def test_night_worked_minutes(note, worked_hours):
    assert assess_leave('N', note).worked_minutes == worked_hours * 60


def test_overlapping_ranges_are_not_double_subtracted():
    a = assess_leave('E', '補假(16:00~20:00)補假(18:00~21:00)')
    assert a.worked_minutes == 3 * 60   # 請假聯集 16-21，實際上 21-24


# --- 需要人工確認的異常 ---

def test_no_range_means_unknown_worked_time():
    a = assess_leave('E', '')
    assert a.has_range is False
    assert a.worked_minutes is None


def test_range_outside_window_is_flagged():
    a = assess_leave('E', '補假8(08:00~17:00)')
    assert a.outside_window is True
    assert assess_leave('E', '補假3(21:00~24:00)').outside_window is False


def test_stated_hours_mismatch_is_flagged():
    # 「休假4」但時段只有 1 小時 40 分
    assert assess_leave('E', '休假4(16:00~17:40)').stated_hours_mismatch is True
    assert assess_leave('E', '補假3(16:00~19:00)').stated_hours_mismatch is False
    assert assess_leave('E', '補假(16:00~19:00)').stated_hours_mismatch is False  # 沒寫時數就不比對
