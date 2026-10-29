"""The transposition of each part of a work read from a PDF (2026-10-29). copista reads the notes as printed, in the
key of each instrument, but writes no <transpose>: the page shows the notes and «in B♭» only as text. Each part the
catalog (or a name the account confirmed before) recognises takes the <transpose> of its instrument, so it sounds
and is graded at its real pitch. A part that already says its transposition, or is unknown, is left as it is.

Parts are always printed in the key of their instrument; a score may be too, or in C, at sounding pitch («Score in C»,
«Guion en Do»). A score in C is left as it is: the reader says so when the page says it, and the key signatures of a score
tell it otherwise (in a transposed score a B♭ clarinet has two sharps more than the flute; in C both have the same)."""
from __future__ import annotations

from xml.etree import ElementTree as ET

from backend.domain.instrument_catalog import identity_by_id, instrument_name_key, match_instrument_name
from backend.domain.instrument_transposition import written_to_sounding

# MusicXML's order inside <attributes>: <transpose> comes after these.
_BEFORE_TRANSPOSE = ("divisions", "key", "time", "staves", "part-symbol", "instruments", "clef", "staff-details")


def _instrument(name: str, learned: dict[str, str]) -> str | None:
    identity = match_instrument_name(name).identity
    return identity.canonical_id if identity else learned.get(instrument_name_key(name))


def _fifths(part) -> int | None:
    found = part.findtext("measure/attributes/key/fifths")
    try:
        return int(found) if found is not None else None
    except ValueError:
        return None


def _key_shift(interval: tuple[int, int, int]) -> int:
    """How many fifths the written key is above the sounding one: B♭ instruments 2, F 1, E♭ 3."""
    return (-interval[0] * 7) % 12


def _at_sounding_pitch(parts: list[tuple[object, tuple[int, int, int] | None, bool]]) -> bool:
    """True when the transposing parts have the key of the instruments that sound as written (a score in C)."""
    reference = [_fifths(part) for part, interval, pitched in parts if pitched and interval is None]
    reference = [fifths for fifths in reference if fifths is not None]
    every = {_fifths(part) for part, _, pitched in parts if pitched} - {None}
    if not reference or every <= {0}:
        # No key signature in any staff (a work in C, or written without one): the keys say nothing, and band scores
        # are mostly transposed.
        return False
    concert = max(set(reference), key=reference.count)
    in_c = transposed = 0
    for part, interval, _ in parts:
        fifths = _fifths(part)
        if interval is None or fifths is None or not _key_shift(interval):
            continue
        difference = (fifths - concert) % 12
        in_c += difference == 0
        transposed += difference == _key_shift(interval)
    return in_c > transposed


def add_transpositions(musicxml: bytes, learned: dict[str, str] | None = None, concert_pitch: bool = False,
                       source: str = "parts") -> bytes:
    """source: «parts» (always printed in the key of each instrument) or «score» (maybe in C)."""
    if concert_pitch:
        return musicxml
    root = ET.fromstring(musicxml)
    names = {item.get("id"): item.findtext("part-name") or "" for item in root.iter("score-part")}
    found = []
    for part in root.findall("part"):
        if part.find(".//transpose") is not None:
            continue
        instrument = _instrument(names.get(part.get("id"), ""), learned or {})
        if instrument is None:
            continue
        identity = identity_by_id(instrument)
        pitched = identity is not None and identity.section not in ("percussion",)
        found.append((part, written_to_sounding(instrument, part.findtext(".//clef/sign")), pitched))
    if source == "score" and _at_sounding_pitch(found):
        return musicxml
    changed = False
    for part, interval, _ in found:
        attributes = part.find("measure/attributes")
        if interval is None or attributes is None:
            continue
        transpose = ET.Element("transpose")
        for tag, value in zip(("diatonic", "chromatic", "octave-change"), (interval[1], interval[0], interval[2])):
            if tag != "octave-change" or value:
                ET.SubElement(transpose, tag).text = str(value)
        before = [index for index, child in enumerate(attributes) if child.tag in _BEFORE_TRANSPOSE]
        attributes.insert(before[-1] + 1 if before else 0, transpose)
        changed = True
    if not changed:
        return musicxml
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")
