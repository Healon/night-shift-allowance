"""D020：以「班別時段扣除請假時段後的實際工時」判定夜班津貼。

規格（Lin 於 2026-11-03 裁定）：
- 小夜班時段 16:00–24:00、大夜班時段 00:00–08:00，各 8 小時
- 實際工時 = 班別時段 − 下方備註請假時段與班別時段的重疊部分（多段請假取聯集，不重複扣）
- `E(請)` / `N(請)`：實際工時 ≥ 4 小時 → 小夜半班 / 大夜半班；未滿 4 小時 → 不計
- 判定只看備註中的時段，不看「補假3」「休假4」這類時數數字；
  兩者不一致時列為需人工確認（例：休假4(16:00~17:40) 實際只請 1 小時 40 分）

本模組只負責時間計算與異常偵測，班別歸類由 `src/classifier.py` 決定。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MINUTES_PER_HOUR = 60
SHIFT_WINDOWS: dict[str, tuple[int, int]] = {
    'E': (16 * MINUTES_PER_HOUR, 24 * MINUTES_PER_HOUR),  # 小夜 16:00–24:00
    'N': (0, 8 * MINUTES_PER_HOUR),                      # 大夜 00:00–08:00
}
HALF_SHIFT_MIN_MINUTES = 4 * MINUTES_PER_HOUR

# 接受 21:00~24:00、1600-1740、16:00～19:00 等寫法
_RANGE = re.compile(r'(\d{1,2}):?(\d{2})\s*[~～\-－]\s*(\d{1,2}):?(\d{2})')
# 時段前緊鄰的時數，例如「補假3(」「休假4（」
_STATED_HOURS_BEFORE = re.compile(r'(\d+(?:\.\d+)?)\s*[(（]\s*$')


def _to_minutes(hour: str, minute: str) -> int | None:
    h, m = int(hour), int(minute)
    if m >= 60 or h > 24 or (h == 24 and m != 0):
        return None
    return h * MINUTES_PER_HOUR + m


def parse_leave_ranges(note: str) -> list[tuple[int, int]]:
    """從備註擷取所有請假時段，回傳 [(起, 迄)]（自 00:00 起算的分鐘數）。

    不合理的時間（25:00、16:70、迄早於起）直接略過，視同沒有該時段。
    """
    ranges = []
    for m in _RANGE.finditer(note or ''):
        start = _to_minutes(m.group(1), m.group(2))
        end = _to_minutes(m.group(3), m.group(4))
        if start is None or end is None or start >= end:
            continue
        ranges.append((start, end))
    return ranges


def _stated_hour_mismatches(note: str) -> list[tuple[float, int]]:
    """回傳 [(標示時數, 時段實際分鐘)]，只列出兩者不一致者。"""
    mismatches = []
    for m in _RANGE.finditer(note or ''):
        start = _to_minutes(m.group(1), m.group(2))
        end = _to_minutes(m.group(3), m.group(4))
        stated = _STATED_HOURS_BEFORE.search(note[:m.start()])
        if start is None or end is None or start >= end or stated is None:
            continue
        stated_hours = float(stated.group(1))
        if round(stated_hours * MINUTES_PER_HOUR) != end - start:
            mismatches.append((stated_hours, end - start))
    return mismatches


def _overlap_minutes(window: tuple[int, int], ranges: list[tuple[int, int]]) -> int:
    """請假時段與班別時段重疊的總分鐘數（先取聯集，避免重複扣除）。"""
    lo, hi = window
    clipped = sorted((max(s, lo), min(e, hi)) for s, e in ranges if min(e, hi) > max(s, lo))
    total, cur_s, cur_e = 0, None, None
    for s, e in clipped:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


@dataclass(frozen=True)
class LeaveAssessment:
    shift: str                                  # 'E' 或 'N'
    ranges: list[tuple[int, int]] = field(default_factory=list)
    worked_minutes: int | None = None           # 無請假時段時為 None
    outside_window: bool = False                # 有請假時段落在班別時段之外
    stated_mismatches: list[tuple[float, int]] = field(default_factory=list)

    @property
    def has_range(self) -> bool:
        return bool(self.ranges)

    @property
    def leave_minutes(self) -> int:
        """請假時段與班別時段重疊的分鐘數。"""
        return 0 if self.worked_minutes is None else shift_minutes(self.shift) - self.worked_minutes

    @property
    def stated_hours_mismatch(self) -> bool:
        return bool(self.stated_mismatches)


def shift_minutes(shift: str) -> int:
    lo, hi = SHIFT_WINDOWS[shift]
    return hi - lo


def assess_leave(shift: str, note: str) -> LeaveAssessment:
    """計算某班別（'E' 小夜／'N' 大夜）在該備註下的實際工時與異常。"""
    window = SHIFT_WINDOWS[shift]
    ranges = parse_leave_ranges(note)
    if not ranges:
        return LeaveAssessment(shift=shift)
    lo, hi = window
    return LeaveAssessment(
        shift=shift,
        ranges=ranges,
        worked_minutes=shift_minutes(shift) - _overlap_minutes(window, ranges),
        outside_window=any(s < lo or e > hi for s, e in ranges),
        stated_mismatches=_stated_hour_mismatches(note),
    )


def format_minutes(minutes: int) -> str:
    """240 → '4 小時'；100 → '1 小時 40 分'；30 → '30 分'。"""
    h, m = divmod(minutes, MINUTES_PER_HOUR)
    if h and m:
        return f'{h} 小時 {m} 分'
    if h:
        return f'{h} 小時'
    return f'{m} 分'
