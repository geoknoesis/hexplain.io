"""Physical Parser cases: the further text encodings (Processing Model, Decoding text, Further encodings).

A Physical Parser need not decode an encoding beyond the five every parser reads, so every case here is gated: its
manifest's `encodings.requires` names the bddo:Encoding it uses, and a processor whose claims statement does not
list that encoding skips the case. For a processor that does list it, the cases fix one decode per encoding and
every point at which the encoding's definition makes a byte sequence not well-formed. The expected text of each
decode is read off the character set's registered mapping (the Unicode Consortium's mapping tables for the
single-byte sets and JIS X 0208 for Shift_JIS), never off a decoder.
"""

from __future__ import annotations

from typing import Any

from cases_physical import pp
from suite import ENCODING_NAMESPACE

SECTIONS = ["text-decoding"]
#: The requirement that governs the Further encodings list (a processor that decodes one decodes it by its mapping
#: and takes exactly these sequences as well-formed), the requirement of each family (the items of the list), and
#: the two rules every refusal rests on: text that is not well-formed is a validation error, and is never replaced.
DECODES = "req-pm-text-decoding-9"
UTF32 = "req-pm-text-decoding-10"
UCS2 = "req-pm-text-decoding-11"
SINGLE_BYTE = "req-pm-text-decoding-12"
SHIFT_JIS = "req-pm-text-decoding-13"
NOT_REPLACED = "req-pm-text-decoding-1"
REFUSED = "req-pm-text-decoding-2"


def encoded(
    id: str,
    title: str,
    intent: str,
    family: str,
    encoding: str,
    data: bytes,
    text: str | None = None,
) -> None:
    """One string field of the whole input in [encoding] (a bddo:Encoding local name): [text] when it decodes,
    a validation error when [text] is None."""
    extra: dict[str, Any] = {"expected": {"s": text}} if text is not None else {"error": "Validation"}
    pp(
        f"encoding-{id}",
        title,
        intent,
        [DECODES, family] if text is not None else [DECODES, family, REFUSED, NOT_REPLACED],
        SECTIONS,
        f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:{encoding} ; bddo:size {len(data)} .
   """,
        data,
        manifest={"encodings": {"requires": [ENCODING_NAMESPACE + encoding]}},
        **extra,
    )


# ----------------------------------------------------------------- UTF-32

encoded(
    "utf32le-decodes",
    "UTF-32LE reads four bytes to a scalar value, least significant byte first",
    "41 00 00 00 is U+0041 and 00 F6 01 00 is U+1F600, beyond the Basic Multilingual Plane, in one code unit.",
    UTF32,
    "utf32le",
    bytes.fromhex("41000000 00f60100"),
    "A\U0001f600",
)
encoded(
    "utf32be-decodes",
    "UTF-32BE reads four bytes to a scalar value, most significant byte first",
    "00 00 00 41 is U+0041 and 00 01 F6 00 is U+1F600. A leading 00 00 FE FF would be content, not a mark removed.",
    UTF32,
    "utf32be",
    bytes.fromhex("00000041 0001f600"),
    "A\U0001f600",
)
encoded(
    "utf32be-byte-order-mark-is-content",
    "A byte order mark is ordinary content in UTF-32",
    "00 00 FE FF is U+FEFF, the first character of the value; it is not removed and does not select a byte order.",
    UTF32,
    "utf32be",
    bytes.fromhex("0000feff 00000041"),
    "﻿A",
)
encoded(
    "utf32le-surrogate",
    "A surrogate code point is not well-formed UTF-32LE",
    "00 D8 00 00 is U+D800, a surrogate, which is no Unicode scalar value.",
    UTF32,
    "utf32le",
    bytes.fromhex("41000000 00d80000"),
)
encoded(
    "utf32be-surrogate",
    "A surrogate code point is not well-formed UTF-32BE",
    "00 00 DF FF is U+DFFF, a surrogate.",
    UTF32,
    "utf32be",
    bytes.fromhex("0000dfff"),
)
encoded(
    "utf32le-out-of-range",
    "A value beyond U+10FFFF is not well-formed UTF-32LE",
    "00 00 11 00 is 0x110000, one past the last code point.",
    UTF32,
    "utf32le",
    bytes.fromhex("00001100"),
)
encoded(
    "utf32be-out-of-range",
    "A value beyond U+10FFFF is not well-formed UTF-32BE",
    "00 11 00 00 is 0x110000; read in the other byte order it would be U+1100, which is why the encoding's own "
    "byte order, and nothing else, is used.",
    UTF32,
    "utf32be",
    bytes.fromhex("00110000"),
)
encoded(
    "utf32le-partial-code-unit",
    "A UTF-32 value that is not a multiple of four bytes is not well-formed",
    "Six bytes are one code unit and half of another.",
    UTF32,
    "utf32le",
    bytes.fromhex("41000000 4200"),
)

# ----------------------------------------------------------------- UCS-2

encoded(
    "ucs2le-decodes",
    "UCS-2LE reads two bytes to a character of the Basic Multilingual Plane",
    "E9 00 is U+00E9 and AC 20 is U+20AC.",
    UCS2,
    "ucs2le",
    bytes.fromhex("e900 ac20"),
    "é€",
)
encoded(
    "ucs2be-decodes",
    "UCS-2BE reads two bytes, most significant first",
    "00 E9 is U+00E9 and 20 AC is U+20AC.",
    UCS2,
    "ucs2be",
    bytes.fromhex("00e9 20ac"),
    "é€",
)
encoded(
    "ucs2le-surrogate-pair",
    "A surrogate pair is not well-formed UCS-2LE, though it is well-formed UTF-16",
    "3D D8 00 DE is the UTF-16LE pair of U+1F600. UCS-2 has no surrogates, paired or not: the value is refused, "
    "not read as one character.",
    UCS2,
    "ucs2le",
    bytes.fromhex("3dd8 00de"),
)
encoded(
    "ucs2be-surrogate-pair",
    "A surrogate pair is not well-formed UCS-2BE",
    "D8 3D DE 00 is the UTF-16BE pair of U+1F600.",
    UCS2,
    "ucs2be",
    bytes.fromhex("d83d de00"),
)
encoded(
    "ucs2be-lone-surrogate",
    "A lone surrogate code unit is not well-formed UCS-2",
    "DC 00 is a low surrogate on its own; it is not passed through as a character.",
    UCS2,
    "ucs2be",
    bytes.fromhex("0041 dc00"),
)

# ----------------------------------------------------------------- the single-byte sets

encoded(
    "windows1252-decodes",
    "windows-1252 reads 80 to 9F by its own mapping, not as C1 controls",
    "80 is U+20AC, 9F is U+0178 and E9 is U+00E9.",
    SINGLE_BYTE,
    "windows1252",
    bytes.fromhex("80 9f e9"),
    "€Ÿé",
)
for unassigned in ("81", "8d", "8f", "90", "9d"):
    encoded(
        f"windows1252-unassigned-{unassigned}",
        f"The byte {unassigned.upper()} is assigned no character in windows-1252",
        f"41 {unassigned.upper()}: the set assigns the byte no character, so the text is not well-formed. It is "
        "not passed through as the C1 control of the same number.",
        SINGLE_BYTE,
        "windows1252",
        bytes.fromhex("41" + unassigned),
    )
encoded(
    "iso8859-2-decodes",
    "ISO-8859-2 reads the Latin-2 letters",
    "A1 is U+0104, B1 is U+0105 and E8 is U+010D.",
    SINGLE_BYTE,
    "iso8859_2",
    bytes.fromhex("a1 b1 e8"),
    "Ąąč",
)
encoded(
    "iso8859-5-decodes",
    "ISO-8859-5 reads the Cyrillic letters",
    "A1 is U+0401, B0 is U+0410 and D0 is U+0430.",
    SINGLE_BYTE,
    "iso8859_5",
    bytes.fromhex("a1 b0 d0"),
    "ЁАа",
)
encoded(
    "iso8859-7-decodes",
    "ISO-8859-7 reads the Greek letters",
    "C1 is U+0391, E1 is U+03B1 and F9 is U+03C9.",
    SINGLE_BYTE,
    "iso8859_7",
    bytes.fromhex("c1 e1 f9"),
    "Ααω",
)
for unassigned in ("ae", "d2", "ff"):
    encoded(
        f"iso8859-7-unassigned-{unassigned}",
        f"The byte {unassigned.upper()} is assigned no character in ISO-8859-7",
        f"C1 {unassigned.upper()}: the set assigns the byte no character, so the text is not well-formed.",
        SINGLE_BYTE,
        "iso8859_7",
        bytes.fromhex("c1" + unassigned),
    )
encoded(
    "iso8859-9-decodes",
    "ISO-8859-9 reads the Turkish letters where Latin-1 has the Icelandic ones",
    "D0 is U+011E, DD is U+0130 and FD is U+0131.",
    SINGLE_BYTE,
    "iso8859_9",
    bytes.fromhex("d0 dd fd"),
    "Ğİı",
)
encoded(
    "iso8859-15-decodes",
    "ISO-8859-15 reads the euro sign and the letters Latin-1 lacks",
    "A4 is U+20AC, A6 is U+0160 and BC is U+0152.",
    SINGLE_BYTE,
    "iso8859_15",
    bytes.fromhex("a4 a6 bc"),
    "€ŠŒ",
)
encoded(
    "ebcdic037-decodes",
    "EBCDIC code page 037 reads its letters, digits and space",
    "C8 C5 D3 D3 D6 is HELLO, 40 is a space and F1 is the digit 1; 81 is a lower-case a.",
    SINGLE_BYTE,
    "ebcdic037",
    bytes.fromhex("c8c5d3d3d6 40 f1 81"),
    "HELLO 1a",
)

# ----------------------------------------------------------------- Shift_JIS

encoded(
    "shift-jis-decodes",
    "Shift_JIS reads one or two bytes to a character",
    "41 is U+0041, a single byte; 93 FA is U+65E5 and 96 7B is U+672C, two bytes each (the trail byte 7B is in "
    "40 to 7E, the trail byte FA in 80 to FC); B1 is the half-width katakana U+FF71, a single byte.",
    SHIFT_JIS,
    "shiftJis",
    bytes.fromhex("41 93fa 967b b1"),
    "A日本ｱ",
)
encoded(
    "shift-jis-lead-without-trail",
    "A Shift_JIS lead byte with no trail byte after it is not well-formed",
    "93 is a lead byte (81 to 9F) and the value ends with it.",
    SHIFT_JIS,
    "shiftJis",
    bytes.fromhex("41 93"),
)
encoded(
    "shift-jis-trail-out-of-range",
    "A Shift_JIS trail byte outside 40 to 7E and 80 to FC is not well-formed",
    "93 20: the byte after the lead is 20, below 40. The pair is refused; 20 is not read as a space after a "
    "dropped lead byte.",
    SHIFT_JIS,
    "shiftJis",
    bytes.fromhex("93 20 41"),
)
encoded(
    "shift-jis-trail-7f",
    "The byte 7F is no Shift_JIS trail byte",
    "E0 7F: 7F lies between the two trail ranges, 40 to 7E and 80 to FC.",
    SHIFT_JIS,
    "shiftJis",
    bytes.fromhex("e0 7f"),
)
encoded(
    "shift-jis-unassigned-pair",
    "A Shift_JIS pair to which the set assigns no character is not well-formed",
    "81 AD has a lead byte and a trail byte in range, and JIS X 0208 leaves the position (row 2, cell 15) unassigned.",
    SHIFT_JIS,
    "shiftJis",
    bytes.fromhex("81 ad"),
)
