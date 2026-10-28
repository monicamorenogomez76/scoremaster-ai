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

from omr.merge import combine_parts, join_pages

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


def read_page(pdf_path: str, number: int, out_dir: str) -> bytes:
    """One page read by copista-2m in its own process, so its memory goes back when it ends."""
    try:
        subprocess.run([sys.executable, "-m", "copisteria.pipeline", "--pdf", pdf_path, "--range", f"{number}-{number}",
                        "--out", out_dir, "--detector", "2m"], cwd=COPISTERIA_DIR, check=True,
                       timeout=PAGE_TIMEOUT_SECONDS, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        return (Path(out_dir) / f"{Path(pdf_path).stem}_p{number:02d}.musicxml").read_bytes()
    except subprocess.CalledProcessError as error:
        raise PageFailed("\n".join((error.stderr or "").strip().splitlines()[-6:])) from None
    except subprocess.TimeoutExpired:
        raise PageFailed(f"More than {PAGE_TIMEOUT_SECONDS} s on one page.") from None
    except OSError as error:
        raise PageFailed(f"{type(error).__name__}: {error}") from None


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
    r"timbal\w*|timpani|caja|snare|bombo|platillos?|cymbals?|xil[óo]fono|xylophone|glockenspiel|lira|campanas|piano|"
    r"arpa|harp|violonchelo|cello|viola|viol[íi]n|violin|guitarra|guitar|"
    r"fl|ob|fg|cl|tpt|tp|trp|tbn|tb|hn|cr|tba|perc|timp|euph|bomb)\b\.?", re.IGNORECASE)


def page_text(pdf_path: str, number: int) -> str:
    """The text of a digital PDF's page (instrument names, titles); empty for a scan."""
    try:
        return subprocess.run(["pdftotext", "-f", str(number), "-l", str(number), "-layout", pdf_path, "-"],
                              check=True, capture_output=True, text=True, timeout=30).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def instrument_name(text: str) -> str | None:
    """The shortest line naming an instrument, without the page number printed beside it."""
    lines = [re.sub(r"\s{2,}\d+\s*$", "", line).strip() for line in (text or "").splitlines()]
    named = [line for line in lines if line and len(line) <= 40 and INSTRUMENT_WORDS.search(line)]
    return min(named, key=len) if named else None


def staves(xml: bytes) -> int:
    """Staves of a page as copista wrote it: each part with its own count of staves."""
    from xml.etree import ElementTree as ET
    total = 0
    for part in ET.fromstring(xml).findall("part"):
        counts = [int(item.text) for item in part.iter("staves") if (item.text or "").isdigit()]
        total += max(counts, default=1)
    return total


def _parts_of(pages: list[tuple[bytes, str]]) -> list[tuple[str, list[bytes]]]:
    """Consecutive part pages grouped by the instrument their text names."""
    groups: list[tuple[str, list[bytes]]] = []
    for xml, text in pages:
        name = instrument_name(text)
        if not groups or (name and name != groups[-1][0]):
            groups.append((name or f"Parte {len(groups) + 1}", [xml]))
        else:
            groups[-1][1].append(xml)
    return groups


def _auto(read: list[tuple[str, list[tuple[int, bytes, str]]]], title: str) -> bytes:
    score, parts = [], []
    for _, pages in read:
        for _, xml, text in pages:
            (score if staves(xml) >= SCORE_STAVES else parts).append((xml, text))
    groups = _parts_of(parts) if parts else []
    named = any(instrument_name(text) for _, text in parts)
    if groups and (named or not score):
        summary = ", ".join(f"{name} ({len(xml)} {'página' if len(xml) == 1 else 'páginas'})" for name, xml in groups)
        print(f"La obra se saca de las particellas: {summary}.", flush=True)
        return combine_parts([(name, join_pages(xml, name)) for name, xml in groups], title)
    print(f"La obra se saca de la partitura general: {len(score)} páginas.", flush=True)
    return join_pages([xml for xml, _ in score], title)


def run(data: dict, client: httpx.Client, read_page=read_page, count_pages=count_pages, page_text=page_text) -> int:
    """Reads the job and reports to ScoreMaster. 0 when the work was sent back, 1 when the failure was."""
    print("::add-mask::" + data["token"], flush=True)
    client.headers["Authorization"] = "Bearer " + data["token"]
    callback = data["callback"].rstrip("/")
    folder = tempfile.mkdtemp(prefix="omr-")
    try:
        saved = _download(client, folder, data["files"])
        pages = [count_pages(path) for _, path in saved]
        total = sum(pages)
        if total > MAX_PAGES:
            raise Refused(f"Se leen hasta {MAX_PAGES} páginas por obra.")
        done, read = 0, []
        client.post(callback + "/progress", json={"pages_done": 0, "pages_total": total})
        for (name, path), count in zip(saved, pages):
            out_dir = tempfile.mkdtemp(dir=folder)
            page_xml = []
            for number in range(1, count + 1):
                try:
                    page_xml.append((number, read_page(path, number, out_dir),
                                     page_text(path, number) if data["kind"] == "auto" else ""))
                except Exception as error:
                    # A cover or a text page: skipped. Why copista failed goes to the log, never the PDF nor the token.
                    print(f"{name}, página {number} sin música, se salta:\n{error}", flush=True)
                done += 1
                client.post(callback + "/progress", json={"pages_done": done, "pages_total": total})
            if page_xml:
                read.append((name, page_xml))
        if not read:
            raise Refused("No se encontró música en el PDF.")
        try:
            if data["kind"] == "auto":
                musicxml = _auto(read, data["title"])
            elif data["kind"] == "score":
                musicxml = join_pages([xml for _, pages_xml in read for _, xml, _ in pages_xml], data["title"])
            else:
                musicxml = combine_parts([(name, join_pages([xml for _, xml, _ in pages_xml], name))
                                          for name, pages_xml in read], data["title"])
        except Exception:
            raise Refused("No se pudo unir lo leído en una obra.") from None
        client.post(callback + "/result", json={"musicxml": musicxml.decode("utf-8")}).raise_for_status()
        print(f"Leídas {total} páginas.", flush=True)
        return 0
    except Refused as reason:
        client.post(callback + "/result", json={"error": str(reason)})
        print(str(reason), flush=True)
        return 1
    finally:
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
