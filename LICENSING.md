# License declarations

The repository has two licensing regimes, decided by its owner.

**Ontology modules: CC BY 4.0.** Every ontology module of the specification family -- each
Turtle file listed in `specification/family.json`, vocabularies, aspects, registers and the
separate `conf/shapes.ttl` and `req/shapes.ttl` documents alike -- declares
`dcterms:license <https://creativecommons.org/licenses/by/4.0/>` and names its creator with
`dcterms:creator <https://geoknoesis.com>`. Attribute reuse to Geoknoesis, the Hexplain
specification. `tools/test_ontology_licenses.py` fails if a module omits the declaration or
declares another licence.

**Everything else: proprietary, all rights reserved.** Files without a notice of their own --
the tools and other code, the format profiles, the documentation and the site -- are covered by
the proprietary notice in [`LICENSE`](LICENSE) (copyright Stephane Fellah / Geoknoesis).

`LICENSE` does not override a more specific declaration. Existing per-file and RDF
`dcterms:license` declarations remain authoritative, and the ontology content a documentation
page reproduces keeps its CC BY 4.0 licence. Imported samples and external specifications
retain their own notices; they are not relicensed here.
