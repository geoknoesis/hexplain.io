"""Static defect checks over the offline tooling, using the shared lint contract."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

result = subprocess.run([sys.executable, '-m', 'ruff', 'check', 'tools', '--no-cache',
                         '--output-format', 'concise'],
                        cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
if result.returncode == 2 and 'No module named' in (result.stderr or ''):
    print('SKIP: ruff is not installed; add it from requirements.txt')
    raise SystemExit(0)
assert result.returncode == 0, (result.stdout or '') + (result.stderr or '')

count = len(list((ROOT/'tools').glob('*.py')))
print(f'PASS: {count} tool modules pass the shared lint contract (ruff.toml)')
