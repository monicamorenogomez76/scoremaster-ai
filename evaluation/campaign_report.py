"""Metrics of a closed evaluation campaign: ScoreLint against the musicians (step 19).

Reads the JSON the director exports from «Valoraciones» and compares, passage by passage, the
prediction stored when the campaign was created with the musicians' ratings. Nothing is tuned
here: the tool only measures, so the same export always produces the same report.

Author's protocol, documented in evaluation/README.md:
- the expert difficulty of a passage is the median of its ratings (grades 1-6, same rubric);
- a passage is critical when most of its raters say so; a tie is left undecided and counted apart;
- passages with fewer ratings than --min-ratings are left out and counted;
- disagreement between raters is reported, never hidden behind the median.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean, median
from typing import Iterable, Optional

from backend.application.evaluations import EXPERIENCE_LEVELS

REPORT_VERSION = "campaign-report-v1"
HEURISTIC = "Heurística (ScoreLint)"


def _ranks(values: list[float]) -> list[float]:
    """Average ranks, so tied values share the same rank."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for position in range(start, end + 1):
            ranks[order[position]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def spearman(left: list[float], right: list[float]) -> Optional[float]:
    """Spearman's rho (Pearson on average ranks); undefined with fewer than 3 pairs or no variation."""
    if len(left) < 3:
        return None
    a, b = _ranks(left), _ranks(right)
    mean_a, mean_b = mean(a), mean(b)
    spread_a = sum((x - mean_a) ** 2 for x in a)
    spread_b = sum((y - mean_b) ** 2 for y in b)
    if spread_a == 0 or spread_b == 0:
        return None
    return sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / math.sqrt(spread_a * spread_b)


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


def _f_beta(precision: Optional[float], recall: Optional[float], beta: float) -> Optional[float]:
    if precision is None or recall is None or precision + recall == 0:
        return None
    weight = beta * beta
    return (1 + weight) * precision * recall / (weight * precision + recall)


def llm_methods(export: dict) -> dict:
    """Method B (step 22): one method per provider, model and prompt version, so versions never mix.
    label → {passage id: review}; in the order they were first reviewed."""
    methods = {}
    for review in export.get("llm_reviews", []):
        label = "LLM ({} · {} · {})".format(review["provider"], review["model"], review["prompt_version"])
        methods.setdefault(label, {})[review["passage_id"]] = review
    return methods


def aggregate(export: dict, min_ratings: int = 1, levels: Optional[Iterable[str]] = None) -> dict:
    """One row per passage with its prediction and the musicians' aggregated judgement."""
    allowed = set(levels) if levels else None
    llm = llm_methods(export)
    by_passage = defaultdict(list)
    for rating in export.get("ratings", []):
        if allowed is None or rating.get("experience_level") in allowed:
            by_passage[rating["passage_id"]].append(rating)
    rows, skipped = [], 0
    for passage in export.get("passages", []):
        ratings = by_passage.get(passage["passage_id"], [])
        if len(ratings) < max(1, min_ratings):
            skipped += 1
            continue
        snapshot = passage.get("snapshot") or {}
        grades = [r["difficulty"] for r in ratings]
        yes = sum(1 for r in ratings if r["critical"])
        no = len(ratings) - yes
        rows.append({
            "passage_id": passage["passage_id"], "work_title": passage.get("work_title"),
            "parts": passage.get("parts", []), "measure_range": passage.get("measure_range"),
            "family": snapshot.get("family") or "sin familia",
            "predicted": {HEURISTIC: {"grade": snapshot.get("grade"), "critical": bool(snapshot.get("critical"))},
                          **{label: {"grade": (reviews.get(passage["passage_id"]) or {}).get("grade"),
                                     "critical": (reviews.get(passage["passage_id"]) or {}).get("critical")}
                             for label, reviews in llm.items()}},
            "ratings": len(ratings),
            "expert_grade": median(grades),
            "grade_spread": max(grades) - min(grades),
            "critical_votes": {"yes": yes, "no": no},
            "expert_critical": None if yes == no else yes > no,
            "expert_priority": mean(r["priority"] for r in ratings) if all(r.get("priority") for r in ratings) else None,
            "grades": grades,
        })
    return {"rows": rows, "skipped": skipped}


def difficulty_metrics(pairs: list[tuple[float, float]]) -> dict:
    """pairs: (predicted grade, expert grade)."""
    if not pairs:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "spearman": None, "exact": None, "within_one": None}
    errors = [p - e for p, e in pairs]
    return {
        "n": len(pairs),
        "mae": mean(abs(x) for x in errors),
        "rmse": math.sqrt(mean(x * x for x in errors)),
        # Positive: the method rates harder than the musicians.
        "bias": mean(errors),
        "spearman": spearman([p for p, _ in pairs], [e for _, e in pairs]),
        "exact": mean(1.0 if abs(x) < 0.5 else 0.0 for x in errors),
        "within_one": mean(1.0 if abs(x) <= 1 else 0.0 for x in errors),
    }


def critical_metrics(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs: (predicted critical, expert critical); undecided passages are left out beforehand."""
    tp = sum(1 for p, e in pairs if p and e)
    fp = sum(1 for p, e in pairs if p and not e)
    fn = sum(1 for p, e in pairs if not p and e)
    tn = sum(1 for p, e in pairs if not p and not e)
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    return {"n": len(pairs), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall,
            "f1": _f_beta(precision, recall, 1.0), "f05": _f_beta(precision, recall, 0.5)}


def _method_metrics(rows: list[dict], method: str) -> dict:
    graded = [(r["predicted"][method]["grade"], r["expert_grade"]) for r in rows
              if r["predicted"][method]["grade"] is not None]
    decided = [(r["predicted"][method]["critical"], r["expert_critical"]) for r in rows
               if r["expert_critical"] is not None and r["predicted"][method]["critical"] is not None]
    return {"difficulty": difficulty_metrics(graded), "critical": critical_metrics(decided),
            "undecided_critical": sum(1 for r in rows if r["expert_critical"] is None)}


def _breakdown(rows: list[dict], method: str, key) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return {str(name): _method_metrics(group, method) for name, group in sorted(groups.items(), key=lambda i: str(i[0]))}


def agreement(rows: list[dict]) -> dict:
    """How much the musicians agree among themselves, on passages rated by two or more."""
    shared = [r for r in rows if r["ratings"] >= 2]
    if not shared:
        return {"passages": 0, "mean_spread": None, "mean_pairwise_difference": None, "critical_unanimous": None}
    differences = [abs(a - b) for r in shared for a, b in combinations(r["grades"], 2)]
    unanimous = [r for r in shared if 0 in (r["critical_votes"]["yes"], r["critical_votes"]["no"])]
    return {"passages": len(shared), "mean_spread": mean(r["grade_spread"] for r in shared),
            "mean_pairwise_difference": mean(differences), "critical_unanimous": len(unanimous) / len(shared)}


def _versions(export: dict) -> dict:
    """Every version recorded in the predictions, so mixed versions are visible."""
    found = defaultdict(set)
    for passage in export.get("passages", []):
        for name, value in ((passage.get("snapshot") or {}).get("versions") or {}).items():
            found[name].add(str(value))
    return {name: sorted(values) for name, values in sorted(found.items())}


def build_report(export: dict, min_ratings: int = 1, levels: Optional[Iterable[str]] = None,
                 source_sha256: Optional[str] = None) -> dict:
    aggregated = aggregate(export, min_ratings, levels)
    rows = aggregated["rows"]
    methods = [HEURISTIC, *llm_methods(export)]
    return {
        "report_version": REPORT_VERSION,
        "campaign": export.get("campaign", {}),
        "source_sha256": source_sha256,
        "settings": {"min_ratings": min_ratings, "experience_levels": sorted(levels) if levels else "todos"},
        "prediction_versions": _versions(export),
        "passages": {"proposed": len(export.get("passages", [])), "evaluated": len(rows),
                     "left_out": aggregated["skipped"], "works": len({r["work_title"] for r in rows}),
                     "ratings": sum(r["ratings"] for r in rows),
                     "evaluators": len({r["evaluator"] for r in export.get("ratings", [])})},
        "agreement": agreement(rows),
        "methods": {method: {
            **_method_metrics(rows, method),
            "by_family": _breakdown(rows, method, lambda r: r["family"]),
            "by_expert_grade": _breakdown(rows, method, lambda r: round(r["expert_grade"])),
            "by_work": _breakdown(rows, method, lambda r: r["work_title"]),
        } for method in methods},
        "rows": rows,
    }


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f} %"


def _table(title: str, groups: dict) -> list[str]:
    lines = [f"### {title}", "", "| Grupo | Pasajes | MAE | Sesgo | Spearman | Precisión | Recall | F0.5 |",
             "|---|---|---|---|---|---|---|---|"]
    for name, metrics in groups.items():
        d, c = metrics["difficulty"], metrics["critical"]
        lines.append(f"| {name} | {d['n']} | {_fmt(d['mae'])} | {_fmt(d['bias'])} | {_fmt(d['spearman'])} | "
                     f"{_pct(c['precision'])} | {_pct(c['recall'])} | {_fmt(c['f05'])} |")
    return lines + [""]


def to_markdown(report: dict) -> str:
    p, a = report["passages"], report["agreement"]
    lines = [f"# Evaluación: {report['campaign'].get('title', 'campaña')}", "",
             f"Informe `{report['report_version']}` generado desde la exportación"
             + (f" (sha256 `{report['source_sha256'][:12]}`)" if report.get("source_sha256") else "") + ".",
             f"Pasajes evaluados: {p['evaluated']} de {p['proposed']} en {p['works']} obras, con {p['ratings']} "
             f"valoraciones de {p['evaluators']} evaluadores. Quedan fuera {p['left_out']} pasajes con menos de "
             f"{report['settings']['min_ratings']} valoraciones. Experiencia: {report['settings']['experience_levels']}.",
             "Versiones de la predicción: " + (", ".join(f"{k} {'/'.join(v)}" for k, v in report["prediction_versions"].items()) or "—") + ".",
             "", "## Resultados", "",
             "| Método | Pasajes | MAE | RMSE | Spearman | Exacto | ±1 grado | Precisión | Recall | F1 | F0.5 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, metrics in report["methods"].items():
        d, c = metrics["difficulty"], metrics["critical"]
        lines.append(f"| {name} | {d['n']} | {_fmt(d['mae'])} | {_fmt(d['rmse'])} | {_fmt(d['spearman'])} | "
                     f"{_pct(d['exact'])} | {_pct(d['within_one'])} | {_pct(c['precision'])} | {_pct(c['recall'])} | "
                     f"{_fmt(c['f1'])} | {_fmt(c['f05'])} |")
    lines.append("")
    for name, metrics in report["methods"].items():
        c = metrics["critical"]
        lines += [f"Criticidad de {name}: {c['tp']} aciertos, {c['fp']} falsos positivos, {c['fn']} críticos no "
                  f"detectados y {c['tn']} no críticos correctos; {metrics['undecided_critical']} pasajes empatados "
                  "quedan fuera. Sesgo positivo: el método puntúa más difícil que los músicos.", ""]
    lines += ["## Acuerdo entre evaluadores", ""]
    if a["passages"]:
        lines.append(f"En {a['passages']} pasajes con dos o más valoraciones: diferencia media entre dos evaluadores "
                     f"{_fmt(a['mean_pairwise_difference'])} grados, rango medio {_fmt(a['mean_spread'])} y "
                     f"criticidad unánime en el {_pct(a['critical_unanimous'])}.")
    else:
        lines.append("Ningún pasaje tiene dos valoraciones: no se puede medir el acuerdo.")
    lines.append("")
    for name, metrics in report["methods"].items():
        lines += _table(f"{name} por familia", metrics["by_family"])
        lines += _table(f"{name} por grado de los músicos", metrics["by_expert_grade"])
        lines += _table(f"{name} por obra", metrics["by_work"])
    lines.append("Métricas sin denominador o con menos de tres pasajes se muestran como «—». Ninguna cifra se edita a mano.")
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Métricas de una campaña de valoración exportada.")
    parser.add_argument("export", type=Path, help="JSON exportado desde «Valoraciones»")
    parser.add_argument("--min-ratings", type=int, default=1, help="valoraciones mínimas por pasaje (por defecto 1)")
    parser.add_argument("--level", action="append", dest="levels",
                        choices=list(EXPERIENCE_LEVELS),
                        help="solo evaluadores con esta experiencia; se puede repetir")
    parser.add_argument("--json", type=Path, help="guardar también el informe completo en JSON")
    parser.add_argument("--markdown", type=Path, help="guardar la tabla en Markdown en lugar de imprimirla")
    args = parser.parse_args(argv)
    raw = args.export.read_bytes()
    report = build_report(json.loads(raw), args.min_ratings, args.levels, hashlib.sha256(raw).hexdigest())
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text = to_markdown(report)
    if args.markdown:
        args.markdown.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
