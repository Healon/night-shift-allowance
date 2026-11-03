"""Browser-side bridge: JSON-in/JSON-out wrappers around the pipeline.

Runs inside Pyodide. The worker unpacks src.zip into /app, puts /app on
sys.path, then imports this module. The uploaded schedule is written into
/work with its original filename preserved (parser extracts ward_code from
it). Error levels mirror web/app.py: ValueError → format (plain-language,
safe to show), anything else → unknown.
"""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from src.builder import build_roster
from src.classifier import classify_shifts
from src.parser import parse_schedule

TEMPLATE_PATH = Path('/app/template.xlsx')
WORK_DIR = Path('/work')
OUT_DIR = Path('/out')

_state: dict = {}


def _error(kind: str, message: str, trace: str = '') -> str:
    return json.dumps({'ok': False, 'kind': kind, 'message': message, 'trace': trace},
                      ensure_ascii=False)


def parse_and_classify(filename: str) -> str:
    """Parse /work/<filename>, classify every staff member, stash state for
    build(), and return a preview payload."""
    try:
        schedule = parse_schedule(WORK_DIR / filename)
        counts = [classify_shifts(s) for s in schedule.staff]
    except ValueError as exc:
        return _error('format', f'排班表格式不符：{exc}')
    except Exception as exc:  # unknown parsing failure
        return _error('unknown', f'排班表無法解析，請確認是否為正確的排班表 Excel。錯誤：{exc}',
                      traceback.format_exc())

    _state['schedule'] = schedule
    _state['counts'] = counts
    return json.dumps({
        'ok': True,
        'preview': {
            'year': schedule.year,
            'month': schedule.month,
            'ward_name': schedule.ward_name,
            'ward_code': schedule.ward_code,
            'staff': [
                {
                    'name': c.name,
                    'E_full': len(c.E_full_days),
                    'E_half': len(c.E_half_days),
                    'N_full': len(c.N_full_days),
                    'N_half': len(c.N_half_days),
                }
                for c in counts
            ],
            # D020：需護理長人工確認的班次（不影響計數）
            'review_flags': sorted(
                (
                    {'name': c.name, 'day': f.day, 'code': f.code, 'note': f.note,
                     'message': f.message}
                    for c in counts for f in c.review_flags
                ),
                key=lambda x: (x['day'], x['name']),
            ),
        },
    }, ensure_ascii=False)


def build(rates_json: str) -> str:
    """Build the roster xlsx with the given rates; returns the output path."""
    if 'schedule' not in _state:
        return _error('format', '尚未成功解析排班表，請先上傳。')
    try:
        rates = {k: int(v) for k, v in json.loads(rates_json).items()}
        OUT_DIR.mkdir(exist_ok=True)
        out = build_roster(
            _state['schedule'],
            _state['counts'],
            template_path=TEMPLATE_PATH,
            output_path=OUT_DIR,
            rates=rates,
        )
    except Exception as exc:
        return _error('unknown', f'清冊產出失敗：{exc}', traceback.format_exc())
    return json.dumps({'ok': True, 'path': str(out), 'filename': out.name}, ensure_ascii=False)
