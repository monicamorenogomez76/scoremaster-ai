"""Copies of Render's free database, which expires 30 days after it was created (~2026-11-06). The round
trip is checked by hand against the Compose database (see docs/DEPLOYMENT.md); these tests keep the
scripts runnable and the database URL and the copies out of the repository."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [ROOT / "scripts" / "backup_db.sh", ROOT / "scripts" / "restore_db.sh"]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_the_scripts_are_valid_shell_and_executable(script):
    assert subprocess.run(["sh", "-n", str(script)]).returncode == 0
    assert script.stat().st_mode & 0o111


def test_the_database_url_is_never_printed_and_reaches_docker_only_as_an_environment_variable():
    for script in SCRIPTS + [ROOT / "scripts" / "db_url.sh"]:
        text = script.read_text()
        assert 'echo "$PGURL' not in text and "echo $PGURL" not in text
    helper = (ROOT / "scripts" / "db_url.sh").read_text()
    docker = next(line for line in helper.splitlines() if line.strip().startswith("docker run"))
    assert '-e PGURL="$PGURL"' in docker and docker.count("PGURL") == 2


def test_copies_never_reach_the_repository():
    assert "backups/" in (ROOT / ".gitignore").read_text().splitlines()


def test_restoring_refuses_a_missing_file():
    result = subprocess.run(["sh", str(SCRIPTS[1]), "backups/no-existe.dump"], capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "DATABASE_URL_EXTERNAL": "postgresql://x"})
    assert result.returncode != 0 and "No existe" in result.stderr


def test_local_urls_are_translated_for_the_container():
    script = '. scripts/db_url.sh; pg_url "postgresql+psycopg://u:p@127.0.0.1:5433/db"'
    out = subprocess.run(["sh", "-c", script], cwd=ROOT, capture_output=True, text=True).stdout
    assert out == "postgresql://u:p@host.docker.internal:5433/db"
