"""Visible difficulty grades 1-6 and the internal technical index 0-10 (step 13).

Decided on 2026-10-05: the index is twice the previous 0-5 score, an explicit transform
that keeps the order between parts, and six equal bands of the index give the grade until the
evaluation with musicians calibrates them. The rubric (docs/DIFFICULTY_CRITICALITY.md) describes
the band that can play each grade; it is not an official certification.
"""
from __future__ import annotations

SCALE = {"version": 2, "grades": 6, "technical_index_max": 10}


def technical_index(legacy_score: float) -> float:
    return round(max(0.0, min(10.0, legacy_score * 2)), 2)


def grade_from_index(index: float) -> int:
    return 1 + min(5, int(index * 6 / 10))


# Publisher grades typed in by the director (PR 5 of the closing plan, 2026-10-14). Equivalences in
# docs/DIFFICULTY_CRITICALITY.md: Grade N is grade N with its halves (Grade 0.5 counts as 1) and the
# letters of J.W. Pepper are grades 1-6. Never extracted automatically nor asked to an LLM.
EXTERNAL_SCALES = ("grade", "pepper")
PEPPER_LEVELS = {"VE": 1, "E": 2, "ME": 3, "M": 4, "MA": 5, "A": 6}


def external_grade(scale: str, value: str) -> tuple[float, str]:
    """(grade on the 1-6 scale, label as published); ValueError for an unknown scale or value."""
    if scale == "pepper":
        letters = str(value).strip().upper()
        if letters not in PEPPER_LEVELS:
            raise ValueError("Nivel de Pepper desconocido: VE, E, ME, M, MA o A.")
        return float(PEPPER_LEVELS[letters]), "Pepper " + letters
    if scale == "grade":
        try:
            number = float(str(value).strip().replace(",", "."))
        except ValueError:
            raise ValueError("El grado debe ser un número de 0,5 a 6.") from None
        if not 0.5 <= number <= 6 or (number * 2) % 1:
            raise ValueError("El grado debe ir de 0,5 a 6 en medios grados.")
        return max(1.0, number), "Grade " + ("{:g}".format(number))
    raise ValueError("Escala desconocida: grade o pepper.")
