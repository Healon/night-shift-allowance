from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_XLS = PROJECT_ROOT / 'tests' / 'fixtures' / '11503-N19W01排班表.xls'
TEMPLATE_XLSX = PROJECT_ROOT / 'templates' / '衛生福利部夜班津貼示範.xlsx'


@pytest.fixture(scope='session')
def fixture_xls_path() -> Path:
    assert FIXTURE_XLS.exists(), f'Missing fixture: {FIXTURE_XLS}'
    return FIXTURE_XLS


@pytest.fixture(scope='session')
def template_xlsx_path() -> Path:
    assert TEMPLATE_XLSX.exists(), f'Missing template: {TEMPLATE_XLSX}'
    return TEMPLATE_XLSX
