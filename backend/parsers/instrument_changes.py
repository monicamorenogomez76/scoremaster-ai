"""Parts that change instrument (2026-11-17): «Mallet Percussion» plays tambourine, bells, chimes and gong in turn; a
xylophone goes «To Wood Blocks». MusicXML says which instrument plays each note (<instrument id> on the note, or a
<sound><instrument-change> from there on). Each instrument then becomes a part of its own, so that its range, difficulty
and sound are its own. A drum set also names an instrument per note, but none of them has a pitch: it stays one part."""
from fractions import Fraction
from typing import Optional
from xml.etree import ElementTree

from backend.domain.instrument_catalog import InstrumentIdentity, match_instrument_name, normalize_instrument_name

NoteKey = tuple[int, int, float]   # staff, measure index from 0, onset in quarters


def note_key(staff: Optional[int], measure_index: int, onset) -> NoteKey:
    return staff or 1, measure_index, round(float(onset), 4)


def _identity(name: str) -> Optional[InstrumentIdentity]:
    return match_instrument_name(name).identity


def changes_instrument(names) -> bool:
    """Several instruments, one of them with a pitch."""
    names = list(names)
    return len(names) > 1 and any(identity and identity.sound for identity in map(_identity, names))


def split_name(part_name: str, instrument: str) -> str:
    """The part keeps its name for the instrument it is named after; any other is added to it: «Xylophone (Wood Blocks)»."""
    same = normalize_instrument_name(part_name) == normalize_instrument_name(instrument)
    named, played = _identity(part_name), _identity(instrument)
    return part_name if same or (named and played and named.canonical_id == played.canonical_id) else f"{part_name} ({instrument})"


def note_instruments(content: bytes) -> dict[str, tuple[tuple[str, ...], dict[NoteKey, str]]]:
    """Per part id that changes instrument: its instruments in the order they are declared, and the one of each note."""
    root = ElementTree.fromstring(content)
    declared = {}
    for score_part in root.iter("score-part"):
        names = {item.get("id"): " ".join((item.findtext("instrument-name") or "").split())
                 for item in score_part.iter("score-instrument")}
        if len(names) > 1:
            declared[score_part.get("id")] = names
    found = {}
    for part in root.iter("part"):
        names = declared.get(part.get("id"))
        if not names:
            continue
        current, divisions, by_note = next(iter(names)), 1, {}
        for index, measure in enumerate(part.iter("measure")):
            now = last = 0
            for element in measure:
                if element.tag == "attributes" and element.findtext("divisions"):
                    divisions = int(float(element.findtext("divisions")))
                elif element.tag == "backup":
                    now -= int(float(element.findtext("duration") or 0))
                elif element.tag == "forward":
                    now += int(float(element.findtext("duration") or 0))
                elif element.tag in ("direction", "sound"):
                    change = element.find(".//instrument-change")
                    if change is not None and change.get("id") in names:
                        current = change.get("id")
                elif element.tag == "note":
                    if element.find("chord") is None:
                        last = now
                        now += int(float(element.findtext("duration") or 0))
                    if element.find("rest") is not None:
                        continue
                    named = element.find("instrument")
                    played = named.get("id") if named is not None and named.get("id") in names else current
                    staff = int(element.findtext("staff") or 1)
                    by_note[note_key(staff, index, Fraction(last, divisions))] = names[played]
        used = set(by_note.values())
        if changes_instrument(used):
            found[part.get("id")] = (tuple(name for name in dict.fromkeys(names.values()) if name in used), by_note)
    return found
