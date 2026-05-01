from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from web.app import app

client = TestClient(app)


def test_index_returns_html():
    r = client.get('/')
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('text/html')
    assert '夜班費清冊產生器' in r.text


def test_health_returns_ok():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json() == {'status': 'ok'}


def test_upload_valid_xls_returns_xlsx(fixture_xls_path):
    with open(fixture_xls_path, 'rb') as f:
        r = client.post(
            '/upload',
            files={
                'file': (
                    fixture_xls_path.name,
                    f,
                    'application/vnd.ms-excel',
                )
            },
        )
    assert r.status_code == 200
    assert r.headers['content-type'].startswith(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Content-Disposition should carry the Chinese filename (URL-encoded)
    cd = r.headers.get('content-disposition', '')
    assert 'attachment' in cd
    decoded = unquote(cd)
    assert '11病房' in decoded
    assert '11503-N19W01' in decoded
    # Actual xlsx payload > 10KB
    assert len(r.content) > 10_000
    # Confirm it's a real xlsx (PK zip magic bytes)
    assert r.content[:2] == b'PK'


def test_upload_wrong_extension_returns_400():
    r = client.post(
        '/upload',
        files={'file': ('fake.pdf', b'%PDF-1.4 fake', 'application/pdf')},
    )
    assert r.status_code == 400
    detail = r.json()['detail']
    assert '只支援' in detail
    assert '.xls' in detail


def test_upload_corrupt_file_returns_400(tmp_path):
    bad = tmp_path / 'broken.xls'
    bad.write_bytes(b'definitely not a real xls file')
    with open(bad, 'rb') as f:
        r = client.post(
            '/upload',
            files={'file': ('broken.xls', f, 'application/vnd.ms-excel')},
        )
    assert r.status_code == 400
    detail = r.json()['detail']
    assert '排班表格式不符' in detail or '無法解析' in detail


def test_upload_missing_file_returns_422():
    # No file field at all → FastAPI validation error
    r = client.post('/upload')
    assert r.status_code == 422


@pytest.mark.parametrize('fixture_name, expected_total', [
    ('11501-N19W01排班表.xls', 88_200),
    ('11502-N19W01排班表.xls', 70_400),
    ('11503-N19W01排班表.xls', 87_200),
])
def test_upload_three_months_end_to_end(fixture_name, expected_total):
    """Upload each month's fixture → download xlsx → verify the embedded
    G:P day cells sum to the known baseline when multiplied by rates."""
    from openpyxl import load_workbook
    from io import BytesIO

    fixture = Path(__file__).parent / 'fixtures' / fixture_name
    with open(fixture, 'rb') as f:
        r = client.post(
            '/upload',
            files={'file': (fixture_name, f, 'application/vnd.ms-excel')},
        )
    assert r.status_code == 200, r.text
    wb = load_workbook(BytesIO(r.content), data_only=False)
    ws = wb.active
    total = 0
    for idx in range(23):
        base = 4 + idx * 10
        def cnt(rs, re):
            return sum(
                1
                for rr in range(rs, re + 1)
                for c in range(7, 17)
                if ws.cell(rr, c).value not in (None, '')
            )
        total += (
            cnt(base, base + 2) * 400
            + cnt(base + 3, base + 4) * 200
            + cnt(base + 5, base + 7) * 600
        )
    assert total == expected_total
