from __future__ import annotations

from dataclasses import dataclass, field

from src.config import HALF_SHIFT_MARKER, N_FULL_LEAVE_MARKER
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
    for day in sorted(staff.daily_codes):
        code = (staff.daily_codes[day] or '').strip()
        note = staff.below_notes.get(day, '') or ''
        if code in ('N', '休;N', '國;N', 'N;休', 'N;國'):
            # 大夜整班整日請假（下列標 00:00~08:00）→ 不列入
            if N_FULL_LEAVE_MARKER in note:
                continue
            result.N_full_days.append(day)
        elif code in ('E', '休;E', '國;E', 'E;休', 'E;國'):
            result.E_full_days.append(day)
        elif code == 'E(請)':
            if HALF_SHIFT_MARKER in note:
                result.E_half_days.append(day)
        elif code in ('JD', '休;JD', '國;JD', 'JD;休', 'JD;國'):
            # JD 班 09-13/17-21，後段 17-21 共 4 小時屬小夜時段，視為小夜半班（D012）
            result.E_half_days.append(day)
        elif code in ('ED', '休;ED', '國;ED', 'ED;休', 'ED;國'):
            # ED 班 08-12/16-20，後段 16-20 共 4 小時屬小夜時段，視為小夜半班（D013）
            result.E_half_days.append(day)
        # all other codes are ignored (D, C, AD, BE, 休, 例, 請, ... )
    return result
