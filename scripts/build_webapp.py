"""Assemble the static web app into dist/ with pinned, self-hosted assets.

Everything the browser needs at runtime (Pyodide core, wheels, src, template)
is vendored into dist/ — the deployed site makes zero external requests.
Versions are pinned here; upgrading Pyodide or any wheel is an explicit edit
followed by `node scripts/test_wasm.mjs`.

Usage: python3 scripts/build_webapp.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = PROJECT_ROOT / 'webapp'
DIST_DIR = PROJECT_ROOT / 'dist'
CACHE_DIR = PROJECT_ROOT / '.vendor-cache'
TEMPLATE_SRC = PROJECT_ROOT / 'templates' / '衛生福利部夜班津貼示範.xlsx'

PYODIDE_VERSION = '314.0.2'
CDN = f'https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/'
# Core files carry no published per-file hash; they are immutable per version on the CDN.
# pyodide.mjs (ESM loader): the worker is a module worker — Pyodide 314 dropped
# classic-worker (importScripts) support.
CORE_FILES = ('pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip')
RUNTIME_PACKAGES = ('pandas', 'xlrd')  # wheel closure resolved from the lockfile

# Pure-python wheels absent from the Pyodide distribution; pinned by version + sha256.
# Download URL is discovered via the PyPI JSON API and verified against the pin.
# Keys and depends use PEP 503 normalized names (lockfile convention);
# imports use the actual import names.
PYPI_WHEELS = {
    'openpyxl': {
        'version': '3.1.5',
        'file_name': 'openpyxl-3.1.5-py2.py3-none-any.whl',
        'sha256': '5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2',
        'imports': ['openpyxl'],
        'depends': ['et-xmlfile'],
    },
    'et-xmlfile': {
        'version': '2.0.0',
        'file_name': 'et_xmlfile-2.0.0-py3-none-any.whl',
        'sha256': '7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f536151b2caa',
        'imports': ['et_xmlfile'],
        'depends': [],
    },
}

WEBAPP_FILES = ('index.html', 'app.js', 'worker.js')
FORBIDDEN_PATH_PARTS = ('fixtures', '排班表')


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch_cached(url: str, file_name: str, sha256: str | None) -> Path:
    """Download url into the cache (once); verify sha256 when pinned."""
    CACHE_DIR.mkdir(exist_ok=True)
    dest = CACHE_DIR / file_name
    if not dest.exists():
        print(f'  下載 {file_name} …')
        with urllib.request.urlopen(url, timeout=120) as resp, dest.open('wb') as f:
            shutil.copyfileobj(resp, f)
    if sha256 and sha256_of(dest) != sha256:
        dest.unlink()
        raise SystemExit(f'sha256 不符：{file_name}（已刪除快取，請重跑）')
    return dest


def pypi_wheel_url(name: str, spec: dict) -> str:
    api = f'https://pypi.org/pypi/{name}/{spec["version"]}/json'
    with urllib.request.urlopen(api, timeout=60) as resp:
        data = json.load(resp)
    for entry in data['urls']:
        if entry['filename'] == spec['file_name']:
            if entry['digests']['sha256'] != spec['sha256']:
                raise SystemExit(f'PyPI 上 {spec["file_name"]} 的 sha256 與釘點不符，中止')
            return entry['url']
    raise SystemExit(f'PyPI 找不到 {spec["file_name"]}')


def lock_closure(lock: dict, roots: tuple[str, ...]) -> list[str]:
    """Return lockfile package keys for roots plus transitive depends."""
    packages = lock['packages']
    norm = lambda n: n.lower().replace('_', '-').replace('.', '-')
    by_norm = {norm(k): k for k in packages}
    need: list[str] = []

    def visit(name: str) -> None:
        key = by_norm.get(norm(name))
        if key is None:
            raise SystemExit(f'lockfile 中找不到套件：{name}')
        if key in need:
            return
        need.append(key)
        for dep in packages[key].get('depends', []):
            visit(dep)

    for r in roots:
        visit(r)
    return need


def patch_lock(lock: dict) -> dict:
    """Add the PyPI wheels as regular lockfile entries so runtime uses one
    mechanism for every package: loadPackage(['pandas', 'xlrd', 'openpyxl'])."""
    sample = lock['packages']['six']  # canonical pure-python entry shape
    for name, spec in PYPI_WHEELS.items():
        entry = {k: v for k, v in sample.items()}
        entry.update(
            name=name,
            version=spec['version'],
            file_name=spec['file_name'],
            sha256=spec['sha256'],
            imports=spec['imports'],
            depends=spec['depends'],
        )
        lock['packages'][name] = entry
    return lock


def build_src_zip(dest: Path) -> list[str]:
    members: list[str] = []
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zf:
        for py in sorted((PROJECT_ROOT / 'src').glob('*.py')):
            zf.write(py, f'src/{py.name}')
            members.append(f'src/{py.name}')
        zf.write(WEBAPP_DIR / 'bridge.py', 'bridge.py')
        members.append('bridge.py')
    return members


def git_version() -> str:
    try:
        rev = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return rev + ('-dirty' if dirty else '')
    except Exception:
        return 'unknown'


def main() -> None:
    for f in WEBAPP_FILES + ('bridge.py',):
        if not (WEBAPP_DIR / f).exists():
            raise SystemExit(f'缺少 webapp/{f}')
    if not TEMPLATE_SRC.exists():
        raise SystemExit(f'缺少範本：{TEMPLATE_SRC}')

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    vendor_pyodide = DIST_DIR / 'vendor' / 'pyodide'
    vendor_pyodide.mkdir(parents=True)

    written: set[str] = set()

    def emit(dest: Path, src: Path | None = None, data: bytes | None = None) -> None:
        if src is not None:
            shutil.copyfile(src, dest)
        else:
            dest.write_bytes(data or b'')
        written.add(dest.relative_to(DIST_DIR).as_posix())

    print('== 靜態網頁建置 ==')
    print('[1/6] Pyodide 核心')
    for f in CORE_FILES:
        emit(vendor_pyodide / f, src=fetch_cached(CDN + f, f, None))

    print('[2/6] lockfile 與 wheels')
    lock_path = fetch_cached(CDN + 'pyodide-lock.json', f'pyodide-lock-{PYODIDE_VERSION}.json', None)
    lock = json.loads(lock_path.read_text())
    wheel_keys = lock_closure(lock, RUNTIME_PACKAGES)
    for key in wheel_keys:
        pkg = lock['packages'][key]
        emit(vendor_pyodide / pkg['file_name'],
             src=fetch_cached(CDN + pkg['file_name'], pkg['file_name'], pkg['sha256']))
    for name, spec in PYPI_WHEELS.items():
        emit(vendor_pyodide / spec['file_name'],
             src=fetch_cached(pypi_wheel_url(name, spec), spec['file_name'], spec['sha256']))
    lock = patch_lock(lock)
    emit(vendor_pyodide / 'pyodide-lock.json',
         data=json.dumps(lock, ensure_ascii=False).encode('utf-8'))

    print('[3/6] 前端靜態檔')
    for f in WEBAPP_FILES:
        emit(DIST_DIR / f, src=WEBAPP_DIR / f)

    print('[4/6] src.zip 與範本')
    src_zip = DIST_DIR / 'vendor' / 'src.zip'
    members = build_src_zip(src_zip)
    written.add(src_zip.relative_to(DIST_DIR).as_posix())
    allowed_members = {f'src/{p.name}' for p in (PROJECT_ROOT / 'src').glob('*.py')} | {'bridge.py'}
    if not set(members) <= allowed_members:
        raise SystemExit(f'src.zip 含未預期成員：{set(members) - allowed_members}')
    emit(DIST_DIR / 'vendor' / 'template.xlsx', src=TEMPLATE_SRC)

    print('[5/6] version.json')
    version = {'version': git_version(), 'built': date.today().isoformat()}
    emit(DIST_DIR / 'version.json', data=json.dumps(version).encode('utf-8'))

    print('[6/6] 白名單檢查')
    actual = {p.relative_to(DIST_DIR).as_posix() for p in DIST_DIR.rglob('*') if p.is_file()}
    if actual != written:
        raise SystemExit(f'dist 檔案清單與預期不符：多出 {actual - written}，缺少 {written - actual}')
    for rel in actual:
        if rel.endswith('.xls') or any(part in rel for part in FORBIDDEN_PATH_PARTS):
            raise SystemExit(f'dist 含禁止檔案：{rel}')

    total = sum((DIST_DIR / rel).stat().st_size for rel in actual)
    largest = sorted(actual, key=lambda rel: (DIST_DIR / rel).stat().st_size, reverse=True)[:5]
    print(f'完成：{len(actual)} 個檔案，共 {total / 1024 / 1024:.1f} MB（未壓縮），版本 {version["version"]}')
    for rel in largest:
        print(f'  {(DIST_DIR / rel).stat().st_size / 1024:8.0f} KB  {rel}')


if __name__ == '__main__':
    sys.exit(main())
