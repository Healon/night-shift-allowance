from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

EMP_ID_COL = 4
NAME_COL = 5
DATE_START_COL = 7  # day 1
EMP_ID_PATTERN = re.compile(r'^[A-Z]{2,4}\d{4,}$')
WARD_CODE_PATTERN = re.compile(r'(\d{5})-([A-Z0-9]+)')


@dataclass
class StaffRecord:
    emp_id: str
    name: str
    daily_codes: dict[int, str] = field(default_factory=dict)
    below_notes: dict[int, str] = field(default_factory=dict)


@dataclass
class ScheduleData:
    year: int
    month: int
    ward_name: str
    ward_code: str
    staff: list[StaffRecord]


def _cell(df: pd.DataFrame, r: int, c: int) -> str:
    if r >= df.shape[0] or c >= df.shape[1]:
        return ''
    v = df.iat[r, c]
    if pd.isna(v):
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _extract_metadata(df: pd.DataFrame) -> tuple[int, int, str]:
    row0 = df.iloc[0].dropna().tolist()
    # Expected sparse layout: [year, '年', month, '月', '排班表', '－', ward_name]
    if len(row0) < 7:
        raise ValueError(f'排班表第一列格式不符，無法解析年月與病房：{row0}')
    try:
        year = int(row0[0])
        month = int(row0[2])
    except (TypeError, ValueError) as exc:
        raise ValueError(f'排班表第一列年月欄位格式錯誤：{row0}') from exc
    ward_name = str(row0[6]).strip()
    return year, month, ward_name


def _extract_ward_code(xls_path: Path) -> str:
    match = WARD_CODE_PATTERN.search(xls_path.stem)
    if not match:
        raise ValueError(f'檔名無法解析病房代碼（期望如 11503-N19W01...）：{xls_path.name}')
    return match.group(2)


def _is_staff_row(df: pd.DataFrame, r: int) -> bool:
    emp = _cell(df, r, EMP_ID_COL)
    name = _cell(df, r, NAME_COL)
    return bool(emp) and bool(name) and EMP_ID_PATTERN.match(emp) is not None


def _pick_engine(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == '.xls':
        return 'xlrd'
    if suffix in ('.xlsx', '.xlsm'):
        return 'openpyxl'
    raise ValueError(f'不支援的 Excel 格式：{suffix}（僅支援 .xls / .xlsx）')


def parse_schedule(xls_path: Path) -> ScheduleData:
    xls_path = Path(xls_path)
    if not xls_path.exists():
        raise FileNotFoundError(f'找不到排班表：{xls_path}')

    engine = _pick_engine(xls_path)
    df = pd.read_excel(xls_path, sheet_name=0, header=None, engine=engine)
    year, month, ward_name = _extract_metadata(df)
    ward_code = _extract_ward_code(xls_path)

    days_in_month = calendar.monthrange(year + 1911, month)[1]  # ROC year → AD year
    last_date_col = DATE_START_COL + days_in_month - 1

    staff: list[StaffRecord] = []
    for r in range(3, df.shape[0]):
        if not _is_staff_row(df, r):
            continue
        emp_id = _cell(df, r, EMP_ID_COL)
        name = _cell(df, r, NAME_COL)
        record = StaffRecord(emp_id=emp_id, name=name)
        for day in range(1, days_in_month + 1):
            c = DATE_START_COL + day - 1
            if c > last_date_col:
                break
            record.daily_codes[day] = _cell(df, r, c)
            record.below_notes[day] = _cell(df, r + 1, c)
        staff.append(record)

    return ScheduleData(
        year=year,
        month=month,
        ward_name=ward_name,
        ward_code=ward_code,
        staff=staff,
    )
