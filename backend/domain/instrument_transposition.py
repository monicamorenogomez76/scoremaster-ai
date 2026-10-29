"""Written to sounding pitch of each catalog instrument (2026-10-29), as MusicXML's <transpose> says it: chromatic and
diatonic steps within the octave, plus whole octaves. Parts are printed in the key of their instrument, and a MusicXML
without <transpose> (the PDF reader's) would sound as written."""
from __future__ import annotations

# (chromatic, diatonic, octave-change); instruments written at sounding pitch are not listed.
_WRITTEN_TO_SOUNDING = {
    "piccolo": (0, 0, 1),
    "flute.alto": (-5, -3, 0),
    "english_horn": (-7, -4, 0),
    "contrabassoon": (0, 0, -1),
    "clarinet.eb": (3, 2, 0),
    "clarinet.bb": (-2, -1, 0),
    "clarinet.a": (-3, -2, 0),
    "clarinet.alto": (-9, -5, 0),
    "clarinet.bass": (-2, -1, -1),
    "clarinet.contrabass": (-2, -1, -2),
    "saxophone.soprano": (-2, -1, 0),
    "saxophone.alto": (-9, -5, 0),
    "saxophone.tenor": (-2, -1, -1),
    "saxophone.baritone": (-9, -5, -1),
    "horn.f": (-7, -4, 0),
    "trumpet.bb": (-2, -1, 0),
    "cornet.bb": (-2, -1, 0),
    "flugelhorn.bb": (-2, -1, 0),
    "double_bass": (0, 0, -1),
    "electric_bass": (0, 0, -1),
    "guitar.electric": (0, 0, -1),
    "guitar.acoustic": (0, 0, -1),
    "glockenspiel": (0, 0, 2),
    "xylophone": (0, 0, 1),
}
# In treble clef these are the B♭ parts of Spanish and brass bands, a ninth above sounding; in bass clef, as written.
_IN_B_FLAT_IN_TREBLE_CLEF = {"euphonium", "baritone_horn", "trombone.tenor"}


def written_to_sounding(canonical_id: str, clef_sign: str | None = None) -> tuple[int, int, int] | None:
    """The interval from written to sounding pitch, None when the instrument sounds as written."""
    if canonical_id in _IN_B_FLAT_IN_TREBLE_CLEF:
        return (-2, -1, -1) if clef_sign == "G" else None
    return _WRITTEN_TO_SOUNDING.get(canonical_id)
