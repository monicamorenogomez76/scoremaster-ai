"""What an account keeps, to give it back or to delete it (2026-11-25): rights of access, portability and erasure."""
from datetime import datetime, timedelta, timezone
import json
from typing import BinaryIO, Optional
import zipfile

from sqlalchemy import Engine, text

from backend.application.accounts import User

# The security log is kept this long: enough to look into an improper access.
EVENTS_DAYS = 365
# What is given back, by name: never the hashes, tokens nor other people's data. Analyses are made again from the score.
QUERIES = {
    "account": "select email, display_name, google_sub, created_at, email_verified_at from users where id = :user",
    "works": "select title, composer, file_name, size, preparation_status, source_format, reading_doubts, created_at, updated_at "
             "from works where user_id = :user order by created_at",
    "analyses": "select w.title as work, a.configuration, a.algorithm_version, a.created_at from analyses a "
                "left join works w on w.id = a.work_id where a.user_id = :user order by a.created_at",
    "corrections": "select w.title as work, c.correction, c.created_at from work_corrections c join works w on w.id = c.work_id "
                   "where c.user_id = :user order by c.created_at",
    "published_grades": "select w.title as work, g.scale, g.label, g.grade, g.source, g.url, g.consulted_on, g.created_at "
                        "from work_external_grades g join works w on w.id = g.work_id where g.user_id = :user order by g.created_at",
    "bands": "select name, locality, place, rehearsal_weekdays, rehearsal_time, rehearsal_minutes, profile, section_levels, is_active, "
             "created_at, updated_at from ensembles where user_id = :user order by created_at",
    "concerts": "select title, scheduled_on, starts_at, place, notes, schedule, created_at, updated_at from concerts "
                "where user_id = :user order by created_at",
    "rehearsals": "select scheduled_on, starts_at, duration_minutes, place, objectives, blocks, phase, reviewed_at, review_notes, "
                  "created_at, updated_at from rehearsals where user_id = :user order by created_at",
    "pdf_readings": "select kind, title, status, created_at, updated_at from pdf_imports where user_id = :user order by created_at",
    "instruments": "select label_es, label_en, section, family, created_at from instruments where owner_id = :user order by created_at",
    "instrument_names": "select name, instrument_id, created_at from instrument_names where owner_id = :user order by created_at",
    "campaigns": "select title, instructions, status, created_at, updated_at from evaluation_campaigns where owner_id = :user order by created_at",
    "invitations": "select c.title as campaign, i.experience_level, i.main_instrument from evaluation_invitations i "
                   "join evaluation_campaigns c on c.id = i.campaign_id where i.email = :email order by c.created_at",
    "ratings": "select c.title as campaign, p.label as passage, r.difficulty, r.critical, r.priority, r.comment, r.created_at, r.updated_at "
               "from evaluation_ratings r join evaluation_invitations i on i.id = r.invitation_id "
               "join evaluation_passages p on p.id = r.passage_id join evaluation_campaigns c on c.id = i.campaign_id "
               "where i.email = :email order by r.created_at",
    "sessions": "select created_at, expires_at from sessions where user_id = :user order by created_at",
    "security_log": "select event, ip, created_at from audit_events where user_id = :user order by created_at",
}


def _safe(name: str) -> str:
    return "".join(character for character in name if character.isalnum() or character in "._- ").strip() or "obra.musicxml"


class PostgresPersonalData:
    def __init__(self, engine: Engine):
        self.engine = engine

    def export(self, user: User, invited_as: Optional[str], target: BinaryIO) -> None:
        """A zip with datos.json and the scores, read one by one. invited_as: the email of the account once confirmed."""
        values = {"user": user.id, "email": (invited_as or "").strip().lower() or None}
        with self.engine.connect() as connection, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            data = {name: [dict(row) for row in connection.execute(text(query), values if ":email" in query else {"user": user.id}).mappings()]
                    for name, query in QUERIES.items()}
            archive.writestr("datos.json", json.dumps(data, ensure_ascii=False, indent=2, default=str))
            works = connection.execute(text("select id, file_name from works where user_id = :user order by created_at"), {"user": user.id}).all()
            for number, (work_id, file_name) in enumerate(works, 1):
                source = connection.execute(text("select source from works where id = :id"), {"id": work_id}).scalar()
                archive.writestr(f"partituras/{number:03d} {_safe(file_name)}", bytes(source))

    def delete(self, user: User, invited_as: Optional[str]) -> None:
        """The account and everything it keeps, at once; its ratings too. What was prepared of a work goes with its last copy."""
        with self.engine.begin() as connection:
            connection.execute(text(
                "delete from prepared_works p where p.source_sha256 in (select source_sha256 from works where user_id = :user) "
                "and not exists (select 1 from works w where w.source_sha256 = p.source_sha256 and w.user_id <> :user)"), {"user": user.id})
            if invited_as:
                connection.execute(text("delete from evaluation_invitations where email = :email"), {"email": invited_as.strip().lower()})
            connection.execute(text("delete from audit_events where user_id = :user"), {"user": user.id})
            # The rest of the tables follow the account (ON DELETE CASCADE).
            connection.execute(text("delete from users where id = :user"), {"user": user.id})

    def forget_old_events(self) -> int:
        limit = datetime.now(timezone.utc) - timedelta(days=EVENTS_DAYS)
        with self.engine.begin() as connection:
            return connection.execute(text("delete from audit_events where created_at < :limit"), {"limit": limit}).rowcount
