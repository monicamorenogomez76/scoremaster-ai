"""PDF reader of ScoreMaster, run by GitHub Actions in its private repository (scoremaster-omr; decided
2026-10-27: Hugging Face no longer runs code for free). ScoreMaster starts the workflow with a job: the PDFs to download
from it, the kind of work (found out from the pages, one score, or the parts of a work with one PDF per
instrument) and a one-time token. The
reader downloads the PDFs with that token, reads them page by page with copista-2m, tells ScoreMaster how far it got
and sends back the work's MusicXML, or why it failed. The PDFs live in a temporary folder deleted at the end, and the
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

from omr.merge import combine_parts, join_pages, staff_of

try:
    # ScoreMaster's instrument catalog (2026-10-28), checked out with the reader; an older workflow brings only omr/.
    from backend.domain.instrument_catalog import instrument_name_key, match_instrument_name, use_catalog
except ImportError:
    use_catalog = None

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES = 40
MAX_PAGES = 80
PAGE_TIMEOUT_SECONDS = 300
# copisteria finds its weights in models/ of its own folder (the workflow prepares it).
COPISTERIA_DIR = Path(os.environ.get("COPISTERIA_DIR", "copisteria"))


class Refused(Exception):
    """A reason to tell ScoreMaster, in Spanish."""


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
            raise Refused(f"{name} supera {MAX_FILE_BYTES // (1024 * 1024)} MB.")
        if not content.startswith(b"%PDF"):
            raise Refused(f"{name} no es un PDF.")
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
        if not self.ready:
            return bool(INSTRUMENT_WORDS.search(piece))
        return match_instrument_name(piece).identity is not None or instrument_name_key(piece) in self.learned

    def same(self, left: str, right: str) -> bool:
        """Two names of the same instrument and players («Tpt. 1» and «Trompeta en Sib 1»)."""
        if self.ready:
            first, second = match_instrument_name(left), match_instrument_name(right)
            if first.identity and second.identity:
                return (first.identity.canonical_id, first.part_numbers) == (second.identity.canonical_id, second.part_numbers)
        return " ".join(left.casefold().split()) == " ".join(right.casefold().split())


catalog = Catalog()


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


def instrument_name(text: str) -> str | None:
    """The shortest piece of a line naming an instrument."""
    named = [piece for piece in _pieces(text) if len(piece) <= 40 and catalog.names(piece)]
    return min(named, key=len) if named else None


def score_names(text: str) -> list[str]:
    """The instruments written beside the staves of a score's page, top to bottom."""
    return [piece for piece in _pieces(text) if len(piece) <= 40 and catalog.names(piece)]


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
        name = instrument_name(text)
        if not groups or (name and name != groups[-1][0]):
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
    return join_pages([xml for xml, _ in pages], title, named), named


def _auto(read: list[tuple[str, list[tuple[int, bytes | None, str]]]], title: str, read_score=lambda: []) -> bytes:
    """read: the pages of each file, None where copista could not read the page. read_score reads the score's pages
    that were set apart, when a part needs them."""
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
        missing = [name for name, found, _ in groups if not found]
        from_score = _from_score(missing, [name for name, _, _ in groups], score + read_score(), title) if missing else {}
        files = [(name, join_pages(found, name) if found else from_score[name]) for name, found, _ in groups
                 if found or name in from_score]
        summary = ", ".join(f"{name} ({len(found)} {'página' if len(found) == 1 else 'páginas'})"
                            for name, found, _ in groups if found)
        print(f"La obra se saca de las particellas: {summary}.", flush=True)
        return combine_parts(files, title)
    print(f"La obra se saca de la partitura general: {len(score)} páginas.", flush=True)
    return _score(score, title)[0]


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
            print(f"No se pudo completar {name}: ninguna página suya se leyó y la partitura general no dice qué "
                  "pentagrama es el suyo.", flush=True)
            continue
        print(f"{name} sale de la partitura general (pentagrama {index + 1}).", flush=True)
        found[name] = staff_of(joined, index)
    return found


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
        plan = [(name, path, number) for (name, path), count in zip(saved, pages) for number in range(1, count + 1)
                if not (named_parts and looks_like_score(texts[(path, number)]))]
        if len(plan) < total:
            print(f"Se apartan {total - len(plan)} páginas de partitura general sin leerlas: la obra sale de las "
                  "particellas.", flush=True)
        done, read, by_file, failed = 0, [], {}, {}
        client.post(callback + "/progress", json={"pages_done": 0, "pages_total": len(plan)})
        out_dirs = {path: tempfile.mkdtemp(dir=folder) for _, path in saved}
        for name, path, number in plan:
            try:
                xml = read_page(path, number, out_dirs[path])
                by_file.setdefault((name, path), []).append((number, xml, texts[(path, number)]))
            except Exception as error:
                # A cover or a text page: skipped. Why copista failed goes to the log, never the PDF nor the token.
                print(f"{name}, página {number} sin música, se salta:\n{error}", flush=True)
                failed.setdefault((name, path), []).append((number, None, texts[(path, number)]))
            done += 1
            client.post(callback + "/progress", json={"pages_done": done, "pages_total": len(plan)})
        set_apart = [(name, path, number) for (name, path), count in zip(saved, pages) for number in range(1, count + 1)
                     if (name, path, number) not in plan]

        def read_score() -> list[tuple[bytes, str]]:
            """The score's pages set apart, read when a part copista could not read needs its staff."""
            nonlocal done
            found = []
            for name, path, number in set_apart:
                try:
                    found.append((read_page(path, number, out_dirs[path]), texts[(path, number)]))
                except Exception as error:
                    print(f"{name}, página {number} sin música, se salta:\n{error}", flush=True)
                done += 1
                client.post(callback + "/progress", json={"pages_done": done, "pages_total": len(plan) + len(set_apart)})
            return found

        if not by_file:
            raise Refused("No se encontró música en el PDF.")
        read = [(name, sorted(by_file.get((name, path), []) + failed.get((name, path), []), key=lambda page: page[0]))
                for name, path in saved if (name, path) in by_file or (name, path) in failed]
        try:
            if data["kind"] == "auto":
                musicxml = _auto(read, data["title"], read_score)
            elif data["kind"] == "score":
                musicxml = _score([(xml, text) for _, pages_xml in read for _, xml, text in pages_xml if xml is not None],
                                  data["title"])[0]
            else:
                musicxml = combine_parts([(name, join_pages([xml for _, xml, _ in pages_xml if xml is not None], name))
                                          for name, pages_xml in read if any(xml for _, xml, _ in pages_xml)],
                                         data["title"])
        except Exception:
            import traceback
            print("\n".join(traceback.format_exc().strip().splitlines()[-8:]), flush=True)
            raise Refused("No se pudo unir lo leído en una obra.") from None
        client.post(callback + "/result", json={"musicxml": musicxml.decode("utf-8")}).raise_for_status()
        print(f"Leídas {total} páginas.", flush=True)
        return 0
    except Refused as reason:
        client.post(callback + "/result", json={"error": str(reason)})
        print(str(reason), flush=True)
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
