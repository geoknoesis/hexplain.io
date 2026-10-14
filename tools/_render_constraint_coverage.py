"""Render the measured ledger without upgrading diagnostic evidence to acceptance.

The page states every obligation with how often it was seen to pass, to fail and to pass on no
values. The cases behind each count are not written out row by row -- two hundred thousand
names made the page as large as the ledger it summarises -- but held once, as the ledger holds
them, and filled into a row when its list is opened. The counts, the filter and the link to
the ledger need no script.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from _constraint_coverage import FIELDS, read_ledger
from _site_inventory import with_print_link

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "specification/validation"
PAGE = OUT / "constraint-coverage.html"
LABELS = {"passed": "Success", "failed": "Failure", "empty_value_passes": "Empty-value success"}
HEAD = (
    '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
    'content="width=device-width,initial-scale=1"><title>Constraint-level '
    "coverage</title><style>body{max-width:1200px;margin:30px auto;padding:20px;font:16px/1.6 "
    "system-ui;color:#18323b}table{width:100%;border-collapse:collapse;table-layout:fixed}"
    "th,td{padding:10px;border-bottom:1px solid #ccd;text-align:left;vertical-align:top;overflow-wrap:anywhere}"
    "input{font:inherit;padding:6px}a{color:#006657}summary{cursor:pointer}</style><main><h1>Constraint-level "
    "coverage</h1>"
)
SCRIPT = (
    "const "
    "q=document.getElementById('query'),g=document.getElementById('gaps'),"
    "rows=[...document.querySelectorAll('tbody tr')];function filter(){let n=0;for(const r of rows){"
    "r.hidden=(g.checked&&r.dataset.covered==='true')||"
    "!r.textContent.toLowerCase().includes(q.value.toLowerCase());if(!r.hidden)n++;}"
    "document.getElementById('count').textContent=n+' obligations "
    "shown';}q.addEventListener('input',filter);g.addEventListener('change',filter);filter();"
    # A list of cases is written into its row the first time the row's list is opened.
    "for(const d of document.querySelectorAll('details[data-cases]')){d.addEventListener('toggle',()=>{"
    "if(!d.open||d.dataset.filled)return;d.dataset.filled='1';for(const i of d.dataset.cases.split(' ')){"
    "if(i==='')continue;d.append(document.createTextNode(names[+i]),document.createElement('br'));}});}"
)


def _row(row: dict[str, Any], index: dict[str, int]) -> str:
    """One obligation's table row; each list of cases is given as indices into the page's name table."""
    cells = (
        f'<tr data-covered="{str(row["two_sided_evaluation"]).lower()}"><td>'
        + escape(row["source"])
        + "<br>"
        + escape(", ".join(row.get("owners", [])))
        + "<br>"
        + escape(row.get("path", ""))
        + "<details><summary>Shape and stable obligation ID</summary>"
        + escape(row["shape"])
        + "<br>"
        + escape(row["id"])
        + "</details></td><td>"
        + escape(row["component"].split("#")[-1])
        + "<details><summary>Parameters</summary>"
        + escape(json.dumps(row["parameters"], ensure_ascii=False))
        + "</details></td><td>"
    )
    for name in FIELDS:
        cases = " ".join(str(index[case]) for case in row[name])
        cells += f'<details data-cases="{cases}"><summary>{LABELS[name]}: {len(row[name])}</summary></details>'
    return cells + "</td></tr>"


def render() -> str:
    """The coverage page for the ledger on disk."""
    e = read_ledger()
    s = e["summary"]
    status = (
        "Every inventoried component has two-sided evaluation evidence."
        if e["complete"]
        else "Component coverage is not complete."
    )
    names = sorted({case for row in e["constraints"] for name in FIELDS for case in row[name]})
    index = {name: position for position, name in enumerate(names)}
    parts = [
        HEAD,
        f"<p><strong>{status}</strong> {s['components']} component obligations; {s['two_sided']} have observed "
        f"success and failure; {s['never_evaluated']} were never evaluated in these {s['cases']} retained validation "
        "calls.</p>",
        "<p>"
        + escape(e["scope"])
        + '</p><p><a href="constraint-coverage.json">Exact obligations, input hashes and case '
        "references</a>. Open a count below to list its cases.</p><p><label>Filter by module, shape or component "
        '<input id="query" '
        'type="search"></label> <label><input id="gaps" type="checkbox" checked> Show gaps only</label></p><p '
        'id="count" role="status"></p><table><thead><tr><th>Source / shape</th><th>Component / '
        "parameters</th><th>Observed cases</th></tr></thead><tbody>",
    ]
    parts.extend(_row(row, index) for row in e["constraints"])
    # "</" cannot occur inside a script element's text, so it is written "<\/" in the name table.
    table = json.dumps(names, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    parts.append(f"</tbody></table><script>const names={table};{SCRIPT}</script></main></html>")
    return with_print_link(PAGE, "".join(parts))


def main() -> int:
    PAGE.write_text(render(), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
