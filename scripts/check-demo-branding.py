from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCANNED = [ROOT / 'frontend' / 'src', ROOT / 'e2e', ROOT / 'docs', ROOT / 'README.md']
FORBIDDEN = [
    (re.compile(r'Y\s*Combinator', re.I), 'Y Combinator reference'),
    (re.compile(r'\bYC\b'), 'YC reference'),
    (re.compile(r'Evidue\s+Verify', re.I), 'retired Evidue Verify brand'),
    (re.compile(r'Customer\s+Verify', re.I), 'retired Customer Verify brand'),
]
violations=[]
for root in SCANNED:
    paths=[root] if root.is_file() else [p for p in root.rglob('*') if p.is_file() and p.suffix in {'.ts','.tsx','.css','.md','.html'}]
    for path in paths:
        text=path.read_text(errors='ignore')
        for pattern,label in FORBIDDEN:
            for match in pattern.finditer(text):
                line=text.count('\n',0,match.start())+1
                violations.append(f'{path.relative_to(ROOT)}:{line}: {label}: {match.group(0)!r}')
if violations:
    raise SystemExit('Branding validation failed:\n'+'\n'.join(violations))
print('Demo branding checks passed.')
