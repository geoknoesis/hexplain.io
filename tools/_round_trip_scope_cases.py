"""Round-trip dependencies follow call arguments and quantifier evaluation scopes."""

from pathlib import Path

import round_trip

PREFIX = """@prefix b:<https://hexplain.io/ns/bddo#>.
@prefix h:<https://hexplain.io/ns/core#>.
@prefix e:<https://example.test/#>.
"""
ROOT = "https://example.test/#Root"


def parameter_controls(root: Path) -> None:
    description = root / "parameter-dependencies.ttl"
    source = (
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:Root.n e:data e:child e:constant).
e:Root.n a b:Field; b:dataType b:uint8.
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:Root.n; h:isEncodedWith <urn:codec>.
e:child a b:Field; b:dataType e:Child; b:hasArgument ("instance.n").
e:constant a b:Field; b:dataType e:Child; b:hasArgument ("7").
e:Child a b:Struct; b:hasParameter (e:Child.p); b:hasField (e:local e:derived e:grandchild).
e:Child.p a b:Parameter.
e:local a b:LocalBinding; b:localExpression "param.p + 1".
e:derived a b:Field; b:valueFromExpression "local + 1".
e:grandchild a b:Field; b:dataType e:Grandchild; b:hasArgument ("param.p + 1").
e:Grandchild a b:Struct; b:hasParameter (e:q); b:hasField (e:value).
e:q a b:Parameter.
e:value a b:Field; b:valueFromExpression "param.q + 1".
"""
    )
    description.write_text(source, encoding="utf-8", newline="\n")
    expected = {
        "n": 25,
        "data": "00",
        "child": {"derived": 27, "grandchild": {"value": 27}},
        "constant": {"derived": 9, "grandchild": {"value": 9}},
    }
    actual = dict(expected, n=21, child={"derived": 23, "grandchild": {"value": 23}})
    exempt = round_trip.recomputed_paths(description, ROOT, expected)
    assert exempt == {("n",), ("child", "local"), ("child", "derived"), ("child", "grandchild", "value")}, exempt
    assert not round_trip.isomorphism_problems(expected, actual, exempt)
    assert round_trip.isomorphism_problems(expected, dict(actual, constant=actual["child"]), exempt)
    # Each repeated call evaluates its arguments at that instance's entry position.
    repeated = (
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:items).
e:items a b:Field; b:dataType e:Item; b:repeatCount 2; b:hasArgument ("stream.position").
e:Item a b:Struct; b:hasParameter (e:at); b:hasField (e:position e:n e:data).
e:at a b:Parameter.
e:position a b:Field; b:valueFromExpression "param.at".
e:n a b:Field; b:dataType b:uint8.
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:n; h:isEncodedWith <urn:codec>.
"""
    )
    description.write_text(repeated, encoding="utf-8", newline="\n")
    tree = {"items": [{"position": 0, "n": 25, "data": "00"}, {"position": 26, "n": 25, "data": "00"}]}
    changed = {"items": [{"position": 0, "n": 21, "data": "00"}, {"position": 22, "n": 25, "data": "00"}]}
    exempt = round_trip.recomputed_paths(description, ROOT, tree)
    assert ("items", 0, "position") not in exempt and ("items", 1, "position") in exempt, exempt
    assert not round_trip.isomorphism_problems(tree, changed, exempt)
    changed["items"][0]["position"] = 99
    assert round_trip.isomorphism_problems(tree, changed, exempt)
    encoded = (
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:n e:items).
e:n a b:Field; b:dataType b:uint8.
e:items a b:Field; b:dataType e:Item; b:repeatCount 2; b:sizeFromField e:n;
    b:hasArgument ("stream.position"); h:isEncodedWith <urn:codec>.
e:Item a b:Struct; b:hasParameter (e:at); b:hasField (e:position e:v).
e:at a b:Parameter.
e:position a b:Field; b:valueFromExpression "param.at".
e:v a b:Field; b:dataType b:uint8.
"""
    )
    description.write_text(encoded, encoding="utf-8", newline="\n")
    encoded_tree = {"n": 25, "items": [{"position": 1, "v": 1}, {"position": 26, "v": 2}]}
    exempt = round_trip.recomputed_paths(description, ROOT, encoded_tree)
    assert ("items", 0, "position") not in exempt and ("items", 1, "position") in exempt, exempt
    updated_items = [{"position": 1, "v": 1}, {"position": 22, "v": 2}]
    encoded_actual = {"n": 21, "items": updated_items}
    assert not round_trip.isomorphism_problems(encoded_tree, encoded_actual, exempt)
    updated_items[0]["position"] = 99
    assert round_trip.isomorphism_problems(encoded_tree, encoded_actual, exempt)
    description.write_text(encoded.replace('("stream.position")', '("stream.length")'), encoding="utf-8", newline="\n")
    lengths = {"n": 25, "items": [{"position": 51, "v": 1}, {"position": 51, "v": 2}]}
    exempt = round_trip.recomputed_paths(description, ROOT, lengths)
    assert ("items", 0, "position") in exempt and ("items", 1, "position") in exempt, exempt


def quantifier_controls(root: Path) -> None:
    description = root / "quantifier-dependencies.ttl"
    base = (
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:n e:data e:items e:scalars e:empty e:result).
e:n a b:Field; b:dataType b:uint8.
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:n; h:isEncodedWith <urn:codec>.
e:items a b:Field; b:dataType e:Item; b:repeatCount 1; b:hasArgument ("7").
e:Item a b:Struct; b:hasParameter (e:p); b:hasField (e:n).
e:p a b:Parameter.
e:scalars a b:Field; b:dataType b:uint8; b:repeatCount 2.
e:empty a b:Field; b:dataType e:Item; b:repeatCount 0; b:hasArgument ("7").
e:result a b:Field; b:valueFromExpression "EXPRESSION".
"""
    )
    tree = {"n": 25, "data": "00", "items": [{"n": 1}], "scalars": [1, 2], "empty": [], "result": True}
    strict = (
        "all(items, instance.n > 0)",
        "any(items, n > 0)",
        "all(items, self.n > 0)",
        "all(items, param.p > 0)",
        "all(scalars, self > 0)",
        "all(empty, root.n > 0)",
        "any(empty, root.n > 0)",
        "all(true ? items : items, instance.n > 0)",
    )
    changing = (
        "all(items, parent.n > 23)",
        "any(items, root.n > 23)",
        "all(scalars, instance.n > 23)",
        "all(items, stream.position > 23)",
    )
    for expression in strict + changing:
        description.write_text(base.replace("EXPRESSION", expression), encoding="utf-8", newline="\n")
        exempt = round_trip.recomputed_paths(description, ROOT, tree)
        assert (("result",) in exempt) == (expression in changing), (expression, exempt)
        if expression in strict:
            expected = dict(tree, result=not expression.startswith("any(empty,"))
            assert round_trip.isomorphism_problems(expected, dict(expected, result=not expected["result"]), exempt), (
                expression
            )
    # A parameter in a struct-element predicate belongs to that element's call.
    parameterized = base.replace('b:hasArgument ("7")', 'b:hasArgument ("instance.n")')
    description.write_text(
        parameterized.replace("EXPRESSION", "all(items, param.p > 23)"), encoding="utf-8", newline="\n"
    )
    assert ("result",) in round_trip.recomputed_paths(description, ROOT, tree)
    local = parameterized.replace("b:hasField (e:n).", "b:hasField (e:n e:flag).")
    local += '\ne:flag a b:LocalBinding; b:localExpression "param.p > 23".\n'
    description.write_text(local.replace("EXPRESSION", "all(items, flag)"), encoding="utf-8", newline="\n")
    assert ("result",) in round_trip.recomputed_paths(description, ROOT, tree)
    # Quantifier parent is the enclosing evaluation instance, even for a remote array.
    remote = base.replace("e:empty e:result).", "e:empty e:other e:result).")
    remote += "\ne:other a b:Field; b:dataType e:Other. e:Other a b:Struct; b:hasField (e:n e:items).\n"
    tree["other"] = {"n": 1, "items": [{"n": 1}]}
    description.write_text(
        remote.replace("EXPRESSION", "all(root.other.items, parent.n > 23)"), encoding="utf-8", newline="\n"
    )
    assert ("result",) in round_trip.recomputed_paths(description, ROOT, tree)
    # Nested quantifiers retain their enclosing evaluation scope, not a borrowed outer name.
    nested = base.replace("b:hasField (e:n).", "b:hasField (e:n e:subitems).")
    nested += "\ne:subitems a b:Field; b:dataType e:Leaf; b:repeatCount 1.\n"
    nested += "e:Leaf a b:Struct; b:hasField (e:v). e:v a b:Field; b:dataType b:uint8.\n"
    tree["items"] = [{"n": 1, "subitems": [{"v": 2}]}]
    for expression, changes in (
        ("all(items, any(subitems, parent.n > 0))", False),
        ("all(items, any(subitems, parent.parent.n > 23))", True),
    ):
        description.write_text(nested.replace("EXPRESSION", expression), encoding="utf-8", newline="\n")
        exempt = round_trip.recomputed_paths(description, ROOT, tree)
        assert (("result",) in exempt) == changes, (expression, exempt)


def check(root: Path) -> None:
    parameter_controls(root)
    quantifier_controls(root)
