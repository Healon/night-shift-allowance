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


# --- D014: HD 車班 08-20 視為小夜半班 ---

@pytest.mark.parametrize('code', ['HD', '休;HD', '國;HD', 'HD;休', 'HD;國'])
def test_HD_variants_count_as_half_evening(code):
    staff = _make_staff({8: code})
    result = classify_shifts(staff)
    assert result.E_half_days == [8]
    assert result.E_full_days == []
    assert result.N_full_days == []


# --- D018: FD 班 08-12/17-21 視為小夜半班 ---

@pytest.mark.parametrize('code', ['FD', '休;FD', '國;FD', 'FD;休', 'FD;國'])
def test_FD_variants_count_as_half_evening(code):
    staff = _make_staff({8: code})
    result = classify_shifts(staff)
    assert result.E_half_days == [8]
    assert result.E_full_days == []
    assert result.N_full_days == []


# --- D015: ND 跨日班，當日小夜半 + 隔日大夜整 ---

@pytest.mark.parametrize('code', ['ND', '休;ND', '國;ND', 'ND;休', 'ND;國'])
def test_ND_variants_split_across_two_days(code):
    staff = _make_staff({8: code, 9: 'D'})
    result = classify_shifts(staff)
    assert result.E_half_days == [8]
    assert result.N_full_days == [9]
    assert result.E_full_days == []


def test_ND_on_last_day_does_not_overflow_month():
    # 4 月最後一天 ND，5/1 不應出現在本月清冊
    daily = {d: '' for d in range(1, 31)}
    daily[30] = 'ND'
    staff = _make_staff(daily)
    result = classify_shifts(staff)
    assert result.E_half_days == [30]
    assert result.N_full_days == []


def test_consecutive_ND_accumulates_correctly():
    # 連兩日 ND：第二日同時記 E_half（自己）+ N_full（從前日帶）
    staff = _make_staff({8: 'ND', 9: 'ND', 10: 'D'})
    result = classify_shifts(staff)
    assert result.E_half_days == [8, 9]
    assert result.N_full_days == [9, 10]


def test_ND_followed_by_N_stacks_two_N_full_on_next_day():
    # 防呆：若 day+1 又是 N 班，會出現同日兩筆 N_full（依計畫決策保留，不去重）
    staff = _make_staff({8: 'ND', 9: 'N'})
    result = classify_shifts(staff)
    assert result.E_half_days == [8]
    assert result.N_full_days == [9, 9]


def test_E_qing_with_marker_is_half_evening():
    staff = _make_staff(
        {7: 'E(請)'},
        notes={7: '補假3(21:00~24:00)'},
    )
    result = classify_shifts(staff)
    assert result.E_half_days == [7]
    assert result.E_full_days == []


def test_E_qing_with_range_mostly_outside_window_counts_by_hours_and_flags():
    # D020：08-17 只有 16-17 跟小夜重疊 → 實際上 7h ≥ 4h → 小夜半，但時段超出小夜要提醒
    staff = _make_staff(
        {8: 'E(請)'},
        notes={8: '補假8(08:00~17:00)'},
    )
    result = classify_shifts(staff)
    assert result.E_half_days == [8]
    assert result.E_full_days == []
    assert result.N_full_days == []
    assert [f.day for f in result.review_flags] == [8]


# --- D016: E 整班請假（下方備註含 16:00~24:00）→ 不計 ---

@pytest.mark.parametrize('code', ['E', '休;E', '國;E', 'E;休', 'E;國'])
def test_E_variants_with_full_leave_marker_are_excluded(code):
    staff = _make_staff({14: code}, notes={14: '補假8(16:00~24:00)'})
    result = classify_shifts(staff)
    assert result.E_full_days == []
    assert result.E_half_days == []
    assert result.N_full_days == []


def test_E_with_leave_mostly_outside_window_counts_by_hours_and_flags():
    # D021：08-17 只有 16-17 與小夜重疊 → 實際上 7h → 小夜半；時段超出小夜 → 提醒
    staff = _make_staff({14: 'E'}, notes={14: '補假8(08:00~17:00)'})
    result = classify_shifts(staff)
    assert result.E_full_days == []
    assert result.E_half_days == [14]
    assert [f.day for f in result.review_flags] == [14]


def test_full_shift_with_unrelated_day_leave_stays_full_without_flag():
    # 請假時段與本班完全不重疊（白班時段）→ 實際上滿 8h → 整班，不提醒
    result = classify_shifts(_make_staff({3: 'N'}, notes={3: '補假8(08:00~17:00)'}))
    assert result.N_full_days == [3]
    assert result.review_flags == []


# --- D017: E(請) 半班 marker 擴充（20:00~24:00 / 16:00~20:00） ---

def test_E_qing_with_20_24_marker_is_half_evening():
    staff = _make_staff({20: 'E(請)'}, notes={20: '補假4(20:00~24:00)'})
    result = classify_shifts(staff)
    assert result.E_half_days == [20]
    assert result.E_full_days == []


def test_E_qing_with_16_20_marker_is_half_evening():
    staff = _make_staff({20: 'E(請)'}, notes={20: '補假4(16:00~20:00)'})
    result = classify_shifts(staff)
    assert result.E_half_days == [20]
    assert result.E_full_days == []


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


# --- D020：E(請)／N(請) 以「班別時段扣除請假後實際工時 ≥ 4 小時」判定半班 ---

@pytest.mark.parametrize('note', [
    '補假3(21:00~24:00)',   # 上 16-21，5h
    '補假4(20:00~24:00)',   # 上 16-20，4h（剛好門檻）
    '補假4(16:00~20:00)',   # 上 20-24，4h
    '補假3(16:00~19:00)',   # 上 19-24，5h（11510 人員K 10/31）
])
def test_E_qing_with_at_least_4_hours_worked_is_half_evening(note):
    result = classify_shifts(_make_staff({20: 'E(請)'}, notes={20: note}))
    assert result.E_half_days == [20]
    assert result.E_full_days == []
    assert result.review_flags == []


def test_E_qing_S29_case_counts_and_flags_stated_hours_mismatch():
    # 11510 人員M 10/12：休假4(16:00~17:40) → 上 17:40-24:00 共 6h20m → 小夜半
    # 但「休假4」與時段長度 1h40m 不符 → 提醒護理長確認
    result = classify_shifts(_make_staff({12: 'E(請)'}, notes={12: '休假4(16:00~17:40)'}))
    assert result.E_half_days == [12]
    assert len(result.review_flags) == 1
    assert '1 小時 40 分' in result.review_flags[0].message


def test_E_qing_with_less_than_4_hours_worked_is_not_counted():
    # 請 16-21 → 只上 21-24 共 3h → 不計，屬規則內結果不提醒
    result = classify_shifts(_make_staff({5: 'E(請)'}, notes={5: '補假5(16:00~21:00)'}))
    assert result.E_half_days == []
    assert result.E_full_days == []
    assert result.review_flags == []


def test_E_qing_without_time_range_is_not_counted_and_flagged():
    result = classify_shifts(_make_staff({6: 'E(請)'}, notes={6: ''}))
    assert result.E_half_days == []
    assert [f.day for f in result.review_flags] == [6]


@pytest.mark.parametrize('code', ['N(請)', 'N( 請)', 'N（請）'])
def test_N_qing_with_at_least_4_hours_worked_is_half_night(code):
    # 11510 人員K 10/17：N( 請) + 補假4(04:00~08:00) → 上 00-04 共 4h → 大夜半
    result = classify_shifts(_make_staff({17: code}, notes={17: '補假4(04:00~08:00)'}))
    assert result.N_half_days == [17]
    assert result.N_full_days == []
    assert result.review_flags == []


def test_N_qing_with_less_than_4_hours_worked_is_not_counted():
    result = classify_shifts(_make_staff({11: 'N(請)'}, notes={11: '補假5(00:00~05:00)'}))
    assert result.N_half_days == []
    assert result.N_full_days == []
    assert result.review_flags == []


def test_N_qing_with_range_outside_window_is_flagged():
    # 21-24 不在大夜時段 → 依公式實際上 8h 仍只算半班，但提醒確認
    result = classify_shifts(_make_staff({11: 'N(請)'}, notes={11: '補假3(21:00~24:00)'}))
    assert result.N_half_days == [11]
    assert [f.day for f in result.review_flags] == [11]


# --- D021：整班代碼底下只請部分時段 → 同樣依實際工時判定（滿 8h 整班／≥4h 半班／<4h 不計） ---

@pytest.mark.parametrize('code, note, expected', [
    ('E', '補假5(16:00~21:00)', {}),                        # 11510 人員K 10/8，實際上 3h → 不計
    ('E', '補假7(17:00~24:00)', {}),                        # 11510 人員M 10/21，實際上 1h → 不計
    ('休;E', '補假4(20:00~24:00)', {'E_half_days': [9]}),    # 實際上 4h（門檻）→ 小夜半
    ('E;國', '補假3(21:00~24:00)', {'E_half_days': [9]}),    # 實際上 5h → 小夜半
    ('N', '補假1(00:00~01:00)', {'N_half_days': [9]}),       # 11504 林睿芸 4/26，實際上 7h → 大夜半
    ('N;國', '補假4(04:00~08:00)', {'N_half_days': [9]}),    # 實際上 4h → 大夜半
    ('休;N', '補假5(00:00~05:00)', {}),                      # 實際上 3h → 不計
])
def test_full_shift_with_partial_leave_counts_by_worked_hours(code, note, expected):
    result = classify_shifts(_make_staff({9: code}, notes={9: note}))
    for field in ('E_full_days', 'E_half_days', 'N_full_days', 'N_half_days'):
        assert getattr(result, field) == expected.get(field, []), field
    assert result.review_flags == []   # 已是既定規則，不再提醒


def test_full_shift_whole_leave_is_excluded_without_flag():
    result = classify_shifts(_make_staff({1: 'E', 2: 'N'},
                                         notes={1: '補假8(16:00~24:00)', 2: '休假8(00:00~08:00)'}))
    assert result.E_full_days == []
    assert result.N_full_days == []
    assert result.review_flags == []


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
    # D021：林睿芸 4/26 N + 補假1(00:00~01:00) 實際上 7h → 大夜整改大夜半
    ('11504-N18W01排班表.xls', 49, 12, 29, 39_700),
    # D020 新增：E(請) 16-19、16-17:40 各 +1 小夜半；N( 請) 04-08 +1 大夜半
    # D021：人員K 10/8、人員M 10/21 整班 E 實際上不到 4h → 不計（小夜整 -2）
    ('11510-N08W01排班表.xlsx', 69,  3, 90, 82_500),
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


# D020／D021：各月提醒筆數基線（整班部分請假自 D021 起依工時判定，不再提醒；
# 只剩 11510 人員M 10/12 標示時數與時段不符）
@pytest.mark.parametrize('fixture_name, expected_flags', [
    ('11501-N19W01排班表.xls', []),
    ('11502-N19W01排班表.xls', []),
    ('11503-N19W01排班表.xls', []),
    ('11504-N18W01排班表.xls', []),
    ('11510-N08W01排班表.xlsx', [('人員M', 12)]),
])
def test_monthly_review_flags(fixture_name, expected_flags):
    from tests.conftest import PROJECT_ROOT
    schedule = parse_schedule(PROJECT_ROOT / 'tests' / 'fixtures' / fixture_name)
    flags = sorted((c.name, f.day) for c in map(classify_shifts, schedule.staff)
                   for f in c.review_flags)
    assert flags == expected_flags
