"""Instrument names as band scores and parts write them (2026-10-28): in Spanish, Valencian and Catalan, English,
German, Italian, French and Galician, with their abbreviations, and with the key written in any of its forms («in Bb»,
«in B b», «B♭», «Sib», «Si b», «Si bemol», the German «in B», «Es», «Mib», «en Fa», «Do»), before or after the name.
Matching stays exact: a name is never guessed from a piece of it."""
import pytest

from backend.domain.instrument_catalog import match_instrument_name


@pytest.mark.parametrize("name, canonical_id", [
    # «Paco el barba» (PDF printed with PDFCreator, 2026-10-28)
    ("Trumpet in B b 2", "trumpet.bb"), ("Trumpet in Bb 3", "trumpet.bb"), ("Clarinet in E b", "clarinet.eb"),
    ("Clarinet in B b 1", "clarinet.bb"), ("Horn in F 1", "horn.f"), ("Tenor Sax.", "saxophone.tenor"),
    ("Baritone Sax.", "saxophone.baritone"), ("Alto Sax. 2", "saxophone.alto"), ("Platos", "crash_cymbals"),
    # the key in every spelling
    ("Trompeta en Sib 1", "trumpet.bb"), ("Trompeta Sib", "trumpet.bb"), ("Trompeta en Si b", "trumpet.bb"),
    ("Trompeta en Si♭", "trumpet.bb"), ("Trompeta en Si bemol", "trumpet.bb"), ("B♭ Trumpet", "trumpet.bb"),
    ("Bb Trumpet 1", "trumpet.bb"), ("Trumpet in B-flat", "trumpet.bb"), ("Trompete in B", "trumpet.bb"),
    ("Trumpet in C", "trumpet.c"), ("Trompeta en Do", "trumpet.c"), ("Tromba in Do", "trumpet.c"),
    ("Clarinete en Mib", "clarinet.eb"), ("Clarinete Mi b", "clarinet.eb"), ("Es-Klarinette", "clarinet.eb"),
    ("Klarinette in Es", "clarinet.eb"), ("Clarinete en La", "clarinet.a"), ("Klarinette in A", "clarinet.a"),
    ("Saxo Tenor Sib", "saxophone.tenor"), ("Saxo Alto Mib", "saxophone.alto"), ("Saxofón barítono Mib", "saxophone.baritone"),
    ("Trompa en Fa 2", "horn.f"), ("Horn in F", "horn.f"), ("Corno in Fa", "horn.f"), ("Cor en Fa", "horn.f"),
    ("Bombardino Do", "euphonium"), ("Bombardino en Sib", "euphonium"), ("Euphonium in Bb", "euphonium"),
    ("Tuba en Do", "tuba"), ("Tuba in C", "tuba"), ("Trombón en Do 2", "trombone.tenor"), ("Trombone in Bb", "trombone.tenor"),
    # Valencian and Catalan
    ("Flautí", "piccolo"), ("Flauta 1", "flute"), ("Oboè", "oboe"), ("Fagot 1", "bassoon"), ("Requint", "clarinet.eb"),
    ("Clarinet 2", "clarinet.bb"), ("Clarinet baix", "clarinet.bass"), ("Saxo alt 1", "saxophone.alto"),
    ("Saxo tenor", "saxophone.tenor"), ("Saxo baríton", "saxophone.baritone"), ("Trompa 3", "horn.f"),
    ("Trompeta 1", "trumpet.bb"), ("Fiscorn 1", "flugelhorn.bb"), ("Fliscorn", "flugelhorn.bb"), ("Trombó 1", "trombone.tenor"),
    ("Trombó baix", "trombone.bass"), ("Bombardí", "euphonium"), ("Tuba 1", "tuba"), ("Contrabaix", "double_bass"),
    ("Violoncel", "cello"), ("Timbals", "timpani"), ("Caixa", "snare_drum"), ("Bombo", "bass_drum"), ("Plats", "crash_cymbals"),
    ("Xilòfon", "xylophone"), ("Triangle", "triangle"), ("Pandereta", "tambourine"),
    # German
    ("Kleine Flöte", "piccolo"), ("Flöte 1", "flute"), ("Oboe 2", "oboe"), ("Fagott", "bassoon"), ("Kontrafagott", "contrabassoon"),
    ("Klarinette in B 1", "clarinet.bb"), ("Bassklarinette", "clarinet.bass"), ("Altsaxophon", "saxophone.alto"),
    ("Tenorsaxophon", "saxophone.tenor"), ("Baritonsaxophon", "saxophone.baritone"), ("Horn in F 3", "horn.f"),
    ("Waldhorn", "horn.f"), ("Trompete 2", "trumpet.bb"), ("Kornett", "cornet.bb"), ("Flügelhorn", "flugelhorn.bb"),
    ("Posaune 1", "trombone.tenor"), ("Bassposaune", "trombone.bass"), ("Tenorhorn", "baritone_horn"), ("Bariton", "euphonium"),
    ("Basstuba", "tuba"), ("Kontrabass", "double_bass"), ("Pauken", "timpani"), ("Kleine Trommel", "snare_drum"),
    ("Große Trommel", "bass_drum"), ("Becken", "crash_cymbals"), ("Glockenspiel", "glockenspiel"), ("Xylophon", "xylophone"),
    ("Schellentrommel", "tambourine"), ("Triangel", "triangle"), ("Schlagzeug", "drum_set"), ("Röhrenglocken", "chimes"),
    # Italian
    ("Ottavino", "piccolo"), ("Flauto 2", "flute"), ("Fagotto", "bassoon"), ("Clarinetto piccolo in Mib", "clarinet.eb"),
    ("Clarinetto in Sib 1", "clarinet.bb"), ("Clarinetto basso", "clarinet.bass"), ("Clarone", "clarinet.bass"),
    ("Sax contralto", "saxophone.alto"), ("Corno 1", "horn.f"), ("Tromba 1", "trumpet.bb"), ("Flicorno soprano", "flugelhorn.bb"),
    ("Trombone 2", "trombone.tenor"), ("Trombone basso", "trombone.bass"), ("Flicorno baritono", "baritone_horn"),
    ("Eufonio", "euphonium"), ("Timpani", "timpani"), ("Tamburo", "snare_drum"), ("Rullante", "snare_drum"),
    ("Gran cassa", "bass_drum"), ("Piatti", "crash_cymbals"), ("Campane tubolari", "chimes"),
    # French
    ("Petite flûte", "piccolo"), ("Flûte 1", "flute"), ("Hautbois", "oboe"), ("Basson", "bassoon"),
    ("Petite clarinette en Mib", "clarinet.eb"), ("Clarinette en Sib 2", "clarinet.bb"), ("Clarinette basse", "clarinet.bass"),
    ("Saxophone alto", "saxophone.alto"), ("Saxophone ténor", "saxophone.tenor"), ("Cor 1", "horn.f"),
    ("Trompette en Sib", "trumpet.bb"), ("Cornet à pistons", "cornet.bb"), ("Bugle", "flugelhorn.bb"),
    ("Trombone basse", "trombone.bass"), ("Tuba basse", "tuba"), ("Contrebasse", "double_bass"), ("Caisse claire", "snare_drum"),
    ("Grosse caisse", "bass_drum"), ("Cymbales", "crash_cymbals"), ("Tambour de basque", "tambourine"), ("Jeu de timbres", "glockenspiel"),
    # Spanish and Galician, with abbreviations
    ("Flautín", "piccolo"), ("Fl. 1", "flute"), ("Ob.", "oboe"), ("Fg.", "bassoon"), ("Req.", "clarinet.eb"), ("Cl. 3", "clarinet.bb"),
    ("Cl. bajo", "clarinet.bass"), ("Sax. alto 1", "saxophone.alto"), ("Sax. tenor", "saxophone.tenor"), ("Sax. barítono", "saxophone.baritone"),
    ("Tpa. 1", "horn.f"), ("Tpta. 2", "trumpet.bb"), ("Fisc. 1", "flugelhorn.bb"), ("Tbn. 1", "trombone.tenor"), ("Bomb.", "euphonium"),
    ("Tubas", "tuba"), ("Timbales", "timpani"), ("Caja", "snare_drum"), ("Plato suspendido", "suspended_cymbal"),
    ("Batería", "drum_set"), ("Lira", "glockenspiel"), ("Campanas", "chimes"), ("Clarinete baixo", "clarinet.bass"),
    ("Frauta", "flute"), ("Óboe", "oboe"), ("Trompeta en Sib", "trumpet.bb"), ("Bombardino", "euphonium"),
])
def test_instrument_names_in_band_languages(name, canonical_id):
    match = match_instrument_name(name)
    assert match.identity is not None, name
    assert match.identity.canonical_id == canonical_id, name


@pytest.mark.parametrize("name, canonical_id, numbers", [
    ("Trumpet in B b 2", "trumpet.bb", (2,)), ("Bb Trumpet 1", "trumpet.bb", (1,)), ("Clarinete en Sib 1 y 2", "clarinet.bb", (1, 2)),
    ("Trompa en Fa 3-4", "horn.f", (3, 4)), ("Posaune 1/2", "trombone.tenor", (1, 2)),
])
def test_the_key_never_hides_the_part_numbers(name, canonical_id, numbers):
    match = match_instrument_name(name)
    assert (match.identity.canonical_id, match.part_numbers) == (canonical_id, numbers)


@pytest.mark.parametrize("name, not_expected", [
    ("Corno inglés", "horn.f"), ("Cor anglais", "horn.f"), ("Englischhorn", "horn.f"),
    ("Clarinete en La", "clarinet.bb"), ("Trompeta en Do", "trumpet.bb"), ("Flauta alto", "flute"),
    ("Clarinete bajo", "clarinet.bb"), ("Trombón bajo", "trombone.tenor"), ("Saxo alto", "saxophone.tenor"),
])
def test_close_names_never_take_another_instrument(name, not_expected):
    match = match_instrument_name(name)
    assert match.identity is None or match.identity.canonical_id != not_expected, name


@pytest.mark.parametrize("name", ["Clarinete en Re", "Trompa en Mib", "Paco el barba", "Marxa Mora", "Bombo i plats",
                                  "Solo", "Tutti"])
def test_what_the_catalog_does_not_know_stays_unknown(name):
    """Unknown keys or names are never forced onto a known instrument: they are asked (Mi banda)."""
    assert match_instrument_name(name).identity is None, name
