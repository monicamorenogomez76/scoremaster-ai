"""Canonical instrument identities and exact multilingual aliases.

The catalog lives in the database (2026-10-28): the infrastructure hands it over with use_catalog; until then, and in
the tests without a database, it is the seed in instrument_catalog.json. Matching is exact on the normalized
name: there is no substring or fuzzy matching, so "English Horn" can never become
"Horn". Anything not in the catalog is UNKNOWN and must be confirmed by a person.

The key of a transposing instrument is written in many ways (2026-10-28): «in Bb», «in B b», «B♭», «Sib», «Si b»,
«Si bemol», the German «in B» (B flat) and «Es», «Mib», «en Fa», «Do», before or after the name. It is read into one
token (kbb, keb, kf…) at the end of the name. A name with a key matches the identity of that key in its family
(«Klarinette in A» → clarinet in A) or, for an instrument read in several keys (euphonium, tuba, trombone), the
instrument itself; any other key stays unknown («Trompa en Mib»).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

UNKNOWN = "UNKNOWN"
ALIAS = "ALIAS"
CATALOG_PATH = Path(__file__).with_name("instrument_catalog.json")
_FIELDS = ("id", "section", "family", "variant", "transposition", "label_es", "label_en", "sound", "rehearsal_group")

_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}
_NUMBER = r"\b(?:\d+|vi|iv|v|iii|ii|i)\b"
# "Horn 1 & 2", "Flute 1/2", "Trompas 1 y 2", "Trompa 3-4" share one staff between several players.
_TRAILING_PARTS = re.compile(r"\s+(" + _NUMBER + r"(?:(?:\s*(?:&|/|,|\band\b|\by\b|\bi\b|\bund\b|\bet\b)\s*|\s+)"
                             + _NUMBER + r")*)$")
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


_SOLFEGE = {"do": "c", "ut": "c", "re": "d", "mi": "e", "fa": "f", "sol": "g", "la": "a", "si": "b"}
_GERMAN = {"b": "bb", "es": "eb", "as": "ab", "des": "db"}
KEY_MARK = "k"


def _key(token: str, flat: str = "") -> str:
    """One key token from a note name: solfège, letter or German (B is B flat, Es is E flat)."""
    token = token.strip()
    if token in _SOLFEGE:
        return KEY_MARK + _SOLFEGE[token] + ("b" if flat else "")
    if flat:
        return KEY_MARK + token + "b"
    return KEY_MARK + _GERMAN.get(token, token)


_AFTER_IN = re.compile(r"\b(?:in|en|em|pour|per|im)\s+(?:(sib|mib|lab|reb)|(do|ut|re|mi|fa|sol|la|si|des|es|as|[a-g]b|[a-g])\b"
                       r"(\s*(?:bemolle|bemol|b)\b)?)")


def _keys(text: str) -> str:
    """Every spelling of a key becomes one token: «in B b» «Sib» «Si bemol» «in B» (German) «Es» «Mib» «en Fa» «Do»."""
    def after_in(match):
        if match.group(1):
            return " " + _key(match.group(1)[:-1], "b")
        token, flat = match.group(2), (match.group(3) or "").strip()
        if len(token) == 2 and token.endswith("b") and token[0] in "abcdefg":
            return " " + KEY_MARK + token
        return " " + _key(token, flat)
    text = _AFTER_IN.sub(after_in, text)
    text = re.sub(r"\b(si|mi|la|re)\s*(?:bemolle|bemol|b)\b", lambda m: " " + _key(m.group(1), "b"), text)
    text = re.sub(r"\b([abeg]b)\b", lambda m: " " + KEY_MARK + m.group(1), text)
    text = re.sub(r"^es\s", " " + KEY_MARK + "eb ", text)
    text = re.sub(r"\s(do|fa)$", lambda m: " " + _key(m.group(1)), text)
    return text


def _prepare(name: str) -> str:
    """Lowercase, accents removed, flats unified, keys read into one token; keeps & and / for part numbers."""
    text = name.replace("&amp;", "&").replace("♭", "b").replace("♯", "#").casefold()
    text = "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))
    # "B flat", "B-flat" and "B♭" are the same tuning token: "bb". Tunings are never dropped.
    text = re.sub(r"\b([a-g])[\s-]*flat\b", r"\1b", text)
    text = re.sub(r"[^a-z0-9#&/]+", " ", text)
    text = _keys(" ".join(text.split()))
    return " ".join(text.split())


def _key_last(words: list[str]) -> list[str]:
    keys = [word for word in words if _is_key(word)]
    return [word for word in words if not _is_key(word)] + keys[:1]


def _is_key(word: str) -> bool:
    return len(word) in (2, 3) and word.startswith(KEY_MARK) and word[1] in "abcdefg" and word[2:] in ("", "b")


def normalize_instrument_name(name: str) -> str:
    return " ".join(_key_last(re.sub(r"[&/]", " ", _prepare(name)).split()))


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
def _seed() -> tuple[str, tuple[dict, ...]]:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return document["version"], tuple(document["instruments"])


def seed_instruments() -> tuple[dict, ...]:
    """The instruments the database starts with, in catalog order: id, fields and aliases."""
    return _seed()[1]


def _fingerprint(items) -> str:
    """The content of a catalog, whatever the order or spelling of its names."""
    content = [[item.get(field) for field in _FIELDS] + [sorted({normalize_instrument_name(a) for a in item["aliases"]})]
               for item in items]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode("utf-8")).hexdigest()


def _build(items) -> tuple[tuple[InstrumentIdentity, ...], dict[str, InstrumentIdentity]]:
    entries, index = [], {}
    for item in items:
        identity = InstrumentIdentity(item["id"], item["section"], item["family"], item["variant"],
                                      item["transposition"], item["label_es"], item["label_en"], tuple(item["aliases"]),
                                      item.get("sound"), item.get("rehearsal_group"))
        for alias in identity.aliases:
            alias = normalize_instrument_name(alias)
            if alias in index and index[alias] is not identity:
                raise ValueError("Alias {!r} is shared by {} and {}".format(alias, index[alias].canonical_id, identity.canonical_id))
            index[alias] = identity
        entries.append(identity)
    # A name of a family with a key names the identity of that key: «klarinette» + A → clarinet in A.
    for identity in entries:
        key = identity.variant if identity.variant and len(identity.variant) <= 2 and identity.variant[0] in "abcdefg" else None
        if not key:
            continue
        for base in entries:
            if base.family != identity.family or base is identity:
                continue
            for alias in base.aliases:
                alias = normalize_instrument_name(alias)
                if not any(_is_key(word) for word in alias.split()):
                    index.setdefault(alias + " " + KEY_MARK + key, identity)
    return tuple(entries), index


_current: dict = {}


def use_catalog(items) -> None:
    """The catalog read from the database (id, fields and aliases per instrument, in order); None goes back to the seed.
    Its version is the seed's while the content is the same, so loading the seed analyses nothing again."""
    version, seed = _seed()
    items = seed if items is None else tuple(items)
    built = _build(items)
    fingerprint = _fingerprint(items)
    _current.update(entries=built[0], index=built[1],
                    version=version if fingerprint == _fingerprint(seed) else version + "+" + fingerprint[:12])


def _load() -> tuple[tuple[InstrumentIdentity, ...], dict[str, InstrumentIdentity]]:
    if not _current:
        use_catalog(None)
    return _current["entries"], _current["index"]


def catalog_version() -> str:
    """Recorded with every persisted analysis, so results stay traceable and are redone when the catalog changes."""
    _load()
    return _current["version"]


def catalog_entries() -> tuple[InstrumentIdentity, ...]:
    return _load()[0]


_private: dict[str, InstrumentIdentity] = {}


def use_private_instruments(items) -> None:
    """The instruments an account created (2026-10-28): found by their id, never by a name of the common catalog, and
    out of the catalog version. Only the account that owns one can confirm it (checked by the application)."""
    built = {}
    for item in items:
        built[item["id"]] = InstrumentIdentity(item["id"], item["section"], item["family"], item["variant"],
                                               item["transposition"], item["label_es"], item["label_en"], (),
                                               item.get("sound"), item.get("rehearsal_group"))
    _private.clear()
    _private.update(built)


def identity_by_id(canonical_id: str) -> InstrumentIdentity | None:
    found = next((identity for identity in catalog_entries() if identity.canonical_id == canonical_id), None)
    return found or _private.get(canonical_id)


def instrument_name_key(name: str) -> str:
    """A part name without its part numbers, normalized: «Fiscornio 1» and «Fiscornio 3» are the same name."""
    return normalize_instrument_name(_split_part_numbers(_prepare(name))[0])


# Instruments read in more than one key keep their identity whatever key is written (euphonium in B flat in treble clef,
# tuba in C, trombone in B flat).
_ANY_KEY = {"euphonium", "baritone_horn", "tuba", "sousaphone", "trombone.tenor", "trombone.bass"}


def _with_key(identity: InstrumentIdentity, key: str) -> bool:
    written = (identity.transposition or "C").casefold()
    return identity.canonical_id in _ANY_KEY or key[1:] == written


def match_instrument_name(name: str) -> CatalogMatch:
    base, part_numbers = _split_part_numbers(_prepare(name))
    alias = normalize_instrument_name(base)
    index = _load()[1]
    identity = index.get(alias)
    words = alias.split()
    if identity is None and words and _is_key(words[-1]):
        unkeyed = index.get(" ".join(words[:-1]))
        identity = unkeyed if unkeyed and _with_key(unkeyed, words[-1]) else None
    if identity is None:
        return CatalogMatch(name, None, (), None, UNKNOWN)
    return CatalogMatch(name, identity, part_numbers, alias, ALIAS)
