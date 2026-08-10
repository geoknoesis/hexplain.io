"""Every .hx profile in the library must compile, and its output must conform.

The profile library is meant to grow one format at a time, indefinitely. That only works if
adding a profile cannot quietly break anything, so each one is compiled with the real HDL
compiler and the resulting Turtle is validated against the family's SHACL — the same two checks
a profile would get if someone hand-wrote it.

This is deliberately weaker than test_hx_roundtrip, which additionally holds nitf.hx against a
hand-written nitf.ttl triple by triple. A round-trip pair is expensive to maintain and only
worth it for a reference profile; everything else needs the cheap gate, or the library would
stop growing.

What this canNOT check is whether a profile is TRUE of the format. A description can compile,
conform, and still say a field is at the wrong offset. Only a parse against a real file shows
that, which is what the behavioural fixtures in hexplain-tools are for. A profile added here
without one is an assertion about a format, not a verified fact, and its header should say so.

Skip discipline mirrors test_hx_roundtrip exactly: a MISSING toolchain skips, a toolchain that
is present and fails is a FAIL. Silence that cannot be told from success is the one thing a
gate must never do.
"""

import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import rdflib
from pyshacl import validate

import specgraph

PROFILE_GLOB = "specification/profiles/*/*.hx"


def locate_toolchain():
    """(gradlew, tools_dir), or None with a printed reason when genuinely absent."""
    tools_dir = pathlib.Path(os.environ.get("HEXPLAIN_TOOLS", "../hexplain-tools"))
    if not tools_dir.is_dir():
        print(f"SKIP: hexplain-tools checkout not found at {tools_dir} "
              f"(set HEXPLAIN_TOOLS to override)")
        return None
    gradlew = tools_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not gradlew.exists():
        print(f"SKIP: {gradlew} not found -- hexplain-tools checkout looks incomplete")
        return None
    if shutil.which("java") is None:
        print("SKIP: no `java` on PATH -- cannot run the Gradle-based HDL compiler")
        return None
    return gradlew, tools_dir


def main():
    profiles = sorted(glob.glob(PROFILE_GLOB))
    if not profiles:
        print("SKIP: no .hx profiles in the library yet")
        return 0

    found = locate_toolchain()
    if found is None:
        return 0
    gradlew, tools_dir = found

    shapes = specgraph.shapes()
    ontologies = specgraph.ontology_paths()
    failures = []

    with tempfile.TemporaryDirectory(prefix="hx_library_") as tmp:
        for hx in profiles:
            name = pathlib.Path(hx).stem
            out = pathlib.Path(tmp) / f"{name}.ttl"
            args = f"{pathlib.Path(hx).resolve().as_posix()} -o {out.as_posix()}"
            cmd = [str(gradlew), "-q", "--offline", ":hdl:run", f"--args={args}"]
            try:
                proc = subprocess.run(cmd, cwd=str(tools_dir), capture_output=True,
                                      text=True, timeout=300, encoding="utf-8")
            except subprocess.TimeoutExpired:
                failures.append(f"{hx}: the compiler timed out after 300s")
                continue

            if proc.returncode != 0 or not out.exists():
                # The compiler prints its own diagnostics with source locations; they are far
                # more useful than anything this gate could add, so pass them through.
                diag = (proc.stdout + proc.stderr).strip()
                failures.append(f"{hx}: did not compile\n    " + diag.replace("\n", "\n    "))
                continue

            data = specgraph.load(ontologies)
            try:
                data.parse(data=out.read_text(encoding="utf-8"), format="turtle")
            except Exception as exc:  # noqa: BLE001 -- a malformed emit is a real failure
                failures.append(f"{hx}: compiled to Turtle that does not parse: {exc}")
                continue

            conforms, _, report = validate(data, shacl_graph=shapes, inference="none",
                                           advanced=True, meta_shacl=False)
            if not conforms:
                lines = [ln for ln in report.splitlines() if ln.strip().startswith("Message:")]
                failures.append(f"{hx}: compiled but does not conform\n    "
                                + "\n    ".join(lines[:8]))

    if failures:
        print(f"FAIL: {len(failures)} of {len(profiles)} profile(s):\n  " + "\n  ".join(failures))
        return 1
    print(f"PASS: {len(profiles)} profile(s) compile and conform")
    return 0


if __name__ == "__main__":
    sys.exit(main())
