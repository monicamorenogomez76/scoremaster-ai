"""Deterministic demo of the AI layer (step 20): rules that write the explanation from the same
evidence a real provider receives. It works without an API key and is always identified as a demo,
never as AI (decision of the original brief)."""
from backend.application.ai import ProviderInfo

# Which findings of a critical passage show each dimension.
DIMENSION_FINDINGS = {"density": {"SL003"}, "register": {"SL002"}, "range": {"SL002"}, "intervals": {"SL004"},
                      "endurance": {"SL005"}, "tempo": {"SL003"}}
DIMENSION_TEXT = {
    "density": "muchas notas seguidas por pulso: ataques muy próximos que exigen precisión rítmica",
    "tempo": "un tempo rápido que deja poco margen para preparar cada ataque",
    "endurance": "pasajes largos sin descanso que piden resistencia",
    "range": "una tesitura amplia, con cambios frecuentes de registro",
    "register": "notas en el registro extremo del instrumento, donde cuesta afinar y controlar el sonido",
    "intervals": "saltos amplios entre notas, difíciles de afinar y de ligar",
}
STUDY_TIPS = {
    "density": "Estudiar los pasajes señalados lento y con metrónomo, por grupos de notas, y subir el tempo poco a poco.",
    "tempo": "Empezar al 70 % del tempo, asegurar las entradas y subir de cinco en cinco pulsaciones.",
    "endurance": "Marcar dónde respirar antes de ensayar y repartir el esfuerzo en los pasajes largos.",
    "range": "Trabajar los cambios de registro por separado, con notas largas en los extremos.",
    "register": "Calentar el registro extremo con notas largas y afinador antes de abordar el pasaje.",
    "intervals": "Practicar los saltos lentos y ligados, cantándolos antes de tocarlos.",
    "general": "Leer la obra completa a tempo lento antes de trabajar los detalles.",
}
NAMES = {"density": "Densidad de ataques", "tempo": "Tempo", "endurance": "Continuidad", "range": "Tesitura",
         "register": "Registro extremo", "intervals": "Saltos"}
WIND = {"Viento madera", "Viento metal", "woodwinds", "brass"}
STRONG = 5.0   # half the technical index: below it a dimension does not explain the grade


def _joined(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


class DemoExplanationProvider:
    info = ProviderInfo("demo", "demo")

    def explain_difficulty(self, evidence: dict) -> dict:
        instruments = evidence["instruments"][:4]
        strength = {dimension: max((item["dimensions"][dimension] for item in instruments), default=0)
                    for dimension in NAMES}
        ranked = [dimension for dimension in sorted(NAMES, key=lambda name: (-strength[name], name))
                  if strength[dimension] >= STRONG][:3]
        factors = []
        for dimension in ranked:
            who = [item for item in instruments if item["dimensions"][dimension] >= STRONG][:3]
            showing = [passage for passage in evidence["passages"]
                       if DIMENSION_FINDINGS[dimension] & {finding["code"] for finding in passage["findings"]}]
            # Its own passages first; otherwise those of other instruments where the analysis saw it.
            names = {item["name"] for item in who}
            passages = ([passage for passage in showing if passage["instrument"] in names] or showing)[:3]
            text = "{}. {}".format(NAMES[dimension], DIMENSION_TEXT[dimension][0].upper() + DIMENSION_TEXT[dimension][1:])
            if dimension == "endurance" and any(item["family"] in WIND for item in who):
                text += " y una buena gestión del aire"
            if who:
                text += ", sobre todo en " + _joined([item["label"] for item in who])
            # The cited passages are shown as links next to the text, not repeated in it.
            factors.append({"dimension": dimension, "text": text + ".", "instruments": [item["name"] for item in who],
                            "passages": [passage["id"] for passage in passages]})
        if not factors:
            factors = [{"dimension": "general", "instruments": [], "passages": [],
                        "text": "Ninguna dimensión destaca: la dificultad está repartida y es moderada."}]
        leading = [item["label"] for item in instruments[:2]]
        description = evidence["grade_description"]
        summary = "«{}» tiene grado {} ({}, {} de las editoriales) en la escala de ScoreLint: {}".format(
            evidence["title"], evidence["grade"], evidence["grade_label"], evidence["grade_standard"],
            description[0].lower() + description[1:])
        reasons = evidence.get("grade_reasons") or []
        if reasons:
            # difficulty-v3: the grade is the guides', so the summary says which of their criteria sets it.
            summary += " Lo fijan las guías de las editoriales: {}.".format(
                "; ".join(reason[0].lower() + reason[1:] for reason in reasons[:2]))
        elif leading:
            summary += " Lo más exigente está en " + _joined(leading) + "."
        if evidence["passages"]:
            summary += " Hay {} pasajes críticos señalados.".format(len(evidence["passages"]))
        return {"summary": summary, "factors": factors, "study_tip": STUDY_TIPS[factors[0]["dimension"]]}

    def explain_rehearsal(self, evidence: dict) -> dict:
        rehearsal, blocks = evidence["rehearsal"], evidence["blocks"]
        ids = lambda chosen: [block["id"] for block in chosen][:6]
        summary = "Ensayo de {} minutos".format(rehearsal["duration_minutes"])
        if rehearsal["phase"]:
            summary += " ({})".format(rehearsal["phase"])
        concert = rehearsal["concert"]
        if concert:
            days = concert["days_before"]
            summary += " para «{}», {} {} antes del concierto".format(concert["title"], days, "día" if days == 1 else "días")
        summary += "."
        per_work = {}
        for block in blocks:
            if block["work"]:
                per_work[block["work"]] = per_work.get(block["work"], 0) + (block["minutes"] or 0)
        warmup = sum(block["minutes"] or 0 for block in blocks if block["kind"] == "Calentamiento")
        shares = ["{} {} min".format(work, minutes) for work, minutes in sorted(per_work.items(), key=lambda item: -item[1])]
        if shares:
            summary += " Reparte el tiempo entre " + _joined(shares)
            summary += (", más {} min de calentamiento.".format(warmup) if warmup else ".")
        reasons = []
        warm = [block for block in blocks if block["kind"] == "Calentamiento"]
        if warm:
            reasons.append({"blocks": ids(warm), "text": "El calentamiento con toda la banda prepara el sonido, la afinación "
                                                         "y el pulso antes de lo difícil."})
        common = [block for block in blocks if block["kind"] == "Línea o ritmo común"]
        if common:
            reasons.append({"blocks": ids(common), "text": "Primero se trabajan juntas las partes que tocan la misma línea "
                                                           "o el mismo ritmo, para corregirlo una sola vez."})
        sectional = [block for block in blocks if block["kind"].startswith("Seccional")]
        if sectional:
            names = sorted({block["kind"].split(" · ", 1)[1].lower() for block in sectional})
            reasons.append({"blocks": ids(sectional), "text": "Las seccionales de {} trabajan por separado lo más difícil "
                                                              "de cada sección.".format(_joined(names))})
        critical = [block for block in blocks if block["critical_passages"] and block["kind"] != "Tutti"]
        if critical:
            examples = ["{} {} ({})".format(item["instrument"], item["measures"], ", ".join(item["findings"]).lower())
                        for block in critical for item in block["critical_passages"]][:2]
            reasons.append({"blocks": ids(critical), "text": "Estos bloques recogen pasajes críticos del análisis: "
                                                             + _joined(examples) + "."})
        pending = [item for item in evidence["pending_from_review"] if item["blocks"]]
        if pending:
            cited = sorted({code for item in pending for code in item["blocks"]}, key=lambda code: int(code[1:]))
            what = _joined(["{} {} ({})".format(item["work"], item["measures"], item["status"].lower()) for item in pending[:2]])
            reasons.append({"blocks": cited[:6], "text": "Incluye lo que quedó pendiente en la última revisión, " + what
                                                         + ": por eso gana tiempo en este ensayo."})
        through = [block for block in blocks if block["kind"] == "Pasada completa"]
        if through:
            reasons.append({"blocks": ids(through), "text": "La pasada completa toca cada obra seguida y en orden, como en el concierto."})
        tutti = [block for block in blocks if block["kind"] == "Tutti"]
        if tutti:
            reasons.append({"blocks": ids(tutti), "text": "Los tutti juntan lo trabajado por secciones y comprueban el "
                                                          "equilibrio de la banda."})
        if not reasons and blocks:
            reasons.append({"blocks": ids(blocks), "text": "Los bloques siguen el orden en que la directora los ha planificado."})
        return {"summary": summary, "reasons": reasons[:6], "advice": PHASE_ADVICE.get(rehearsal["phase"], PHASE_ADVICE[None])}


PHASE_ADVICE = {
    "Lectura y pasajes": "En esta fase prima leer y localizar las dificultades: tempo cómodo, sin buscar todavía el detalle.",
    "Pasajes e integración": "Trabaja los pasajes a tempo creciente y guarda el final para juntarlos con toda la banda.",
    "Integración": "Prioriza el equilibrio y las transiciones entre secciones: los pasajes ya deberían estar resueltos.",
    "Ensayo general": "Toca sin parar, como en el concierto, y anota lo que falle para trabajarlo aparte.",
    None: "Respeta el tiempo de cada bloque y anota en la revisión lo que quede pendiente.",
}
