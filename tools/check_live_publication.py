"""Read-only publication acceptance; a successful HTML fallback is a failure.

Every ontology IRI the reference manifest publishes is fetched with ``Accept: text/turtle`` and
compared with the canonical graph; every release manifest is fetched as JSON and compared with the
immutable snapshot. The record is written under ``specification/evidence/<date>/`` (today, UTC,
unless ``--date`` or ``--output`` says otherwise), so a run never overwrites an earlier day's
evidence by default. Not a gate: run by the live-publication workflow and by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rdflib import OWL, RDF, Graph
from rdflib.compare import isomorphic

ROOT = Path(__file__).resolve().parents[1]
RESPONSE_LIMIT = 4 * 1024 * 1024
REQUEST_TIMEOUT = 15

Case = tuple[str, str, Path]


def discover(base: str) -> list[Case]:
    """(URL, expected media type, local file) for every published ontology and release manifest."""
    cases: list[Case] = []
    for module in json.loads((ROOT / "specification/reference/manifest.json").read_text(encoding="utf-8")):
        for file in sorted((ROOT / module["module"]).glob("*.ttl")):
            graph = Graph().parse(file, format="turtle")
            for ontology in graph.subjects(RDF.type, OWL.Ontology):
                iri = str(ontology)
                if iri.startswith("https://hexplain.io/ns/"):
                    cases.append((base + iri.removeprefix("https://hexplain.io"), "text/turtle", file))
            if file.name.endswith("-doc.ttl"):
                # A generated annotation graph declares no ontology; it is published at its own path.
                cases.append((base + "/" + file.relative_to(ROOT).as_posix(), "text/turtle", file))
    for file in sorted((ROOT / "releases").glob("*/manifest.json")):
        cases.append((base + "/" + file.relative_to(ROOT).as_posix(), "application/json", file))
    assert cases, "No publication contracts discovered"
    return cases


def check(case: Case) -> dict[str, Any]:
    """Fetch one URL and compare it with its local counterpart; never raises."""
    url, media, file = case
    row: dict[str, Any] = dict(url=url, expected_media_type=media, passed=False)
    try:
        request = urllib.request.Request(url, headers={"Accept": media})
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            row.update(status=response.status, media_type=response.headers.get_content_type(), final_url=response.url)
            if response.status != 200:
                raise ValueError("Expected HTTP 200")
            body = response.read(RESPONSE_LIMIT + 1)
        if len(body) > RESPONSE_LIMIT:
            raise ValueError("Response exceeds publication check limit")
        row["response_sha256"] = hashlib.sha256(body).hexdigest()
        if row["media_type"] != media:
            raise ValueError("Incorrect negotiated media type; possible HTML fallback")
        if media == "application/json":
            if json.loads(body) != json.loads(file.read_text(encoding="utf-8")):
                raise ValueError("Published manifest differs from local immutable snapshot")
        elif not isomorphic(
            Graph().parse(data=body, format="turtle"), Graph().parse(data=file.read_bytes(), format="turtle")
        ):
            raise ValueError("Published RDF differs from canonical graph")
        row["passed"] = True
    except Exception as error:  # noqa: BLE001 - every failure is a recorded verdict, not a crash
        row["error"] = str(error)
    return row


def output_path(output: str | None, date: str | None) -> Path:
    """``--output`` as given, else the dated evidence directory (today, UTC)."""
    if output:
        return ROOT / output
    day = date or datetime.now(UTC).strftime("%Y-%m-%d")
    return ROOT / "specification/evidence" / day / "live-publication.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url", default="https://hexplain.io", help="Origin to check (default: the public origin)"
    )
    parser.add_argument("--date", help="Evidence directory date, YYYY-MM-DD (default: today, UTC)")
    parser.add_argument(
        "--output",
        help="Record path relative to the repository root "
        "(default: specification/evidence/<date>/live-publication.json)",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    cases = discover(base)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, cases))
    out = output_path(args.output, args.date)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(dict(checked_at=datetime.now(UTC).isoformat(), base_url=base, checks=results), indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(results, indent=2))
    where = out.relative_to(ROOT).as_posix() if out.is_relative_to(ROOT) else str(out)
    print(f"Recorded {len(results)} checks in {where}")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
