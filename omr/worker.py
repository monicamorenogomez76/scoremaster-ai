"""PDF reader of ScoreMaster, run by GitHub Actions in the author's private repository (author's decision,
2026-10-27: Hugging Face no longer runs code for free). ScoreMaster starts the workflow with a job: the PDFs to download
from it, the kind of work (one score, or the parts of a work with one PDF per instrument) and a one-time token. The
reader downloads the PDFs with that token, reads them page by page with copista-2m, tells ScoreMaster how far it got
and sends back the work's MusicXML, or why it failed. The PDFs live in a temporary folder deleted at the end, and the
token is masked in the log. The job comes in OMR_PAYLOAD, never through the shell."""
from __future__ import annotations

import json
import os
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


def read_page(pdf_path: str, number: int, out_dir: str) -> bytes:
    """One page read by copista-2m in its own process, so its memory goes back when it ends."""
    subprocess.run([sys.executable, "-m", "copisteria.pipeline", "--pdf", pdf_path, "--range", f"{number}-{number}",
                    "--out", out_dir, "--detector", "2m"], cwd=COPISTERIA_DIR, check=True, timeout=PAGE_TIMEOUT_SECONDS,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (Path(out_dir) / f"{Path(pdf_path).stem}_p{number:02d}.musicxml").read_bytes()


def count_pages(pdf_path: str) -> int:
    output = subprocess.run(["pdfinfo", pdf_path], check=True, capture_output=True, text=True, timeout=30).stdout
    return next(int(line.split()[1]) for line in output.splitlines() if line.startswith("Pages:"))


def payload_from_environment() -> dict:
    """The job as ScoreMaster sent it. Its addresses must be ScoreMaster's, over https (http only on this machine)."""
    data = json.loads(os.environ["OMR_PAYLOAD"])
    callback = urlsplit(data["callback"])
    local = callback.hostname in ("127.0.0.1", "localhost")
    if callback.scheme != "https" and not local:
        raise ValueError("The callback must be https.")
    if any(urlsplit(item["url"]).netloc != callback.netloc for item in data["files"]):
        raise ValueError("The PDFs must come from ScoreMaster.")
    if data.get("kind") not in ("score", "parts") or not data["files"] or len(data["files"]) > MAX_FILES:
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


def run(data: dict, client: httpx.Client, read_page=read_page, count_pages=count_pages) -> int:
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
                    page_xml.append(read_page(path, number, out_dir))
                except Exception:
                    raise Refused(f"No se pudo leer la página {number} de {name}.") from None
                done += 1
                client.post(callback + "/progress", json={"pages_done": done, "pages_total": total})
            read.append((name, page_xml))
        try:
            if data["kind"] == "score":
                musicxml = join_pages([xml for _, pages_xml in read for xml in pages_xml], data["title"])
            else:
                musicxml = combine_parts([(name, join_pages(pages_xml, name)) for name, pages_xml in read], data["title"])
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
