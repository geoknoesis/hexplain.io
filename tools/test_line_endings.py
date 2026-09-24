"""Files .gitattributes pins to LF are LF in the working tree, and nothing is committed CRLF.

The Turtle and TSV files are compared byte-for-byte by the gates and by the engine after
multi-line literals are parsed, so a carriage return inside a triple-quoted SHACL query changes
the graph. .gitattributes pins them to eol=lf, but a working tree checked out before that rule
existed, or written by a generator that used the platform newline, keeps CRLF until the files
are checked out again. `git ls-files --eol` reports both the index and the working-tree form;
this gate fails on any eol=lf file whose working copy is CRLF or mixed, and on any text file
committed with CRLF. Fix a stale checkout with `git rm --cached -r -q . && git reset --hard`
(after committing your work) or by deleting and re-checking out the listed files.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = subprocess.run(["git", "ls-files", "--eol"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    bad, checked = [], 0
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        index, work = (meta.split() + ["", ""])[:2]
        attr = meta.split("attr/", 1)[-1]
        # A file declared -text (the conformance suite's byte-exact case data, some of whose inputs
        # are CRLF text on purpose) is binary to git: its bytes are the content, not line endings.
        if index in ("i/crlf", "i/mixed") and "-text" not in attr:
            bad.append(f"{path}: committed with {index[2:].upper()} line endings")
        if "eol=lf" in attr:
            checked += 1
            if work in ("w/crlf", "w/mixed"):
                bad.append(f"{path}: {work[2:].upper()} in the working tree although .gitattributes says eol=lf")
    if bad:
        print("FAIL:\n  " + "\n  ".join(bad))
        sys.exit(1)
    print(f"PASS: {checked} eol=lf files are LF in the working tree; no text file is committed CRLF")


if __name__ == "__main__":
    main()
