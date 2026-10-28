"""Verify the delivered source/assets checksums using only the Python standard library."""
from pathlib import Path, PurePosixPath
import hashlib
import sys

def verify(root):
    root = Path(root).resolve(); failures = []; checked = set()
    for line in (root/'CHECKSUMS.sha256').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1); relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or name in checked:
            raise ValueError('Unsafe or duplicate checksum path')
        checked.add(name); path = root/name
        if not path.resolve().is_relative_to(root):raise ValueError('Checksum path escapes release directory')
        if not path.is_file():
            failures.append('MISSING '+name); continue
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(8*1024*1024), b''):h.update(block)
        if h.hexdigest() != expected:failures.append('CHANGED '+name)
    return len(checked), failures

if __name__ == '__main__':
    try:
        count, failures = verify(Path(__file__).parent)
        print('\n'.join(failures) if failures else f'PASS: {count} declared release files match SHA-256.')
        sys.exit(1 if failures else 0)
    except (OSError, ValueError) as exc:
        print(f'STOP: {exc}', file=sys.stderr);sys.exit(2)
