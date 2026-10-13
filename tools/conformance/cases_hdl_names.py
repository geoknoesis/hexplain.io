"""HDL Compiler cases: names that must stay apart, and YAML mappings that must be exact.

Colliding minted IRIs (HDL, IRI Minting, One IRI, one declaration), two documents of one compilation sharing a base
namespace (Modules), an unknown key and a value of the wrong kind in any YAML mapping (YAML Surface), and a name in
the media-encoding register's namespace that is no concept of the register (Semantic Mapping). Each is an ERROR: the
alternative in every case is a graph that parses and says something the author did not write.
"""

from __future__ import annotations

from cases_hdl import err

#: A collision is an ERROR, and is not resolved by emitting anything (an error case has no compiled output).
COLLISION = ["req-hdl-iri-minting-1", "req-hdl-iri-minting-2"]
SHARED_NAMESPACE = ["req-hdl-modules-5"]
UNKNOWN_KEY = ["req-hdl-yaml-6"]
VALUE_KIND = ["req-hdl-yaml-7"]
UNKNOWN_CONCEPT = ["req-hdl-semantic-2"]

# ----------------------------------------------------------------- one IRI, one declaration

err(
    "mint-collision-struct-enum",
    "A struct and a top-level enum of one name mint one IRI",
    "struct Color and enum Color are both <base>Color: emitted, the resource would be a bddo:Struct and a "
    "bddo:Enumeration at once.",
    COLLISION,
    ["iri-minting"],
    """
    format t @namespace "{ns}"
    struct Color { v : u8 }
    enum Color { 0 => Gray, 1 => RGB }
    """,
)

err(
    "mint-collision-struct-enum-yaml",
    "A struct and a top-level enum of one name mint one IRI (YAML surface)",
    "structs.Color and enums.Color are both <base>Color; the two mappings hide the collision no better than the "
    "text does.",
    COLLISION + ["req-hdl-conformance-section-2"],
    ["iri-minting", "yaml"],
    """
    format: t
    namespace: "{ns}"
    structs:
      Color:
        fields:
          - { name: v, type: u8 }
    enums:
      Color:
        values: { 0: Gray, 1: RGB }
    """,
    yaml=True,
)

err(
    "mint-collision-enums",
    "Two top-level enums of one name mint one IRI",
    "Both declarations are <base>Mode; the second is reported.",
    COLLISION,
    ["iri-minting"],
    """
    format t @namespace "{ns}"
    struct Root { a : u8 }
    enum Mode { 0 => Off }
    enum Mode { 1 => On }
    """,
    line=4,
)

err(
    "mint-collision-dispatch-table-struct",
    "A dispatch table named as a struct mints the struct's IRI",
    "dispatch Blob and struct Blob are both <base>Blob: one resource would be a table and a struct.",
    COLLISION,
    ["iri-minting", "modules"],
    """
    format t @namespace "{ns}"
    struct Root {
      kind : u8
      body : bytes[..] dispatch Blob on kind { 1 => A }
    }
    struct A { a : u8 }
    struct Blob { raw : bytes[..] }
    """,
)

err(
    "mint-collision-dispatch-arms",
    "Two arms whose keys mint one IRI collide",
    'The string keys "a b" and "a%20b" are different keys, and both arms are <base>T.arm.a%20b.str: the space of '
    "the first is percent-encoded into the spelling of the second.",
    COLLISION + ["req-hdl-modules-4"],
    ["iri-minting", "modules"],
    """
    format t @namespace "{ns}"
    struct Root {
      kind : ascii[5]
      body : bytes[..] dispatch T on kind { "a b" => A  "a%20b" => B }
    }
    struct A { a : u8 }
    struct B { b : u8 }
    """,
    line=4,
)

err(
    "mint-collision-bundle-struct",
    "A bundle and a struct of one name mint one IRI",
    "bundle Grid and struct Grid are both <base>Grid, so the profile's described-by would name itself.",
    COLLISION,
    ["iri-minting", "bundle-profile"],
    """
    format t @namespace "{ns}"
    bundle Grid @bound-by naming-convention {
      part ".dat" role Payload required primary described-by Grid
    }
    struct Grid { v : u8 }
    """,
)

err(
    "mint-collision-asset-bundle",
    "An asset and a bundle of one name mint one IRI",
    "bundle Tiles and asset Tiles are both <base>Tiles: an asset that is its own profile.",
    COLLISION,
    ["iri-minting", "asset"],
    """
    format t @namespace "{ns}"
    bundle Tiles @bound-by naming-convention {
      part ".dat" role Payload required primary
    }
    asset Tiles conforms Tiles {
      part data role Payload
    }
    """,
)

err(
    "mint-collision-asset-part-struct",
    "An asset's part is named in the base namespace and collides with a struct of its name",
    "part Grid of asset roads is <base>Grid, not <base>roads.Grid, and so is struct Grid.",
    COLLISION,
    ["iri-minting", "asset"],
    """
    format t @namespace "{ns}"
    struct Grid { v : u8 }
    asset roads {
      part Grid role Payload
    }
    """,
)

err(
    "mint-collision-parameters",
    "Two parameters of one struct of one name mint one IRI",
    "Both parameters of Row are <base>Row.n; an argument list of two would bind one name twice.",
    COLLISION,
    ["iri-minting", "parameters"],
    """
    format t @namespace "{ns}"
    struct Root { r : Row(1, 2) }
    struct Row(n, n) { data : bytes[1] }
    """,
    line=3,
)

err(
    "mint-collision-alias-struct",
    "A field alias that spells a struct's name mints the struct's IRI",
    "a as Box is <base>Box, the alias replacing the field's own Root.a, and struct Box is <base>Box too.",
    COLLISION,
    ["iri-minting"],
    """
    format t @namespace "{ns}"
    struct Root { a as Box : u8 }
    struct Box { n : u8 }
    """,
)

# ----------------------------------------------------------------- one namespace, one document

err(
    "shared-namespace-root-and-module",
    "A module that declares the root document's namespace is an ERROR",
    "The root and lib/mod.hx both mint in the same base namespace, so <ns>Box would be whatever either declares; "
    "the import that brings the second document in is reported.",
    SHARED_NAMESPACE,
    ["modules", "iri-minting"],
    """
    format t @namespace "{ns}"
    import "lib/mod.hx" as lib
    struct Root { b : lib:Box }
    """,
    line=2,
    files={
        "lib/mod.hx": """
        module lib @namespace "{ns}"
        struct Box { n : u8 }
        """
    },
)

err(
    "shared-namespace-two-modules",
    "Two imported modules with one namespace are an ERROR",
    "one.hx and two.hx are different documents and declare the same base namespace, which is not the root's: "
    "the second import is reported.",
    SHARED_NAMESPACE,
    ["modules", "iri-minting"],
    """
    format t @namespace "{ns}"
    import "lib/one.hx" as one
    import "lib/two.hx" as two
    struct Root { a : one:A  b : two:B }
    """,
    line=3,
    files={
        "lib/one.hx": """
        module one @namespace "https://example.org/hc-shared-namespace/lib#"
        struct A { n : u8 }
        """,
        "lib/two.hx": """
        module two @namespace "https://example.org/hc-shared-namespace/lib#"
        struct B { n : u8 }
        """,
    },
)

# ----------------------------------------------------------------- YAML: unknown keys, in every mapping

YAML_HEAD = """
    format: t
    namespace: "{ns}"
    structs:
      Root:
"""


def unknown_key(id: str, where: str, intent: str, body: str, head: str = YAML_HEAD) -> None:
    err(
        f"yaml-unknown-key-{id}",
        f"An unknown key in {where} is an ERROR",
        intent,
        UNKNOWN_KEY,
        ["yaml"],
        head.strip("\n") + "\n" + body.strip("\n") + "\n",
        yaml=True,
    )


unknown_key(
    "struct",
    "a struct mapping",
    "colour is no key of a struct; ignored, the document would compile as if it were not there.",
    """
        colour: red
        fields:
          - { name: a, type: u8 }
    """,
)
unknown_key(
    "layout",
    "a layout mapping",
    "interleave is no key of layout: (the keys are cell, dims, order, chunks, cell-bits and packing).",
    """
        fields:
          - { name: w, type: u8 }
          - name: pixels
            type: bytes
            size: ".."
            layout:
              cell: u8
              interleave: bil
              dims:
                - { axis: X, size: w }
    """,
)
unknown_key(
    "dims-entry",
    "an entry of dims",
    "extent is no key of a dimension (axis, size, stride, chunk): a misspelt size would leave the dimension "
    "without one.",
    """
        fields:
          - { name: w, type: u8 }
          - name: pixels
            type: bytes
            size: ".."
            layout:
              cell: u8
              dims:
                - { axis: X, size: w, extent: 4 }
    """,
)
unknown_key(
    "dispatch",
    "a dispatch mapping",
    "fallback is no key of dispatch (name, on, default, cases): the author meant default, and without the "
    "ERROR the table would have none.",
    """
        fields:
          - { name: kind, type: u8 }
          - name: body
            type: bytes
            size: ".."
            dispatch: { name: T, on: kind, fallback: Blob, cases: { 1: Blob } }
      Blob:
        fields:
          - { name: raw, type: bytes, size: ".." }
    """,
)
unknown_key(
    "checksum",
    "a checksum mapping",
    "seed is no key of checksum (algorithm or crc, with from and to, or covers).",
    """
        fields:
          - { name: a, type: u8 }
          - name: crc
            type: u32
            checksum: { algorithm: crc32, from: a, to: a, seed: 0 }
    """,
)
unknown_key(
    "enum",
    "an enum mapping",
    "colour is no key of an enum (as, label, flags, values).",
    """
        fields:
          - { name: a, type: u8 }
    enums:
      Mode:
        colour: red
        values: { 0: Off }
    """,
)
unknown_key(
    "bundle-part",
    "a part mapping of a bundle",
    "rol is no key of a part: the part would be compiled without the role the author wrote.",
    """
    bundles:
      Sidecar:
        bound-by: naming-convention
        parts:
          - { extension: ".dat", role: Payload, rol: Metadata, required: true, primary: true }
    """,
    head="""
    format: t
    namespace: "{ns}"
    """,
)

# ----------------------------------------------------------------- YAML: a value of the wrong kind


def value_kind(id: str, title: str, intent: str, body: str, head: str = YAML_HEAD) -> None:
    err(
        f"yaml-value-kind-{id}",
        title,
        intent,
        VALUE_KIND,
        ["yaml"],
        head.strip("\n") + "\n" + body.strip("\n") + "\n",
        yaml=True,
    )


value_kind(
    "fields-scalar",
    "A scalar where fields takes a sequence is an ERROR",
    "fields: 3 is not a list of fields; read as absent, Root would be an empty struct.",
    """
        fields: 3
    """,
)
value_kind(
    "name-mapping",
    "A mapping where name takes a scalar is an ERROR",
    "name is a scalar; a mapping there names nothing.",
    """
        fields:
          - { name: { a: 1 }, type: u8 }
    """,
)
value_kind(
    "size-sequence",
    "A sequence where size takes a scalar is an ERROR",
    "size: [4] is a list; it is not coerced to its one element.",
    """
        fields:
          - { name: a, type: bytes, size: [4] }
    """,
)
value_kind(
    "layout-scalar",
    "A scalar where layout takes a mapping is an ERROR",
    "layout: u8 gives the cell type where the mapping { cell, dims } is required.",
    """
        fields:
          - { name: pixels, type: bytes, size: "..", layout: u8 }
    """,
)
value_kind(
    "structs-sequence",
    "A sequence where structs takes a mapping is an ERROR",
    "structs maps each struct's name to its declaration; a list of declarations has no names.",
    """
    structs:
      - { name: Root, fields: [ { name: a, type: u8 } ] }
    """,
    head="""
    format: t
    namespace: "{ns}"
    """,
)

# ----------------------------------------------------------------- a register name that is no concept

err(
    "encoded-with-unknown-register-concept",
    "A name in the media-encoding register's namespace that is no concept is an ERROR",
    "menc:Zlip is not in the register: it is a misspelling, not a catalogue-only codec, so the WARNING a "
    "catalogue-only concept draws does not apply and the description is not compiled.",
    UNKNOWN_CONCEPT,
    ["semantic"],
    """
    format t @namespace "{ns}"
    use menc: <https://hexplain.io/ns/register/media-encoding#>
    struct Root {
      data : bytes[..] @encoded-with menc:Zlip
    }
    """,
    line=4,
)

err(
    "pipeline-unknown-register-concept",
    "A pipeline step that names no concept of the register is an ERROR",
    "menc:Deflat names no concept; the step before it is a real codec, and the pipeline is refused all the same.",
    UNKNOWN_CONCEPT,
    ["semantic"],
    """
    format t @namespace "{ns}"
    use menc: <https://hexplain.io/ns/register/media-encoding#>
    struct Root {
      data : bytes[..] @pipeline { menc:Delta(elementSize 1), menc:Deflat }
    }
    """,
    line=4,
)
