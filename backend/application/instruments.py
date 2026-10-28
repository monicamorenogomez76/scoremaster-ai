"""The instrument catalog kept in the database (2026-10-28). Port only: PostgreSQL lives in
backend/infrastructure/instrument_repository.py; the resolver receives the catalog through use_catalog."""
from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

# What a catalog instrument may say, besides its labels and names: the values the resolver, BandFit, the rehearsal
# plan and playback know.
SECTIONS = ("woodwinds", "brass", "percussion", "strings", "keyboard", "rhythm")
KEYS = ("Bb", "Eb", "F", "A", "G", "D")
REHEARSAL_GROUPS = ("flutes", "double_reeds", "clarinets", "saxophones", "high_brass", "low_voices", "percussion",
                    "strings_rhythm")


class DuplicateName(Exception):
    """The name already names an instrument."""


class InstrumentRepository(Protocol):
    def common(self) -> list[dict]:
        """Every common instrument in catalog order, as the resolver takes it: id, fields and aliases."""

    def listing(self) -> list[dict]:
        """The common instruments with their names (id and text), for the administration."""

    def add_name(self, instrument_id: str, name: str, name_key: str) -> Optional[dict]:
        """None when the instrument does not exist; DuplicateName when the name is taken."""

    def delete_name(self, name_id: int) -> bool: ...

    def create_instrument(self, fields: dict, names: list[tuple[str, str]]) -> dict:
        """DuplicateName when the id or a name is taken."""

    def update_instrument(self, instrument_id: str, fields: dict) -> Optional[dict]: ...

    def private(self) -> list[dict]:
        """Every instrument created by an account, so the resolver finds it by its id."""

    def for_account(self, user_id: UUID) -> list[dict]:
        """The instruments the account created."""

    def learned(self, user_id: UUID) -> dict[str, str]:
        """Part names the account confirmed (normalized, without part numbers) → instrument id."""

    def learn(self, user_id: UUID, names: list[tuple[str, str, str]]) -> None:
        """(name, normalized name, instrument id) confirmed by the account; a name confirmed again takes the new one."""

    def create_own(self, user_id: UUID, fields: dict) -> dict: ...
