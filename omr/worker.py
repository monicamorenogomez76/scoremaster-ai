"""PDF reader of ScoreMaster, run by GitHub Actions in its private repository (scoremaster-omr; decided
2026-10-27: Hugging Face no longer runs code for free). ScoreMaster starts the workflow with a job: the PDFs to download
from it, the kind of work (found out from the pages, one score, or the parts of a work with one PDF per
instrument) and a one-time token. The
reader downloads the PDFs with that token, reads them page by page with copista-2m, tells ScoreMaster how far it got
and sends back the work's MusicXML, already prepared when it can (2026-11-04), or why it failed. The PDFs live in a temporary folder deleted at the end, and the
token is masked in the log. The job is read from GitHub's event file, never from a variable of the step, which GitHub
prints in the log (2026-10-27)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from omr.merge import add_instrumentation, add_tempo, combine_parts, fill_lost_rests, join_pages, measure_count, staff_of

try:
    # ScoreMaster's instrument catalog (2026-10-28), checked out with the reader; an older workflow brings only omr/.
    from backend.domain.instrument_catalog import instrument_name_key, match_instrument_name, use_catalog
except ImportError:
    use_catalog = None

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES = 40
MAX_PAGES = 160
PAGE_TIMEOUT_SECONDS = 300
# copisteria finds its weights in models/ of its own folder (the workflow prepares it).
COPISTERIA_DIR = Path(os.environ.get("COPISTERIA_DIR", "copisteria"))


class Refused(Exception):
    """A reason to tell ScoreMaster, in Spanish. The reader's repository is public (2026-11-01), so the log gets its own
    text when the reason names a file: anyone can read the log, and it never says which work was read."""

    def __init__(self, reason: str, logged: str | None = None):
        super().__init__(reason)
        self.logged = logged or reason


class PageFailed(Exception):
    """copista could not read a page; the message is the end of its error, for the log only."""


class _Copista:
    """copista-2m loaded once for the whole job (2026-10-28: a process per page loaded PyTorch and the model again
    for every page)."""
    model = None

    @classmethod
    def read(cls, pdf_path: str, number: int, out_dir: str) -> bytes:
        os.environ["COPISTERIA_DETECTOR"] = "2m"
        from copisteria import read
        from copisteria.paths import EVIDENCE
        from copisteria.pipeline import transcribe
        from copisteria.vision.page.scan import from_pdf
        if cls.model is None:
            cls.model = read.load_model(str(EVIDENCE), "cpu")
        png = from_pdf(pdf_path, number, Path(out_dir)).path
        return transcribe(png, cls.model).encode("utf-8")


def _timed_out(signum, frame):
    raise TimeoutError


def read_page(pdf_path: str, number: int, out_dir: str) -> bytes:
    """One page read by copista-2m, at most PAGE_TIMEOUT_SECONDS."""
    import signal
    import traceback
    previous = signal.signal(signal.SIGALRM, _timed_out)
    signal.alarm(PAGE_TIMEOUT_SECONDS)
    try:
        return _Copista.read(pdf_path, number, out_dir)
    except TimeoutError:
        raise PageFailed(f"More than {PAGE_TIMEOUT_SECONDS} s on one page.") from None
    except Exception:
        raise PageFailed("\n".join(traceback.format_exc().strip().splitlines()[-6:])) from None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


DEFAULT_READ_PAGE = read_page
# Several processes of one processor each read faster than one process with all of them (2026-11-03, 12 pages on four
# processors: 54 s one after another, 43 s with four threads, 29 s two by two, 22 s four processes of one). GitHub's
# machine for public repositories has four processors and 16 GB. OMR_PAGE_WORKERS changes it.
MAX_PAGE_WORKERS = 4


def page_workers() -> int:
    try:
        configured = int(os.environ.get("OMR_PAGE_WORKERS", "0"))
    except ValueError:
        configured = 0
    return max(1, configured) if configured else max(1, min(MAX_PAGE_WORKERS, os.cpu_count() or 1))


def _one_thread() -> None:
    """Each process reads on one processor, so that they do not fight over them."""
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[name] = "1"


def _read_one(read_page, pdf_path: str, number: int, out_dir: str):
    """The page read, or why it could not be (an exception returned, so that it crosses between processes)."""
    try:
        return read_page(pdf_path, number, out_dir)
    except Exception as error:
        return error


def read_pages(pages: list[tuple[str, str, int]], read_page, out_dirs: dict, workers: int, on_done) -> dict:
    """{(name, path, number): MusicXML or the exception} of every page, read by `workers` processes at once; on_done is
    called after each page, in the order they finish."""
    results = {}
    if workers <= 1 or len(pages) <= 1:
        for page in pages:
            results[page] = _read_one(read_page, page[1], page[2], out_dirs[page[1]])
            on_done()
        return results
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from concurrent.futures.process import BrokenProcessPool
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork"),
                                 initializer=_one_thread) as pool:
            futures = {pool.submit(_read_one, read_page, page[1], page[2], out_dirs[page[1]]): page for page in pages}
            for future in as_completed(futures):
                results[futures[future]] = future.result()
                on_done()
    except BrokenProcessPool:
        # A process died (out of memory): the pages left are read one after another.
        print(f"Un lector se detuvo; se leen de una en una las {len(pages) - len(results)} páginas que faltan.", flush=True)
        left = [page for page in pages if page not in results]
        results.update(read_pages(left, read_page, out_dirs, 1, on_done))
    return results


def count_pages(pdf_path: str) -> int:
    output = subprocess.run(["pdfinfo", pdf_path], check=True, capture_output=True, text=True, timeout=30).stdout
    return next(int(line.split()[1]) for line in output.splitlines() if line.startswith("Pages:"))


def payload_from_environment() -> dict:
    """The job as ScoreMaster sent it. Its addresses must be ScoreMaster's, over https (http only on this machine)."""
    data = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["client_payload"]
    callback = urlsplit(data["callback"])
    local = callback.hostname in ("127.0.0.1", "localhost")
    if callback.scheme != "https" and not local:
        raise ValueError("The callback must be https.")
    if any(urlsplit(item["url"]).netloc != callback.netloc for item in data["files"]):
        raise ValueError("The PDFs must come from ScoreMaster.")
    if data.get("kind") not in ("auto", "score", "parts") or not data["files"] or len(data["files"]) > MAX_FILES:
        raise ValueError("Unknown job.")
    return data


def _download(client: httpx.Client, folder: str, files: list[dict]) -> list[tuple[str, str]]:
    saved = []
    for index, item in enumerate(files):
        name = os.path.basename(item["name"]) or f"{index + 1}.pdf"
        content = client.get(item["url"]).raise_for_status().content
        if len(content) > MAX_FILE_BYTES:
            raise Refused(f"{name} supera {MAX_FILE_BYTES // (1024 * 1024)} MB.",
                          f"El archivo {index + 1} supera {MAX_FILE_BYTES // (1024 * 1024)} MB.")
        if not content.startswith(b"%PDF"):
            raise Refused(f"{name} no es un PDF.", f"El archivo {index + 1} no es un PDF.")
        path = os.path.join(folder, f"{index:02d}.pdf")
        Path(path).write_bytes(content)
        saved.append((name, path))
    return saved


# «Detectar solo» (2026-10-28): band PDFs usually bring the score and the parts in one file, in either order. A page
# with three or more staves is the score, one with one or two a part, and one copista cannot read (a cover, a text
# page) is skipped. A part's instrument is the short line of the page's text that names one; a page without it
# continues the part before. With named parts the work comes from them (copista reads them better and they say their
# instrument); without, from the score.
SCORE_STAVES = 3
INSTRUMENT_WORDS = re.compile(
    r"\b(flaut\w*|flute|fl[öo]te|piccolo|ottavino|oboe|hautbois|corno ingl\w*|english horn|fagot\w*|bassoon|basson|"
    r"clarin\w*|klarinette|requinto|sax\w*|trompet\w*|trumpet|tromba|cornet\w*|fliscorno|flugel\w*|trompa|horn|corno|"
    r"trombo\w*|tromb[óo]n|posaune|bombardino|euphonium|bar[íi]tono|baritone|tuba|contrabaj\w*|bass|bajo|percu\w*|"
    r"timbal\w*|timpani|caja|snare|bombo|platillos?|platos?|cymbals?|xil[óo]fono|xylophone|glockenspiel|lira|campanas|piano|"
    r"arpa|harp|violonchelo|cello|viola|viol[íi]n|violin|guitarra|guitar|"
    r"fl|ob|fg|cl|tpt|tp|trp|tbn|tb|hn|cr|tba|perc|timp|euph|bomb)\b\.?", re.IGNORECASE)


class Catalog:
    """ScoreMaster's catalog and the part names the account confirmed before (2026-10-28): a piece of text names an
    instrument when the catalog recognises it. Without them the reader keeps its short list of instrument words."""

    def __init__(self, document: dict | None = None):
        self.ready = bool(use_catalog and document and document.get("instruments"))
        self.learned = set(document.get("learned") or []) if self.ready else set()
        if self.ready:
            use_catalog(document["instruments"])

    def names(self, piece: str) -> bool:
        piece = _flats(piece)
        if not self.ready:
            return bool(INSTRUMENT_WORDS.search(piece))
        return match_instrument_name(piece).identity is not None or instrument_name_key(piece) in self.learned

    def same(self, left: str, right: str) -> bool:
        """Two names of the same instrument and players («Tpt. 1» and «Trompeta en Sib 1»)."""
        if self.ready:
            first, second = match_instrument_name(_flats(left)), match_instrument_name(_flats(right))
            if first.identity and second.identity:
                return (first.identity.canonical_id, first.part_numbers) == (second.identity.canonical_id, second.part_numbers)
        return " ".join(left.casefold().split()) == " ".join(right.casefold().split())


catalog = Catalog()


def _flats(text: str) -> str:
    """«≤» is how Finale's music font writes the flat in a PDF's text («B≤ Clarinet», «E≤ Alto Saxophone»)."""
    return text.replace("≤", "♭")


def _load_catalog(client: httpx.Client, callback: str) -> Catalog:
    try:
        return Catalog(client.get(callback + "/instruments").raise_for_status().json())
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        print("Sin el catálogo de ScoreMaster: los instrumentos se buscan con la lista corta del lector.", flush=True)
        return Catalog()


def page_text(pdf_path: str, number: int) -> str:
    """The text of a digital PDF's page (instrument names, titles); empty for a scan."""
    try:
        return subprocess.run(["pdftotext", "-f", str(number), "-l", str(number), "-layout", pdf_path, "-"],
                              check=True, capture_output=True, text=True, timeout=30).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def _pieces(text: str) -> list[str]:
    """The pieces of each line, cut where words stand far apart (2026-10-28: a PDF printed the name on the line of the
    dedication), which also leaves out the page number printed beside it."""
    return [piece.strip() for line in (text or "").splitlines() for piece in re.split(r"\s{3,}", line) if piece.strip()]


def looks_like_score(text: str) -> bool:
    """A score page names many instruments beside its staves; a part page one, maybe in its title too."""
    named = sum(1 for piece in _pieces(text) if len(piece) <= 40 and catalog.names(piece))
    return max(named, len(INSTRUMENT_WORDS.findall(text or ""))) >= 4


# The name of a part is in the header of its pages (2026-11-01, «Arabian Dances»): below it, the cues of other
# instruments («Hn.», «B. Sax.») among the staves are no names. Its first lines are enough for a title, a dedication and
# the name, as in «Paco el barba».
HEADER_LINES = 8
# «Arabian Dances - Fl. 1»: the title of the work before the part's name, on the pages after the first.
_TITLE_BEFORE = re.compile(r"^(.+?)\s*-\s+(\S.*)$")


def _header(text: str) -> str:
    return "\n".join([line for line in (text or "").splitlines() if line.strip()][:HEADER_LINES])


def _without_title(piece: str) -> str:
    found = _TITLE_BEFORE.match(piece)
    return found.group(2).strip() if found else piece


def _a_name(piece: str) -> bool:
    """A short piece naming an instrument, by the catalog or by the reader's list («Percussion 1» is in neither the
    catalog nor a part of it)."""
    return 0 < len(piece) <= 40 and len(piece.split()) <= 4 and (catalog.names(piece) or bool(INSTRUMENT_WORDS.search(piece)))


def part_header(text: str) -> tuple[str | None, bool]:
    """(the part's name, whether the page continues a part). The pages after the first start with «Title - name»; a first
    page starts with its name, maybe over two lines («E♭ Baritone» / «Saxophone»), above the title in capitals and the
    instruments in brackets (2026-11-01, «Arabian Dances»). Otherwise, as in «Paco el barba», the shortest piece of the
    header that names an instrument."""
    lines = [re.split(r"\s{3,}", line.strip())[0] for line in (text or "").splitlines() if line.strip()]
    if lines:
        titled = _TITLE_BEFORE.match(lines[0])
        if titled and _a_name(titled.group(2).strip()):
            return titled.group(2).strip(), True
        second = lines[1] if len(lines) > 1 else ""
        # The rest of a name split over two lines is one word («Saxophone»); a list of instruments («Caja y bombo») is not.
        if second and len(second.split()) == 1 and not second.isupper() and not second.startswith("(") \
                and not re.search(r"\d", second):
            joined = lines[0] + " " + second
            if _a_name(joined) and (_a_name(second) or not _a_name(lines[0])):
                return joined, False
        if _a_name(lines[0]):
            return lines[0], False
    named = [name for name in (_without_title(piece) for piece in _pieces(_header(text)))
             if len(name) <= 40 and catalog.names(name)]
    return (min(named, key=len) if named else None), False


def instrument_name(text: str) -> str | None:
    """The name of the part on the page, or None."""
    return part_header(text)[0]


def _words(name: str) -> list[str]:
    """The words of a name, before any «/» («Timp./Shkr.»: the timpani, then the shaker); «≤» is the flat of Finale's font."""
    return re.findall(r"[^\W\d_]+", name.split("/")[0].replace("≤", "b").casefold())


def _in_order(letters: str, word: str) -> bool:
    found = iter(word)
    return all(letter in found for letter in letters)


def same_part(left: str, right: str) -> bool:
    """Two names of one part: the same part number and one name shortening the other («Flute 1» and «Fl. 1»), or the
    same instrument and players for the catalog."""
    left, right = _without_title(left), _without_title(right)
    if catalog.same(left, right):
        return True
    if re.findall(r"\d+", left) != re.findall(r"\d+", right):
        return False
    first, second = _words(left), _words(right)
    if not first or not second:
        return False
    return _first_word_shortens(first, second) or _first_word_shortens(second, first)


def _first_word_shortens(short: list[str], full: list[str]) -> bool:
    """Every word of the short name shortens a word of the full one, in order: «Fl.» «Flute», «Hn.» «F Horn», «A. Sax.»
    «E♭ Alto Saxophone»; never «F Horn» «Flute»."""
    at = 0
    for word in short:
        while at < len(full) and not (full[at][0] == word[0] and _in_order(word, full[at])):
            at += 1
        if at == len(full):
            return False
        at += 1
    return True


# The instrumentation page of a band PDF (2026-11-02, «Arabian Dances»): «2 - Percussion 1» and, indented below it in its
# column, «Marimba», «Low Tom»…; elsewhere «Percussion 2 — 2 players».
_INSTRUMENTATION = re.compile(r"(?im)^\s*(instrumentation|instrumentaci[oó]n|instrumentaci[oó]|plantilla)\s*$")
_ENTRY = re.compile(r"^\d+\s*[-–—]\s+(\S.*)$")
_PLAYERS = re.compile(r"(?im)^\s*(\S[^—–\n]*?)\s*[—–]\s*(\d+)\s+(?:players?|m[uú]sicos?|percusionistas?|int[eé]rpretes?)\b")
_PERCUSSION = re.compile(r"perc|timp|drum|bater|schlag", re.IGNORECASE)


def percussion_plan(texts: list[str]) -> dict[str, dict]:
    """What each percussion part plays and how many players it needs, as the PDF's text says; {} when it does not."""
    plan: dict[str, dict] = {}
    for text in texts:
        if not _INSTRUMENTATION.search(text or ""):
            continue
        entries: list[tuple[int, str, list[str]]] = []
        for line in text.splitlines():
            for found in re.finditer(r"\S(?:.*?\S)?(?=\s{3,}|$)", line):
                at, piece = found.start(), found.group()
                entry = _ENTRY.match(piece)
                if entry:
                    entries.append((at, _flats(entry.group(1).strip()), []))
                    continue
                # An item belongs to the last entry of its column: the one further right among those it is indented from.
                owners = [index for index, (start, _, _) in enumerate(entries) if start < at]
                if owners:
                    entries[max(owners, key=lambda index: (entries[index][0], index))][2].append(piece)
        for _, name, items in entries:
            if _PERCUSSION.search(name):
                plan[name] = {"instruments": items or [part.strip() for part in name.split("/") if part.strip()],
                              "players": None}
    for text in texts:
        for name, players in _PLAYERS.findall(text or ""):
            name = _flats(name.strip())
            if _PERCUSSION.search(name):
                plan.setdefault(name, {"instruments": [], "players": None})["players"] = int(players)
    return plan


# The staves of a score page in its text (2026-11-02, «Arabian Dances»): each staff starts with its clef in the left
# margin («&» treble, «?» bass, «÷» percussion in the music fonts of Finale and Sibelius) and the instrument's name
# beside it, sometimes over two lines around the staff («Timp.» / «Shkr.»).
_CLEF_GLYPH = re.compile(r"(?<!\S)[&?÷](?=\s|$)")
_MARGIN_NAME = re.compile(r"^\s{0,16}([A-Za-zÀ-ÖØ-öø-ÿ][^\s&?÷œ∑]*(?: [^\s&?÷œ∑]+)*)(?=\s{2,}|$)")


def staff_labels(text: str, count: int) -> list[str | None] | None:
    """The name of each of the page's `count` staves, None for a staff of a group that has one name for several; None
    when the clefs of the page are not those staves (one system of them, or several repeating them)."""
    clefs, names = [], []
    for index, line in enumerate((text or "").splitlines()):
        found = _MARGIN_NAME.match(line)
        if found and len(found.group(1)) <= 20 and re.search(r"[^\W\d_]{2}", found.group(1)):
            names.append((index, found.group(1)))
        clef = _CLEF_GLYPH.search(line[:45])
        if clef and (not clefs or abs(clef.start() - clefs[0][1]) <= 3):
            clefs.append((index, clef.start()))
    if not count or not clefs or len(clefs) % count:
        return None
    lines = [index for index, _ in clefs]
    staff_names: list[list[str]] = [[] for _ in range(count)]
    for at, name in names:
        # The nearest staff; between two, the one below (a name is printed above or beside its staff).
        nearest = min(range(len(lines)), key=lambda staff: (abs(lines[staff] - at), -staff))
        if nearest < count:
            staff_names[nearest].append(name)
    return [" ".join(found) if found else None for found in staff_names]


def score_names(text: str) -> list[str]:
    """The instruments written beside the staves of a score's page, top to bottom."""
    return [piece for piece in _pieces(text) if len(piece) <= 40 and catalog.names(piece)]


CONCERT_PITCH = re.compile(r"\b(?:full\s+score|score|partitura(?:\s+general)?|gui[oó]n)\s+(?:in|en)\s+(?:c|do)\b|"
                           r"\bc\s+score\b|\bconcert\s+pitch\b|\bsonidos?\s+reales?\b|\bsons\s+r[ée]els\b",
                           re.IGNORECASE)


def at_concert_pitch(text: str) -> bool:
    """The page says the score is in C, at sounding pitch («Score in C», «Guion en Do»; 2026-10-29)."""
    return bool(CONCERT_PITCH.search(text or ""))


# A tempo as the music fonts of Finale and Sibelius write it in a PDF's text (2026-11-01): «q = 50» is crotchet = 50
# (h minim, e quaver, a dot after the note dotted); or with the Unicode notes.
_TEMPO = re.compile(r"(?<![\w.])([qhe\u2669\u266a])(\.?)\s*=\s*(\d{2,3})(?!\d)")
_TEMPO_BEATS = {"q": 1.0, "\u2669": 1.0, "h": 2.0, "e": 0.5, "\u266a": 0.5}


def tempo_from_text(text: str) -> tuple[int, float] | None:
    """(beats per minute, beat in quarters) of the first tempo written in the text, or None."""
    found = _TEMPO.search(text or "")
    if not found or not 20 <= int(found.group(3)) <= 300:
        return None
    return int(found.group(3)), _TEMPO_BEATS[found.group(1)] * (1.5 if found.group(2) else 1)


def staves(xml: bytes) -> int:
    """Staves of a page as copista wrote it: each part with its own count of staves."""
    from xml.etree import ElementTree as ET
    total = 0
    for part in ET.fromstring(xml).findall("part"):
        counts = [int(item.text) for item in part.iter("staves") if (item.text or "").isdigit()]
        total += max(counts, default=1)
    return total


def _parts_of(pages: list[tuple[bytes | None, str]]) -> list[tuple[str, list[bytes], bool]]:
    """Consecutive part pages grouped by the instrument their text names: (name, pages read, had pages copista could
    not read). A page copista could not read has no music (None) but still says its instrument."""
    groups: list[tuple[str, list[bytes], bool]] = []
    for xml, text in pages:
        name, continues = part_header(text)
        name = _flats(name) if name else name
        # A first page starts its part unless it repeats the name; a page after it follows it while it names the same part.
        if not groups or (name and (not same_part(groups[-1][0], name) if continues else name != groups[-1][0])):
            groups.append((name or f"Parte {len(groups) + 1}", [], False))
        found_name, found, failed = groups[-1]
        groups[-1] = (found_name, found + ([xml] if xml is not None else []), failed or xml is None)
    return groups


def _score(pages: list[tuple[bytes, str]], title: str) -> tuple[bytes, list[str] | None]:
    """The score's pages joined, its staves named after the instruments written beside them on its first page when
    there is one name per staff."""
    count = staves(pages[0][0]) if pages else 0
    joined = max((staves(xml) for xml, _ in pages), default=0)
    names = score_names(pages[0][1]) if pages else []
    named = names if names and len(names) == joined == count else None
    # The names beside the staves place the staves of a page that shows fewer of them (2026-11-02).
    labels = [staff_labels(text, staves(xml)) for xml, text in pages]
    return join_pages([xml for xml, _ in pages], title, named, labels, same_part), named


def _auto(read: list[tuple[str, list[tuple[int, bytes | None, str]]]], title: str,
          read_score=lambda: []) -> tuple[bytes, str, bool]:
    """read: the pages of each file, None where copista could not read the page. read_score reads the score's pages
    that were set apart, when a part needs them. Returns the work, where it came from (parts or score) and whether the
    score says it is in C."""
    score, parts = [], []
    for _, pages in read:
        for _, xml, text in pages:
            if xml is None:
                if not looks_like_score(text):
                    parts.append((None, text))
            else:
                (score if staves(xml) >= SCORE_STAVES else parts).append((xml, text))
    groups = _parts_of(parts) if parts else []
    named = any(instrument_name(text) for _, text in parts)
    if named:
        # A cover or a page of notes before the named parts is no part (2026-10-28).
        groups = [group for group in groups if not group[0].startswith("Parte ")]
    if groups and (named or not score):
        read_pages = []

        def score_pages() -> list[tuple[bytes, str]]:
            """The score's pages, the ones set apart read only once."""
            if not read_pages:
                read_pages.append(score + read_score())
            return read_pages[0]

        missing = [name for name, found, _ in groups if not found]
        from_score = _from_score(missing, [name for name, _, _ in groups], score_pages(), title) if missing else {}
        files = [(name, join_pages(found, name) if found else from_score[name]) for name, found, _ in groups
                 if found or name in from_score]
        # Parts of different lengths: copista skipped multi-measure rests (2026-10-29); the score keeps every measure.
        if len({measure_count(xml) for _, xml in files}) > 1 and score_pages():
            files = fill_lost_rests(files, _score(score_pages(), title)[0], same_part)
        read_pages = sum(len(found) for _, found, _ in groups)
        print(f"La obra se saca de {len(files)} particellas ({read_pages} {'página' if read_pages == 1 else 'páginas'}).",
              flush=True)
        return combine_parts(files, title), "parts", False
    print(f"La obra se saca de la partitura general: {len(score)} páginas.", flush=True)
    return _score(score, title)[0], "score", any(at_concert_pitch(text) for _, text in score)


def _from_score(missing: list[str], order: list[str], score: list[tuple[bytes, str]], title: str) -> dict[str, bytes]:
    """The staff of each part copista could not read, taken from the score (2026-10-28): the staff named like the part,
    or the one in the part's place when the score has one staff per part. Otherwise the part is left out and said."""
    joined, names = _score(score, title) if score else (None, None)
    count = max((staves(xml) for xml, _ in score), default=0)
    found = {}
    for name in missing:
        if names:
            index = next((at for at, written in enumerate(names) if catalog.same(written, name)), None)
        else:
            index = order.index(name) if count == len(order) else None
        if joined is None or index is None:
            print(f"No se pudo completar la parte {order.index(name) + 1}: ninguna página suya se leyó y la partitura general no dice qué "
                  "pentagrama es el suyo.", flush=True)
            continue
        print(f"La parte {order.index(name) + 1} sale de la partitura general (pentagrama {index + 1}).", flush=True)
        found[name] = staff_of(joined, index)
    return found


def prepared_work(client: httpx.Client, callback: str, body: dict) -> dict | None:
    """The work prepared here (2026-11-04): this machine reads with music21 in seconds what takes Render minutes. Only
    a help: on any failure ScoreMaster reads the work itself. Without its catalog the audio would not be what it prepares."""
    if not catalog.ready:
        return None
    try:
        # Imported here: the processes that read the pages do not load music21, and an older workflow does not bring it.
        from backend.parsers.prepare import prepare_work
        answer = client.post(callback + "/final", json=body)
        if answer.status_code != 200:
            print("ScoreMaster preparará la obra.", flush=True)
            return None
        return prepare_work(answer.json()["musicxml"].encode("utf-8"))
    except Exception as error:
        # The kind of error, without its message (it may carry a part's name).
        print(f"ScoreMaster preparará la obra: {type(error).__name__}.", flush=True)
        return None


def send_result(client: httpx.Client, callback: str, body: dict) -> None:
    prepared = prepared_work(client, callback, body)
    if prepared:
        try:
            client.post(callback + "/result", json={**body, "prepared": prepared}).raise_for_status()
            print("Obra preparada para ScoreMaster.", flush=True)
            return
        except httpx.HTTPError as error:
            # A reading is worth more than its preparation: sent again without it.
            print(f"No se pudo enviar la obra preparada: {type(error).__name__}.", flush=True)
    client.post(callback + "/result", json=body).raise_for_status()


def run(data: dict, client: httpx.Client, read_page=read_page, count_pages=count_pages, page_text=page_text) -> int:
    """Reads the job and reports to ScoreMaster. 0 when the work was sent back, 1 when the failure was."""
    print("::add-mask::" + data["token"], flush=True)
    client.headers["Authorization"] = "Bearer " + data["token"]
    callback = data["callback"].rstrip("/")
    folder = tempfile.mkdtemp(prefix="omr-")
    global catalog
    catalog = _load_catalog(client, callback)
    try:
        saved = _download(client, folder, data["files"])
        pages = [count_pages(path) for _, path in saved]
        total = sum(pages)
        if total > MAX_PAGES:
            raise Refused(f"Se leen hasta {MAX_PAGES} páginas por obra.")
        # «Detectar solo»: with parts named in the PDF's text, the score's pages are never read.
        texts = {(path, number): page_text(path, number) if data["kind"] in ("auto", "score") else ""
                 for (_, path), count in zip(saved, pages) for number in range(1, count + 1)}
        named_parts = any(instrument_name(text) and not looks_like_score(text) for text in texts.values())
        score_like = {key: looks_like_score(text) for key, text in texts.items()}

        def set_apart(path: str, number: int) -> bool:
            """A page naming several instruments between two part pages is a part's, not the score's (the percussion of
            «Arabian Dances», 2026-11-01)."""
            between_parts = score_like.get((path, number - 1)) is False and score_like.get((path, number + 1)) is False
            return named_parts and score_like[(path, number)] and not between_parts

        plan = [(name, path, number) for (name, path), count in zip(saved, pages) for number in range(1, count + 1)
                if not set_apart(path, number)]
        if len(plan) < total:
            print(f"Se apartan {total - len(plan)} páginas de partitura general sin leerlas: la obra sale de las "
                  "particellas.", flush=True)
        done, read, by_file, failed = 0, [], {}, {}
        client.post(callback + "/progress", json={"pages_done": 0, "pages_total": len(plan)})
        out_dirs = {path: tempfile.mkdtemp(dir=folder) for _, path in saved}
        # The log numbers the files: it never says which work was read (2026-11-01).
        numbered = {path: number for number, (_, path) in enumerate(saved, 1)}
        # The real copista reads several pages at once; a reading given by the tests, one after another.
        workers = page_workers() if read_page is DEFAULT_READ_PAGE else 1

        def page_done(total: int):
            def tell():
                nonlocal done
                done += 1
                client.post(callback + "/progress", json={"pages_done": done, "pages_total": total})
            return tell

        results = read_pages(plan, read_page, out_dirs, workers, page_done(len(plan)))
        for name, path, number in plan:
            outcome = results[(name, path, number)]
            if isinstance(outcome, Exception):
                # A cover or a text page: skipped. Why copista failed goes to the log, never the PDF nor the token.
                print(f"Archivo {numbered[path]}, página {number} sin música, se salta:\n{outcome}", flush=True)
                failed.setdefault((name, path), []).append((number, None, texts[(path, number)]))
            else:
                by_file.setdefault((name, path), []).append((number, outcome, texts[(path, number)]))
        set_apart = [(name, path, number) for (name, path), count in zip(saved, pages) for number in range(1, count + 1)
                     if (name, path, number) not in plan]

        def read_score() -> list[tuple[bytes, str]]:
            """The score's pages set apart, read when a part copista could not read needs its staff."""
            found = []
            results = read_pages(set_apart, read_page, out_dirs, workers, page_done(len(plan) + len(set_apart)))
            for name, path, number in set_apart:
                outcome = results[(name, path, number)]
                if isinstance(outcome, Exception):
                    print(f"Archivo {numbered[path]}, página {number} sin música, se salta:\n{outcome}", flush=True)
                else:
                    found.append((outcome, texts[(path, number)]))
            return found

        if not by_file:
            raise Refused("No se encontró música en el PDF.")
        read = [(name, sorted(by_file.get((name, path), []) + failed.get((name, path), []), key=lambda page: page[0]))
                for name, path in saved if (name, path) in by_file or (name, path) in failed]
        try:
            if data["kind"] == "auto":
                musicxml, source, concert_pitch = _auto(read, data["title"], read_score)
            elif data["kind"] == "score":
                pages_read = [(xml, text) for _, pages_xml in read for _, xml, text in pages_xml if xml is not None]
                musicxml, source = _score(pages_read, data["title"])[0], "score"
                concert_pitch = any(at_concert_pitch(text) for _, text in pages_read)
            else:
                source, concert_pitch = "parts", False
                musicxml = combine_parts([(name, join_pages([xml for _, xml, _ in pages_xml if xml is not None], name))
                                          for name, pages_xml in read if any(xml for _, xml, _ in pages_xml)],
                                         data["title"])
        except Exception:
            import traceback
            # Where it failed and the kind of error, without its message (it may carry a part's name).
            kind, _, stack = sys.exc_info()
            print("".join(traceback.format_tb(stack)[-3:]) + kind.__name__, flush=True)
            raise Refused("No se pudo unir lo leído en una obra.") from None
        # What each percussion part plays and its players, from the PDF's instrumentation page (2026-11-02).
        percussion = percussion_plan(list(texts.values()))
        if percussion:
            musicxml = add_instrumentation(musicxml, percussion, same_part)
            print(f"Percusión leída de la plantilla del PDF: {len(percussion)} particellas.", flush=True)
        # copista reads no tempo: the first one written in the pages' text, at the start of the work (2026-11-01).
        tempo = next((found for found in (tempo_from_text(texts[(path, number)]) for _, path, number in plan) if found), None)
        if tempo:
            musicxml = add_tempo(musicxml, *tempo)
            print(f"Tempo leído del texto del PDF: {tempo[0]} por minuto.", flush=True)
        # ScoreMaster adds the transposition of each instrument, never to a score in C (2026-10-29).
        send_result(client, callback, {"musicxml": musicxml.decode("utf-8"), "source": source,
                                       "concert_pitch": concert_pitch})
        print(f"Leídas {total} páginas.", flush=True)
        return 0
    except Refused as reason:
        client.post(callback + "/result", json={"error": str(reason)})
        print(reason.logged, flush=True)
        return 1
    finally:
        catalog = Catalog()
        shutil.rmtree(folder, ignore_errors=True)


def main() -> int:
    data = payload_from_environment()
    with httpx.Client(timeout=httpx.Timeout(120.0), follow_redirects=False) as client:
        try:
            return run(data, client)
        except httpx.HTTPError:
            print("No se pudo hablar con ScoreMaster.", flush=True)
            return 1


if __name__ == "__main__":
    sys.exit(main())
