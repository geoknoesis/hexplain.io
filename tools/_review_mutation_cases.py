"""Mutation probes for the 2026-09-24 ontology review: each names one defect the review found.

A probe is a small graph and the verdict the family's shapes must reach on it. Each probe states
one mutation of a conforming graph (a missing verdict, a '..' path segment, a deprecated entry
replaced by itself...) and whether the shapes must reject it. The probes were written from the
review's findings, not read off the shapes; tools/test_review_mutations.py runs them, and with
--root runs them against another checkout to show which defects that checkout lets through.
"""

P = """@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req: <https://hexplain.io/ns/req#> .
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix abnd: <https://hexplain.io/ns/aspect/bundle#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <urn:review-probe:> .
"""

CONF_SHAPES = ["specification/conf/shapes.ttl", "specification/req/shapes.ttl"]
REQ_SHAPES = ["specification/req/shapes.ttl"]
CORE_SHAPES = ["specification/hexplain/core.ttl"]
BUNDLE_SHAPES = ["specification/aspect/bundle/bundle.ttl"]
BDDO_SHAPES = ["specification/bddo/bddo.ttl"]
STRICT_SHAPES = ["specification/validation/test/strict-profile-shapes.ttl"]

# A conforming run report: a Warning-level constraint finding, an attributed Parse finding, a
# rule set with one constraint and one parse attribution, and one outcome per requirement.
REPORT = """
ex:req1 a req:Requirement ; req:requirementId "R1" ; req:fromStandard "Example 1.0" ; req:statement "One." ; req:discrepancyType req:Syntactic .
ex:req2 a req:Requirement ; req:requirementId "R2" ; req:fromStandard "Example 1.0" ; req:statement "Two." ; req:discrepancyType req:Semantic .
ex:field a bddo:Field .
ex:con a conf:Constraint ; conf:scope ex:field ; conf:assertion "self > 0" ; conf:satisfies ex:req1 ; conf:message "m" ; conf:severity sh:Warning .
ex:pa a conf:ParseAttribution ; conf:errorCategory conf:BoundsError ; conf:satisfies ex:req2 .
ex:run a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:versionScopingApplied false ;
    conf:profile ex:profile ; conf:ruleSet ex:rules ; conf:input "input.bin" ; conf:failOn sh:Violation ;
    conf:outcome [ conf:outcomeRequirement ex:req1 ; conf:outcomeValue conf:Evaluated ] ,
                 [ conf:outcomeRequirement ex:req2 ; conf:outcomeValue conf:Evaluated ] ;
    conf:finding ex:f1 , ex:f2 .
ex:f1 a conf:Finding ; conf:findingKind conf:Violation ; conf:findingConstraint ex:con ; conf:findingRequirement ex:req1 ;
    conf:severity sh:Warning ; conf:findingMessage "m" .
ex:f2 a conf:Finding ; conf:findingKind conf:Parse ; conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:req2 ;
    conf:severity sh:Violation ; conf:findingMessage "p" .
"""
# The same report with no Violation-level finding: conformant.
CLEAN = (REPORT.replace("conf:verdict conf:NonConformant", "conf:verdict conf:Conformant")
         .replace("conf:finding ex:f1 , ex:f2 .", "conf:finding ex:f1 .")
         .split("ex:f2 a conf:Finding")[0])


def _sub(text, *pairs):
    for old, new in pairs:
        assert old in text, old
        text = text.replace(old, new)
    return text


def conf_cases():
    c = []

    def add(name, data, ok):
        c.append(dict(group="conf report", name=name, shapes=CONF_SHAPES, data=P + data, conforms=ok))
    add("valid report", REPORT, True)
    add("valid conformant report", CLEAN, True)
    add("run without a verdict", _sub(REPORT, ("conf:verdict conf:NonConformant ;", "")), False)
    add("run with two verdicts", _sub(REPORT, ("conf:verdict conf:NonConformant", "conf:verdict conf:NonConformant , conf:Conformant")), False)
    add("verdict outside the closed set", _sub(REPORT, ("conf:verdict conf:NonConformant", "conf:verdict ex:maybe")), False)
    add("run without a truncated flag", _sub(REPORT, ("conf:truncated false ;", "")), False)
    add("run with two truncated flags", _sub(REPORT, ("conf:truncated false", "conf:truncated false , true")), False)
    add("truncated flag as a string", _sub(REPORT, ("conf:truncated false", 'conf:truncated "false"')), False)
    add("truncated run with a conformant verdict", _sub(CLEAN, ("conf:truncated false", 'conf:truncated true ; conf:truncationReason "finding limit"')), False)
    add("truncated run, non-conformant, with a reason", _sub(REPORT, ("conf:truncated false", 'conf:truncated true ; conf:truncationReason "finding limit"')), True)
    add("truncation reason on an untruncated run", _sub(REPORT, ("conf:truncated false", 'conf:truncated false ; conf:truncationReason "why"')), False)
    add("truncation reason that is not a string", _sub(REPORT, ("conf:truncated false", "conf:truncated true ; conf:truncationReason 7")), False)
    add("version scoping flag as a string", _sub(REPORT, ("conf:versionScopingApplied false", 'conf:versionScopingApplied "no"')), False)
    add("file version that is a number", _sub(REPORT, ("conf:versionScopingApplied false", "conf:versionScopingApplied true ; conf:fileVersion 2")), False)
    add("file version without version scoping", _sub(REPORT, ("conf:versionScopingApplied false", 'conf:versionScopingApplied false ; conf:fileVersion "2.0"')), False)
    add("version scoping without a file version", _sub(REPORT, ("conf:versionScopingApplied false", "conf:versionScopingApplied true")), False)
    add("profile given as a literal", _sub(REPORT, ("conf:profile ex:profile", 'conf:profile "profile.ttl"')), False)
    add("rule set given as a literal", _sub(REPORT, ("conf:ruleSet ex:rules", 'conf:ruleSet "rules.ttl"')), False)
    add("input given as an IRI", _sub(REPORT, ('conf:input "input.bin"', "conf:input ex:input")), True)
    add("input given as a blank node", _sub(REPORT, ('conf:input "input.bin"', "conf:input [ ]")), False)
    add("fail-on outside the SHACL severities", _sub(REPORT, ("conf:failOn sh:Violation", "conf:failOn ex:fatal")), False)
    add("fail-on info with a warning finding", _sub(REPORT, ("conf:failOn sh:Violation", "conf:failOn sh:Info")), True)
    for prop, first, second in [("input", '"input.bin"', '"copy.bin"'), ("failOn", "sh:Violation", "sh:Warning"),
                                ("ruleSet", "ex:rules", "ex:other"), ("profile", "ex:profile", "ex:other"),
                                ("versionScopingApplied", "false", "true")]:
        add(f"run with two conf:{prop} values", _sub(REPORT, (f"conf:{prop} {first}", f"conf:{prop} {first} , {second}")), False)
    add("run with two file versions", _sub(REPORT, ("conf:versionScopingApplied false", 'conf:versionScopingApplied true ; conf:fileVersion "1.0" , "2.0"')), False)
    add("run with two truncation reasons", _sub(REPORT, ("conf:truncated false", 'conf:truncated true ; conf:truncationReason "a" , "b"')), False)
    add("finding not linked to the run", _sub(REPORT, ("conf:finding ex:f1 , ex:f2 .", "conf:finding ex:f1 .")), False)
    add("finding linked by two runs", REPORT + "ex:run2 a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:finding ex:f2 ; "
        "conf:outcome [ conf:outcomeRequirement ex:req1 ; conf:outcomeValue conf:Evaluated ] , [ conf:outcomeRequirement ex:req2 ; conf:outcomeValue conf:Evaluated ] .", False)
    add("conf:finding naming a literal", _sub(REPORT, ("conf:finding ex:f1 , ex:f2 .", 'conf:finding ex:f1 , ex:f2 , "f3" .')), False)
    add("requirement in the graph without an outcome", REPORT + 'ex:req3 a req:Requirement ; req:requirementId "R3" ; req:fromStandard "Example 1.0" ; req:statement "Three." ; req:discrepancyType req:Functional .', False)
    add("two outcomes for one requirement", _sub(REPORT, ("[ conf:outcomeRequirement ex:req2 ; conf:outcomeValue conf:Evaluated ]",
        "[ conf:outcomeRequirement ex:req2 ; conf:outcomeValue conf:Evaluated ] , [ conf:outcomeRequirement ex:req2 ; conf:outcomeValue conf:Errored ]")), False)
    na = _sub(REPORT, ("[ conf:outcomeRequirement ex:req1 ; conf:outcomeValue conf:Evaluated ]", "[ conf:outcomeRequirement ex:req1 ; conf:outcomeValue conf:NotApplicable ]"))
    add("not applicable without appliesToVersion", _sub(na, ("conf:versionScopingApplied false", 'conf:versionScopingApplied true ; conf:fileVersion "1.0"')), False)
    scoped = _sub(na, ("conf:versionScopingApplied false", 'conf:versionScopingApplied true ; conf:fileVersion "1.0"'),
                  ('req:statement "One."', 'req:statement "One." ; req:appliesToVersion "2.0"'))
    add("not applicable from version scoping", scoped, True)
    add("not applicable without version scoping", _sub(na, ('req:statement "One."', 'req:statement "One." ; req:appliesToVersion "2.0"')), False)
    add("not applicable although the version matches", _sub(scoped, ('req:appliesToVersion "2.0"', 'req:appliesToVersion "2.0" , "1.0"')), False)
    add("conformant verdict with a violation finding", _sub(REPORT, ("conf:verdict conf:NonConformant", "conf:verdict conf:Conformant")), False)
    add("conformant verdict with an errored outcome", _sub(CLEAN, ("conf:outcomeValue conf:Evaluated ] ;", "conf:outcomeValue conf:Errored ] ;")), False)
    add("conformant verdict with a warning at fail-on warning", _sub(CLEAN, ("conf:failOn sh:Violation", "conf:failOn sh:Warning")), False)
    add("non-conformant verdict with no reason", _sub(CLEAN, ("conf:verdict conf:Conformant", "conf:verdict conf:NonConformant")), False)
    # Finding severity follows the constraint, and is sh:Violation for rule errors and parse errors.
    add("violation finding above its constraint's severity", _sub(REPORT, ("conf:severity sh:Warning ; conf:findingMessage", "conf:severity sh:Violation ; conf:findingMessage")), False)
    add("violation finding without severity under a warning constraint", _sub(REPORT, ("conf:severity sh:Warning ; conf:findingMessage", "conf:findingMessage")), False)
    add("finding and constraint both at the default severity", _sub(REPORT, ("conf:severity sh:Warning ; conf:findingMessage", "conf:findingMessage"),
        ('conf:message "m" ; conf:severity sh:Warning', 'conf:message "m"')), True)
    add("rule error finding at warning", _sub(REPORT, ("conf:findingKind conf:Violation", "conf:findingKind conf:RuleError")), False)
    add("parse finding at warning", _sub(REPORT, ('conf:severity sh:Violation ; conf:findingMessage "p"', 'conf:severity sh:Warning ; conf:findingMessage "p"')), False)
    # A Parse finding cites exactly the requirement its category's attribution names.
    add("attributed parse finding citing no requirement", _sub(REPORT, ("conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:req2 ;", "conf:errorCategory conf:BoundsError ;")), False)
    add("parse finding citing another requirement", _sub(REPORT, ("conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:req2 ;", "conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:req1 ;")), False)
    unattributed = _sub(REPORT, ("conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:req2 ;", "conf:errorCategory conf:DispatchError ;"))
    add("unattributed parse finding citing no requirement", unattributed, True)
    add("unattributed parse finding citing a requirement", _sub(unattributed, ("conf:errorCategory conf:DispatchError ;", "conf:errorCategory conf:DispatchError ; conf:findingRequirement ex:req2 ;")), False)
    add("parse finding naming its category by the deprecated string", _sub(REPORT, ("conf:errorCategory conf:BoundsError ; conf:findingRequirement", 'conf:errorCategory "Bounds" ; conf:findingRequirement')), True)
    add("attribution naming ResourceLimit", _sub(REPORT, ("ex:pa a conf:ParseAttribution ; conf:errorCategory conf:BoundsError", 'ex:pa a conf:ParseAttribution ; conf:errorCategory "ResourceLimit"'),
        ("conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:req2 ;", "conf:errorCategory conf:DispatchError ;")), False)
    add("parse finding naming ResourceLimit", _sub(unattributed, ("conf:errorCategory conf:DispatchError ;", 'conf:errorCategory "ResourceLimit" ;')), False)
    add("attribution naming Dispatch by string", _sub(REPORT, ("ex:pa a conf:ParseAttribution ; conf:errorCategory conf:BoundsError", 'ex:pa a conf:ParseAttribution ; conf:errorCategory "Dispatch"'),
        ("conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:req2 ;", 'conf:errorCategory "Dispatch" ; conf:findingRequirement ex:req2 ;')), True)
    add("error category on a violation finding", _sub(REPORT, ("conf:findingKind conf:Violation ;", "conf:findingKind conf:Violation ; conf:errorCategory conf:SyncError ;")), False)
    add("error category on a constraint", _sub(REPORT, ('conf:message "m" ;', 'conf:message "m" ; conf:errorCategory conf:SyncError ;')), False)
    add("error category on a run", _sub(REPORT, ("conf:truncated false ;", "conf:truncated false ; conf:errorCategory conf:SyncError ;")), False)
    add("error category on a requirement", _sub(REPORT, ('req:statement "One."', 'req:statement "One." ; conf:errorCategory conf:SyncError')), False)
    add("error category with the wrong case", _sub(REPORT, ("ex:pa a conf:ParseAttribution ; conf:errorCategory conf:BoundsError", 'ex:pa a conf:ParseAttribution ; conf:errorCategory "bounds"')), False)
    add("error category that is not a category", _sub(REPORT, ("ex:pa a conf:ParseAttribution ; conf:errorCategory conf:BoundsError", "ex:pa a conf:ParseAttribution ; conf:errorCategory conf:Parse")), False)
    # An attribution without rdf:type is still an attribution.
    add("untyped attribution citing a literal", REPORT + 'ex:pb conf:errorCategory conf:SyncError ; conf:satisfies "R1" .', False)
    add("untyped attribution citing two requirements", REPORT + "ex:pb conf:errorCategory conf:SyncError ; conf:satisfies ex:req1 , ex:req2 .", False)
    add("untyped attribution repeating a typed one's category", REPORT + "ex:pb conf:errorCategory conf:BoundsError ; conf:satisfies ex:req1 .", False)
    add("attributions naming one category by IRI and by string", REPORT + 'ex:pb a conf:ParseAttribution ; conf:errorCategory "Bounds" ; conf:satisfies ex:req1 .', False)
    add("attributions of two categories", REPORT + "ex:pb a conf:ParseAttribution ; conf:errorCategory conf:SyncError ; conf:satisfies ex:req1 .", True)
    # The report's kinds of resource are disjoint.
    add("node that is a finding and a run", _sub(REPORT, ("ex:f1 a conf:Finding ;", "ex:f1 a conf:Finding , conf:Run ;")), False)
    add("node that is a constraint and a parse attribution", _sub(REPORT, ("ex:con a conf:Constraint ;", "ex:con a conf:Constraint , conf:ParseAttribution ;")), False)
    add("node that is a requirement and a finding", _sub(REPORT, ("ex:req1 a req:Requirement ;", "ex:req1 a req:Requirement , conf:Finding ;")), False)
    return c


REQUIREMENT = ('ex:r a req:Requirement ; req:requirementId "R1" ; req:fromStandard "Example 1.0" ; '
               'req:statement "The magic shall be HX." ; req:discrepancyType req:Syntactic .\n')


def req_cases():
    c = []

    def add(name, data, ok):
        c.append(dict(group="req", name=name, shapes=REQ_SHAPES, data=P + data, conforms=ok))
    add("valid requirement", REQUIREMENT, True)
    add("identifier of spaces", _sub(REQUIREMENT, ('"R1"', '"   "')), False)
    add("identifier of a no-break space", _sub(REQUIREMENT, ('"R1"', '"\\u00A0"')), False)
    add("identifier of a zero-width space", _sub(REQUIREMENT, ('"R1"', '"\\u200B"')), False)
    add("identifier of a tab and a byte-order mark", _sub(REQUIREMENT, ('"R1"', '"\\t\\uFEFF"')), False)
    add("standard of spaces", _sub(REQUIREMENT, ('"Example 1.0"', '" \\u00A0 "')), False)
    add("identifier with an inner space", _sub(REQUIREMENT, ('"R1"', '"R 1"')), True)
    add("language-tagged statement", _sub(REQUIREMENT, ('"The magic shall be HX."', '"The magic shall be HX."@en')), True)
    add("statement in two languages", _sub(REQUIREMENT, ('"The magic shall be HX."', '"The magic shall be HX."@en , "La magie doit être HX."@fr')), False)
    add("statement that is a number", _sub(REQUIREMENT, ('"The magic shall be HX."', "42")), False)
    add("statement of spaces", _sub(REQUIREMENT, ('"The magic shall be HX."', '"\\u00A0"@en')), False)
    add("identifiers differing by a trailing no-break space", REQUIREMENT + _sub(REQUIREMENT, ("ex:r ", "ex:r2 "), ('"R1"', '"R1\\u00A0"')), False)
    add("standards differing by a no-break space", REQUIREMENT + _sub(REQUIREMENT, ("ex:r ", "ex:r2 "), ('"Example 1.0"', '"Example\\u00A01.0"')), False)
    add("identifiers differing by a zero-width space", REQUIREMENT + _sub(REQUIREMENT, ("ex:r ", "ex:r2 "), ('"R1"', '"R\\u200B1"')), False)
    add("two identifiers in one standard", REQUIREMENT + _sub(REQUIREMENT, ("ex:r ", "ex:r2 "), ('"R1"', '"R2"')), True)
    return c


REGISTER = """
ex:Scheme a skos:ConceptScheme .
ex:Other a skos:ConceptScheme .
ex:current a skos:Concept ; skos:inScheme ex:Scheme .
ex:next a skos:Concept ; skos:inScheme ex:Scheme .
"""


def register_cases():
    c = []

    def add(name, data, ok, **extra):
        c.append(dict(group="register lifecycle", name=name, shapes=CORE_SHAPES, data=P + REGISTER + data, conforms=ok, **extra))
    add("valid entry", "ex:current hexplain:status hexplain:statusValid .", True)
    add("valid entry marked deprecated", "ex:current hexplain:status hexplain:statusValid ; owl:deprecated true .", False)
    add("deprecated entry without a status", 'ex:current owl:deprecated true ; skos:historyNote "Retired."@en .', False)
    add("deprecated entry without a history note", "ex:current owl:deprecated true ; hexplain:status hexplain:statusDeprecated .", False)
    add("deprecated entry with a change note", 'ex:current owl:deprecated true ; hexplain:status hexplain:statusDeprecated ; skos:changeNote "Retired."@en .', True)
    add("deprecated scheme without a history note", "ex:Other owl:deprecated true ; hexplain:status hexplain:statusDeprecated .", False)
    add("superseded entry replaced by itself", 'ex:current owl:deprecated true ; hexplain:status hexplain:statusSuperseded ; dcterms:isReplacedBy ex:current ; skos:historyNote "Replaced."@en .', False)
    add("superseded entry replaced by a deprecated entry",
        'ex:current owl:deprecated true ; hexplain:status hexplain:statusSuperseded ; dcterms:isReplacedBy ex:next ; skos:historyNote "Replaced."@en .\n'
        'ex:next owl:deprecated true ; hexplain:status hexplain:statusDeprecated ; skos:historyNote "Retired."@en .', False)
    add("superseded entry replaced by a current entry", 'ex:current owl:deprecated true ; hexplain:status hexplain:statusSuperseded ; dcterms:isReplacedBy ex:next ; skos:historyNote "Replaced."@en .', True)
    add("superseded entry naming no successor", 'ex:current owl:deprecated true ; hexplain:status hexplain:statusSuperseded ; skos:historyNote "Replaced."@en .', False)
    add("deprecated ontology property needs no register status", "ex:prop a owl:ObjectProperty ; owl:deprecated true .", True)
    add("entry stated not deprecated", "ex:current owl:deprecated false ; hexplain:status hexplain:statusValid .", True)
    add("deprecated collection with its record", 'ex:Group a skos:Collection ; skos:member ex:current ; owl:deprecated true ; '
        'hexplain:status hexplain:statusDeprecated ; skos:historyNote "Withdrawn."@en .', True)
    add("deprecated collection without a history note", "ex:Group a skos:Collection ; skos:member ex:current ; owl:deprecated true ; "
        "hexplain:status hexplain:statusDeprecated .", False)
    # Using a retired value is legal (old data keeps its meaning) but reported.
    add("deprecated value of a bound property", 'ex:profile hexplain:usesRegister [ hexplain:forProperty ex:level ; hexplain:register ex:Scheme ] .\n'
        'ex:current owl:deprecated true ; hexplain:status hexplain:statusDeprecated ; skos:historyNote "Retired."@en .\n'
        "ex:doc ex:level ex:current .", False, severity="http://www.w3.org/ns/shacl#Warning")
    return c


BINDINGS = """
ex:Us a skos:ConceptScheme . ex:Nato a skos:ConceptScheme .
ex:secret a skos:Concept ; skos:inScheme ex:Us .
ex:natoSecret a skos:Concept ; skos:inScheme ex:Nato .
ex:elsewhere a skos:Concept .
ex:usProfile hexplain:usesRegister [ hexplain:forProperty ex:level ; hexplain:register ex:Us ] .
"""
NATO = "ex:natoProfile hexplain:usesRegister [ hexplain:forProperty ex:level ; hexplain:register ex:Nato ] .\n"


def binding_cases():
    c = []

    def add(name, data, ok):
        c.append(dict(group="register binding", name=name, shapes=CORE_SHAPES, data=P + BINDINGS + data, conforms=ok))
    add("value in the one bound scheme", "ex:doc ex:level ex:secret .", True)
    add("value outside the one bound scheme", "ex:doc ex:level ex:elsewhere .", False)
    add("two bindings, value in the first scheme", NATO + "ex:doc ex:level ex:secret .", True)
    add("two bindings, value in the second scheme", NATO + "ex:doc ex:level ex:natoSecret .", True)
    add("two bindings, value in neither scheme", NATO + "ex:doc ex:level ex:elsewhere .", False)
    return c


BUNDLE = """
ex:role a skos:Concept .
ex:profile a abnd:BundleProfile ; abnd:partSpec ex:spec .
ex:spec a abnd:PartSpec ; abnd:partRole ex:role ; abnd:extension ".dbf" .
"""


def bundle_cases():
    c = []

    def add(name, data, ok):
        c.append(dict(group="bundle paths", name=name, shapes=BUNDLE_SHAPES, data=P + data, conforms=ok))
    add("extension with a dot", BUNDLE, True)
    for label, value, ok in [("two-part extension", ".tar.gz", True), ("extension without a dot", "dbf", False),
                             ("extension that is only a dot", ".", False), ("extension of two dots", "..", False),
                             ("extension with a slash", ".a/b", False), ("extension with a backslash", ".a\\\\b", False),
                             ("empty extension", "", False), ("extension with an empty step", ".tar..gz", False),
                             ("extension with a drive colon", ".c:x", False)]:
        add(label, _sub(BUNDLE, ('".dbf"', f'"{value}"')), ok)
    patterned = _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:pathPattern "data/*.tif"'))
    add("relative path pattern", patterned, True)
    for label, value, ok in [("recursive pattern", "**/*.xml", True), ("dot-dot name that is not a segment", "..hidden/x.tif", True),
                             ("leading dot-dot segment", "../x.tif", False), ("inner dot-dot segment", "a/../x.tif", False),
                             ("trailing dot-dot segment", "a/..", False), ("backslash separator", "a\\\\b.tif", False),
                             ("drive letter", "C:/x.tif", False), ("absolute path", "/x.tif", False),
                             ("empty pattern", "", False), ("empty segment", "a//b.tif", False), ("current-directory segment", "./x.tif", False)]:
        add(label, _sub(patterned, ('"data/*.tif"', f'"{value}"')), ok)
    add("required spec allowing no part", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:required true ; abnd:maxParts 0')), False)
    add("required spec with minParts 0", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:required true ; abnd:minParts 0')), False)
    add("optional spec allowing no part", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:required false ; abnd:maxParts 0')), True)
    add("part role that is a literal", _sub(BUNDLE, ("abnd:partRole ex:role", 'abnd:partRole "dbf"')), False)
    add("part role that is not a concept", _sub(BUNDLE, ("abnd:partRole ex:role", "abnd:partRole ex:notAConcept")), False)
    add("nested profile naming its own profile", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:nestedProfile ex:profile')), False)
    add("nested profiles forming a cycle", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:nestedProfile ex:inner')) +
        'ex:inner a abnd:BundleProfile ; abnd:partSpec ex:innerSpec . ex:innerSpec a abnd:PartSpec ; abnd:extension ".shp" ; abnd:nestedProfile ex:profile .', False)
    add("nested profile naming another profile", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:nestedProfile ex:inner')) +
        'ex:inner a abnd:BundleProfile .', True)
    add("lifted property given as a literal", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:liftsProperty "width"')), False)
    add("lifted property given as an IRI", _sub(BUNDLE, ('abnd:extension ".dbf"', 'abnd:extension ".dbf" ; abnd:liftsProperty ex:width')), True)
    return c


TREE = """
bddo:string a bddo:DataType .
ex:doc a bddo:TreeDocument ; bddo:treeSyntax bddo:xml ;
    bddo:hasNamespaceBinding [ a bddo:NamespaceBinding ; bddo:namespacePrefix "a.b" ; bddo:namespaceIRI "urn:x"^^xsd:anyURI ] ;
    bddo:hasField ( ex:f ) .
ex:f a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/a.b:item" .
"""


def tree_cases():
    c = []

    def add(name, data, ok):
        c.append(dict(group="tree documents", name=name, shapes=BDDO_SHAPES, data=P + data, conforms=ok))
    add("path using a bound dotted prefix", TREE, True)
    add("path using an unbound prefix the dotted one matches as a regex", _sub(TREE, ('"/a.b:item"', '"/axb:item"')), False)
    add("path using a bound hyphenated prefix", _sub(TREE, ('"a.b"', '"a-b"'), ('"/a.b:item"', '"/a-b:item"')), True)
    add("path field shared with a struct that is not a tree", TREE + "ex:flat a bddo:Struct ; bddo:hasField ( ex:f ) .", False)
    add("path field in no container", _sub(TREE, ("bddo:hasField ( ex:f ) .", "bddo:hasField ( ) .")), False)
    return c


STRICT = """
ex:Header a bddo:Struct ; bddo:hasField ( ex:magic ) .
ex:magic a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:size 1 .
"""


def strict_cases():
    c = []

    def add(name, data, ok):
        c.append(dict(group="strict profile", name=name, shapes=STRICT_SHAPES, data=P + data, conforms=ok))
    add("plain struct and field", STRICT, True)
    add("aspect property on a field", _sub(STRICT, ("bddo:size 1", "bddo:size 1 ; <https://hexplain.io/ns/aspect/raster#width> 3")), False)
    add("field property on a struct", _sub(STRICT, ("ex:Header a bddo:Struct ;", "ex:Header a bddo:Struct ; bddo:dataType bddo:uint8 ;")), False)
    add("struct property on a field", _sub(STRICT, ("bddo:size 1", "bddo:size 1 ; bddo:hasField ( )")), False)
    add("tree property on a plain struct", _sub(STRICT, ("ex:Header a bddo:Struct ;", "ex:Header a bddo:Struct ; bddo:treeSyntax bddo:json ;")), False)
    add("tree document with its properties", "ex:Doc a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; bddo:hasField ( ex:v ) .\n"
        'ex:v a bddo:Field ; bddo:nodePath "/v" ; bddo:dataType bddo:string .', True)
    add("field property on a data type", "ex:t a bddo:DataType ; bddo:bitWidth 8 ; bddo:baseType bddo:baseInteger ; bddo:hasField ( ) .", False)
    add("untyped node using a field property and an aspect property",
        "ex:u bddo:dataType bddo:uint8 ; <https://hexplain.io/ns/aspect/raster#width> 3 .", False)
    add("untyped node using a struct property and a field property", "ex:u bddo:hasField ( ) ; bddo:dataType bddo:uint8 .", False)
    return c


def cases():
    rows = conf_cases() + req_cases() + register_cases() + binding_cases() + bundle_cases() + tree_cases() + strict_cases()
    names = [(r["group"], r["name"]) for r in rows]
    assert len(names) == len(set(names)), "probe names must be unique within a group"
    return rows
