"""The rules that answer a question about the work (M6, 2026-11-20) from the results of the functions it read: the
suggested questions always, and any question when there is no AI or its answer was rejected. Never presented as AI."""

TEXTS = {
    "es": {
        "grade": "«{title}» tiene grado {grade} ({label}) en la escala de 1 a 6.",
        "reasons": " Lo fijan estos criterios de las guías de las editoriales: {}.",
        "passages": "Los pasajes más exigentes son {}.",
        "passage": "{label} en los compases {measures} ({why})",
        "passage_one": "{label} en el compás {measures} ({why})",
        "no_passages": "ScoreLint no ha señalado pasajes críticos en esta obra.",
        "part": "{label}: grado {grade}", "demands": "; lo que más pesa, {}",
        "part_passages": " Conviene preparar {}.", "part_no_passages": " Sin pasajes críticos señalados.",
        "no_part": "Esta obra no tiene ese instrumento.",
        "no_band": "Todavía no has indicado tu plantilla, así que no puedo comparar la banda con la obra.",
        "band_ok": "Tu banda cubre todas las partes de la obra.",
        "band_short": "Tu banda cubre el {percent} % de la obra. Faltan: {missing}.",
        "missing": "{label} (tienes {available} de {required})",
        "unconfirmed": " Hay {count} partes sin instrumento confirmado: confírmalas en la pestaña Dificultad.",
        "form": "Tiene forma {form}, en {key}. Secciones: {sections}.",
        "section": "{label} (compases {first}–{last}, {key})",
        "cadences": " Hay {count} cadencias señaladas.",
        "rehearsals": "Próximos ensayos con esta obra: {}.",
        "rehearsal": "el {date}{time}{minutes}",
        "at": " a las {}", "minutes": ", {} min con ella",
        "no_rehearsals": "No está en ningún ensayo próximo.",
        "past": " Ya se ha trabajado en {} ensayos anteriores.",
        "concerts": " Está en el programa de {}.",
        "concert": "«{title}» del {date} ({days})",
        "today": "es hoy", "days": "faltan {} días", "tomorrow": "es mañana",
        "no_concerts": " No está en el programa de ningún concierto próximo.",
        "unknown": "Sin IA solo puedo responder a las preguntas sugeridas o a preguntas sobre el grado, los pasajes, la "
                   "banda, la forma o los ensayos de la obra. Prueba con una de las sugeridas.",
        "nothing": "Los datos de la obra no responden a esta pregunta.",
        "and": " y ",
    },
    "en": {
        "grade": "«{title}» is grade {grade} ({label}) on the 1 to 6 scale.",
        "reasons": " These criteria of the publishers' guides set it: {}.",
        "passages": "The most demanding passages are {}.",
        "passage": "{label} in measures {measures} ({why})",
        "passage_one": "{label} in measure {measures} ({why})",
        "no_passages": "ScoreLint has not marked any critical passage in this work.",
        "part": "{label}: grade {grade}", "demands": "; what weighs most, {}",
        "part_passages": " Worth preparing: {}.", "part_no_passages": " No critical passages marked.",
        "no_part": "This work does not have that instrument.",
        "no_band": "You have not entered your band's lineup yet, so the band cannot be compared with the work.",
        "band_ok": "Your band covers every part of the work.",
        "band_short": "Your band covers {percent} % of the work. Missing: {missing}.",
        "missing": "{label} (you have {available} of {required})",
        "unconfirmed": " {count} parts have no confirmed instrument: confirm them in the Difficulty tab.",
        "form": "Its form is {form}, in {key}. Sections: {sections}.",
        "section": "{label} (measures {first}–{last}, {key})",
        "cadences": " {count} cadences are marked.",
        "rehearsals": "Coming rehearsals with this work: {}.",
        "rehearsal": "{date}{time}{minutes}",
        "at": " at {}", "minutes": ", {} min on it",
        "no_rehearsals": "It is in no coming rehearsal.",
        "past": " It has been worked on in {} earlier rehearsals.",
        "concerts": " It is in the programme of {}.",
        "concert": "«{title}» on {date} ({days})",
        "today": "today", "days": "in {} days", "tomorrow": "tomorrow",
        "no_concerts": " It is in no coming concert programme.",
        "unknown": "Without the AI I can only answer the suggested questions, or questions about the grade, the passages, "
                   "the band, the form or the rehearsals of the work. Try one of the suggested ones.",
        "nothing": "The data of the work do not answer this question.",
        "and": " and ",
    },
}


def _joined(items: list, glue: str) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + glue + items[-1]


def _date(text: str) -> str:
    year, month, day = text.split("-")
    return "{}/{}/{}".format(day, month, year)


def _difficulty(found: dict, topic, say) -> tuple[list, list]:
    texts, cites = [], []
    if topic in (None, "grade"):
        text = say["grade"].format(title=found.get("title"), grade=found.get("grade"), label=found.get("grade_label"))
        reasons = found.get("grade_reasons") or []
        texts.append(text + (say["reasons"].format("; ".join(reasons[:3])) if reasons else ""))
    if topic in (None, "passages"):
        passages = (found.get("passages") or [])[:3]
        if passages:
            texts.append(say["passages"].format(_joined([_passage(item, say) for item in passages], say["and"])))
            cites += [item["id"] for item in passages]
        else:
            texts.append(say["no_passages"])
    return texts, cites


def _passage(item: dict, say) -> str:
    return say["passage" if "-" in str(item["measures"]) else "passage_one"].format(
        label=item["label"], measures=item["measures"], why=", ".join(finding["label"].lower() for finding in item["findings"]) or "—")


def _instrument(found: dict, say) -> tuple[str, list]:
    if not found.get("parts"):
        return say["no_part"], []
    text = ". ".join(say["part"].format(label=part["label"], grade=part["grade"])
                     + (say["demands"].format(part["demands"][0]["aspect"]) if part["demands"] else "") for part in found["parts"]) + "."
    passages = found.get("passages") or []
    text += say["part_passages"].format(_joined([_passage(item, say) for item in passages[:4]], say["and"])) if passages \
        else say["part_no_passages"]
    return text, [item["id"] for item in passages[:4]]


def _band(found: dict, say) -> str:
    if found.get("compatibility_percent") is None:
        return say["no_band"]
    missing = found.get("missing") or []
    text = say["band_short"].format(percent=found["compatibility_percent"], missing=_joined(
        [say["missing"].format(**item) for item in missing], say["and"])) if missing else say["band_ok"]
    return text + (say["unconfirmed"].format(count=found["unconfirmed"]) if found.get("unconfirmed") else "")


def _analysis(found: dict, say) -> tuple[str, list]:
    sections = found.get("sections") or []
    text = say["form"].format(form=found.get("form") or "—", key=found.get("main_key") or "—", sections=_joined(
        [say["section"].format(**{**item, "key": item.get("key") or "—"}) for item in sections], say["and"]) or "—")
    if found.get("cadences"):
        text += say["cadences"].format(count=len(found["cadences"]))
    return text, [item["id"] for item in sections]


def _schedule(found: dict, say) -> tuple[str, list]:
    rehearsals, concerts = found.get("rehearsals") or [], found.get("concerts") or []
    text = say["rehearsals"].format(_joined([say["rehearsal"].format(
        date=_date(item["date"]), time=say["at"].format(item["time"]) if item.get("time") else "",
        minutes=say["minutes"].format(item["minutes"]) if item.get("minutes") else "") for item in rehearsals],
        say["and"])) if rehearsals else say["no_rehearsals"]
    if found.get("past_rehearsals"):
        text += say["past"].format(found["past_rehearsals"])
    days = lambda left: say["today"] if left == 0 else say["tomorrow"] if left == 1 else say["days"].format(left)
    text += say["concerts"].format(_joined([say["concert"].format(title=item["title"], date=_date(item["date"]),
                                                                  days=days(item["days_left"])) for item in concerts],
                                           say["and"])) if concerts else say["no_concerts"]
    return text, [item["id"] for item in rehearsals] + [item["id"] for item in concerts]


MAX_ANSWER = 1200   # WorkAnswer.answer (2026-11-26): a long demo answer made the question fail with a 500


def _fit(texts: list, limit: int = MAX_ANSWER) -> str:
    """The texts that fit whole; if not even the first does, it is cut at its last full sentence (or word)."""
    kept = []
    for text in texts:
        if len(" ".join(kept + [text])) <= limit:
            kept.append(text)
        elif not kept:
            cut = text[:limit - 1]
            end = cut.rfind(". ")
            kept.append(cut[:end + 1] if end > limit // 2 else cut[:cut.rfind(" ")] + "…")
    return " ".join(kept)


def work_answer(evidence: dict) -> dict:
    say = TEXTS["en" if evidence.get("language") == "en" else "es"]
    results, topic = evidence["results"], evidence.get("topic")
    if not results:
        return {"answer": say["unknown"] if evidence["question"] or topic is None else say["nothing"], "answered": False,
                "cites": []}
    texts, cites = [], []
    if "difficulty" in results:
        found, cited = _difficulty(results["difficulty"], topic, say)
        texts += found
        cites += cited
    if "band" in results:
        texts.append(_band(results["band"], say))
    for name, write in (("instrument", _instrument), ("analysis", _analysis), ("schedule", _schedule)):
        if name in results:
            text, cited = write(results[name], say)
            texts.append(text)
            cites += cited
    return {"answer": _fit(texts), "answered": True, "cites": cites[:12]}


# Asking the repertoire (M6, 2026-11-20): the rules write from the results of the calls they made, or of the AI's.
REPERTOIRE = {
    "es": {
        "intro": {"ready": "Tu banda cubre enteras {total} obras", "easiest": "Las obras más fáciles de tu repertorio",
                  "hardest": "Las obras más difíciles de tu repertorio", "preparing": "Estáis preparando {total} obras",
                  None: "Hay {total} obras que encajan"},
        "work": "«{title}» ({details})", "grade": "grado {}", "minutes": "{} min", "more": " y {} más",
        "short": "menos de 1 min",
        "none": "Ninguna obra de tu repertorio encaja con eso.",
        "detail": "«{title}» tiene grado {grade}.", "reasons": " Lo fijan: {}.",
        "passage": " Su pasaje más exigente: {label} en {where} {measures}.", "measures": ("el compás", "los compases"),
        "lacks": " A tu banda le falta: {}.", "covers": " Tu banda la cubre entera.",
        "no_match": "No encuentro esa obra en tu repertorio.",
        "concerts": "Próximos conciertos: {}.", "concert": "«{title}» el {date} ({days}){programme}",
        "programme": ", con {}", "today": "es hoy", "tomorrow": "es mañana", "days": "faltan {} días",
        "no_concerts": "No hay conciertos próximos.",
        "rehearsals": " Próximos ensayos: {}.", "rehearsal": "el {date}{works}", "rehearsal_works": " ({})",
        "band": "Tu banda tiene {musicians} músicos: {list}.", "player": "{count} de {label}",
        "no_band": "Todavía no has indicado la plantilla de tu banda.",
        "unknown": "Sin IA solo puedo responder a las preguntas sugeridas o a preguntas sobre el grado, la duración, la "
                   "banda, la preparación o los conciertos de tus obras. Prueba con una de las sugeridas.",
        "and": " y ",
    },
    "en": {
        "intro": {"ready": "Your band covers {total} works entirely", "easiest": "The easiest works of your repertoire",
                  "hardest": "The hardest works of your repertoire", "preparing": "You are preparing {total} works",
                  None: "{total} works match"},
        "work": "«{title}» ({details})", "grade": "grade {}", "minutes": "{} min", "more": " and {} more",
        "short": "under 1 min",
        "none": "No work of your repertoire matches that.",
        "detail": "«{title}» is grade {grade}.", "reasons": " It is set by: {}.",
        "passage": " Its most demanding passage: {label} in {where} {measures}.", "measures": ("measure", "measures"),
        "lacks": " Your band lacks: {}.", "covers": " Your band covers it entirely.",
        "no_match": "I cannot find that work in your repertoire.",
        "concerts": "Coming concerts: {}.", "concert": "«{title}» on {date} ({days}){programme}",
        "programme": ", with {}", "today": "today", "tomorrow": "tomorrow", "days": "in {} days",
        "no_concerts": "There are no coming concerts.",
        "rehearsals": " Coming rehearsals: {}.", "rehearsal": "{date}{works}", "rehearsal_works": " ({})",
        "band": "Your band has {musicians} musicians: {list}.", "player": "{count} {label}",
        "no_band": "You have not entered your band's lineup yet.",
        "unknown": "Without the AI I can only answer the suggested questions, or questions about the grade, length, band, "
                   "preparation or concerts of your works. Try one of the suggested ones.",
        "and": " and ",
    },
}
SHOWN = 6


def _decimal(value, language: str) -> str:
    text = ("{:.1f}".format(value)).rstrip("0").rstrip(".")
    return text if language == "en" else text.replace(".", ",")


def _found(result: dict, topic, say, language) -> tuple[str, list]:
    works = result["works"][:SHOWN]
    if not works:
        return say["none"], []
    described = []
    for work in works:
        details = [say["grade"].format(work["grade"])] if work.get("grade") is not None else []
        if work.get("minutes") is not None:
            details.append(say["short"] if work["minutes"] < 1 else say["minutes"].format(_decimal(work["minutes"], language)))
        described.append(say["work"].format(title=work["title"], details=", ".join(details) or "—"))
    intro = say["intro"].get(topic if topic in say["intro"] else None).format(total=result["total"])
    more = say["more"].format(result["total"] - len(works)) if result["total"] > len(works) else ""
    return intro + ": " + _joined(described, say["and"]) + more + ".", [work["id"] for work in works]


def _work_details(result: dict, say) -> tuple[str, list]:
    if not result["works"]:
        return say["no_match"], []
    texts = []
    for work in result["works"]:
        text = say["detail"].format(title=work["title"], grade=work.get("grade"))
        if work.get("grade_reasons"):
            text += say["reasons"].format("; ".join(work["grade_reasons"][:2]))
        if work.get("passages"):
            passage = work["passages"][0]
            where = say["measures"][1 if "-" in str(passage["measures"]) else 0]
            text += say["passage"].format(label=passage["label"], where=where, measures=passage["measures"])
        band = work.get("band") or {}
        if band.get("missing"):
            text += say["lacks"].format(_joined([item["label"] for item in band["missing"]], say["and"]))
        elif band.get("compatibility_percent") == 100:
            text += say["covers"]
        texts.append(text)
    return " ".join(texts), [work["id"] for work in result["works"]]


def _agenda(result: dict, say) -> tuple[str, list]:
    cites, concerts = [], result.get("concerts") or []
    days = lambda left: say["today"] if left == 0 else say["tomorrow"] if left == 1 else say["days"].format(left)
    titles = lambda works: _joined(["«{}»".format(work["title"]) for work in works], say["and"])
    if concerts:
        text = say["concerts"].format(_joined([say["concert"].format(
            title=item["title"], date=_date(item["date"]), days=days(item["days_left"]),
            programme=say["programme"].format(titles(item["works"])) if item["works"] else "") for item in concerts],
            say["and"]))
        cites += [item["id"] for item in concerts] + [work["id"] for item in concerts for work in item["works"]]
    else:
        text = say["no_concerts"]
    rehearsals = (result.get("rehearsals") or [])[:3]
    if rehearsals:
        text += say["rehearsals"].format(_joined([say["rehearsal"].format(
            date=_date(item["date"]), works=say["rehearsal_works"].format(titles(item["works"])) if item["works"] else "")
            for item in rehearsals], say["and"]))
        cites += [item["id"] for item in rehearsals]
    return text, list(dict.fromkeys(cites))


def _lineup(result: dict, say) -> str:
    instruments = result.get("instruments") or []
    if not instruments:
        return say["no_band"]
    return say["band"].format(musicians=result.get("musicians"), list=_joined(
        [say["player"].format(**item) for item in instruments[:12]], say["and"]))


def repertoire_answer(evidence: dict) -> dict:
    language = "en" if evidence.get("language") == "en" else "es"
    say = REPERTOIRE[language]
    if not evidence["results"]:
        return {"answer": say["unknown"], "answered": False, "cites": []}
    texts, cites = [], []
    for item in evidence["results"]:
        name, result = item["function"], item["result"]
        if name == "find_works":
            text, cited = _found(result, evidence.get("topic"), say, language)
        elif name == "work_details":
            text, cited = _work_details(result, say)
        elif name == "schedule":
            text, cited = _agenda(result, say)
        else:
            text, cited = _lineup(result, say), []
        texts.append(text)
        cites += cited
    return {"answer": _fit(texts), "answered": True, "cites": list(dict.fromkeys(cites))[:12]}
