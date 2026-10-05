from __future__ import annotations

from backend.domain.models import Finding, Score
from backend.domain.timing import attack_count, measure_length


def _measure_attack_density(measure) -> tuple[float, int, float]:
    """Estimate density from note attacks relative to the bar length.

    A bar containing four quarter notes is legitimately dense, while a bar with
    just two half notes is not. The key is to score how many note onsets occur
    within the measure length, not only the cumulative duration.
    """
    attacks = attack_count(measure)
    if not attacks:
        return 0.0, 0, 0.0

    measure_length_quarters = measure_length(measure)
    reference_window = max(2.0, measure_length_quarters / 2.0)
    attack_density = attacks / reference_window
    return attack_density, attacks, measure_length_quarters


def find_high_rhythm_density(score: Score) -> list[Finding]:
    """Detect high-density rhythm passages while grouping consecutive dense measures.

    The key change is that we score the number of note attacks relative to the
    measure length, rather than simply summing note durations. This makes a
    measure packed with eighths or sixteenths read as more difficult than a
    measure with just two long sustained notes, even if both last a full bar.
    """
    findings: list[Finding] = []
    density_threshold = 1.5

    for part in score.parts:
        dense_measure_numbers: list[int] = []

        for measure in part.measures:
            attack_density, note_count, measure_length_quarters = _measure_attack_density(measure)
            if attack_density > density_threshold:
                dense_measure_numbers.append(measure.number)

        if not dense_measure_numbers:
            continue

        clusters: list[tuple[int, int]] = []
        start = dense_measure_numbers[0]
        previous = dense_measure_numbers[0]

        for measure_number in dense_measure_numbers[1:]:
            if measure_number == previous + 1:
                previous = measure_number
                continue

            clusters.append((start, previous))
            start = measure_number
            previous = measure_number

        clusters.append((start, previous))

        for measure_start, measure_end in clusters:
            measure = next(
                candidate
                for candidate in part.measures
                if candidate.number == measure_start
            )
            attack_density, note_count, measure_length_quarters = _measure_attack_density(measure)
            measure_range = str(measure_start) if measure_start == measure_end else f"{measure_start}-{measure_end}"
            findings.append(
                Finding(
                    code="SL003",
                    severity="warning",
                    instrument=part.name,
                    measure_range=measure_range,
                    description="High rhythmic density",
                    evidence={
                        "measure_start": measure_start,
                        "measure_end": measure_end,
                        "attack_density": round(attack_density, 2),
                        "note_count": note_count,
                        "measure_length_quarters": round(measure_length_quarters, 2),
                        "threshold": density_threshold,
                    },
                )
            )

    return findings
