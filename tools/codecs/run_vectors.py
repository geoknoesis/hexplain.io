"""Run the specification's codec vectors against one implementation.

    python tools/codecs/run_vectors.py --command TEMPLATE [--codec NAME]... [--timeout SECONDS]

TEMPLATE is the command that runs ONE vector, split like a POSIX shell command line (use forward
slashes in paths), with the placeholders {manifest} (absolute path of the suite's manifest.json),
{id} (the vector id) and {codec} (the codec IRI) substituted inside its words; no shell is
involved. It must print the result JSON documented in tools/codecs/vectors.py and exit 0,
whatever the vector's own outcome. For the reference engine (after `:core:installDist`):

    --command "d:/work/hexplain-tools/core/build/install/core/bin/hexplain-codec vector --manifest {manifest} --id {id}"

--codec restricts the run to suites by local name (repeatable). Exit status: 0 every vector
passed, 1 a vector failed or the command misbehaved, 2 usage.
"""
import argparse
import json
import pathlib
import shlex
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vectors  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--command", required=True)
    parser.add_argument("--codec", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    suites = sorted((vectors.ROOT / "specification/codecs").glob("*/vectors/manifest.json"))
    if args.codec:
        suites = [s for s in suites if s.parent.parent.name in set(args.codec)]
        missing = set(args.codec) - {s.parent.parent.name for s in suites}
        if missing:
            print(f"no vector suite for {sorted(missing)}")
            return 2
    failures, count = [], 0
    for path in suites:
        manifest = vectors.load(path)
        for vector in manifest["vectors"]:
            count += 1
            values = {"{manifest}": path.as_posix(), "{id}": vector["id"], "{codec}": manifest["codec"]}
            command = []
            for word in shlex.split(args.command):
                for placeholder, value in values.items():
                    word = word.replace(placeholder, value)
                command.append(word)
            try:
                run = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
            except subprocess.TimeoutExpired:
                failures.append(f"{path.parent.parent.name}/{vector['id']}: timed out after {args.timeout} s")
                continue
            try:
                result = json.loads(run.stdout)
            except json.JSONDecodeError:
                failures.append(f"{path.parent.parent.name}/{vector['id']}: exit {run.returncode}, no JSON result: "
                                f"{run.stdout[:300]} {run.stderr[:300]}")
                continue
            for problem in vectors.compare(vector, result):
                failures.append(f"{path.parent.parent.name}/{vector['id']}: {problem}")
    if failures:
        print(f"FAIL: {len(failures)} of {count} vectors\n  " + "\n  ".join(failures))
        return 1
    print(f"PASS: {count} vectors in {len(suites)} suites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
