"""Canonical instrument identities and exact multilingual aliases.

The catalog lives in instrument_catalog.json. Matching is exact on the normalized
name: there is no substring or fuzzy matching, so "English Horn" can never become
"Horn". Anything not in the catalog is UNKNOWN and must be confirmed by a person.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

UNKNOWN = "UNKNOWN"
ALIAS = "ALIAS"
CATALOG_PATH = Path(__file__).with_name("instrument_catalog.json")
# Recorded with every persisted analysis, so results stay traceable when aliases change.
CATALOG_VERSION = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["version"]

_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}
_NUMBER = r"\b(?:\d+|vi|iv|v|iii|ii|i)\b"
# "Horn 1 & 2", "Flute 1/2", "Trompas 1 y 2" share one staff between several players.
_TRAILING_PARTS = re.compile(r"\s+(" + _NUMBER + r"(?:\s*(?:&|/|,|\band\b|\by\b)\s*" + _NUMBER + r")*)$")
_LEADING_ORDINAL = re.compile(r"^(\d+)(?:st|nd|rd|th|o|a)\s+")


@dataclass(frozen=True)
class InstrumentIdentity:
    canonical_id: str
    section: str
    family: str
    variant: str | None
    transposition: str | None
    label_es: str
    label_en: str
    aliases: tuple[str, ...] = ()
    # General MIDI soundfont for playback; None for unpitched percussion.
    sound: str | None = None
    # Subsection for ensemble rehearsal: flutes, double_reeds, clarinets, saxophones,
    # high_brass, low_voices, percussion or strings_rhythm.
    rehearsal_group: str | None = None


@dataclass(frozen=True)
class CatalogMatch:
    original_name: str
    identity: InstrumentIdentity | None
    part_numbers: tuple[int, ...]
    matched_alias: str | None
    source: str


def _prepare(name: str) -> str:
    """Lowercase, accents removed, flats unified; keeps & and / for part numbers."""
    text = name.replace("&amp;", "&").replace("♭", "b").replace("♯", "#").casefold()
    text = "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))
    # "B flat", "B-flat" and "B♭" are the same tuning token: "bb". Tunings are never dropped.
    text = re.sub(r"\b([a-g])[\s-]*flat\b", r"\1b", text)
    text = re.sub(r"[^a-z0-9#&/]+", " ", text)
    return " ".join(text.split())


def normalize_instrument_name(name: str) -> str:
    return " ".join(re.sub(r"[&/]", " ", _prepare(name)).split())


def _split_part_numbers(prepared: str) -> tuple[str, tuple[int, ...]]:
    numbers: list[int] = []
    leading = _LEADING_ORDINAL.match(prepared)
    if leading:
        numbers.append(int(leading.group(1)))
        prepared = prepared[leading.end():]
    trailing = _TRAILING_PARTS.search(prepared)
    if trailing:
        tokens = re.findall(_NUMBER, trailing.group(1))
        numbers.extend(int(token) if token.isdigit() else _ROMAN[token] for token in tokens)
        prepared = prepared[:trailing.start()]
    return prepared, tuple(numbers)


@lru_cache(maxsize=1)
def _load() -> tuple[tuple[InstrumentIdentity, ...], dict[str, InstrumentIdentity]]:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entries, index = [], {}
    for item in document["instruments"]:
        identity = InstrumentIdentity(item["id"], item["section"], item["family"], item["variant"],
                                      item["transposition"], item["label_es"], item["label_en"], tuple(item["aliases"]),
                                      item.get("sound"), item.get("rehearsal_group"))
        for alias in identity.aliases:
            if alias in index:
                raise ValueError("Alias {!r} is shared by {} and {}".format(alias, index[alias].canonical_id, identity.canonical_id))
            index[alias] = identity
        entries.append(identity)
    return tuple(entries), index


def catalog_entries() -> tuple[InstrumentIdentity, ...]:
    return _load()[0]


def identity_by_id(canonical_id: str) -> InstrumentIdentity | None:
    return next((identity for identity in catalog_entries() if identity.canonical_id == canonical_id), None)


def match_instrument_name(name: str) -> CatalogMatch:
    base, part_numbers = _split_part_numbers(_prepare(name))
    alias = normalize_instrument_name(base)
    identity = _load()[1].get(alias)
    if identity is None:
        return CatalogMatch(name, None, (), None, UNKNOWN)
    return CatalogMatch(name, identity, part_numbers, alias, ALIAS)
