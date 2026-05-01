from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from src.builder import build_roster
from src.classifier import classify_shifts
from src.config import DEFAULT_OUTPUT_DIR
from src.parser import parse_schedule

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {'.xls', '.xlsx'}
XLSX_MEDIA = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
INDEX_HTML = Path(__file__).parent / 'templates' / 'index.html'

app = FastAPI(title='夜班費清冊產生器', docs_url=None, redoc_url=None)


@app.get('/', response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML.read_text(encoding='utf-8')


@app.get('/health')
def health() -> dict:
    return {'status': 'ok'}


@app.post('/upload')
async def upload(file: UploadFile = File(...)) -> FileResponse:
    original_name = file.filename or ''
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail='只支援 .xls / .xlsx 格式的排班表，請確認檔案類型後重新上傳。',
        )

    # Preserve original filename because parser extracts ward_code from stem.
    workdir = Path(tempfile.mkdtemp(prefix='nsa_'))
    input_path = workdir / original_name
    try:
        with input_path.open('wb') as buf:
            shutil.copyfileobj(file.file, buf)

        try:
            schedule = parse_schedule(input_path)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f'排班表格式不符：{exc}',
            ) from exc
        except Exception as exc:  # unknown parsing failure
            logger.exception('parse_schedule failed')
            raise HTTPException(
                status_code=400,
                detail=f'排班表無法解析，請確認是否為正確的排班表 Excel。錯誤：{exc}',
            ) from exc

        counts = [classify_shifts(s) for s in schedule.staff]

        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = build_roster(
            schedule,
            counts,
            output_path=DEFAULT_OUTPUT_DIR,
        )

        return FileResponse(
            path=str(output_path),
            media_type=XLSX_MEDIA,
            filename=output_path.name,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
