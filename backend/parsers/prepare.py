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
from backend.parsers.playback import TIMELINE_VERSION, encode_timeline, timeline_has_parts
from backend.parsers.score_codec import SCORE_VERSION, decode_score, encode_score

# Render has 512 MB: what opens into more than this is not opened.
MAX_PREPARED_BYTES = 64 * 1024 * 1024


def prepare_work(content: bytes) -> dict:
    """The parsed model and the audio timeline of a work, ready to travel in the reader's result."""
    with NamedTemporaryFile(suffix=".musicxml", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(content)
    try:
        score = encode_score(parse_musicxml(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)
    return {"sha256": sha256(content).hexdigest(),
            "score_version": SCORE_VERSION, "score": base64.b64encode(score).decode(),
            "timeline_version": TIMELINE_VERSION, "timeline": base64.b64encode(encode_timeline(content)).decode()}


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
