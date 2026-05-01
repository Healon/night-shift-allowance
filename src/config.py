from pathlib import Path

RATES = {
    'E_full': 400,
    'E_half': 200,
    'N_full': 600,
    'N_half': 300,
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / 'templates' / '衛生福利部夜班津貼示範.xlsx'
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / 'output'

HALF_SHIFT_MARKER = '21:00~24:00'
N_FULL_LEAVE_MARKER = '00:00~08:00'
TEMPLATE_STAFF_CAPACITY = 22
TEMPLATE_TOTAL_ROW = 224
