from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.builder import build_roster
from src.classifier import classify_shifts
from src.config import DEFAULT_OUTPUT_DIR
from src.parser import parse_schedule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='夜班費清冊產生器 — 從排班表 .xls 產出衛福部格式清冊 .xlsx',
    )
    parser.add_argument('input', type=Path, help='排班表 .xls 路徑')
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f'輸出目錄（預設 {DEFAULT_OUTPUT_DIR}）',
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f'[ERROR] 找不到輸入檔：{args.input}', file=sys.stderr)
        return 2

    try:
        schedule = parse_schedule(args.input)
    except ValueError as exc:
        print(f'[ERROR] 排班表格式不符：{exc}', file=sys.stderr)
        return 3

    counts = [classify_shifts(s) for s in schedule.staff]
    out = build_roster(schedule, counts, output_path=args.output)

    total = sum(
        len(c.E_full_days) * 400
        + len(c.E_half_days) * 200
        + len(c.N_full_days) * 600
        + len(c.N_half_days) * 300
        for c in counts
    )
    print(
        f'[OK] {schedule.year}年{schedule.month}月 {schedule.ward_name} '
        f'({len(schedule.staff)}人) 預估總額 NT$ {total:,}'
    )
    print(f'[OK] 產出 → {out}')

    flags = [(c.name, f) for c in counts for f in c.review_flags]
    if flags:
        print(f'[注意] 共 {len(flags)} 筆班次需要人工確認（D020）：')
        for name, f in sorted(flags, key=lambda x: (x[1].day, x[0])):
            print(f'  - {schedule.month}/{f.day} {name} [{f.code}] {f.note}')
            print(f'      {f.message}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
