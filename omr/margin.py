"""The name beside each staff of a score's page, read with its place on the page (2026-11-21, «Arabian Dances»).

A score names its staves in the margin, and one name often covers several staves under a brace: «Fls.» with «1» and
«2» beside one staff (the two flutes share it), «Cls.» with «1» beside one staff and «2 3» beside the next. The text of
the page without positions (`pdftotext -layout`) loses which staff a name or a number is beside. With them
(`pdftotext -bbox`) each clef is a word in the column where the staves start, one per staff, top to bottom: each name
line goes to the staff nearest to it, a staff with no name of its own takes the nearest one (the name of its brace),
and each number goes to the staff it is beside."""
from __future__ import annotations

from dataclasses import dataclass
import html
import re
import subprocess

# The clefs as the music fonts of Finale and Sibelius write them in the text: treble, bass and percussion.
CLEF_GLYPHS = {"&", "?", "÷"}
# Words on one line of the margin are this close in height, in points.
SAME_LINE = 2.0
# Signs of the music fonts: a line with them is notes that fell in the margin, not a name.
MUSIC_SIGNS = re.compile(r"[÷œ∑&?]")
# A capital printed apart from the rest of its word (2026-11-21, «1812»: «F l. 1», «H n. 1», «B . C l.», «P iccolo»): the
# rest starts lowercase or with a dot, closer than this share of the height of the letters; a space is twice as wide.
SPLIT_CAPITAL_GAP = 0.15
_WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')


@dataclass(frozen=True)
class Word:
    text: str
    left: float
    right: float
    middle: float     # height of its middle, in points from the top of the page
    height: float = 0.0


def page_words(pdf_path: str, number: int, joined: bool = True) -> list[Word]:
    """The words of a digital PDF's page with their place, each capital printed apart joined to its word unless
    `joined` is False; none for a scan or when poppler fails."""
    try:
        found = subprocess.run(["pdftotext", "-bbox", "-f", str(number), "-l", str(number), pdf_path, "-"],
                               check=True, capture_output=True, text=True, timeout=30).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    words = [Word(html.unescape(text), float(x0), float(x1), (float(y0) + float(y1)) / 2, float(y1) - float(y0))
             for x0, y0, x1, y1, text in _WORD.findall(found)]
    return join_split_capitals(words) if joined else words


# Names are printed small: a capital this tall is a dynamic or a sign («F legato» in «Arabian Dances»).
SPLIT_CAPITAL_HEIGHT = 16.0


def _split(left: Word, right: Word) -> bool:
    """A capital and the rest of its word: two letters at least or a dot (one letter is a scan's OCR, «T e»), no music
    sign, small print."""
    rest = right.text
    return (len(left.text) == 1 and left.text.isupper() and (rest == "." or (len(rest) >= 2 and rest[0].islower()))
            and not MUSIC_SIGNS.search(rest) and max(left.height, right.height) <= SPLIT_CAPITAL_HEIGHT
            and abs(left.middle - right.middle) <= SAME_LINE
            and 0 <= right.left - left.right < SPLIT_CAPITAL_GAP * max(left.height, right.height))


def _in_lines(words: list[Word]) -> list[Word]:
    return sorted(words, key=lambda word: (round(word.middle / SAME_LINE), word.left))


def split_capitals(words: list[Word]) -> set[tuple[str, str]]:
    """The (capital, rest) printed apart on a page, as its text shows them with a space between."""
    ordered = _in_lines(words)
    return {(left.text, right.text) for left, right in zip(ordered, ordered[1:]) if _split(left, right)}


def join_split_capitals(words: list[Word]) -> list[Word]:
    """The words with each capital printed apart joined to the rest of its word."""
    joined: list[Word] = []
    for word in _in_lines(words):
        if joined and _split(joined[-1], word):
            left = joined.pop()
            word = Word(left.text + word.text, left.left, word.right, left.middle, max(left.height, word.height))
        joined.append(word)
    return joined


def _clefs(words: list[Word]) -> list[Word]:
    """The clefs in the column where most of them are: the start of the staves."""
    clefs = [word for word in words if word.text in CLEF_GLYPHS]
    if not clefs:
        return []
    columns: dict[int, list[Word]] = {}
    for clef in clefs:
        columns.setdefault(round(clef.left / 4), []).append(clef)
    return sorted(max(columns.values(), key=len), key=lambda clef: clef.middle)


def _lines(words: list[Word]) -> list[tuple[float, str]]:
    """The words grouped into lines, left to right: (height, text)."""
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda word: word.middle):
        if lines and abs(lines[-1][0].middle - word.middle) <= SAME_LINE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [(sum(word.middle for word in line) / len(line), " ".join(word.text for word in sorted(line, key=lambda word: word.left)))
            for line in lines]


def names_by_staff(words: list[Word], staves: int) -> list[str] | None:
    """The name of each of the page's first `staves` staves with the numbers beside it («Cls. 2 3»); None when the
    clefs of the page are not those staves (one system of them, or several repeating them) or a staff has no name."""
    clefs = _clefs(words)
    if not staves or not clefs or len(clefs) % staves:
        return None
    centres = [clef.middle for clef in clefs[:staves]]
    column = min(clef.left for clef in clefs)
    # One staff of room above and below the system: the page number at the top is no name.
    spacing = min((below - above for above, below in zip(centres, centres[1:])), default=20.0)
    margin = [word for word in words if word.right <= column and centres[0] - spacing <= word.middle <= centres[-1] + spacing]
    names: dict[int, list[tuple[float, str]]] = {}
    numbers: dict[int, list[tuple[float, str]]] = {}
    for height, text in _lines(margin):
        if MUSIC_SIGNS.search(text) or text.startswith("("):
            continue
        nearest = min(range(staves), key=lambda staff: abs(centres[staff] - height))
        target = numbers if re.fullmatch(r"\d+(?:\s+\d+)*", text) else names
        target.setdefault(nearest, []).append((height, text))
    if not names:
        return None
    labelled = []
    for staff, centre in enumerate(centres):
        own = names.get(staff)
        if own is None:
            # A staff of a brace: the name written between its staves.
            nearest = min(names, key=lambda other: min(abs(height - centre) for height, _ in names[other]))
            own = names[nearest]
        # A name over two lines is one name of two instruments or two words: «Timp.» and «Shkr.», «Bar./» and «Euph.».
        name = "/".join(text.rstrip("/ ") for _, text in sorted(own))
        beside = " ".join(text for _, text in sorted(numbers.get(staff, [])))
        labelled.append(f"{name} {beside}".strip())
    return labelled


# A page naming each of its staves with a name of its own is one system (2026-11-21, «1812»): copisteria took its 30
# staves for three systems where the bar lines break between the families. This many names may be missing (a name the
# text lost, staves under a brace with one name).
ONE_SYSTEM_MISSING = 3


def one_system(staves: list[tuple[float, float, float]], words: list[Word]) -> bool:
    """Whether the staves found on a page, (top, bottom, left) in points, are one system: a different name beside nearly
    each of them. Two systems name their instruments twice; a page without text has no names."""
    if len(staves) < 2 or not words:
        return False
    column = min(left for _, _, left in staves)
    height = staves[0][1] - staves[0][0]
    margin = [word for word in words
              if word.right <= column and staves[0][0] - height <= word.middle <= staves[-1][1] + height]
    names = {text for _, text in _lines(margin)
             if not MUSIC_SIGNS.search(text) and not text.startswith("(") and re.search(r"[^\W\d_]{2}", text)}
    return len(names) >= len(staves) - ONE_SYSTEM_MISSING


def names_at(words: list[Word], centres: list[float], column: float) -> list[str | None]:
    """The name beside each staff read, by the height of its middle (points), when the page has no clefs in its text:
    the name lines within half a staff spacing of it, over one or two lines («Bass Clarinet» / «in Bb»); None for a staff
    with none. The name of a staff copisteria missed is nobody's (2026-11-21, «1812»)."""
    if not centres:
        return []
    gaps = sorted(below - above for above, below in zip(centres, centres[1:]))
    spacing = gaps[(len(gaps) - 1) // 2] if gaps else 20.0
    margin = [word for word in words if word.right <= column and centres[0] - spacing <= word.middle <= centres[-1] + spacing]
    found: dict[int, list[tuple[float, str]]] = {}
    for height, text in _lines(margin):
        if MUSIC_SIGNS.search(text) or text.startswith("("):
            continue
        nearest = min(range(len(centres)), key=lambda staff: abs(centres[staff] - height))
        if abs(centres[nearest] - height) <= spacing / 2:
            found.setdefault(nearest, []).append((height, text))
    return [" ".join(text for _, text in sorted(found[staff])) if staff in found else None for staff in range(len(centres))]


# The tempo marks of a page (2026-11-22, «1812»: fourteen, and the reader took only the first for the whole work): a
# metronome mark, «(q = 132)», «(h. = 72)», with the words before it on its line («E Allegro giusto»), where it starts.
_METRONOME = re.compile(r"\(?([qhe\u2669\u266a])(\.?)\s*=\s*(\d{2,3})\)?")
_BEAT_QUARTERS = {"q": 1.0, "\u2669": 1.0, "h": 2.0, "e": 0.5, "\u266a": 0.5}
# Words of one tempo mark are closer than this, in points: the page number or another mark is further.
TEMPO_PHRASE_GAP = 12.0


def _word_lines(words: list[Word]) -> list[list[Word]]:
    """The words in lines, each left to right; a rehearsal letter in its box sits a little higher than the words."""
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda word: word.middle):
        if lines and abs(lines[-1][-1].middle - word.middle) <= max(SAME_LINE, 0.5 * max(word.height, lines[-1][-1].height)):
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda word: word.left) for line in lines]


def tempo_marks(words: list[Word]) -> list[tuple[float, int, float]]:
    """(where it starts, beats per minute, beat in quarters) of each metronome mark of the page, top to bottom."""
    found = []
    for line in _word_lines(words):
        index = 0
        while index < len(line):
            for span in (1, 2, 3):
                mark = _METRONOME.fullmatch(" ".join(word.text for word in line[index:index + span]))
                if mark and 20 <= int(mark.group(3)) <= 300:
                    start = index
                    while start and line[start].left - line[start - 1].right < TEMPO_PHRASE_GAP:
                        start -= 1
                    found.append((line[start].left, int(mark.group(3)),
                                  _BEAT_QUARTERS[mark.group(1)] * (1.5 if mark.group(2) else 1)))
                    index += span - 1
                    break
            index += 1
    return found


class PageText(str):
    """A page's text that also keeps its words with their place, for the names beside the staves; plain text elsewhere."""
    words: list[Word]

    def __new__(cls, text: str, words: list[Word]):
        found = super().__new__(cls, text)
        found.words = words
        return found


def words_of(text: str) -> list[Word]:
    return getattr(text, "words", None) or []
