from __future__ import annotations

from dataclasses import dataclass, field

from src.config import E_FULL_LEAVE_MARKER, HALF_SHIFT_MARKERS, N_FULL_LEAVE_MARKER
from src.parser import StaffRecord


@dataclass
class ShiftCount:
    emp_id: str
    name: str
    E_full_days: list[int] = field(default_factory=list)
    E_half_days: list[int] = field(default_factory=list)
    N_full_days: list[int] = field(default_factory=list)
    N_half_days: list[int] = field(default_factory=list)


def classify_shifts(staff: StaffRecord) -> ShiftCount:
    result = ShiftCount(emp_id=staff.emp_id, name=staff.name)
    nd_carryover_days: set[int] = set()
    for day in sorted(staff.daily_codes):
        code = (staff.daily_codes[day] or '').strip()
        note = staff.below_notes.get(day, '') or ''
        # 來自前一日 ND 的大夜整班 carryover（D015），需在當日分類前先補上
        if day in nd_carryover_days:
            result.N_full_days.append(day)
        if code in ('N', '休;N', '國;N', 'N;休', 'N;國'):
            # 大夜整班整日請假（下列標 00:00~08:00）→ 不列入
            if N_FULL_LEAVE_MARKER in note:
                continue
            result.N_full_days.append(day)
        elif code in ('E', '休;E', '國;E', 'E;休', 'E;國'):
            # 小夜整班整日請假（下列標 16:00~24:00）→ 不列入（D016）
            if E_FULL_LEAVE_MARKER in note:
                continue
            result.E_full_days.append(day)
        elif code == 'E(請)':
            # E(請) 本身代表整班請假；若下方備註顯示僅部分時段請假
            # （21-24 / 20-24 / 16-20 之一）即代表實際上了一段小夜時段 → E_half（D017）
            if any(marker in note for marker in HALF_SHIFT_MARKERS):
                result.E_half_days.append(day)
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
        # all other codes are ignored (D, C, AD, BE, 休, 例, 請, ... )
    return result
