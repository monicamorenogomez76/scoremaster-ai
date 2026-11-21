"""The name beside each staff of a score's page, read with its place on the page (2026-11-21, «Arabian Dances»)."""
from omr.margin import Word, names_by_staff


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
