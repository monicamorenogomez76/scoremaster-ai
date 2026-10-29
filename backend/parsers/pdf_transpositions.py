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


# The order of the sharps and of the flats: the steps a key signature alters.
_SHARPS, _FLATS = "FCGDAEB", "BEADGCF"


def _altered(fifths: int) -> dict[str, int]:
    return {step: 1 for step in _SHARPS[:fifths]} if fifths >= 0 else {step: -1 for step in _FLATS[:-fifths]}


def _keys(part) -> list[int | None]:
    """The key read at each measure, carried from the measures before."""
    found, current = [], None
    for measure in part.findall("measure"):
        fifths = measure.findtext("attributes/key/fifths")
        try:
            current = int(fifths) if fifths is not None else current
        except ValueError:
            pass
        found.append(current)
    return found


def _shift(part) -> int | None:
    """How many fifths the part is written above the band's key, from its <transpose>; None without one."""
    chromatic = part.findtext("measure/attributes/transpose/chromatic")
    return None if chromatic is None else (-int(chromatic) * 7) % 12


def _set_alter(pitch, value: float) -> None:
    alter = pitch.find("alter")
    if alter is not None:
        pitch.remove(alter)
    if value:
        alter = ET.Element("alter")
        alter.text = str(int(value)) if float(value).is_integer() else str(value)
        pitch.insert(1, alter)


def _alter(pitch) -> float:
    return float(pitch.findtext("alter") or 0)


def _spell(measure, before: int, after: int, tied: dict) -> dict:
    """The notes without an accidental of their own take the new key; a printed accidental lasts until the bar line,
    and a tied note keeps the pitch of the note it continues (tied: from the measure before; returns the next one's)."""
    old, new = _altered(before), _altered(after)
    printed, ties = set(), {}
    for element in measure.findall("note"):
        pitch = element.find("pitch")
        if pitch is None:
            continue
        step, octave = pitch.findtext("step"), pitch.findtext("octave")
        if element.find("tie[@type='stop']") is not None and (step, octave) in tied:
            _set_alter(pitch, tied[(step, octave)])
        elif element.find("accidental") is not None:
            printed.add((step, octave))
        elif (step, octave) not in printed and _alter(pitch) == old.get(step, 0):
            # Read altered without a printed accidental, the reader knew better: only the key's notes change.
            _set_alter(pitch, new.get(step, 0))
        if element.find("tie[@type='start']") is not None:
            ties[(step, octave)] = _alter(pitch)
    return ties


def _set_key(measure, fifths: int) -> None:
    key = measure.find("attributes/key")
    if key is None:
        attributes = measure.find("attributes")
        if attributes is None:
            attributes = ET.Element("attributes")
            measure.insert(0, attributes)
        key = ET.Element("key")
        ET.SubElement(key, "fifths")
        before = [index for index, child in enumerate(attributes) if child.tag == "divisions"]
        attributes.insert(before[-1] + 1 if before else 0, key)
    key.find("fifths").text = str(fifths)


def fix_key_signatures(musicxml: bytes) -> bytes:
    """A transposed part whose key is not the band's plus its interval missed its key signature (2026-10-29): it takes
    that key and its notes without a printed accidental are spelled in it. The band's key at each measure is the one
    most of its non-transposing parts agree on (at least two); without them nothing is changed."""
    root = ET.fromstring(musicxml)
    names = {item.get("id"): item.findtext("part-name") or "" for item in root.iter("score-part")}
    reference, transposed = [], []
    for part in root.findall("part"):
        shift = _shift(part)
        if shift:
            transposed.append((part, shift))
            continue
        identity = match_instrument_name(names.get(part.get("id"), "")).identity
        if identity is not None and identity.section != "percussion":
            reference.append(_keys(part))
    if len(reference) < 2 or not transposed:
        return musicxml
    band = []
    for read in zip(*reference):
        known = [fifths for fifths in read if fifths is not None]
        common = max(set(known), key=known.count) if known else None
        band.append(common if common is not None and known.count(common) >= max(2, len(known) // 2 + 1) else None)
    changed = False
    for part, shift in transposed:
        measures, read = part.findall("measure"), _keys(part)
        carried, tied, fixed = None, {}, False
        for index, measure in enumerate(measures):
            written = read[index] if index < len(read) else None
            wanted = written
            if index < len(band) and band[index] is not None and written is not None \
                    and (written - band[index] - shift) % 12:
                wanted = band[index] + shift
                wanted = wanted - 12 if wanted > 7 else wanted + 12 if wanted < -7 else wanted
                tied = _spell(measure, written, wanted, tied)
                changed = fixed = True
            elif tied:
                tied = _spell(measure, written, written, tied)
            if fixed and wanted is not None:
                # The key is written where it changes, and only there.
                if wanted != carried:
                    _set_key(measure, wanted)
                elif measure.find("attributes/key") is not None:
                    measure.find("attributes").remove(measure.find("attributes/key"))
            carried = wanted
    if not changed:
        return musicxml
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")
