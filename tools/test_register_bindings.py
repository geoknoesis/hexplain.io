"""hexplain:usesRegister must be enforced: a value outside the declared register FAILS.

Mirrors tools/test_shapes.py's optional-pyshacl skip so the rdflib-only suite stays green.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        from pyshacl import validate
    except ImportError:
        print("SKIP: pyshacl not installed (optional formal SHACL gate)")
        return 77  # The runner's SKIP status (tools/_gate_runner.SKIP_EXIT).

    import rdflib

    shapes = rdflib.Graph()
    shapes.parse(ROOT / "specification/hexplain/core.ttl", format="turtle")

    def conforms(path: str) -> tuple[bool, str]:
        data = rdflib.Graph()
        data.parse(ROOT / path, format="turtle")
        ok, _, text = validate(data, shacl_graph=shapes, advanced=True)
        return ok, text

    valid_ok, valid_text = conforms("specification/hexplain/test/register-binding-valid.ttl")
    invalid_ok, _ = conforms("specification/hexplain/test/register-binding-invalid.ttl")
    # One property bound to two registers (US and NATO): a value in either scheme is valid.
    multi_ok, multi_text = conforms("specification/hexplain/test/register-binding-multi-valid.ttl")

    problems = []
    if not multi_ok:
        problems.append("a value in one of two registers bound to the same property did NOT conform:\n" + multi_text)
    if not valid_ok:
        problems.append("value inside the declared register did NOT conform:\n" + valid_text)
    if invalid_ok:
        problems.append("value OUTSIDE the declared register conformed (binding not enforced)")
    if problems:
        print("FAIL:\n" + "\n".join(problems))
        return 1
    print("PASS: register bindings enforced (in-register conforms, out-of-register rejected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
