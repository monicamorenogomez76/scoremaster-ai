"""PDF reader of ScoreMaster in a private Hugging Face Space (author's decision, 2026-10-27). Only ScoreMaster calls
it: Hugging Face lets the request into the private Space with the author's token (Authorization) and this service
checks its own secret, OMR_TOKEN, in X-OMR-Token. A job is one score (one or more PDFs read in order) or the parts of a work (one PDF per
instrument). One job is read at a time, page by page with copista-2m (copisteria), in a temporary folder deleted at the
end; the job is forgotten once its MusicXML is collected, or an hour later. Nothing sent is logged."""
from __future__ import annotations

import hmac
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from omr.merge import combine_parts, join_pages

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES = 40
MAX_PAGES = 80
PAGE_TIMEOUT_SECONDS = 300
FORGET_AFTER_SECONDS = 3600
# copisteria finds its models/ folder in the directory it runs from (omr/Dockerfile).
COPISTERIA_DIR = Path(os.environ.get("COPISTERIA_DIR", "/opt/copisteria"))

app = FastAPI(title="ScoreMaster OMR", docs_url=None, redoc_url=None, openapi_url=None)
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
_WORKER = ThreadPoolExecutor(max_workers=1)


def read_page(pdf_path: str, number: int, out_dir: str) -> bytes:
    """One page read by copista-2m in its own process, so its memory goes back when it ends."""
    subprocess.run([sys.executable, "-m", "copisteria.pipeline", "--pdf", pdf_path, "--range", f"{number}-{number}",
                    "--out", out_dir, "--detector", "2m"], cwd=COPISTERIA_DIR, check=True, timeout=PAGE_TIMEOUT_SECONDS,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (Path(out_dir) / f"{Path(pdf_path).stem}_p{number:02d}.musicxml").read_bytes()


def count_pages(pdf_path: str) -> int:
    output = subprocess.run(["pdfinfo", pdf_path], check=True, capture_output=True, text=True, timeout=30).stdout
    return next(int(line.split()[1]) for line in output.splitlines() if line.startswith("Pages:"))


def start(job) -> None:
    _WORKER.submit(job)


def _authorised(sent: str | None) -> None:
    token = os.environ.get("OMR_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="El lector no está configurado.")
    if not sent or not hmac.compare_digest(sent.encode(), token.encode()):
        raise HTTPException(status_code=401, detail="No autorizado.")


def _forget_old() -> None:
    limit = time.time() - FORGET_AFTER_SECONDS
    with LOCK:
        for job_id in [job_id for job_id, job in JOBS.items() if job["created"] < limit]:
            JOBS.pop(job_id, None)


def _read(job_id: str, folder: str, files: list[tuple[str, str, int]], kind: str, title: str) -> None:
    job = JOBS[job_id]
    try:
        job["status"] = "reading"
        read: list[tuple[str, bytes]] = []
        for name, path, pages in files:
            out_dir = tempfile.mkdtemp(dir=folder)
            page_xml = []
            for number in range(1, pages + 1):
                try:
                    page_xml.append(read_page(path, number, out_dir))
                except Exception:
                    raise RuntimeError(f"No se pudo leer la página {number} de {name}.") from None
                job["pages_done"] += 1
            read.append((name, page_xml))
        if kind == "score":
            job["musicxml"] = join_pages([xml for _, pages in read for xml in pages], title).decode("utf-8")
        else:
            job["musicxml"] = combine_parts([(name, join_pages(pages, name)) for name, pages in read], title).decode("utf-8")
        job["status"] = "done"
    except RuntimeError as error:
        job.update(status="failed", error=str(error))
    except Exception:
        job.update(status="failed", error="No se pudo unir lo leído en una obra.")
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@app.get("/")
def health():
    """Public and empty: ScoreMaster calls it to wake the Space."""
    return {"status": "ok"}


@app.post("/jobs", status_code=202)
def create_job(files: list[UploadFile] = File(default=[]), kind: str = Form(...), title: str = Form("", max_length=200),
               x_omr_token: str | None = Header(default=None)):
    _authorised(x_omr_token)
    if kind not in ("score", "parts"):
        raise HTTPException(status_code=422, detail="kind debe ser score o parts.")
    if not files or len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Envía entre 1 y {MAX_FILES} PDF.")
    _forget_old()
    folder = tempfile.mkdtemp(prefix="omr-")
    try:
        saved, total = [], 0
        for index, upload in enumerate(files):
            content = upload.file.read(MAX_FILE_BYTES + 1)
            if len(content) > MAX_FILE_BYTES:
                raise HTTPException(status_code=413, detail=f"Cada PDF puede tener hasta {MAX_FILE_BYTES // (1024 * 1024)} MB.")
            if not content.startswith(b"%PDF"):
                raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")
            path = os.path.join(folder, f"{index:02d}.pdf")
            with open(path, "wb") as handle:
                handle.write(content)
            pages = count_pages(path)
            total += pages
            if total > MAX_PAGES:
                raise HTTPException(status_code=413, detail=f"Se leen hasta {MAX_PAGES} páginas por obra.")
            saved.append((os.path.basename(upload.filename or f"{index + 1}.pdf"), path, pages))
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    job_id = uuid.uuid4().hex
    with LOCK:
        JOBS[job_id] = {"status": "queued", "pages_done": 0, "pages_total": total, "created": time.time()}
    start(lambda: _read(job_id, folder, saved, kind, title.strip() or "Obra leída de PDF"))
    return JSONResponse(status_code=202, content={"id": job_id})


@app.get("/jobs/{job_id}")
def job_status(job_id: str, x_omr_token: str | None = Header(default=None)):
    _authorised(x_omr_token)
    with LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Trabajo desconocido.")
        answer = {key: job[key] for key in ("status", "pages_done", "pages_total") if key in job}
        if "error" in job:
            answer["error"] = job["error"]
        if job["status"] == "done":
            answer["musicxml"] = job["musicxml"]
        if job["status"] in ("done", "failed"):
            JOBS.pop(job_id, None)
    return answer
