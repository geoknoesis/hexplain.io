"""Stable identifiers for the normative requirements of the processing specifications.

Every sentence of the Processing Model, HEL, HDL and the conformance sections of the conf and
req pages that states an RFC 2119 requirement (MUST, MUST NOT, SHALL, SHALL NOT, REQUIRED,
SHOULD, SHOULD NOT, RECOMMENDED) carries an empty anchor at its start:

    <span class="req" id="req-pm-size-resolution-4"></span>A declared region ...

The conformance suite cites these IDs, so they must never be renumbered: an ID, once
assigned, keeps its number for as long as its sentence exists, and a new sentence gets the
next free number of its section. The registry specification/conformance/requirements.json
records every ID with its page, section, level and a hash of its text; test_requirement_ids
fails when an anchor is missing, duplicated or unregistered, and when a registered ID
disappears or its text changes without an entry naming it, as a whole word, in the CHANGELOG
section of the change (Unreleased).

Each entry records the conformance class it binds (by section, or by CLASS_OVERRIDE for a
sentence that binds another class), its audience (processor, or description for a rule on a
description's author, which a processor cannot fail), and, for a vocabulary page's rule that a
shape enforces, kind "shape-backed" and the shapes. The registry's text is the sentence as a
reader sees it: an empty link reads as its target's title, and a superscript as ^.

    python tools/_requirement_ids.py            # anchor new sentences and refresh the registry
    python tools/_requirement_ids.py --check    # report what --write would change; exit 1 if any
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "specification/conformance/requirements.json"

#: page -> (ID prefix, only this section id or None for the whole page)
PAGES = {
    "specification/processing/index.html": ("pm", None),
    "specification/hel/index.html": ("hel", None),
    "specification/hdl/index.html": ("hdl", None),
    "specification/conf/index.html": ("ce-conf", "conformance"),
    "specification/req/index.html": ("ce-req", "conformance"),
    # The vocabulary pages' own normative sentences (their generated term references are not
    # read: those restate the RDF). Most constrain descriptions and are enforced by a shape.
    "specification/bddo/index.html": ("bddo", None),
    "specification/dlv/index.html": ("dlv", None),
    "specification/hexplain/index.html": ("core", None),
    "specification/aspect/bundle/index.html": ("bundle", None),
    "specification/aspect/geometry/index.html": ("geometry", None),
    "specification/aspect/raster/index.html": ("raster", None),
    "specification/aspect/spatialref/index.html": ("spatialref", None),
}
VOCABULARY_PAGES = {
    page
    for page, (prefix, _) in PAGES.items()
    if prefix in ("bddo", "dlv", "core", "bundle", "geometry", "raster", "spatialref")
}
#: Default conformance class of a vocabulary page's processor requirements.
VOCABULARY_CLASS = {
    "bddo": "physical-parser",
    "dlv": "physical-parser",
    "core": "semantic-emitter",
    "bundle": "bundle-processor",
    "geometry": "semantic-emitter",
    "raster": "semantic-emitter",
    "spatialref": "semantic-emitter",
}
GENERATED = re.compile(r"<!-- BEGIN GENERATED ([A-Z ]+) -->.*?<!-- END GENERATED \1 -->", re.S)

#: Processing Model sections whose requirements belong to a class other than Physical Parser.
PM_SECTION_CLASS = {
    "iri-minting": "semantic-emitter",
    "value-mapping": "semantic-emitter",
    "computed-values": "semantic-emitter",
    "emission": "semantic-emitter",
    "multi-part-assets": "bundle-processor",
    "conformance-evaluation": "conformance-evaluator",
    "serialisation": "writer",  # the optional Writer target: the suite's writer case class, not a processor class
}

#: Sentence-level class: a requirement whose sentence binds a class other than its section's.
CLASS_OVERRIDE = {
    "req-pm-conformance-classes-1": "bundle-processor",  # nested profiles: a Bundle Processor
    "req-pm-conformance-classes-2": "hdl-compiler",  # an HDL compiler's output
    "req-pm-errors-13": "conformance-evaluator",  # the lenient mode a conformance run uses
    "req-pm-errors-14": "conformance-evaluator",
    "req-pm-multi-part-assets-3": "physical-parser",  # "a processor that is not a Bundle Processor"
    "req-hdl-layout-1": "physical-parser",  # which processor can run the example
    "req-pm-emission-1": "physical-parser",  # decoding a block is parsing
    "req-pm-privacy-1": "semantic-emitter",  # the base a processor chooses for minting
    "req-pm-privacy-2": "conformance-evaluator",  # what a run report names its input by
    "req-pm-codec-contracts-5": "hdl-compiler",  # a compiler's warning on a catalogue-only codec
}
#: Requirements on a description's author, not on a processor: they are registered and cited like
#: any other, but a processor cannot fail them, so they never count as processor requirements.
DESCRIPTION_AUDIENCE = {
    "req-hel-key-resolution-3",  # a field that expressions need MUST NOT have a reserved name
    "req-hel-name-binding-2",  # new descriptions MUST NOT use the alias
    "req-pm-context-2",  # new descriptions MUST NOT use the alias
    "req-hel-operator-precedence-1",  # a guard MUST be written with the ternary
    "req-dlv-conditional-1",  # a more specific arm MUST precede a more general one
    "req-raster-document-4",  # calibration values MUST be finite
    "req-raster-document-5",  # axes MUST NOT be forced into X/Y/Z
    "req-spatialref-document-2",  # a description MUST NOT use pixelRegistration to shift the affine
    "req-spatialref-document-7",  # a polynomialBasis IRI MUST identify a published contract
    "req-spatialref-document-8",  # coefficient orders MUST NOT be interchanged
    "req-spatialref-document-9",  # a profile MUST identify the complete contract
    "req-bddo-parameterised-structs-2",  # a parameter MUST NOT share its name with another member
    "req-bddo-parameterised-structs-4",  # a text container MUST NOT declare parameters
    "req-hel-expression-literals-2",  # authoring tools SHOULD type expressions bddo:HelExpression
    "req-pm-text-decoding-8",  # a custom encoding's ianaCharset MUST determine the byte order
}
_B, _D, _C = "https://hexplain.io/ns/bddo#", "https://hexplain.io/ns/dlv#", "https://hexplain.io/ns/core#"
_SR, _R = "https://hexplain.io/ns/aspect/spatialref#", "https://hexplain.io/ns/aspect/raster#"
#: A vocabulary page's rule that a shape of the family enforces: the ID names the sentence, the
#: shapes name its executable form. Every other vocabulary-page requirement binds a processor, or
#: (DESCRIPTION_AUDIENCE) a description's author where no shape can check it.
SHAPE_BACKED = {
    "req-bddo-core-datatypes-2": [_B + "VarintWidthShape"],
    "req-bddo-structural-properties-1": [_B + "StructShape"],
    "req-bddo-structural-properties-2": [_B + "StructShape", _B + "DataTypeShape"],
    "req-bddo-structural-properties-3": [_B + "StructShape"],
    "req-bddo-structural-properties-5": [_B + "StructShape", _B + "RangeDatatypeShape"],
    "req-bddo-field-properties-1": [_B + "FieldShape"],
    "req-bddo-field-properties-2": [_B + "FieldShape"],
    "req-bddo-field-properties-3": [_B + "DispatchKeyUniquenessShape"],
    "req-bddo-field-properties-4": [_B + "FieldSizingShape", _B + "VariableLengthFieldShape"],
    "req-bddo-field-properties-5": [_B + "FieldShape", _B + "RangeDatatypeShape"],
    "req-bddo-field-properties-6": [_B + "FieldShape"],
    "req-bddo-field-properties-7": [_B + "FieldRepetitionShape"],
    "req-bddo-field-properties-9": [_B + "DelimitedRecordsShape", _B + "RangeDatatypeShape"],
    "req-bddo-field-properties-10": [_B + "DelimitedRecordsShape", _B + "RangeDatatypeShape"],
    "req-bddo-data-type-rule-1": [_B + "DataTypeShape"],
    "req-bddo-checksum-algorithms-1": [_B + "CustomCrcShape"],
    "req-bddo-parameterised-structs-1": [_B + "ArgumentArityShape"],
    "req-bddo-parameterised-structs-3": [_B + "LocalBindingShape"],
    "req-dlv-properties-1": [_D + "DataLayoutShape"],
    "req-dlv-properties-2": [_D + "DimensionShape"],
    "req-core-static-mapping-properties-1": [_C + "MapsToClassShape"],
    "req-core-static-mapping-properties-2": [_C + "MapsToPropertyShape"],
    "req-spatialref-document-1": [_SR + "GeoTransformShape"],
    "req-spatialref-document-5": [_SR + "GroundControlPointShape"],
    "req-spatialref-document-6": [_SR + "CubicRationalTransformShape"],
    "req-raster-document-1": [_R + "BandMembershipShape"],
    "req-raster-document-2": [_R + "SampleArrayShape"],
}
CLASS_OVERRIDE.update(
    {
        "req-core-static-mapping-properties-3": "physical-parser",  # decoding a block is parsing
    }
)

KEYWORD = re.compile(r"\b(MUST NOT|MUST|SHALL NOT|SHALL|REQUIRED|SHOULD NOT|SHOULD|NOT RECOMMENDED|RECOMMENDED)\b")
MUST_LEVEL = {"MUST", "MUST NOT", "SHALL", "SHALL NOT", "REQUIRED"}
BOILERPLATE = '"MUST"'
BLOCK = {
    "p",
    "li",
    "td",
    "dd",
    "dt",
    "figcaption",
    "caption",
    "blockquote",
    "div",
    "ul",
    "ol",
    "table",
    "tr",
    "dl",
    "section",
    "body",
    "nav",
    "header",
    "footer",
    "aside",
    "main",
    "article",
}
EXCLUDED_BLOCK = {"th", "h1", "h2", "h3", "h4", "h5", "h6"}
SKIPPED = {"pre", "script", "style"}
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "cf.", "vs.", "Fig.", "no.", "approx.")
ANCHOR = re.compile(r'<span class="req" id="(req-[a-z0-9-]+)">')
TAG = re.compile(r"<!--.*?-->|<(/?)([A-Za-z][A-Za-z0-9]*)\b([^>]*)>", re.S)
#: Openings whose subject is in the previous sentence.
ANAPHOR = re.compile(r"(It|Its|They|Their|This|These|That|Those|Each|Both|Such)\b")
SPLIT = re.compile(r"(?<=[.!])[)\"”’]?\s+(?=[A-Za-z0-9(“\"'\[])")


@dataclass
class Sentence:
    page: str
    section: str
    text: str
    start: int  # source offset of its first character
    anchors: list[str] = field(default_factory=list)  # IDs of anchors inside it
    inherited: str | None = None  # level of the "...MUST:" sentence that introduces this item
    context: str | None = None  # what the sentence needs to be read alone: see `sentences` and `standalone`
    block: Block | None = None  # the Block the sentence was split from
    items: list[str] = field(default_factory=list)  # the items of the list or table this sentence introduces

    @property
    def keywords(self) -> list[str]:
        return [m.group(1) for m in KEYWORD.finditer(self.text)]

    @property
    def is_requirement(self) -> bool:
        return (bool(self.keywords) or self.inherited is not None) and BOILERPLATE not in self.text

    @property
    def level(self) -> str:
        if self.inherited:
            return self.inherited
        return "MUST" if MUST_LEVEL & set(self.keywords) else "SHOULD"

    @property
    def introduces_items(self) -> bool:
        """A requirement ending in a colon ("A conforming evaluator MUST:") governs the next list or table."""
        return bool(self.keywords) and self.text.rstrip().endswith(":")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:16]


def slug(text: str) -> str:
    head = text.split("(")[0]
    words = re.findall(r"[a-z0-9]+", head.lower())[:3]
    return "-".join(words) or "section"


@dataclass
class Block:
    section: str
    chars: list[tuple[str, int]]  # [(char, source offset)]
    anchors: list[tuple[int, str]]  # [(plain offset, anchor id)]
    kind: str  # the element holding the text: li, td, p, ...
    element: int  # a number identifying that element
    container: int  # the innermost list or table around it (0 for none)
    row: int  # the table row, for a td


HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.S)


def link_titles(page: str, source: str) -> dict[str, str]:
    """What an empty link renders as: ReSpec fills <a href="#x"></a> with the title of section x.

    The registry records a sentence as a reader sees it, so an empty link reads as its target's
    title rather than as nothing ("(see )" was the text of ten entries).
    """
    titles: dict[str, str] = {}
    for match in re.finditer(r'<a\s[^>]*href="([^"]*)"[^>]*></a>', source):
        href = match.group(1)
        target, _, fragment = href.partition("#")
        text = source
        if target:
            path = (ROOT / page).parent / target
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
        at = re.search(rf'\bid="{re.escape(fragment)}"', text) if fragment else None
        if not at:
            continue
        heading = HEADING.search(text, at.end())
        if heading:
            titles[href] = normalise(html.unescape(re.sub(r"<[^>]+>", "", heading.group(1))))
    return titles


def _blocks(
    source: str, only_section: str | None, titles: dict[str, str] | None = None, terms: dict[int, str] | None = None
) -> Iterator[Block]:
    """Yield one Block per run of text between block-level tags. `terms`, when given, is filled with what names
    a block from outside it: {table row: its header cells' text} and {dd element: the text of its dt}."""
    return _BlockReader(source, only_section, titles or {}, {} if terms is None else terms).blocks()


class _BlockReader:
    """The state of one pass over a page's markup: the open sections, elements, lists and tables, the text of the
    block being read, and whether it is in scope."""

    def __init__(self, source: str, only_section: str | None, titles: dict[str, str], terms: dict[int, str]) -> None:
        self.source, self.only_section, self.titles, self.terms = source, only_section, titles, terms
        self.header: list[list[str]] = []
        self.last_dt = ""
        self.sections: list[list[str | None]] = []  # stack of [id-or-None, heading-slug-or-None]
        self.elements: list[tuple[str, int]] = []  # stack of (tag, number) of open block elements
        self.containers = [0]
        self.counter = 0
        self.row = 0
        self.skip = self.excluded = 0
        self.chars: list[tuple[str, int]] = []
        self.anchors: list[tuple[int, str]] = []
        self.in_scope = only_section is None
        self.scope_depth: int | None = None
        self.heading_open: str | None = None
        self.heading_text: list[str] = []

    def blocks(self) -> Iterator[Block]:
        pos = 0
        for match in TAG.finditer(self.source):
            self.text(self.source[pos : match.start()], pos)
            pos = match.end()
            yield from self.tag(match)
        yield from self.flush()

    def number(self) -> int:
        self.counter += 1
        return self.counter

    def current_section(self) -> str:
        for sid, heading in reversed(self.sections):
            if sid:
                return sid
            if heading:
                return heading
        return "document"

    def flush(self) -> list[Block]:
        """The block read so far, if it has text in scope; the next block starts empty."""
        out = []
        if self.chars and self.in_scope and "".join(c for c, _ in self.chars).strip():
            kind, element = self.elements[-1] if self.elements else ("body", 0)
            out.append(
                Block(self.current_section(), self.chars, self.anchors, kind, element, self.containers[-1], self.row)
            )
        self.chars, self.anchors = [], []
        return out

    def text(self, text: str, pos: int) -> None:
        """The text between two tags, at source offset [pos]."""
        if not text or self.skip:
            return
        if self.heading_open:
            self.heading_text.append(text)
        if self.header:
            self.header[-1].append(text)
        if self.excluded:
            return
        for piece in re.finditer(r"&[#A-Za-z0-9]+;|[^&]+|&", text):
            raw = piece.group()
            if raw.startswith("&"):
                self.chars.extend((ch, pos + piece.start()) for ch in html.unescape(raw))
            else:
                self.chars.extend((ch, pos + piece.start() + i) for i, ch in enumerate(raw))

    def tag(self, match: re.Match[str]) -> list[Block]:
        """One tag: the block it ends, if any."""
        if match.group(0).startswith("<!--"):
            return []
        closing, name, attrs = match.group(1), match.group(2).lower(), match.group(3)
        if name in SKIPPED:
            self.skip += -1 if closing else 1
            return []
        if self.skip or self.inline(match, name, closing, attrs):
            return []
        if name not in BLOCK and name not in EXCLUDED_BLOCK:
            return []
        if name == "dt" and closing and self.chars:
            self.last_dt = normalise("".join(c for c, _ in self.chars))
        out = self.flush()
        if name == "th":
            self.header_cell(closing)
        if closing:
            self.close(name)
        else:
            self.open(name)
        if name == "section":
            self.section(closing, attrs)
        if name in EXCLUDED_BLOCK:
            self.excluded_block(name, closing)
        return out

    def inline(self, match: re.Match[str], name: str, closing: str, attrs: str) -> bool:
        """Whether the tag is one read inside a block's text (an anchor, a break, an empty link, a superscript)."""
        if name == "span" and not closing and 'class="req"' in attrs:
            anchor = ANCHOR.match(match.group(0))
            if anchor:
                self.anchors.append((len(self.chars), anchor.group(1)))
            return True
        if name == "br":
            if self.chars:
                self.chars.append((" ", match.start()))
            return True
        if name == "a" and not closing and not self.excluded and self.source.startswith("</a>", match.end()):
            href = re.search(r'href="([^"]*)"', attrs)
            if href:
                self.chars.extend((ch, match.start()) for ch in self.titles.get(href.group(1), ""))
            return True
        if name == "sup" and not closing and not self.excluded:
            self.chars.append(("^", match.start()))  # 2<sup>63</sup> reads as 2^63
            return True
        return False

    def header_cell(self, closing: str) -> None:
        if closing and self.header:
            cell = normalise(html.unescape(re.sub(r"<[^>]+>", "", "".join(self.header.pop()))))
            self.terms[self.row] = " | ".join(p for p in (self.terms.get(self.row, ""), cell) if p)
        elif not closing:
            self.header.append([])

    def close(self, name: str) -> None:
        while self.elements and self.elements[-1][0] != name:
            self.elements.pop()
        if self.elements:
            self.elements.pop()
        if name in ("ul", "ol", "table") and len(self.containers) > 1:
            self.containers.pop()

    def open(self, name: str) -> None:
        self.elements.append((name, self.number()))
        if name in ("ul", "ol", "table"):
            self.containers.append(self.elements[-1][1])
        if name == "tr":
            self.row = self.elements[-1][1]
        if name == "dd":
            self.terms[self.elements[-1][1]] = self.last_dt

    def section(self, closing: str, attrs: str) -> None:
        if closing:
            if self.sections:
                self.sections.pop()
            if self.scope_depth is not None and len(self.sections) < self.scope_depth:
                self.in_scope, self.scope_depth = False, None
        else:
            sid = re.search(r'\bid="([^"]+)"', attrs)
            self.sections.append([sid.group(1) if sid else None, None])
            if self.only_section and sid and sid.group(1) == self.only_section:
                self.in_scope, self.scope_depth = True, len(self.sections)

    def excluded_block(self, name: str, closing: str) -> None:
        if closing:
            self.excluded = max(0, self.excluded - 1)
            if name.startswith("h") and self.heading_open == name:
                self.heading_open = None
                if self.sections and self.sections[-1][1] is None:
                    self.sections[-1][1] = slug("".join(self.heading_text))
        else:
            self.excluded += 1
            if name.startswith("h"):
                self.heading_open, self.heading_text = name, []


def _split(
    page: str,
    block: Block,
    inherited: str | None = None,
    text_override: str | None = None,
    context: str | None = None,
) -> list[Sentence]:
    chars, anchors = block.chars, block.anchors
    plain = "".join(c for c, _ in chars)
    if inherited:
        # One requirement for the whole item: the list item, or the table row it heads.
        start = len(plain) - len(plain.lstrip())
        return [
            Sentence(
                page,
                block.section,
                normalise(text_override or plain),
                chars[start][1],
                [aid for _, aid in anchors],
                inherited,
                context,
                block,
            )
        ]
    bounds = (
        [0]
        + [m.end() for m in SPLIT.finditer(plain) if not plain[: m.start() + 1].rstrip().endswith(ABBREVIATIONS)]
        + [len(plain)]
    )
    out = []
    for a, b in zip(bounds, bounds[1:], strict=False):
        start = a + len(plain[a:b]) - len(plain[a:b].lstrip())
        text = plain[start:b].strip()
        if text:
            ids = [aid for off, aid in anchors if a <= off < b]
            out.append(Sentence(page, block.section, text, chars[start][1], ids, block=block))
    return out


class Governing(NamedTuple):
    """A requirement ending in a colon and the list or table it governs: its level, the container (of the
    sentence while the list is pending, of the list once it is read), its text, and the sentence itself."""

    level: str
    container: int
    text: str
    sentence: Sentence


def _plain(block: Block) -> str:
    return "".join(c for c, _ in block.chars)


def _governing(
    block: Block, pending: Governing | None, governed: Governing | None
) -> tuple[Governing | None, Governing | None]:
    """(pending, governed) once [block] is reached: only a list or table that directly follows the introducing
    sentence is governed by it, and the governed list ends at the first block outside it that is not an item."""
    if pending:
        if block.container not in (0, pending.container):
            governed = pending._replace(container=block.container)
        return None, governed
    if governed and block.container != governed.container and block.kind not in ("li", "td"):
        return None, None
    return None, governed


def _inheritance(block: Block, governed: Governing, rows: dict[int, list[Block]]) -> tuple[str | None, str | None]:
    """(level, text) an item of a governed list or table takes from the sentence introducing it: a list item, or a
    table row's first cell (the row is the item), that states no keyword of its own."""
    plain = _plain(block)
    if block.kind == "li" and not KEYWORD.search(plain):
        return governed.level, None
    if block.kind == "td" and rows[block.row][0] is block and not KEYWORD.search(plain):
        return governed.level, " | ".join(normalise(_plain(b)) for b in rows[block.row])
    return None, None


def sentences(page: str, source: str) -> list[Sentence]:
    """Every sentence of the page's normative text, in document order.

    A requirement that ends in a colon ("A conforming HEL 1.0 evaluator MUST:") governs the list or
    table that follows it: each item of that list, and each row of that table, is a requirement of
    the same level, anchored at the item (or at the row's first cell) unless it states a keyword
    of its own, in which case its own sentences carry the anchors.
    """
    titles = link_titles(page, source)
    # A generated region restates other sources (the term reference restates the RDF); blank it
    # out, keeping every offset, so its sentences are neither anchored nor registered.
    source = GENERATED.sub(lambda m: " " * len(m.group(0)), source)
    terms: dict[int, str] = {}
    blocks = list(_blocks(source, PAGES[page][1], titles, terms))
    rows: dict[int, list[Block]] = {}
    for block in blocks:
        if block.kind == "td":
            rows.setdefault(block.row, []).append(block)
    out: list[Sentence] = []
    pending: Governing | None = None
    governed: Governing | None = None
    seen: set[int] = set()
    for block in blocks:
        pending, governed = _governing(block, pending, governed)
        inherit = override = None
        first = governed is not None and block.container == governed.container and block.element not in seen
        if governed is not None and first:
            inherit, override = _inheritance(block, governed, rows)
            if block.kind in ("li", "td"):
                governed.sentence.items.append(normalise(_plain(block)))
        seen.add(block.element)
        # An item of a governed list or table is a fragment on its own ("Integer | An xsd:long literal ..."):
        # the registry records the sentence that introduces the list with it, so the entry stands alone.
        context = normalise(governed.text) if governed is not None and inherit else None
        items = _split(page, block, inherit, override, context)
        if governed is not None and block.container == governed.container and block.kind in ("li", "td"):
            for s in items:
                if s.is_requirement and not s.inherited:
                    s.context = normalise(governed.text)
        for s in items:
            if s.introduces_items and not inherit:
                pending = Governing(s.level, block.container, s.text, s)
        out.extend(items)
    _anaphora(out)
    standalone(out, rows, terms, source)
    return out


def _anaphora(out: list[Sentence]) -> None:
    """A sentence that opens with a pronoun ("It MUST be raised ...") names its subject in the sentence before it;
    the registry records that sentence too, so an entry read on its own keeps its subject."""
    for before, s in zip(out, out[1:], strict=False):
        if s.is_requirement and not s.inherited and ANAPHOR.match(s.text):
            s.context = normalise(before.text)


#: A requirement shorter than this names its subject elsewhere ("Value MUST be a bddo:DataType.").
SHORT = 60
#: How much of an introduced item, and of the whole introduced list, a list head's context quotes.
ITEM_QUOTE, LIST_QUOTE = 160, 1200
#: A requirement that introduces the rules after it.
HEAD = re.compile(r"(:|\bas follows\.)$")
PRE = re.compile(r"\s*(?:</[a-z0-9]+>\s*)*<pre\b[^>]*>(.*?)</pre>", re.S)


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


def introduced(s: Sentence, after: list[Sentence], source: str) -> str | None:
    """What a list head introduces, quoted so the entry reads alone: the items of the list or table it governs;
    for a head followed by a grammar or an example, the opening of that block; and for a head whose rules follow
    in its own paragraph ("... as follows. With ..."), those sentences."""
    if s.items:
        return clip("Introduces: " + " | ".join(clip(item, ITEM_QUOTE) for item in s.items), LIST_QUOTE)
    block = PRE.match(source, s.block.chars[-1][1] + 1) if s.block else None
    if block and s.text.rstrip().endswith(":"):
        return clip("Introduces: " + normalise(html.unescape(re.sub(r"<[^>]+>", "", block.group(1)))), LIST_QUOTE)
    rest = [normalise(t.text) for t in after if t.block is s.block]
    return clip("Introduces: " + " ".join(rest), LIST_QUOTE) if rest else None


def surroundings(s: Sentence, before: Sentence | None, rows: dict[int, list[Block]], terms: dict[int, str]) -> str:
    """The subject of a short requirement: the rest of its table row (its header cell first), or the term a
    definition belongs to, then the sentence before it."""
    block, parts = s.block, []
    assert block is not None, "a registered sentence is split from a block"
    if block.kind == "td":
        parts = [terms.get(block.row, "")]
        parts += [normalise("".join(c for c, _ in b.chars)) for b in rows[block.row] if b is not block]
    elif block.kind == "dd":
        parts = [terms.get(block.element, "")]
    if before is not None and (before.block is block or not any(parts)):
        parts.append(normalise(before.text))
    return clip(" | ".join(p for p in parts if p), LIST_QUOTE)


def standalone(out: list[Sentence], rows: dict[int, list[Block]], terms: dict[int, str], source: str) -> None:
    """Give every requirement that cannot be read alone a context: a list head ("... MUST:", "... as follows.")
    gets what it introduces, and a short sentence gets its table row or definition term and the sentence before
    it. A context already set (the introducing sentence of an item, the antecedent of a pronoun) is kept."""
    before = None
    for n, s in enumerate(out):
        if s.is_requirement and not s.inherited and not s.context:
            head = bool(s.items) or bool(HEAD.search(s.text.rstrip()))
            if head:
                s.context = introduced(s, out[n + 1 :], source)
            if not s.context and (head or len(normalise(s.text)) < SHORT):
                s.context = surroundings(s, before, rows, terms) or None
        before = s


def read(page: str) -> str:
    """The page's text with its line endings as they are on disk, so a rewrite changes only anchors."""
    with open(ROOT / page, encoding="utf-8", newline="") as stream:
        return stream.read()


def load_registry() -> dict[str, Any]:
    if REGISTRY.is_file():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"schema": 1, "requirements": {}}


def requirement_class(page: str, section: str, identifier: str | None = None) -> str:
    if identifier in CLASS_OVERRIDE:
        return CLASS_OVERRIDE[identifier]
    prefix = PAGES[page][0]
    if prefix == "pm":
        return PM_SECTION_CLASS.get(section, "physical-parser")
    if prefix in VOCABULARY_CLASS:
        return VOCABULARY_CLASS[prefix]
    return {"hel": "hel", "hdl": "hdl-compiler"}.get(prefix, "conformance-evaluator")


def audience(identifier: str) -> str:
    """processor, or description for a rule on a description's author (a shape-backed one included)."""
    return "description" if identifier in DESCRIPTION_AUDIENCE or identifier in SHAPE_BACKED else "processor"


def scan() -> tuple[dict[str, list[Sentence]], list[str]]:
    """(sentences per page, problems) for the pages as they are on disk."""
    found: dict[str, list[Sentence]] = {}
    problems: list[str] = []
    for page in PAGES:
        source = read(page)
        found[page] = sentences(page, source)
        for s in found[page]:
            if not s.is_requirement and s.anchors:
                problems.append(
                    f"{page}: anchor {', '.join(s.anchors)} is on a sentence with no requirement: {s.text[:90]!r}"
                )
            if s.is_requirement and len(s.anchors) > 1:
                problems.append(f"{page}: one requirement carries several anchors {s.anchors}: {s.text[:90]!r}")
    return found, problems


def entries(found: dict[str, list[Sentence]]) -> dict[str, dict[str, Any]]:
    out = {}
    for page, items in found.items():
        for s in items:
            if s.is_requirement and len(s.anchors) == 1:
                identifier = s.anchors[0]
                entry: dict[str, Any] = dict(
                    page=page,
                    section=s.section,
                    cls=requirement_class(page, s.section, identifier),
                    level=s.level,
                    audience=audience(identifier),
                    text=normalise(s.text),
                    sha256=text_hash(s.text),
                )
                if s.context:
                    entry["context"] = s.context
                if identifier in SHAPE_BACKED:
                    entry.update(kind="shape-backed", shapes=list(SHAPE_BACKED[identifier]))
                out[identifier] = entry
    return out


def assign(write: bool) -> tuple[int, list[str]]:
    """Anchor every unanchored requirement sentence; return the number of anchors added."""
    found, problems = scan()
    registry = load_registry()["requirements"]
    used = set(registry) | {a for items in found.values() for s in items for a in s.anchors}
    added = 0
    for page, items in found.items():
        prefix = PAGES[page][0]
        missing = [s for s in items if s.is_requirement and not s.anchors]
        if not missing:
            continue
        source = read(page)
        inserts = []
        for s in missing:
            stem = f"req-{prefix}-{s.section}-"
            numbers = [int(i[len(stem) :]) for i in used if i.startswith(stem) and i[len(stem) :].isdigit()]
            new = f"{stem}{max(numbers, default=0) + 1}"
            used.add(new)
            inserts.append((s.start, f'<span class="req" id="{new}"></span>'))
            added += 1
        for offset, markup in sorted(inserts, reverse=True):
            source = source[:offset] + markup + source[offset:]
        if write:
            (ROOT / page).write_text(source, encoding="utf-8", newline="")
    return added, problems


CHANGELOG = ROOT / "CHANGELOG.md"
#: The text of a withdrawn entry as a reader saw it, where the registry recorded it before empty links
#: were read as their target's title (its hash is of the text as recorded then).
LEGACY_TEXT = {
    "req-pm-errors-15": "A HEL type error, division/modulo by zero, undefined name, forward reference, or an array "
    "subscript out of range; asset.X read before part X is parsed or naming a part the asset does "
    "not have, and the asset root or partExtension() in a part parsed on its own (Multi-part "
    "Assets); a malformed HEL expression (one the HEL grammar does not generate, including an "
    "out-of-range literal, an unknown escape or a call with the wrong number of arguments), which "
    "SHOULD be raised when the description is loaded and is this category, not a Description "
    "error, even then.",
}
ID_PATTERN = re.compile(
    r"^req-(pm|hel|hdl|ce-conf|ce-req|bddo|dlv|core|bundle|geometry|raster|spatialref)"
    r"-[a-z0-9]+(-[a-z0-9]+)*-[1-9][0-9]*$"
)


def pending_changes(changelog: str) -> str:
    """The CHANGELOG section that records changes not yet in a snapshot.

    A changed or withdrawn requirement must be named where its change is recorded -- the
    "Unreleased" section, or the newest section when there is none -- not anywhere in the file:
    a mention in a snapshot's section from months ago records that change, not this one.
    """
    sections = re.split(r"(?m)^## ", changelog)[1:]
    for section in sections:
        if section.lower().startswith("unreleased"):
            return section
    return sections[0] if sections else ""


def names(text: str, identifier: str) -> bool:
    """True when [text] names [identifier] as a whole word: req-pm-errors-1 is not in req-pm-errors-10."""
    return re.search(r"(?<![A-Za-z0-9-])" + re.escape(identifier) + r"(?![A-Za-z0-9-])", text) is not None


def reconcile(
    current: dict[str, dict[str, Any]], old: dict[str, dict[str, Any]], changelog: str
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """The registry that follows from the pages ([current]) and the previous registry ([old]).

    An ID never changes meaning silently: when its sentence's text changes, the old hash is kept in
    the entry's history, and when its sentence disappears the entry stays, marked withdrawn. Either
    needs an entry in the pending section of CHANGELOG.md that names the ID exactly; without one
    this returns a problem instead.
    """
    merged: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for identifier, entry in current.items():
        before = old.get(identifier)
        history = list(before.get("history", [])) if before else []
        if before and not before.get("withdrawn") and before["sha256"] != entry["sha256"]:
            if not names(changelog, identifier):
                problems.append(f"{identifier}: its text changed; name it in CHANGELOG.md or restore the text")
            history.append(before["sha256"])
        if before and before.get("withdrawn"):
            problems.append(f"{identifier}: a withdrawn ID is anchored again; IDs are never reused")
        merged[identifier] = dict(entry, **({"history": history} if history else {}))
    for identifier, before in old.items():
        if identifier in merged:
            continue
        if not before.get("withdrawn") and not names(changelog, identifier):
            problems.append(f"{identifier}: its anchor disappeared; name it in CHANGELOG.md or restore it")
        # An entry withdrawn before the registry recorded audiences, or before empty links read as their
        # target's title, is completed here: the registry, not the page, is its only record.
        withdrawn = dict(before, withdrawn=True)
        withdrawn.setdefault("audience", audience(identifier))
        withdrawn["text"] = LEGACY_TEXT.get(identifier, withdrawn["text"])
        merged[identifier] = withdrawn
    for identifier in merged:
        if not ID_PATTERN.match(identifier):
            problems.append(f"{identifier}: not a well-formed requirement ID")
    return {i: merged[i] for i in sorted(merged, key=sort_key)}, problems


def main(argv: list[str]) -> int:
    write = "--check" not in argv
    added, problems = assign(write)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    found, _ = scan()
    current = entries(found)
    old = load_registry()["requirements"]
    changelog = pending_changes(CHANGELOG.read_text(encoding="utf-8")) if CHANGELOG.is_file() else ""
    merged, problems = reconcile(current, old, changelog)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    if write:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(
            json.dumps({"schema": 1, "requirements": merged}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"anchored {added} new requirement(s); registry lists {len(merged)}")
        return 0
    if added or merged != old:
        stale = sorted(i for i in merged.keys() | old.keys() if merged.get(i) != old.get(i))
        print(
            f"FAIL: {added} requirement sentence(s) lack an anchor and {len(stale)} registry entr(ies) are "
            "missing or stale; run python tools/_requirement_ids.py\n  " + "\n  ".join(stale[:20])
        )
        return 1
    live = sum(1 for e in merged.values() if not e.get("withdrawn"))
    print(f"PASS: {live} requirements anchored and registered ({len(merged) - live} withdrawn)")
    return 0


def sort_key(identifier: str) -> tuple[int, str, int]:
    order = {p[0]: n for n, p in enumerate(PAGES.values())}
    stem, _, number = identifier.rpartition("-")
    prefix = next((p for p in sorted(order, key=len, reverse=True) if identifier.startswith(f"req-{p}-")), "")
    return (order.get(prefix, 99), stem, int(number) if number.isdigit() else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
