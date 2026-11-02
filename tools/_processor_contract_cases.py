"""Regression probes for processor failures, bounded execution and complete reports."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import psutil
from _gate_process import _Reader


def command(script: Path) -> str:
    return f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}" {{case}} {{out}} {{err}}'


def artifact_problems(root: Path) -> None:
    import run_suite

    case = root / "case"
    case.mkdir()
    (case / "manifest.json").write_text('{"class":"physical-parser"}', encoding="utf-8", newline="\n")
    (case / "expected.json").write_text('{"n":1}', encoding="utf-8", newline="\n")
    script = root / "processor.py"

    def result(body: str) -> str:
        script.write_text("import sys,pathlib\n" + body, encoding="utf-8", newline="\n")
        return run_suite.run_case(case, command(script), None, 5)[0]

    assert result("pathlib.Path(sys.argv[2]).write_text('{\"n\":1}')\n") == "PASS"
    assert result("pathlib.Path(sys.argv[2]).write_text('{\"n\":1}')\nsys.exit(42)\n") == "FAIL"
    (case / "expected.json").unlink()
    (case / "expected-error.json").write_text('{"category":"Bounds"}', encoding="utf-8", newline="\n")
    refusal = 'pathlib.Path(sys.argv[3]).write_text(\'{"category":"Bounds"}\')\n'
    assert result(refusal) == "FAIL"
    assert result(refusal + "sys.exit(1)\n") == "PASS"
    assert result(refusal + 'pathlib.Path(sys.argv[2]).write_text("{}")\nsys.exit(1)\n') == "FAIL"
    (case / "manifest.json").write_text('{"class":"hdl-compiler"}', encoding="utf-8", newline="\n")
    (case / "expected-error.json").write_text('{"severity":"ERROR"}', encoding="utf-8", newline="\n")
    assert result('pathlib.Path(sys.argv[3]).write_text("{broken")\nsys.exit(1)\n') == "FAIL"
    diagnostic = 'print("input.hx:3:1: ERROR: bad input", file=sys.stderr)\n'
    assert result(diagnostic + "sys.exit(1)\n") == "PASS"
    assert result(diagnostic) == "FAIL"
    assert result(diagnostic.replace("sys.stderr", "sys.stdout") + "sys.exit(1)\n") == "FAIL"
    assert run_suite.run_case(case, '"missing-processor-executable"', None, 5)[0] == "FAIL"


def round_trip_problems(root: Path) -> None:
    import run_suite

    case = root / "round-trip"
    case.mkdir()
    (case / "manifest.json").write_text('{"class":"physical-parser"}', encoding="utf-8", newline="\n")
    (case / "expected.json").write_text('{"n":1}', encoding="utf-8", newline="\n")
    (case / "description.ttl").write_text("", encoding="utf-8", newline="\n")
    writer = root / "writer.py"
    writer.write_text(
        "import pathlib,sys\npathlib.Path(sys.argv[2]).write_bytes(b'x')\n", encoding="utf-8", newline="\n"
    )
    parser = root / "parser.py"
    claims = {"classes": ["Physical Parser"], "optionalFeatures": ["writer"]}
    for output, expected in (("{broken", "FAIL"), ('{"n":1}', "PASS")):
        parser.write_text(
            f"import pathlib,sys\npathlib.Path(sys.argv[2]).write_text({output!r})\n",
            encoding="utf-8",
            newline="\n",
        )
        assert run_suite.run_round_trip(case, command(writer), command(parser), claims, "round-trip", 5)[0] == expected


def containment_problems(root: Path) -> None:
    from processor_process import execute

    script = root / "contained.py"
    script.write_text('import sys\nsys.stderr.write("x" * 1100000)\n', encoding="utf-8", newline="\n")
    assert "exceeded" in (execute([sys.executable, str(script)], root, 10)[2] or "")
    script.write_text('import sys\nsys.stdout.write("x" * 1100000)\n', encoding="utf-8", newline="\n")
    assert "exceeded" in (execute([sys.executable, str(script)], root, 10)[2] or "")
    script.write_text(
        "import subprocess,sys,pathlib,time\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
        "pathlib.Path('child.pid').write_text(str(child.pid))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
        newline="\n",
    )
    assert "timed out" in (execute([sys.executable, str(script)], root, 2)[2] or "")
    child = int((root / "child.pid").read_text())
    assert not psutil.pid_exists(child) or psutil.Process(child).status() == psutil.STATUS_ZOMBIE
    # The implementation exits first, leaving a child holding inherited pipes open.
    script.write_text(
        "import subprocess,sys,pathlib\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
        "pathlib.Path('orphan.pid').write_text(str(child.pid))\n",
        encoding="utf-8",
        newline="\n",
    )
    try:
        assert "timed out" in (execute([sys.executable, str(script)], root, 2)[2] or "")
        orphan = psutil.Process(int((root / "orphan.pid").read_text()))
        assert not orphan.is_running() or orphan.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass
    finally:
        if (root / "orphan.pid").is_file():
            with contextlib.suppress(psutil.Error):
                psutil.Process(int((root / "orphan.pid").read_text())).kill()


def report_problems(root: Path) -> None:
    import run_suite
    from suite import CLASSES

    suite = root / "suite"
    for cls in CLASSES:
        (suite / cls).mkdir(parents=True)
    for name in ("a-malformed", "b-valid"):
        case = suite / "physical-parser" / name
        case.mkdir()
        (case / "manifest.json").write_text('{"class":"physical-parser"}', encoding="utf-8", newline="\n")
        (case / "expected.json").write_text('{"n":1}', encoding="utf-8", newline="\n")
    script = root / "report-processor.py"
    script.write_text(
        "import pathlib,sys\n"
        "case=pathlib.Path(sys.argv[1])\n"
        "pathlib.Path(sys.argv[2]).write_text('{broken' if case.name=='a-malformed' else '{\"n\":1}')\n",
        encoding="utf-8",
        newline="\n",
    )
    output = root / "report.json"
    with contextlib.redirect_stdout(io.StringIO()):
        assert (
            run_suite.main(
                [
                    "--suite",
                    str(suite),
                    "--pp-cmd",
                    command(script),
                    "--json",
                    str(output),
                    "--implementation-revision",
                    "abcdef0",
                    "--toolchain",
                    "regression probe",
                ]
            )
            == 1
        )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["counts"] == {"PASS": 1, "FAIL": 1, "SKIP": 0}
    assert [r["case"] for r in report["results"]] == ["a-malformed", "b-valid"]
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            run_suite.main(["--case", "a*", "--json", str(root / "partial.json")])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("a partial implementation report was permitted")
    assert not (root / "partial.json").exists()
    claims_file = root / "claims.json"
    claims_file.write_text('{"classes":["Physical Parser"]}', encoding="utf-8", newline="\n")
    with contextlib.redirect_stdout(io.StringIO()):
        assert run_suite.main(["--suite", str(suite), "--claims", str(claims_file)]) == 1


def artifact_boundary_problems(root: Path) -> None:
    import run_suite
    from suite import SUITE

    script = root / "artifact-boundary.py"
    for name, payload in (
        ("ce-report-rdf-blank-requirement", {}),
        ("ce-absent-optional-fires-nothing", {"category": None}),
    ):
        case = SUITE / "conformance-evaluator" / name
        script.write_text(
            "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text("
            + repr(json.dumps(payload))
            + ")\nsys.exit(1)\n",
            encoding="utf-8",
            newline="\n",
        )
        template = f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}" {{err}}'
        assert run_suite.run_case(case, template, None, 5)[0] == "FAIL"
    case = root / "artifact-tree"
    case.mkdir()
    (case / "manifest.json").write_text('{"class":"physical-parser"}', encoding="utf-8", newline="\n")
    (case / "expected.json").write_text('{"category":"Bounds"}', encoding="utf-8", newline="\n")
    serialized = json.dumps({"category": "Bounds"})
    script.write_text(
        "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text(" + repr(serialized) + ")\nsys.exit(1)\n",
        encoding="utf-8",
        newline="\n",
    )
    assert run_suite.run_case(case, template, None, 5)[0] == "FAIL"


def required_error_problems(root: Path) -> None:
    import run_suite
    from suite import SUITE

    case = SUITE / "physical-parser/pp-align-derived-field"
    script = root / "required-error.py"
    payload = (case / "expected-error.json").read_text(encoding="utf-8")
    script.write_text(
        "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text(" + repr(payload) + ")\n",
        encoding="utf-8",
        newline="\n",
    )
    template = f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}" {{out}}'
    assert run_suite.run_case(case, template, None, 5)[0] == "FAIL"
    script.write_text(
        "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text(" + repr(payload) + ")\nsys.exit(1)\n",
        encoding="utf-8",
        newline="\n",
    )
    assert run_suite.run_case(case, template.replace("{out}", "{err}"), None, 5)[0] == "PASS"
    serialized = json.dumps({"category": "ResourceLimit"})
    script.write_text(
        "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text(" + repr(serialized) + ")\n",
        encoding="utf-8",
        newline="\n",
    )
    # Select an actual optional-refusal report case, without depending on its name.
    case = next(
        p.parent
        for p in (SUITE / "conformance-evaluator").glob("*/expected-report.json")
        if json.loads((p.parent / "manifest.json").read_text(encoding="utf-8")).get("orError") == "ResourceLimit"
    )
    assert run_suite.run_case(case, template, None, 5)[0] == "FAIL"


def preflight_problems(root: Path) -> None:
    import run_suite

    output = root / "preflight.json"
    output.write_bytes(b"retain the original bytes\r\n")
    original = output.read_bytes()
    base = ["--json", str(output), "--implementation-revision", "abcdef0", "--toolchain", "probe"]
    for flags in (
        ["--implementation-revision", "main"],
        ["--implementation-revision", "abcdef0\n"],
        ["--implementation", " "],
        ["--implementation-version", " "],
        ["--toolchain", " "],
        ["--jvm", " "],
        ["--os", " "],
    ):
        with patch.object(run_suite, "case_results") as execute, contextlib.redirect_stderr(io.StringIO()):
            try:
                run_suite.main(base + flags)
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError("invalid metadata was accepted")
            execute.assert_not_called()
        assert output.read_bytes() == original
    with patch.object(run_suite.report, "build", return_value={}), contextlib.redirect_stdout(io.StringIO()):
        # A report that fails final validation must not replace an existing output either.
        args = run_suite.argparse.Namespace(
            implementation="probe",
            implementation_version="1",
            implementation_revision="abcdef0",
            os="probe",
            jvm="none",
            toolchain="probe",
            suite=root,
            json=str(output),
        )
        assert not run_suite.write_report(args, [], None)
    assert output.read_bytes() == original


def comparison_limits(root: Path) -> None:
    import run_suite
    from comparison_worker import MAX_ARTIFACT_BYTES, artifact_problem
    from suite import SUITE

    actual = root / "oversized.json"
    with actual.open("wb") as stream:
        stream.truncate(MAX_ARTIFACT_BYTES + 1)
    assert artifact_problem(actual)
    case = SUITE / "conformance-evaluator/ce-conformant"
    assert "exceeds" in run_suite.bounded_comparison("case", case, actual, 5)[0]
    actual.write_text("{}", encoding="utf-8", newline="\n")
    worker_dir = root / "comparison-timeout"
    worker_dir.mkdir()
    (worker_dir / "comparison_worker.py").write_text("import time; time.sleep(30)", encoding="utf-8", newline="\n")
    with patch.object(run_suite, "HERE", worker_dir):
        assert "timed out" in run_suite.bounded_comparison("case", case, actual, 0.2)[0]
    actual.write_text((case / "expected-report.json").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    assert run_suite.bounded_comparison("case", case, actual, 5) == []


def reader_setup_problems(root: Path) -> None:
    import processor_process
    from windows_job import Job

    if sys.platform != "win32":
        try:
            Job()
            raise AssertionError("Windows jobs must fail explicitly on another platform")
        except OSError as error:
            assert "require Windows" in str(error), error

    reader_factory = processor_process._Reader
    for stage in ("stdout", "stderr", "close_job"):
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=sys.platform != "win32",
            text=True,
        )
        readers: list[_Reader] = []

        def create_reader(*args: Any) -> _Reader:
            if stage == "stdout" or (stage == "stderr" and len(readers) == 1):
                raise RuntimeError("reader setup failed")
            reader = reader_factory(*args)
            readers.append(reader)
            return reader

        def close_job() -> None:
            if stage == "close_job":
                raise RuntimeError("job closure failed")

        try:
            with patch.object(processor_process, "_Reader", side_effect=create_reader):
                try:
                    processor_process.collect(proc, 0.2, close_job)
                    raise AssertionError(f"{stage} failure was swallowed")
                except RuntimeError:
                    pass
            assert proc.poll() is not None, stage
            assert proc.stdout is not None and proc.stdout.closed, stage
            assert proc.stderr is not None and proc.stderr.closed, stage
            assert all(not reader.thread.is_alive() for reader in readers), stage
        finally:
            if proc.poll() is None:
                processor_process.terminate(proc)
            proc.wait(timeout=10)
            for reader in readers:
                reader.close()
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None:
                    pipe.close()


def check() -> list[str]:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        comparison_limits(root)
        required_error_problems(root)
        artifact_boundary_problems(root)
        preflight_problems(root)
        artifact_problems(root)
        round_trip_problems(root)
        containment_problems(root)
        reader_setup_problems(root)
        report_problems(root)
    return []
