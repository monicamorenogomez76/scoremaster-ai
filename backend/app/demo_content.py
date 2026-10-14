"""Content of the demo account, so the examiners and the video never start from an empty app (PR 4 of the
closing plan, 2026-10-14): the three generated works of demo/, a band, a concert with its series of
rehearsals up to the general rehearsal, and a draft evaluation campaign.

Everything goes through the real API with the demo account's session, so it passes the same validation as
a director's own data. Only the shape of the saved blocks is built here, as the editor does in the browser
(frontend/src/rehearsals.js proposalBlocks). Idempotent: an account that already has works is left alone.
"""
from datetime import date, timedelta
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo"
PROGRAMME = ("Marcha de la plaza", "Andante y danza")
BAND = {
    "name": "Banda de demostración", "locality": "Valencia", "place": "Sala de ensayo",
    "rehearsal_weekdays": [1, 3], "rehearsal_time": "20:00", "rehearsal_minutes": 90,
    "profile": {"flute": 3, "oboe": 1, "clarinet.bb": 8, "saxophone.alto": 2, "saxophone.tenor": 1, "horn.f": 2,
                "trumpet.bb": 4, "trombone.tenor": 3, "euphonium": 2, "tuba": 2, "percussion": 3},
}
GROUPS = {"flutes": "Flautas", "double_reeds": "Dobles cañas", "clarinets": "Clarinetes", "saxophones": "Saxofones",
          "high_brass": "Metales agudos", "low_voices": "Graves", "percussion": "Percusión",
          "strings_rhythm": "Cuerda y rítmica", "other": "Otros"}
COMMON = {"line": "Línea común", "rhythm": "Ritmo común"}
FINDINGS = {"SL002": "Registro agudo", "SL003": "Alta densidad rítmica", "SL004": "Intervalos amplios",
            "SL005": "Pasaje prolongado sin descanso"}


def _block(segment: dict) -> dict:
    """A planned segment as the editor saves it (the same rules as proposalBlocks in the browser)."""
    kind = segment["type"]
    if kind == "warmup":
        title, group, objective = "Calentamiento", "warmup", "Afinación, sonido y articulación de toda la banda."
    elif kind == "runthrough":
        title, group, objective = "Pasada completa", "tutti", "Obra completa en orden de concierto."
    elif kind == "tutti":
        title, group, objective = "Tutti para juntar", "tutti", "Toda la banda"
    elif kind == "common":
        title, group = COMMON.get(segment.get("kind"), COMMON["rhythm"]), "common"
        objective = ", ".join(segment.get("parts") or [])
    else:
        name = GROUPS.get(segment.get("group"), GROUPS["other"])
        title, group, objective = "Seccional · " + name, segment.get("group") or "other", ", ".join(segment.get("parts") or [])
    if kind not in ("warmup", "runthrough", "tutti") and segment.get("findings"):
        objective += " · " + ", ".join(FINDINGS.get(code, code) for code in segment["findings"])
    if kind in ("warmup", "tutti", "runthrough"):
        sections = ["Toda la banda"]
    elif kind == "common":
        sections = [GROUPS.get(item, GROUPS["other"]) for item in segment.get("groups") or []]
    else:
        sections = [GROUPS.get(segment.get("group"), GROUPS["other"])]
    measures = ", ".join(segment.get("measure_ranges") or []) if kind == "tutti" else segment.get("measure_range") or ""
    return {"title": title, "minutes": segment["minutes"], "group": group, "parts": segment.get("parts") or [],
            "work_id": segment.get("work_id"), "measures": measures[:40],
            "sections": list(dict.fromkeys(sections))[:20], "objective": objective[:500]}


def _ok(response, what: str) -> dict:
    if response.status_code >= 400:
        raise RuntimeError("No se pudo crear {} de la demo: {} {}".format(what, response.status_code, response.text[:200]))
    return response.json() if response.content else {}


def seed_demo_content(client, email: str, password: str, today: date) -> str:
    """client: an HTTP client of this app (TestClient). Returns created, exists or skipped."""
    login = client.post("/auth/login", json={"email": email, "password": password})
    if login.status_code != 200:
        return "skipped"
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    if _ok(client.get("/works"), "la lista de obras")["works"]:
        return "exists"
    _ok(client.post("/bands", json=BAND), "la banda")
    titles = {}
    for path in sorted(DEMO_DIR.glob("*.musicxml")):
        analysed = _ok(client.post("/analyze", files={"file": (path.name, path.read_bytes(), "application/xml")},
                                   data={"total_minutes": "90"}), "el análisis de " + path.name)
        titles[analysed["title"]] = analysed["work_id"]
    # The works of the concert are being prepared: the summary shows them and their critical passages.
    for title in PROGRAMME:
        _ok(client.patch("/works/" + titles[title], json={"preparation_status": "preparing"}), "el estado de " + title)
    concert = _ok(client.post("/concerts", json={
        "title": "Concierto de Santa Cecilia", "date": (today + timedelta(days=42)).isoformat(), "time": "19:00",
        "place": "Auditorio municipal", "notes": "Concierto de demostración.",
        "work_ids": [titles[title] for title in PROGRAMME],
        "schedule": {"weekdays": [1, 3], "time": "20:00", "duration_minutes": 90, "start_date": today.isoformat()},
    }), "el concierto")
    plan = _ok(client.post("/concerts/{}/plan".format(concert["id"]), json={"today": today.isoformat()}), "la planificación")
    _ok(client.put("/concerts/{}/rehearsals".format(concert["id"]), json={"today": today.isoformat(), "rehearsals": [
        {"id": item["id"], "date": item["date"], "time": item["time"], "duration_minutes": item["duration_minutes"],
         "phase": item["phase"], "work_ids": item["work_ids"], "blocks": [_block(block) for block in item["blocks"]]}
        for item in plan["rehearsals"]]}), "los ensayos")
    _ok(client.post("/evaluations", json={
        "title": "Valoración de pasajes (demostración)",
        "instructions": "Valora cada pasaje pensando en una banda amateur de nivel medio.",
        "work_ids": [titles[title] for title in PROGRAMME], "size": 20,
    }), "la campaña")
    return "created"
