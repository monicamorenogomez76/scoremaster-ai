"""Deterministic demo of the AI layer (step 20): rules that write the explanation from the same
evidence a real provider receives. It works without an API key and is always identified as a demo,
never as AI (decision of the original brief). It writes in the language of the evidence: Spanish, or English when the
evidence says so (2026-10-30)."""
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
WIND = {"Viento madera", "Viento metal", "woodwinds", "brass", "Woodwinds", "Brass"}
STRONG = 5.0   # half the technical index: below it a dimension does not explain the grade

PHASE_ADVICE = {
    "Lectura y pasajes": "En esta fase prima leer y localizar las dificultades: tempo cómodo, sin buscar todavía el detalle.",
    "Pasajes e integración": "Trabaja los pasajes a tempo creciente y guarda el final para juntarlos con toda la banda.",
    "Integración": "Prioriza el equilibrio y las transiciones entre secciones: los pasajes ya deberían estar resueltos.",
    "Ensayo general": "Toca sin parar, como en el concierto, y anota lo que falle para trabajarlo aparte.",
    None: "Respeta el tiempo de cada bloque y anota en la revisión lo que quede pendiente.",
}

# Every text of the demo, by the language of the evidence.
TEXTS = {
    "es": {
        "and": " y ", "dimension_text": DIMENSION_TEXT, "study_tips": STUDY_TIPS, "names": NAMES, "phase_advice": PHASE_ADVICE,
        "air": " y una buena gestión del aire", "mostly": ", sobre todo en ",
        "nothing_stands_out": "Ninguna dimensión destaca: la dificultad está repartida y es moderada.",
        "grade": "«{}» tiene grado {} ({}, {} de las editoriales) en la escala de ScoreLint: {}",
        "guides": " Lo fijan las guías de las editoriales: {}.", "hardest": " Lo más exigente está en {}.",
        "passages": " Hay {} pasajes críticos señalados.",
        "rehearsal": "Ensayo de {} minutos", "for_concert": " para «{}», {} {} antes del concierto", "day": ("día", "días"),
        "shares": " Reparte el tiempo entre {}", "warmup_minutes": ", más {} min de calentamiento.",
        "kinds": {"warmup": "Calentamiento", "common": "Línea o ritmo común", "sectional": "Seccional", "tutti": "Tutti",
                  "runthrough": "Pasada completa"},
        "warmup": "El calentamiento con toda la banda prepara el sonido, la afinación y el pulso antes de lo difícil.",
        "common": "Primero se trabajan juntas las partes que tocan la misma línea o el mismo ritmo, para corregirlo una sola vez.",
        "sectional": "Las seccionales de {} trabajan por separado lo más difícil de cada sección.",
        "critical": "Estos bloques recogen pasajes críticos del análisis: {}.",
        "pending": "Incluye lo que quedó pendiente en la última revisión, {}: por eso gana tiempo en este ensayo.",
        "runthrough": "La pasada completa toca cada obra seguida y en orden, como en el concierto.",
        "tutti": "Los tutti juntan lo trabajado por secciones y comprueban el equilibrio de la banda.",
        "order": "Los bloques siguen el orden en que la directora los ha planificado.",
    },
    "en": {
        "and": " and ",
        "dimension_text": {
            "density": "many notes in a row per beat: attacks very close together that demand rhythmic precision",
            "tempo": "a fast tempo that leaves little room to prepare each attack",
            "endurance": "long passages without rest that call for stamina",
            "range": "a wide range, with frequent changes of register",
            "register": "notes in the extreme register of the instrument, where tuning and controlling the sound are hard",
            "intervals": "wide leaps between notes, hard to tune and to slur",
        },
        "study_tips": {
            "density": "Practise the passages marked slowly and with a metronome, in groups of notes, and raise the tempo little by little.",
            "tempo": "Start at 70 % of the tempo, secure the entries and go up five beats per minute at a time.",
            "endurance": "Mark where to breathe before rehearsing and spread the effort over the long passages.",
            "range": "Work on the changes of register apart, with long notes at the extremes.",
            "register": "Warm up the extreme register with long notes and a tuner before tackling the passage.",
            "intervals": "Practise the leaps slowly and slurred, singing them before playing them.",
            "general": "Read through the whole work at a slow tempo before working on the details.",
        },
        "names": {"density": "Attack density", "tempo": "Tempo", "endurance": "Endurance", "range": "Range",
                  "register": "Extreme register", "intervals": "Leaps"},
        "phase_advice": {
            "Reading and passages": "In this phase reading and finding the difficulties come first: a comfortable tempo, "
                                    "without looking for detail yet.",
            "Passages and integration": "Work on the passages at a rising tempo and keep the end to put them together with the full band.",
            "Integration": "Put balance and the transitions between sections first: the passages should be resolved by now.",
            "Dress rehearsal": "Play without stopping, as in the concert, and note what goes wrong to work on it apart.",
            None: "Keep to the time of each block and note in the review what is left pending.",
        },
        "air": " and good breath management", "mostly": ", above all in ",
        "nothing_stands_out": "No dimension stands out: the difficulty is spread out and moderate.",
        "grade": "«{}» is grade {} ({}, {} of the publishers) on ScoreLint's scale: {}",
        "guides": " The publishers' guides set it: {}.", "hardest": " The most demanding part is in {}.",
        "passages": " There are {} critical passages marked.",
        "rehearsal": "Rehearsal of {} minutes", "for_concert": " for «{}», {} {} before the concert", "day": ("day", "days"),
        "shares": " It shares the time between {}", "warmup_minutes": ", plus {} min of warm-up.",
        "kinds": {"warmup": "Warm-up", "common": "Common line or rhythm", "sectional": "Sectional", "tutti": "Tutti",
                  "runthrough": "Full run-through"},
        "warmup": "The warm-up with the full band prepares sound, tuning and pulse before the hard part.",
        "common": "First the parts that play the same line or the same rhythm work together, to correct it only once.",
        "sectional": "The sectionals of {} work apart on the hardest part of each section.",
        "critical": "These blocks gather critical passages of the analysis: {}.",
        "pending": "It includes what was left pending in the last review, {}: that is why it gets more time in this rehearsal.",
        "runthrough": "The full run-through plays each work straight through and in order, as in the concert.",
        "tutti": "The tutti put together what was worked on by sections and check the balance of the band.",
        "order": "The blocks follow the order in which the conductor planned them.",
    },
}


def _joined(items, joiner=" y "):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + joiner + items[-1]


def _texts(evidence: dict) -> dict:
    return TEXTS["en" if evidence.get("language") == "en" else "es"]


class DemoExplanationProvider:
    info = ProviderInfo("demo", "demo")

    def explain_difficulty(self, evidence: dict) -> dict:
        say = _texts(evidence)
        joined = lambda items: _joined(items, say["and"])
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
            described = say["dimension_text"][dimension]
            text = "{}. {}".format(say["names"][dimension], described[0].upper() + described[1:])
            if dimension == "endurance" and any(item["family"] in WIND for item in who):
                text += say["air"]
            if who:
                text += say["mostly"] + joined([item["label"] for item in who])
            # The cited passages are shown as links next to the text, not repeated in it.
            factors.append({"dimension": dimension, "text": text + ".", "instruments": [item["name"] for item in who],
                            "passages": [passage["id"] for passage in passages]})
        if not factors:
            factors = [{"dimension": "general", "instruments": [], "passages": [], "text": say["nothing_stands_out"]}]
        leading = [item["label"] for item in instruments[:2]]
        description = evidence["grade_description"]
        summary = say["grade"].format(evidence["title"], evidence["grade"], evidence["grade_label"], evidence["grade_standard"],
                                      description[0].lower() + description[1:])
        reasons = evidence.get("grade_reasons") or []
        if reasons:
            # difficulty-v3: the grade is the guides', so the summary says which of their criteria sets it.
            summary += say["guides"].format("; ".join(reason[0].lower() + reason[1:] for reason in reasons[:2]))
        elif leading:
            summary += say["hardest"].format(joined(leading))
        if evidence["passages"]:
            summary += say["passages"].format(len(evidence["passages"]))
        return {"summary": summary, "factors": factors, "study_tip": say["study_tips"][factors[0]["dimension"]]}

    def explain_rehearsal(self, evidence: dict) -> dict:
        say = _texts(evidence)
        kinds = say["kinds"]
        joined = lambda items: _joined(items, say["and"])
        rehearsal, blocks = evidence["rehearsal"], evidence["blocks"]
        ids = lambda chosen: [block["id"] for block in chosen][:6]
        summary = say["rehearsal"].format(rehearsal["duration_minutes"])
        if rehearsal["phase"]:
            summary += " ({})".format(rehearsal["phase"])
        concert = rehearsal["concert"]
        if concert:
            days = concert["days_before"]
            summary += say["for_concert"].format(concert["title"], days, say["day"][0] if days == 1 else say["day"][1])
        summary += "."
        per_work = {}
        for block in blocks:
            if block["work"]:
                per_work[block["work"]] = per_work.get(block["work"], 0) + (block["minutes"] or 0)
        warmup = sum(block["minutes"] or 0 for block in blocks if block["kind"] == kinds["warmup"])
        shares = ["{} {} min".format(work, minutes) for work, minutes in sorted(per_work.items(), key=lambda item: -item[1])]
        if shares:
            summary += say["shares"].format(joined(shares))
            summary += (say["warmup_minutes"].format(warmup) if warmup else ".")
        reasons = []
        warm = [block for block in blocks if block["kind"] == kinds["warmup"]]
        if warm:
            reasons.append({"blocks": ids(warm), "text": say["warmup"]})
        common = [block for block in blocks if block["kind"] == kinds["common"]]
        if common:
            reasons.append({"blocks": ids(common), "text": say["common"]})
        sectional = [block for block in blocks if block["kind"].startswith(kinds["sectional"])]
        if sectional:
            names = sorted({block["kind"].split(" · ", 1)[1].lower() for block in sectional})
            reasons.append({"blocks": ids(sectional), "text": say["sectional"].format(joined(names))})
        critical = [block for block in blocks if block["critical_passages"] and block["kind"] != kinds["tutti"]]
        if critical:
            examples = ["{} {} ({})".format(item["instrument"], item["measures"], ", ".join(item["findings"]).lower())
                        for block in critical for item in block["critical_passages"]][:2]
            reasons.append({"blocks": ids(critical), "text": say["critical"].format(joined(examples))})
        pending = [item for item in evidence["pending_from_review"] if item["blocks"]]
        if pending:
            cited = sorted({code for item in pending for code in item["blocks"]}, key=lambda code: int(code[1:]))
            what = joined(["{} {} ({})".format(item["work"], item["measures"], item["status"].lower()) for item in pending[:2]])
            reasons.append({"blocks": cited[:6], "text": say["pending"].format(what)})
        through = [block for block in blocks if block["kind"] == kinds["runthrough"]]
        if through:
            reasons.append({"blocks": ids(through), "text": say["runthrough"]})
        tutti = [block for block in blocks if block["kind"] == kinds["tutti"]]
        if tutti:
            reasons.append({"blocks": ids(tutti), "text": say["tutti"]})
        if not reasons and blocks:
            reasons.append({"blocks": ids(blocks), "text": say["order"]})
        advice = say["phase_advice"]
        return {"summary": summary, "reasons": reasons[:6], "advice": advice.get(rehearsal["phase"], advice[None])}
