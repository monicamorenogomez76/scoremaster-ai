"""Content of the demo account, so a visitor never starts from an empty app (2026-10-14): the three generated works of demo/, a band, a concert with its series of
rehearsals up to the general rehearsal, and an evaluation campaign.

The demo is not an administrator (its password is in the README; 2026-10-14): it never sees the musicians'
emails or results. The seed acts as the server's operator only while it runs, to create the example
campaign, open it and invite the demo itself, which then shows the musician's side.

Everything goes through the real API with the demo account's session, so it passes the same validation as
a director's own data. Only the shape of the saved blocks is built here, as the editor does in the browser
(frontend/src/rehearsals.js proposalBlocks). Idempotent: an account that already has works is left alone.
"""
import os
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import text

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo"
# sha256 of the demo works published before they followed the rules of harmony (#93, and #97 with the
# key signatures fixed): an account holding only these gets the current works and everything made of them.
OUTDATED_SOURCES = frozenset({
    "f0e98abb551193ec6de9a365d7b0d48da1b49a9a72de88d24a1437c2384908f1",
    "5254375ebcefcc59e861bc33055202e423607f5474c92422575ca2268eb78c4c",
    "b03866f277447ecf0cf4ce92e484ca5d0e3aff5c1bee0362569a157698d0d852",
    "d6e53457e0c2f39c940032a3e2c9af3b16bb19a3ffcf59d84658e7f44890c3a0",
    "2dd55fa9a21cc90e2cd6ab5e05f533ab04e125aea570bc05fb2b58972928ef76",
    "734a22c20abde8e892d558987a4a598c479dfe2027d3a4fce39abe25d7ec58fe",
})
PROGRAMME = ("Marcha de la plaza", "Andante y danza")
DEMO_CAMPAIGN = "Valoración de pasajes (demostración)"
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


@contextmanager
def _as_administrator(email: str):
    """ADMIN_EMAILS with the demo only inside the seed's own process, restored afterwards."""
    saved = os.environ.get("ADMIN_EMAILS")
    os.environ["ADMIN_EMAILS"] = ",".join(item for item in (saved, email) if item)
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("ADMIN_EMAILS", None)
        else:
            os.environ["ADMIN_EMAILS"] = saved


def _open_to_the_demo(client, email: str):
    """Each draft example campaign is opened with the demo invited (also the one an earlier seed left)."""
    for item in _ok(client.get("/evaluations"), "la lista de campañas")["owned"]:
        if item["title"] == DEMO_CAMPAIGN and item["status"] == "draft":
            path = "/evaluations/" + item["id"]
            _ok(client.put(path + "/invitations", json={"emails": [email]}), "la invitación de la demo")
            _ok(client.post(path + "/status", json={"status": "open"}), "la apertura de la campaña")


def seed_demo_content(client, email: str, password: str, today: date) -> str:
    """client: an HTTP client of this app (TestClient). Returns created, exists or skipped."""
    login = client.post("/auth/login", json={"email": email, "password": password})
    if login.status_code != 200:
        return "skipped"
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    with _as_administrator(email):
        if _ok(client.get("/works"), "la lista de obras")["works"]:
            _open_to_the_demo(client, email)
            return "exists"
        _seed(client, today)
        _open_to_the_demo(client, email)
    return "created"


def _seed(client, today: date):
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
        "title": DEMO_CAMPAIGN,
        "instructions": "Valora cada pasaje pensando en una banda amateur de nivel medio.",
        "work_ids": [titles[title] for title in PROGRAMME], "size": 20,
    }), "la campaña")


def reset_outdated_demo(engine, email: str) -> bool:
    """Empties the demo account when all its works are earlier versions of the demo works, so the seed
    creates them again: analyses, concert, rehearsals and campaign were made of the old notes. An account
    with any other work, or with ratings already given, is left alone. Returns whether it was emptied."""
    with engine.begin() as connection:
        user = connection.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email.strip().lower()}).scalar()
        if user is None:
            return False
        sources = set(connection.execute(text("SELECT source_sha256 FROM works WHERE user_id = :user"), {"user": user}).scalars())
        if not sources or not sources <= OUTDATED_SOURCES:
            return False
        rated = connection.execute(text(
            "SELECT 1 FROM evaluation_ratings r JOIN evaluation_passages p ON p.id = r.passage_id "
            "JOIN evaluation_campaigns c ON c.id = p.campaign_id WHERE c.owner_id = :user LIMIT 1"), {"user": user}).first()
        if rated:
            return False
        # Campaigns take their passages and invitations; works take their analyses.
        for table, owner in (("evaluation_campaigns", "owner_id"), ("rehearsals", "user_id"), ("concerts", "user_id"),
                             ("ensembles", "user_id"), ("analyses", "user_id"), ("works", "user_id")):
            connection.execute(text("DELETE FROM {} WHERE {} = :user".format(table, owner)), {"user": user})
    return True
