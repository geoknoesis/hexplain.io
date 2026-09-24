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
disappears or its text changes without a CHANGELOG entry naming it.

    python tools/_requirement_ids.py            # anchor new sentences and refresh the registry
    python tools/_requirement_ids.py --check    # report what --write would change; exit 1 if any
"""
import hashlib
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "specification/conformance/requirements.json"

#: page -> (ID prefix, only this section id or None for the whole page, default class)
PAGES = {
    "specification/processing/index.html": ("pm", None),
    "specification/hel/index.html": ("hel", None),
    "specification/hdl/index.html": ("hdl", None),
    "specification/conf/index.html": ("ce-conf", "conformance"),
    "specification/req/index.html": ("ce-req", "conformance"),
}

#: Processing Model sections whose requirements belong to a class other than Physical Parser.
PM_SECTION_CLASS = {
    "iri-minting": "semantic-emitter",
    "value-mapping": "semantic-emitter",
    "emission": "semantic-emitter",
    "multi-part-assets": "bundle-processor",
    "conformance-evaluation": "conformance-evaluator",
}

KEYWORD = re.compile(r"\b(MUST NOT|MUST|SHALL NOT|SHALL|REQUIRED|SHOULD NOT|SHOULD|NOT RECOMMENDED|RECOMMENDED)\b")
MUST_LEVEL = {"MUST", "MUST NOT", "SHALL", "SHALL NOT", "REQUIRED"}
BOILERPLATE = '"MUST"'
BLOCK = {"p", "li", "td", "dd", "dt", "figcaption", "caption", "blockquote", "div", "ul", "ol",
         "table", "tr", "dl", "section", "body", "nav", "header", "footer", "aside", "main", "article"}
EXCLUDED_BLOCK = {"th", "h1", "h2", "h3", "h4", "h5", "h6"}
SKIPPED = {"pre", "script", "style"}
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "cf.", "vs.", "Fig.", "no.", "approx.")
ANCHOR = re.compile(r'<span class="req" id="(req-[a-z0-9-]+)">')
TAG = re.compile(r"<!--.*?-->|<(/?)([A-Za-z][A-Za-z0-9]*)\b([^>]*)>", re.S)
SPLIT = re.compile(r"(?<=[.!])[)\"”’]?\s+(?=[A-Za-z0-9(“\"'\[])")


@dataclass
class Sentence:
    page: str
    section: str
    text: str
    start: int                      # source offset of its first character
    anchors: list = field(default_factory=list)   # IDs of anchors inside it
    inherited: str = None           # level of the "...MUST:" sentence that introduces this item

    @property
    def keywords(self):
        return [m.group(1) for m in KEYWORD.finditer(self.text)]

    @property
    def is_requirement(self):
        return (bool(self.keywords) or self.inherited is not None) and BOILERPLATE not in self.text

    @property
    def level(self):
        if self.inherited:
            return self.inherited
        return "MUST" if MUST_LEVEL & set(self.keywords) else "SHOULD"

    @property
    def introduces_items(self):
        """A requirement ending in a colon ("A conforming evaluator MUST:") governs the next list or table."""
        return bool(self.keywords) and self.text.rstrip().endswith(":")


def normalise(text):
    return re.sub(r"\s+", " ", text).strip()


def text_hash(text):
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:16]


def slug(text):
    head = text.split("(")[0]
    words = re.findall(r"[a-z0-9]+", head.lower())[:3]
    return "-".join(words) or "section"


@dataclass
class Block:
    section: str
    chars: list          # [(char, source offset)]
    anchors: list        # [(plain offset, anchor id)]
    kind: str            # the element holding the text: li, td, p, ...
    element: int         # a number identifying that element
    container: int       # the innermost list or table around it (0 for none)
    row: int             # the table row, for a td


def _blocks(source, only_section):
    """Yield one Block per run of text between block-level tags."""
    sections = []            # stack of [id-or-None, heading-slug-or-None]
    elements = []            # stack of (tag, number) of open block elements
    containers = [0]
    counter = [0]
    row = 0
    skip = excluded = 0
    chars, anchors = [], []
    in_scope = only_section is None
    scope_depth = None
    heading_open, heading_text = None, []

    def number():
        counter[0] += 1
        return counter[0]

    def current_section():
        for sid, heading in reversed(sections):
            if sid:
                return sid
            if heading:
                return heading
        return "document"

    def flush():
        nonlocal chars, anchors
        if chars and in_scope and "".join(c for c, _ in chars).strip():
            kind, element = elements[-1] if elements else ("body", 0)
            yield Block(current_section(), chars, anchors, kind, element, containers[-1], row)
        chars, anchors = [], []

    pos = 0
    for match in TAG.finditer(source):
        text = source[pos:match.start()]
        if text and not skip:
            if heading_open:
                heading_text.append(text)
            if not excluded:
                for piece in re.finditer(r"&[#A-Za-z0-9]+;|[^&]+|&", text):
                    raw = piece.group()
                    if raw.startswith("&"):
                        chars.extend((ch, pos + piece.start()) for ch in html.unescape(raw))
                    else:
                        chars.extend((ch, pos + piece.start() + i) for i, ch in enumerate(raw))
        pos = match.end()
        if match.group(0).startswith("<!--"):
            continue
        closing, name, attrs = match.group(1), match.group(2).lower(), match.group(3)
        if name in SKIPPED:
            skip += -1 if closing else 1
            continue
        if skip:
            continue
        if name == "span" and not closing and 'class="req"' in attrs:
            anchor = ANCHOR.match(match.group(0))
            if anchor:
                anchors.append((len(chars), anchor.group(1)))
            continue
        if name == "br":
            if chars:
                chars.append((" ", match.start()))
            continue
        if name not in BLOCK and name not in EXCLUDED_BLOCK:
            continue
        yield from flush()
        if closing:
            while elements and elements[-1][0] != name:
                elements.pop()
            if elements:
                elements.pop()
            if name in ("ul", "ol", "table") and len(containers) > 1:
                containers.pop()
        else:
            elements.append((name, number()))
            if name in ("ul", "ol", "table"):
                containers.append(elements[-1][1])
            if name == "tr":
                row = elements[-1][1]
        if name == "section":
            if closing:
                if sections:
                    sections.pop()
                if scope_depth is not None and len(sections) < scope_depth:
                    in_scope, scope_depth = False, None
            else:
                sid = re.search(r'\bid="([^"]+)"', attrs)
                sections.append([sid.group(1) if sid else None, None])
                if only_section and sid and sid.group(1) == only_section:
                    in_scope, scope_depth = True, len(sections)
        if name in EXCLUDED_BLOCK:
            if closing:
                excluded = max(0, excluded - 1)
                if name.startswith("h") and heading_open == name:
                    heading_open = None
                    if sections and sections[-1][1] is None:
                        sections[-1][1] = slug("".join(heading_text))
            else:
                excluded += 1
                if name.startswith("h"):
                    heading_open, heading_text = name, []
    yield from flush()


def _split(page, block, inherited=None, text_override=None):
    chars, anchors = block.chars, block.anchors
    plain = "".join(c for c, _ in chars)
    if inherited:
        # One requirement for the whole item: the list item, or the table row it heads.
        start = len(plain) - len(plain.lstrip())
        return [Sentence(page, block.section, normalise(text_override or plain), chars[start][1],
                         [aid for _, aid in anchors], inherited)]
    bounds = [0] + [m.end() for m in SPLIT.finditer(plain)
                    if not plain[:m.start() + 1].rstrip().endswith(ABBREVIATIONS)] + [len(plain)]
    out = []
    for a, b in zip(bounds, bounds[1:], strict=False):
        start = a + len(plain[a:b]) - len(plain[a:b].lstrip())
        text = plain[start:b].strip()
        if text:
            out.append(Sentence(page, block.section, text, chars[start][1],
                                [aid for off, aid in anchors if a <= off < b]))
    return out


def sentences(page, source):
    """Every sentence of the page's normative text, in document order.

    A requirement that ends in a colon ("A conforming HEL 1.0 evaluator MUST:") governs the list or
    table that follows it: each item of that list, and each row of that table, is a requirement of
    the same level, anchored at the item (or at the row's first cell) unless it states a keyword
    of its own, in which case its own sentences carry the anchors.
    """
    blocks = list(_blocks(source, PAGES[page][1]))
    rows = {}
    for block in blocks:
        if block.kind == "td":
            rows.setdefault(block.row, []).append(block)
    out = []
    pending = None           # (level, container of the introducing sentence)
    governed = None          # (level, container) of the list or table being read
    seen = set()
    for block in blocks:
        if pending:
            # Only a list or table that directly follows the introducing sentence is governed by it.
            if block.container not in (0, pending[1]):
                governed = (pending[0], block.container)
            pending = None
        elif governed and block.container != governed[1] and block.kind not in ("li", "td"):
            governed = None
        inherit = override = None
        if governed and block.container == governed[1] and block.element not in seen:
            plain = "".join(c for c, _ in block.chars)
            if block.kind == "li" and not KEYWORD.search(plain):
                inherit = governed[0]
            elif block.kind == "td" and rows[block.row][0] is block and not KEYWORD.search(plain):
                inherit = governed[0]
                override = " | ".join(normalise("".join(c for c, _ in b.chars)) for b in rows[block.row])
        seen.add(block.element)
        items = _split(page, block, inherit, override)
        for s in items:
            if s.introduces_items and not inherit:
                pending = (s.level, block.container)
        out.extend(items)
    return out


def read(page):
    """The page's text with its line endings as they are on disk, so a rewrite changes only anchors."""
    with open(ROOT / page, encoding="utf-8", newline="") as stream:
        return stream.read()


def load_registry():
    if REGISTRY.is_file():
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {"schema": 1, "requirements": {}}


def requirement_class(page, section):
    prefix = PAGES[page][0]
    if prefix == "pm":
        return PM_SECTION_CLASS.get(section, "physical-parser")
    return {"hel": "hel", "hdl": "hdl-compiler"}.get(prefix, "conformance-evaluator")


def scan():
    """(sentences per page, problems) for the pages as they are on disk."""
    found, problems = {}, []
    for page in PAGES:
        source = read(page)
        found[page] = sentences(page, source)
        for s in found[page]:
            if not s.is_requirement and s.anchors:
                problems.append(f"{page}: anchor {', '.join(s.anchors)} is on a sentence with no requirement: {s.text[:90]!r}")
            if s.is_requirement and len(s.anchors) > 1:
                problems.append(f"{page}: one requirement carries several anchors {s.anchors}: {s.text[:90]!r}")
    return found, problems


def entries(found):
    out = {}
    for page, items in found.items():
        for s in items:
            if s.is_requirement and len(s.anchors) == 1:
                out[s.anchors[0]] = dict(page=page, section=s.section, cls=requirement_class(page, s.section),
                                         level=s.level, text=normalise(s.text), sha256=text_hash(s.text))
    return out


def assign(write):
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
            numbers = [int(i[len(stem):]) for i in used if i.startswith(stem) and i[len(stem):].isdigit()]
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
ID_PATTERN = re.compile(r"^req-(pm|hel|hdl|ce-conf|ce-req)-[a-z0-9]+(-[a-z0-9]+)*-[1-9][0-9]*$")


def reconcile(current, old, changelog):
    """The registry that follows from the pages ([current]) and the previous registry ([old]).

    An ID never changes meaning silently: when its sentence's text changes, the old hash is kept in
    the entry's history, and when its sentence disappears the entry stays, marked withdrawn. Either
    needs a CHANGELOG.md entry that names the ID; without one this returns a problem instead.
    """
    merged, problems = {}, []
    for identifier, entry in current.items():
        before = old.get(identifier)
        history = list(before.get("history", [])) if before else []
        if before and not before.get("withdrawn") and before["sha256"] != entry["sha256"]:
            if identifier not in changelog:
                problems.append(f"{identifier}: its text changed; name it in CHANGELOG.md or restore the text")
            history.append(before["sha256"])
        if before and before.get("withdrawn"):
            problems.append(f"{identifier}: a withdrawn ID is anchored again; IDs are never reused")
        merged[identifier] = dict(entry, **({"history": history} if history else {}))
    for identifier, before in old.items():
        if identifier in merged:
            continue
        if not before.get("withdrawn") and identifier not in changelog:
            problems.append(f"{identifier}: its anchor disappeared; name it in CHANGELOG.md or restore it")
        merged[identifier] = dict(before, withdrawn=True)
    for identifier in merged:
        if not ID_PATTERN.match(identifier):
            problems.append(f"{identifier}: not a well-formed requirement ID")
    return {i: merged[i] for i in sorted(merged, key=sort_key)}, problems


def main(argv):
    write = "--check" not in argv
    added, problems = assign(write)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    found, _ = scan()
    current = entries(found)
    old = load_registry()["requirements"]
    changelog = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.is_file() else ""
    merged, problems = reconcile(current, old, changelog)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    if write:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(json.dumps({"schema": 1, "requirements": merged}, indent=1, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
        print(f"anchored {added} new requirement(s); registry lists {len(merged)}")
        return 0
    if added or merged != old:
        stale = sorted(i for i in merged.keys() | old.keys() if merged.get(i) != old.get(i))
        print(f"FAIL: {added} requirement sentence(s) lack an anchor and {len(stale)} registry entr(ies) are "
              "missing or stale; run python tools/_requirement_ids.py\n  " + "\n  ".join(stale[:20]))
        return 1
    live = sum(1 for e in merged.values() if not e.get("withdrawn"))
    print(f"PASS: {live} requirements anchored and registered ({len(merged) - live} withdrawn)")
    return 0


def sort_key(identifier):
    order = {p[0]: n for n, p in enumerate(PAGES.values())}
    stem, _, number = identifier.rpartition("-")
    prefix = next((p for p in sorted(order, key=len, reverse=True) if identifier.startswith(f"req-{p}-")), "")
    return (order.get(prefix, 99), stem, int(number) if number.isdigit() else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
