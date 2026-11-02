"""Exercise the actual Nginx configuration in a disposable local container.

Only what the site serves is mounted into the container: specification/, releases/ and the
published root files (index.html, robots.txt, sitemap.xml), each read-only. The repository root
itself -- .git, the tooling, evidence that is not published -- is never exposed to the server.
Declared as the ``docker`` gate class in tools/gates.json; the site workflow runs it with
``python tools/run_gates.py --class docker``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from _publication import ROOT, routes
from rdflib import Graph
from rdflib.compare import isomorphic

#: Published root files; the directories specification/ and releases/ are mounted whole.
ROOT_FILES = ["index.html", "robots.txt", "sitemap.xml"]
SERVE = "/srv/hexplain"
READINESS_ATTEMPTS = 50
READINESS_PAUSE = 0.2
REQUEST_TIMEOUT = 10


def mounts() -> list[str]:
    """Read-only bind mounts for exactly the published tree."""
    sources: list[tuple[Path, str]] = [
        (ROOT / "specification", f"{SERVE}/specification"),
        (ROOT / "releases", f"{SERVE}/releases"),
        *((ROOT / name, f"{SERVE}/{name}") for name in ROOT_FILES if (ROOT / name).is_file()),
        (ROOT / "deployment/publication.conf", "/etc/nginx/conf.d/default.conf"),
    ]
    arguments = []
    for source, target in sources:
        arguments += ["--mount", f"type=bind,source={source},target={target},readonly"]
    return arguments


def fetch(url: str, accept: str | None = None) -> tuple[str, bytes]:
    """Content type and body of a GET, bounded by REQUEST_TIMEOUT."""
    headers = {"Accept": accept} if accept else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=REQUEST_TIMEOUT) as response:
        return response.headers.get_content_type(), response.read()


def wait_ready(base: str) -> None:
    """Poll the server until it answers; fail loudly instead of running the checks against nothing."""
    last: Exception | None = None
    for _attempt in range(READINESS_ATTEMPTS):
        try:
            fetch(base + "/")
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
            last = error
            time.sleep(READINESS_PAUSE)
    raise RuntimeError(
        f"Nginx at {base} did not become ready within {READINESS_ATTEMPTS * READINESS_PAUSE:.0f}s: {last}"
    )


def check_routes(base: str) -> list[str]:
    checks = []
    for route, file in sorted(routes().items()):
        media, body = fetch(base + route, "text/turtle")
        assert media == "text/turtle", route
        assert isomorphic(
            Graph().parse(data=body, format="turtle"), Graph().parse(data=file.read_bytes(), format="turtle")
        ), route
        checks.append(route)
    for manifest in sorted((ROOT / "releases").glob("*/manifest.json")):
        media, body = fetch(base + "/" + manifest.relative_to(ROOT).as_posix())
        assert media == "application/json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert json.loads(body) == data
        _, archive = fetch(base + "/" + (manifest.parent / data["archive"]).relative_to(ROOT).as_posix())
        assert hashlib.sha256(archive).hexdigest() == data["sha256"]
        checks.append(manifest.relative_to(ROOT).as_posix())
    try:
        fetch(base + "/ns/unknown-review-probe")
        raise AssertionError("Unknown namespace did not return 404")
    except urllib.error.HTTPError as error:
        assert error.code == 404
    # Nothing outside the published tree is reachable: the tooling is not mounted at all.
    try:
        fetch(base + "/tools/run_gates.py")
        raise AssertionError("The tooling is reachable through the server")
    except urllib.error.HTTPError as error:
        assert error.code == 404
    return checks


def main() -> int:
    image = (ROOT / "deployment/nginx-image.txt").read_text(encoding="utf-8").strip()
    command = ["docker", "run", "--rm", "-d", "-p", "127.0.0.1::8080", *mounts(), image]
    container = subprocess.check_output(command, text=True, timeout=300).strip()
    try:
        binding = subprocess.check_output(["docker", "port", container, "8080/tcp"], text=True, timeout=30).strip()
        base = "http://" + binding
        wait_ready(base)
        checks = check_routes(base)
        out = ROOT / ".gate-results/local-publication.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(
            json.dumps(dict(image=image, passed=True, checks=checks, unknown_namespace_status=404), indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"PASS: actual Nginx image/config, {len(checks)} ontology/version/release checks, archive bytes, "
            "unknown-IRI 404 and nothing outside the published tree"
        )
    finally:
        subprocess.run(["docker", "stop", container], check=True, capture_output=True, timeout=120)
    return 0


if __name__ == "__main__":
    sys.exit(main())
