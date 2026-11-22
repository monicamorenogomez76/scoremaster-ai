"""The doubts of the PDF reader (2026-11-22): the measures it took from a part because the score's staff read otherwise.
The director sees them grouped by part, opens each passage beside the PDF and marks a part as reviewed."""
from backend.application.reading_doubts import grouped, printed, reviewed
from backend.test.test_pdf_measures import note, work


def test_the_doubts_keep_the_numbers_the_pdf_prints():
    """The reader counts measures from 1; the work kept numbers an upbeat 0, as the PDF does."""
    from backend.parsers.prepare import final_musicxml
    finished = final_musicxml(work(note(4), note(8), note(8)), None, False, "score")
    found = printed(finished, [{"part": "Flauta", "measure": 1}, {"part": "Flauta", "measure": 3},
                               {"part": "Flauta", "measure": 9}, {"part": "Oboe", "measure": "x"}])
    assert found == {"measures": [{"part": "Flauta", "position": 1, "measure": "0"},
                                  {"part": "Flauta", "position": 3, "measure": "2"}], "reviewed": []}


def test_the_doubts_are_shown_by_part_in_passages_of_consecutive_measures():
    stored = {"measures": [{"part": "Fl. 1", "position": 81, "measure": "81"}, {"part": "Tpt. 2", "position": 5, "measure": "5"},
                           {"part": "Fl. 1", "position": 82, "measure": "82"}, {"part": "Fl. 1", "position": 83, "measure": "83"},
                           {"part": "Fl. 1", "position": 95, "measure": "95"}],
              "reviewed": ["Tpt. 2"]}
    assert grouped(stored) == [
        {"part": "Fl. 1", "measures": 4, "reviewed": False, "passages": ["81-83", "95"]},
        {"part": "Tpt. 2", "measures": 1, "reviewed": True, "passages": ["5"]},
    ]
    assert grouped(None) == []


def test_a_part_is_marked_reviewed_and_back():
    stored = {"measures": [{"part": "Fl. 1", "position": 1, "measure": "1"}], "reviewed": []}
    marked = reviewed(stored, "Fl. 1", True)
    assert marked["reviewed"] == ["Fl. 1"] and stored["reviewed"] == [], "the stored doubts are not changed in place"
    assert reviewed(marked, "Fl. 1", False)["reviewed"] == []
    assert reviewed(stored, "Oboe", True) is None, "a part without doubts"
