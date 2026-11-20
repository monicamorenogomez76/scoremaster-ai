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
            texts.append(say["passages"].format(_joined([say["passage" if "-" in str(item["measures"]) else "passage_one"].format(
                label=item["label"], measures=item["measures"],
                why=", ".join(finding["label"].lower() for finding in item["findings"]) or "—") for item in passages],
                say["and"])))
            cites += [item["id"] for item in passages]
        else:
            texts.append(say["no_passages"])
    return texts, cites


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
    for name, write in (("analysis", _analysis), ("schedule", _schedule)):
        if name in results:
            text, cited = write(results[name], say)
            texts.append(text)
            cites += cited
    return {"answer": " ".join(texts), "answered": True, "cites": cites[:12]}
