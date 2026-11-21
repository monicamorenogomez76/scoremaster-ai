"""The name beside each staff of a score's page, read with its place on the page (2026-11-21, «Arabian Dances»)."""
from omr.margin import Word, join_split_capitals, names_at, names_by_staff, one_system, split_capitals


def word(text, left, middle, width=8.0):
    return Word(text, left, left + width, middle)


def page_six():
    """The margin of page 6 of «Arabian Dances», as pdftotext places it: one clef per staff at x = 69, names to the left,
    and the numbers of the parts between the names and the clefs."""
    clefs = [word("&", 69, 58), word("&", 69, 90), word("?", 69, 121), word("&", 69, 184), word("&", 69, 215),
             word("?", 69, 563)]
    return clefs + [
        word("6", 16, 23),                                   # the page number
        word("Picc.", 42, 59),
        word("Fls.", 44, 90), word("1", 58, 86, 3), word("2", 58, 95, 3),
        word("Bsns.", 42, 120), word("1", 58, 116, 3), word("2", 58, 125, 3),
        word("Cls.", 43, 200), word("1", 57, 185, 3), word("2", 56, 212, 3), word("3", 56, 220, 3),
        word("Timp.", 42, 559), word("Shkr.", 42, 567), word("÷ œœ œœ", 40, 600),
    ]


def test_each_staff_takes_the_name_beside_it_and_the_numbers_of_its_parts():
    assert names_by_staff(page_six(), 6) == ["Picc.", "Fls. 1 2", "Bsns. 1 2", "Cls. 1", "Cls. 2 3", "Timp./Shkr."]


def test_a_page_with_several_systems_names_the_staves_of_the_first():
    words = page_six()
    repeated = words + [Word(item.text, item.left, item.right, item.middle + 700) for item in words if item.text in "&?"]
    assert names_by_staff(repeated, 6) == names_by_staff(words, 6)


def test_without_one_clef_per_staff_nothing_is_named():
    assert names_by_staff(page_six(), 5) is None
    assert names_by_staff([word("Picc.", 42, 59)], 1) is None


# «1812» (2026-11-21): its font prints each name's capital apart, closer to the rest than a space («F l. 1», «H n. 1»,
# «B . C l.», «P iccolo»); the catalog knew none of them, and no staff of the score was named.
def letters(*pieces, middle=129.0, height=6.85):
    """Words of one line from (text, left, right)."""
    return [Word(text, left, right, middle, height) for text, left, right in pieces]


def test_a_capital_printed_apart_is_joined_to_the_rest_of_its_word():
    flute = letters(("F", 59.28, 63.07), ("l.", 63.84, 67.46), ("1", 69.12, 72.53))
    assert [found.text for found in join_split_capitals(flute)] == ["Fl.", "1"]
    clarinet = letters(("B", 55.08, 59.25), (".", 60.00, 61.71), ("C", 63.36, 68.20), ("l.", 68.88, 72.63))
    assert [found.text for found in join_split_capitals(clarinet)] == ["B.", "Cl."]


def test_words_a_space_apart_stay_apart():
    horn = letters(("F", 40.0, 44.0), ("horn", 45.65, 60.0))
    assert [found.text for found in join_split_capitals(horn)] == ["F", "horn"]
    tom = letters(("Low", 40.0, 52.0), ("Tom,", 52.8, 66.0))
    assert [found.text for found in join_split_capitals(tom)] == ["Low", "Tom,"]


def test_a_capital_beside_one_letter_a_note_or_big_print_stays_apart():
    """A scan's OCR («T e», «I m»), a capital before a music sign («N œ»), a dynamic in big print («F legato»)."""
    ocr = letters(("T", 40.0, 43.0), ("e", 43.8, 46.0))
    assert [found.text for found in join_split_capitals(ocr)] == ["T", "e"]
    note = letters(("N", 40.0, 50.0), ("œ", 50.5, 60.0), height=19.9)
    assert [found.text for found in join_split_capitals(note)] == ["N", "œ"]
    big = letters(("F", 40.0, 60.0), ("legato", 64.0, 120.0), height=36.8)
    assert [found.text for found in join_split_capitals(big)] == ["F", "legato"]


def test_the_pairs_joined_mend_the_page_s_text():
    words = letters(("F", 59.28, 63.07), ("l.", 63.84, 67.46)) + letters(("H", 59.0, 63.5), ("n.", 64.2, 68.0), middle=500)
    assert split_capitals(words) == {("F", "l."), ("H", "n.")}


# «1812» (2026-11-21): copisteria found the 30 staves of a page but took them for three systems (13 woodwinds, 11 brass,
# 6 percussion: the bar lines break between the families) and wrote one after another, as later measures of 13 parts.
def staves_at(count, top=90.0, gap=34.0, left=74.0):
    return [(top + gap * index, top + gap * index + 12, left) for index in range(count)]


def names_beside(names, top=96.0, gap=34.0):
    return [Word(name, 40.0, 70.0, top + gap * index, 7.0) for index, name in enumerate(names)]


BAND = ["Picc.", "Fl. 1", "Fl. 2", "Ob.", "Cl. 1", "Cl. 2", "Cl. 3", "B. Cl.", "Bsn.", "A. Sax. 1", "A. Sax. 2",
        "T. Sax.", "B. Sax.", "Tpt. 1", "Tpt. 2", "Tpt. 3", "Tpt. 4", "Hn. 1", "Hn. 2", "Tbn. 1"]


def test_a_page_naming_each_of_its_staves_is_one_system():
    assert one_system(staves_at(20), names_beside(BAND))


def test_two_systems_name_their_instruments_twice():
    assert not one_system(staves_at(20), names_beside(BAND[:10] * 2))


def test_a_page_without_names_is_left_as_copisteria_reads_it():
    assert not one_system(staves_at(20), [])
    assert not one_system(staves_at(20), names_beside(BAND[:6]))


# Each staff copisteria read on such a page takes the name beside it (2026-11-21, «1812»): it misses one to three of
# the 30 staves of a page, those resting, and by clef and key alone three clarinets or four trumpets are alike.
def test_each_staff_read_takes_the_name_nearest_to_it_even_when_one_is_missing():
    words = names_beside(["Fl. 1", "Fl. 2", "Cl. 1"], top=96.0)
    assert names_at(words, [96.0, 164.0, 198.0], 74.0) == ["Fl. 1", "Cl. 1", None]


def test_a_name_over_two_lines_is_one_name():
    words = [Word("Bass Clarinet", 30.0, 70.0, 92.0, 7.0), Word("in Bb", 50.0, 70.0, 101.0, 7.0),
             Word("Bsn.", 50.0, 70.0, 130.0, 7.0)]
    assert names_at(words, [96.5, 130.0], 74.0) == ["Bass Clarinet in Bb", "Bsn."]

