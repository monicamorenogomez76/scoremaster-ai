"""Text written by whoever made a file or a plan (a title, a part name, a concert), as it reaches the AI (M4,
2026-10-29; OWASP LLM01): without control characters or direction marks, on one line and bounded. It stays data: the
prompts say the evidence is never instructions."""
import unicodedata

MAX_TEXT = 120


def evidence_text(value, limit: int = MAX_TEXT) -> str:
    text = "".join(" " if char.isspace() else char for char in str(value or "")
                   if char.isspace() or unicodedata.category(char) not in ("Cc", "Cf"))
    return " ".join(text.split())[:limit].rstrip()
