from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.parser import StaffRecord
from src.shift_hours import HALF_SHIFT_MIN_MINUTES, assess_leave, format_minutes, shift_minutes

E_FULL_CODES = ('E', '休;E', '國;E', 'E;休', 'E;國')
N_FULL_CODES = ('N', '休;N', '國;N', 'N;休', 'N;國')
LEAVE_CODES = {'E(請)': 'E', 'N(請)': 'N'}  # 部分請假的夜班代碼 → 班別
SHIFT_LABELS = {'E': '小夜', 'N': '大夜'}


@dataclass(frozen=True)
class ReviewFlag:
    """需要護理長人工確認的班次（D020）。不影響計數，只提醒。"""
    day: int
    code: str
    note: str
    message: str


@dataclass
class ShiftCount:
    emp_id: str
    name: str
    E_full_days: list[int] = field(default_factory=list)
    E_half_days: list[int] = field(default_factory=list)
    N_full_days: list[int] = field(default_factory=list)
    N_half_days: list[int] = field(default_factory=list)
    review_flags: list[ReviewFlag] = field(default_factory=list)


def _normalize_code(code: str) -> str:
    # 排班系統偶有 `N( 請)`、`N（請）` 等寫法，去空白並統一半形括號
    return re.sub(r'\s+', '', code or '').replace('（', '(').replace('）', ')')


def _anomaly_notes(assessment) -> list[str]:
    label = SHIFT_LABELS[assessment.shift]
    notes = []
    if assessment.outside_window:
        notes.append(f'請假時段有部分不在{label}時段內')
    for stated, actual in assessment.stated_mismatches:
        stated_txt = f'{stated:g}'
        notes.append(f'標示請假 {stated_txt} 小時，但時段實際為 {format_minutes(actual)}')
    return notes


def _anomaly_flag(a, level: str | None) -> str | None:
    """有異常（時段超出班別、標示時數不符）時組出提醒訊息，否則回傳 None。"""
    anomalies = _anomaly_notes(a)
    if not anomalies:
        return None
    label = SHIFT_LABELS[a.shift]
    result = f'已列入{label}半班' if level == 'half' else '未列入'
    return (f'{"；".join(anomalies)}。依時段計算實際上班 '
            f'{format_minutes(a.worked_minutes)}，{result}；請確認排班表是否需要修正')


def _classify_by_hours(shift: str, note: str, is_leave_code: bool) -> tuple[str | None, str | None]:
    """依實際工時判定班別等級（D020／D021），回傳（'full'／'half'／None, 需確認訊息或 None）。

    - 實際工時 = 班別時段 − 與請假時段重疊的部分（`src/shift_hours.py`）
    - 滿 8 小時 → 整班；≥ 4 小時 → 半班；未滿 4 小時 → 不計
    - `E(請)`／`N(請)` 本身就是請假班別，最多只算半班
    """
    a = assess_leave(shift, note)
    label = SHIFT_LABELS[shift]
    if a.worked_minutes is None:
        if is_leave_code:
            return None, f'{label}請假但下方未標示請假時段，無法計算實際工時，未列入；請確認是否整班請假'
        return 'full', None  # 整班代碼且無請假時段
    if not is_leave_code and a.worked_minutes == shift_minutes(shift):
        return 'full', None  # 請假時段與本班無關（例：白班時段），不提醒
    level = 'half' if a.worked_minutes >= HALF_SHIFT_MIN_MINUTES else None
    return level, _anomaly_flag(a, level)


def classify_shifts(staff: StaffRecord) -> ShiftCount:
    result = ShiftCount(emp_id=staff.emp_id, name=staff.name)
    nd_carryover_days: set[int] = set()
    for day in sorted(staff.daily_codes):
        raw_code = (staff.daily_codes[day] or '').strip()
        code = _normalize_code(raw_code)
        note = staff.below_notes.get(day, '') or ''
        flag_message: str | None = None
        # 來自前一日 ND 的大夜整班 carryover（D015），需在當日分類前先補上
        if day in nd_carryover_days:
            result.N_full_days.append(day)
        if code in N_FULL_CODES or code in E_FULL_CODES or code in LEAVE_CODES:
            # D020／D021：班別時段扣除下方請假時段後的實際工時決定等級
            # 整班代碼：滿 8h 整班／≥4h 半班／<4h 不計（整班請假即 0h，D010／D016）
            # E(請)／N(請)：≥4h 半班／<4h 不計
            if code in LEAVE_CODES:
                shift, is_leave_code = LEAVE_CODES[code], True
            else:
                shift, is_leave_code = ('N' if code in N_FULL_CODES else 'E'), False
            level, flag_message = _classify_by_hours(shift, note, is_leave_code)
            if level is not None:
                bucket = {('E', 'full'): result.E_full_days, ('E', 'half'): result.E_half_days,
                          ('N', 'full'): result.N_full_days, ('N', 'half'): result.N_half_days}
                bucket[(shift, level)].append(day)
        elif code in ('JD', '休;JD', '國;JD', 'JD;休', 'JD;國'):
            # JD 班 09-13/17-21，後段 17-21 共 4 小時屬小夜時段，視為小夜半班（D012）
            result.E_half_days.append(day)
        elif code in ('ED', '休;ED', '國;ED', 'ED;休', 'ED;國'):
            # ED 班 08-12/16-20，後段 16-20 共 4 小時屬小夜時段，視為小夜半班（D013）
            result.E_half_days.append(day)
        elif code in ('HD', '休;HD', '國;HD', 'HD;休', 'HD;國'):
            # HD 車班 08-20，後段 17-20 屬小夜時段，視為小夜半班（D014）
            result.E_half_days.append(day)
        elif code in ('FD', '休;FD', '國;FD', 'FD;休', 'FD;國'):
            # FD 班 08-12/17-21，後段 17-21 共 4 小時屬小夜時段，視為小夜半班（D018）
            result.E_half_days.append(day)
        elif code in ('ND', '休;ND', '國;ND', 'ND;休', 'ND;國'):
            # ND 跨日：當日 21-24 小夜半 + 隔日 00-08 大夜整（D015）
            # 月底 ND 因 day+1 不存在於 daily_codes，N_full carryover 自然不會被加上
            result.E_half_days.append(day)
            nd_carryover_days.add(day + 1)
        # all other codes are ignored (D, C, AD, BE, 休, 例, 請, ... )；未知代碼不提醒（D019）
        if flag_message:
            result.review_flags.append(ReviewFlag(day=day, code=raw_code, note=note,
                                                  message=flag_message))
    return result
