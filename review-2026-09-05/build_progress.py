"""Render the workstream ledger without turning pending acceptance into completion."""
from pathlib import Path
from html import escape
import json
OUT=Path(__file__).resolve().parent
d=json.loads((OUT/'implementation-progress.json').read_text(encoding='utf-8'))
page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Production acceptance implementation</title><style>body{font:17px/1.6 system-ui;max-width:1000px;margin:40px auto;padding:20px;color:#18323b}article{border-top:1px solid #ccd;padding:20px 0}a{color:#006d60}li{overflow-wrap:anywhere}</style><a href="production-readiness.html">Production-readiness review</a><h1>Implementation progress</h1><p>Updated working-tree readiness: specification 7.95/10; engine 8.20/10. See the <a href="production-review-20260908.html">8 September assessment</a> for scoring and scope. Local tooling and tests do not certify deployment or external review.</p><p><a href="../specification/validation/competency-trace.html">Semantic corpus traceability</a> | <a href="../specification/validation/security-mutations.html">Security mutation evidence</a> | <a href="staged-artifact-inventory.json">Staged artifact inventory</a> | <a href="implementation-progress.json">Evidence ledger</a></p><h2>Recorded evidence</h2><ul>'
for key,value in d['evidence'].items():page+='<li><b>'+escape(key)+':</b> '+escape(str(value))+'</li>'
page+='</ul>'
for task in d['tasks']:
    page+='<article><h2>'+escape(task['id'])+': '+escape(task['status'])+'</h2><p>'+escape(task['implemented'])+'</p><p><b>Remaining:</b> '+escape(task['remaining'])+'</p></article>'
(OUT/'implementation-progress.html').write_text(page,encoding='utf-8')
print('PASS: implementation ledger rendered')
