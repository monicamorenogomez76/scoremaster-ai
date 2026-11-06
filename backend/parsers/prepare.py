"""A work read from a PDF is prepared in GitHub's machine (2026-11-04): its four processors read with music21 in seconds
what takes minutes on Render's tenth of a CPU. The reader sends what Render would have stored, and Render only checks
it. Runs in both places, so it imports nothing but the parsers and the domain."""
import base64
import gzip
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
import zlib

from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.pdf_measures import fit_measures
from backend.parsers.pdf_transpositions import add_transpositions, fix_key_signatures
from backend.parsers.playback import TIMELINE_VERSION, encode_timeline, timeline_has_parts
from backend.parsers.score_codec import SCORE_VERSION, decode_score, encode_score

# Render has 512 MB: what opens into more than this is not opened.
MAX_PREPARED_BYTES = 64 * 1024 * 1024


def encoded_model(content: bytes) -> bytes:
    """The parsed model of a work, as the store keeps it."""
    with NamedTemporaryFile(suffix=".musicxml", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(content)
    try:
        return encode_score(parse_musicxml(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)


def prepare_work(content: bytes) -> dict:
    """The parsed model and the audio timeline of a work, ready to travel in the reader's result."""
    score = encoded_model(content)
    return {"sha256": sha256(content).hexdigest(),
            "score_version": SCORE_VERSION, "score": base64.b64encode(score).decode(),
            "timeline_version": TIMELINE_VERSION, "timeline": base64.b64encode(encode_timeline(content)).decode()}


def final_musicxml(read: bytes, learned: dict | None, concert_pitch: bool, source: str) -> bytes:
    """The bytes kept for a work read from a PDF: what the reader read with what it cannot know. Raises ParseError."""
    # copista writes the notes in the key of each instrument but no <transpose> (2026-10-29).
    # Each measure keeps the length of its time signature: one read too long made its part sound late.
    content = add_transpositions(fit_measures(read), learned, concert_pitch, source)
    # A key signature the reader missed in a transposed part is taken from the band.
    return fix_key_signatures(content)


def finish_reading(read: bytes, learned: dict | None, concert_pitch: bool, source: str) -> dict:
    """What prepare_work makes for the final bytes of a reading, with those bytes compressed (12 MB are 347 KB): Render keeps
    them without opening them."""
    content = final_musicxml(read, learned, concert_pitch, source)
    return {**prepare_work(content), "musicxml_gz": base64.b64encode(gzip.compress(content)).decode()}


def opened_final(prepared: dict, limit: int) -> bytes | None:
    """The final bytes the reader sent, if they are what it says and fit in limit bytes."""
    try:
        with gzip.GzipFile(fileobj=BytesIO(base64.b64decode(prepared["musicxml_gz"], validate=True))) as opened:
            content = opened.read(limit + 1)
    except (OSError, EOFError, zlib.error, ValueError, TypeError):
        return None
    if len(content) > limit or b"<!ENTITY" in content or sha256(content).hexdigest() != prepared.get("sha256"):
        return None
    return content


def _fits(data: bytes) -> bool:
    try:
        with gzip.GzipFile(fileobj=BytesIO(data)) as opened:
            return len(opened.read(MAX_PREPARED_BYTES + 1)) <= MAX_PREPARED_BYTES
    except (OSError, EOFError, zlib.error):
        return False


def usable_score(data: bytes) -> bool:
    try:
        return _fits(data) and bool(decode_score(data).parts)
    except ValueError:
        return False


def usable_timeline(data: bytes) -> bool:
    return _fits(data) and timeline_has_parts(data)
