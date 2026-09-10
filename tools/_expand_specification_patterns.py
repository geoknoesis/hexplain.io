"""Expand private authoring patterns; never introduce public helper shapes.

The normative prefix comes from a template; the editorial annotation suffix stays
owned by the existing term-documentation generator. Default mode checks only.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORING = ROOT / 'authoring/specification'
TOKEN = re.compile(r'\{\{(constraint|datatype):([a-zA-Z0-9_]+)\}\}')


def load_catalogs():
    return tuple(json.loads((AUTHORING / p).read_text(encoding='utf-8')) for p in
                 ['manifest.json', 'constraint-patterns.json', 'primitive-types.json'])


def within(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path outside authoring workspace: {relative}')
    return path


def render(template, constraints, datatypes):
    def expand(match):
        kind, name = match.groups()
        if kind == 'constraint':
            text = constraints[name]['text']
        else:
            row = datatypes['presets'][name]
            if row['name'] != name:
                raise ValueError(f'Preset identity mismatch: {name}')
            text = datatypes['formats'][row['format']]
            fields = set(re.findall(r'@([a-z_]+)@', text))
            if fields != set(row) - {'format'}:
                raise ValueError(f'Missing or unexpected preset parameters: {name}')
            text = re.sub(r'@([a-z_]+)@', lambda m: row[m[1]], text)
        if '{{' in text or '}}' in text:
            raise ValueError('Recursive authoring substitutions are forbidden')
        return text
    expanded = TOKEN.sub(expand, template)
    if '{{' in expanded or '}}' in expanded:
        raise ValueError('Unknown or malformed authoring token')
    return expanded


def outputs():
    manifest, constraints, datatypes = load_catalogs()
    result = {}
    for target, source in manifest['templates'].items():
        path = within(ROOT, target)
        if path in result:
            raise ValueError(f'Duplicate output ownership: {target}')
        if not target.startswith('specification/') or not target.endswith('.ttl'):
            raise ValueError(f'Unexpected output: {target}')
        current = path.read_text(encoding='utf-8')
        marker = manifest['annotation_marker']
        if current.count(marker) > 1:
            raise ValueError(f'Ambiguous annotation boundary: {target}')
        suffix = marker + current.split(marker, 1)[1] if marker in current else ''
        template = within(AUTHORING, source).read_text(encoding='utf-8')
        if marker in template:
            raise ValueError(f'Template cannot own generated annotations: {source}')
        result[path] = render(template, constraints, datatypes) + suffix
    return result


def run(write=False):
    rendered = outputs()  # Resolve every input before writing any output.
    changed = [p for p, text in rendered.items() if p.read_text(encoding='utf-8') != text]
    if changed and not write:
        raise AssertionError('Stale generated specification: ' + ', '.join(str(p.relative_to(ROOT)) for p in changed))
    if write:
        for path in changed:
            path.write_text(rendered[path], encoding='utf-8')
    return len(rendered), len(changed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    count, changed = run(args.write)
    print(f'PASS: {count} authoring templates expanded; {changed} changed outputs')
