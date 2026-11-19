"""The demo's commentary of the musical analysis (2026-11-19): rules that put the calculated facts into sentences,
topic by topic, in the language of the evidence. It is never presented as AI; its interpretation only points at what
the facts suggest to rehearse and is marked as opinion like the AI's."""

TEXTS = {
    "es": {
        "and": " y ", "none": "—",
        "summary": "«{title}» está en {key}, tiene {measures} compases y {count} secciones: {form}.",
        "summary_untitled": "La obra está en {key}, tiene {measures} compases y {count} secciones: {form}.",
        "form": "La forma es {form}, en {count} secciones.", "returns": " {label} (cc. {first}–{last}) vuelve al material de {like}.",
        "single": " Es una sola sección sin repeticiones de material.",
        "themes": "Hay {count} temas.", "exposed": " {theme} se expone en la sección {label}{part}{shape}.",
        "shape": " ({range} semitonos, {contour}, {motion})",
        "contours": {"arch": "en arco", "inverted_arch": "en arco invertido", "ascending": "ascendente",
                     "descending": "descendente", "level": "plano"}, "motions": {"conjunct": "por grados", "disjunct": "por saltos"},
        "by_part": ", en {part}", "statement": {"return": "vuelve en {labels}", "transposed": "vuelve en otro tono en {labels}",
                                               "varied": "vuelve variado en {labels}"},
        "heads": " La cabeza de {theme} reaparece en {labels}.", "no_themes": "No se distinguen temas claros.",
        "harmony": "La tonalidad principal es {key}.", "other_key": " La sección {label} está en {key} ({relation}).",
        "modulation": " Dentro de {label} modula a {key} en el c. {measure}.",
        "cadences": " Hay {list}.", "no_cadences": " No se detectan cadencias claras.",
        "secondary": " Aparecen dominantes secundarias: {list}.", "pedal": " Hay una pedal en {note} en la sección {label} (cc. {first}–{last}).",
        "harmonic_rhythm": " El ritmo armónico va de {low} a {high} acordes por compás.",
        "harmonic_rhythm_one": " El ritmo armónico es de {low} acordes por compás.",
        "cadence_names": {"authentic": ("una cadencia auténtica", "{} cadencias auténticas"),
                          "half": ("una semicadencia", "{} semicadencias"), "plagal": ("una cadencia plagal", "{} cadencias plagales"),
                          "deceptive": ("una cadencia rota", "{} cadencias rotas")},
        "relations": {"tonic": "tonalidad principal", "parallel": "homónimo", "relative": "relativo", "dominant": "dominante",
                      "subdominant": "subdominante", "supertonic": "supertónica", "mediant": "mediante",
                      "submediant": "superdominante", "subtonic": "subtónica", "distant": "tono lejano"},
        "texture": "Predomina {kind}.", "melody_in": " La melodía está en {parts}.",
        "solos": " Hay solos escritos en {list}.", "kinds": {"unison": "el unísono", "homorhythmic": "la homorritmia",
                                                             "melody_and_accompaniment": "la melodía acompañada",
                                                             "polyphonic": "la polifonía"},
        "high": " Llegan al agudo extremo {parts}.",
        "rhythm_none": "No hay síncopas, ostinatos ni imitaciones destacados.",
        "hemiola": " Hay hemiolias en {labels}.", "displaced": " Los acentos caen a contratiempo en {labels}.", "syncopated": "Hay síncopas en {labels}.",
        "ostinato": " {part} hace un ostinato en {places}.", "imitation": " {part} imita la melodía en {places}.",
        "at": "c. {measure}", "span": "cc. {first}–{last}",
        "climax": "El clímax llega en el c. {measure} (sección {label}), en {dynamic}, con {count} partes tocando.",
        "no_climax": "No hay dinámicas escritas que marquen un clímax.", "dynamics_used": " Las dinámicas van de {low} a {high}.",
        "section": "Cc. {first}–{last}, en {key}", "section_melody": "; melodía en {part}", "section_kind": "; {kind}",
        "section_phrases": "; frases {phrases}",
        "interpretation": "Conviene {advice}.", "advice_balance": "equilibrar la melodía frente al acompañamiento",
        "advice_climax": "dosificar la intensidad para llegar al clímax del c. {measure}",
        "advice_cadences": "respirar y cerrar juntos en las cadencias", "advice_rhythm": "asegurar las síncopas con metrónomo",
        "advice_high": "calentar y afinar el agudo de {parts}", "advice_default": "leer la obra a tempo lento y cuidar las transiciones",
    },
    "en": {
        "and": " and ", "none": "—",
        "summary": "«{title}» is in {key}, has {measures} measures and {count} sections: {form}.",
        "summary_untitled": "The work is in {key}, has {measures} measures and {count} sections: {form}.",
        "form": "The form is {form}, in {count} sections.", "returns": " {label} (mm. {first}–{last}) brings back the material of {like}.",
        "single": " It is a single section with no return of material.",
        "themes": "There are {count} themes.", "exposed": " {theme} is stated in section {label}{part}{shape}.",
        "shape": " ({range} semitones, {contour}, {motion})",
        "contours": {"arch": "arch-shaped", "inverted_arch": "inverted arch", "ascending": "ascending",
                     "descending": "descending", "level": "level"}, "motions": {"conjunct": "by steps", "disjunct": "by leaps"},
        "by_part": ", in {part}", "statement": {"return": "returns in {labels}", "transposed": "returns in another key in {labels}",
                                               "varied": "returns varied in {labels}"},
        "heads": " The head of {theme} comes back in {labels}.", "no_themes": "No clear themes stand out.",
        "harmony": "The main key is {key}.", "other_key": " Section {label} is in {key} ({relation}).",
        "modulation": " Within {label} it modulates to {key} at m. {measure}.",
        "cadences": " There are {list}.", "no_cadences": " No clear cadences are found.",
        "secondary": " Secondary dominants appear: {list}.", "pedal": " There is a pedal on {note} in section {label} (mm. {first}–{last}).",
        "harmonic_rhythm": " The harmonic rhythm goes from {low} to {high} chords per measure.",
        "harmonic_rhythm_one": " The harmonic rhythm is {low} chords per measure.",
        "cadence_names": {"authentic": ("one authentic cadence", "{} authentic cadences"),
                          "half": ("one half cadence", "{} half cadences"), "plagal": ("one plagal cadence", "{} plagal cadences"),
                          "deceptive": ("one deceptive cadence", "{} deceptive cadences")},
        "relations": {"tonic": "main key", "parallel": "parallel", "relative": "relative", "dominant": "dominant",
                      "subdominant": "subdominant", "supertonic": "supertonic", "mediant": "mediant",
                      "submediant": "submediant", "subtonic": "subtonic", "distant": "distant key"},
        "texture": "The texture is mostly {kind}.", "melody_in": " The melody is in {parts}.",
        "solos": " There are written solos in {list}.", "kinds": {"unison": "unison", "homorhythmic": "homorhythmic",
                                                                   "melody_and_accompaniment": "melody and accompaniment",
                                                                   "polyphonic": "polyphonic"},
        "high": " {parts} reach the extreme high register.",
        "rhythm_none": "There are no salient syncopations, ostinatos or imitations.",
        "hemiola": " There are hemiolas in {labels}.", "displaced": " The accents fall off the beat in {labels}.", "syncopated": "There are syncopations in {labels}.",
        "ostinato": " {part} plays an ostinato in {places}.", "imitation": " {part} imitates the melody at {places}.",
        "at": "m. {measure}", "span": "mm. {first}–{last}",
        "climax": "The climax comes at m. {measure} (section {label}), at {dynamic}, with {count} parts playing.",
        "no_climax": "No written dynamics mark a climax.", "dynamics_used": " The dynamics range from {low} to {high}.",
        "section": "Mm. {first}–{last}, in {key}", "section_melody": "; melody in {part}", "section_kind": "; {kind}",
        "section_phrases": "; phrases {phrases}",
        "interpretation": "It is worth {advice}.", "advice_balance": "balancing the melody against the accompaniment",
        "advice_climax": "pacing the intensity to reach the climax at m. {measure}",
        "advice_cadences": "breathing and closing together at the cadences", "advice_rhythm": "securing the syncopations with a metronome",
        "advice_high": "warming up and tuning the high register of {parts}",
        "advice_default": "reading the work at a slow tempo and minding the transitions",
    },
}
DYNAMICS = ("ppp", "pp", "p", "mp", "mf", "f", "ff", "fff")
SYNCOPATED = 0.15


def _joined(items, joiner):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + joiner + items[-1] if items else ""


def _topic(text, sections=(), cadences=(), themes=()):
    return {"text": text, "sections": list(dict.fromkeys(sections)), "cadences": list(dict.fromkeys(cadences))[:20],
            "themes": list(dict.fromkeys(themes))[:10]}


def analysis_commentary(evidence: dict) -> dict:
    say = TEXTS["en" if evidence.get("language") == "en" else "es"]
    sections = evidence["sections"]
    if not sections:
        empty = _topic(say["none"])
        return {"summary": say["none"], **{name: empty for name in
                                           ("form", "themes", "harmony", "texture", "rhythm", "dynamics", "interpretation")},
                "by_section": []}
    label = {section["id"]: section["label"] for section in sections}
    # A letter can name several sections (A A B A): its measures tell them apart.
    placed = lambda section: section["label"] + " (" + say["at"].format(measure=section["first"]) + ")"
    general = evidence["general"]
    summary = (say["summary"] if evidence["title"] else say["summary_untitled"]).format(
        title=evidence["title"], key=evidence["main_key"], measures=general["measures"], count=len(sections), form=evidence["form"])

    returns = [section for section in sections if section["like"]]
    form = say["form"].format(form=evidence["form"], count=len(sections)) + ("".join(
        say["returns"].format(label=section["label"], first=section["first"], last=section["last"], like=label[section["like"]])
        for section in returns[:6]) if returns else say["single"] if len(sections) == 1 else "")

    themes, cited_themes, theme_sections = evidence["themes"], [], []
    if themes:
        text = say["themes"].format(count=len(themes))
        for theme in themes[:6]:
            later = []
            for statement in ("return", "transposed", "varied"):
                places = [placed(section) for section in sections
                          if section["theme"] and section["theme"] == {"id": theme["id"], "statement": statement}]
                if places:
                    later.append(say["statement"][statement].format(labels=_joined(places, say["and"])))
            part = say["by_part"].format(part=theme["part"]) if theme["part"] else ""
            shape = say["shape"].format(range=theme["range"], contour=say["contours"][theme["contour"]],
                                        motion=say["motions"][theme["motion"]]) if "contour" in theme else ""
            text += say["exposed"].format(theme=theme["id"], label=label.get(theme["section"], "?"), part=part, shape=shape)
            text = text[:-1] + ("; " + "; ".join(later) + "." if later else ".")
            cited_themes.append(theme["id"])
            theme_sections.append(theme["section"])
            heard = [section for section in sections if any(head["theme"] == theme["id"] for head in section["theme_heads"])]
            if heard:
                text += say["heads"].format(theme=theme["id"], labels=_joined([placed(section) for section in heard[:6]], say["and"]))
                theme_sections += [section["id"] for section in heard]
    else:
        text = say["no_themes"]
    themes_topic = _topic(text[:900], theme_sections, themes=cited_themes)

    harmony = say["harmony"].format(key=evidence["main_key"])
    keyed = [section for section in sections if section["relation"] != "tonic"]
    for section in keyed[:6]:
        harmony += say["other_key"].format(label=section["label"], key=section["key"],
                                           relation=say["relations"].get(section["relation"], section["relation"]))
    for section in sections:
        for modulation in section["modulations"][:1]:
            harmony += say["modulation"].format(label=section["label"], key=modulation["key"], measure=modulation["measure"])
    counts = {}
    for cadence in evidence["cadences"]:
        counts[cadence["kind"]] = counts.get(cadence["kind"], 0) + 1
    names = [(one if count == 1 else many.format(count)) for kind, (one, many) in say["cadence_names"].items()
             if (count := counts.get(kind))]
    harmony += say["cadences"].format(list=_joined(names, say["and"])) if names else say["no_cadences"]
    rhythms = [section["harmonic_rhythm"] for section in sections if section.get("harmonic_rhythm")]
    if rhythms:
        low, high = (str(value).replace(".", ",") if say is TEXTS["es"] else str(value) for value in (min(rhythms), max(rhythms)))
        harmony += say["harmonic_rhythm" if low != high else "harmonic_rhythm_one"].format(low=low, high=high)
    secondary = ["V/" + item["of"] + " (" + say["at"].format(measure=item["measure"]) + ")"
                 for section in sections for item in section.get("secondary_dominants", [])]
    harmony += say["secondary"].format(list=_joined(secondary[:5], say["and"])) if secondary else ""
    for section in sections:
        for pedal in section.get("pedals", [])[:1]:
            harmony += say["pedal"].format(note=pedal["note"], label=section["label"], first=pedal["first"], last=pedal["last"])
    harmony_topic = _topic(harmony[:900], [section["id"] for section in keyed[:6]],
                           [cadence["id"] for cadence in evidence["cadences"]])

    kinds = [section["texture_kind"] for section in sections if section["texture_kind"]]
    main_kind = max(set(kinds), key=kinds.count) if kinds else None
    melodies = list(dict.fromkeys(section["melody"] for section in sections if section["melody"]))
    texture = say["texture"].format(kind=say["kinds"][main_kind]) if main_kind else ""
    texture += say["melody_in"].format(parts=_joined(melodies[:4], say["and"])) if melodies else ""
    by_part: dict = {}
    for section in sections:
        for solo in section["solos"]:
            by_part.setdefault(solo["part"], []).append(section["label"])
    solos = [part + " (" + ", ".join(dict.fromkeys(letters)) + ")" for part, letters in by_part.items()]
    texture += say["solos"].format(list=_joined(solos[:4], say["and"])) if solos else ""
    high = list(dict.fromkeys(part for section in sections for part in section["extreme_high_register"]))
    texture += say["high"].format(parts=_joined(high[:4], say["and"])) if high else ""
    texture_topic = _topic(texture.strip() or say["none"], [section["id"] for section in sections if section["solos"]])

    syncopated = [section for section in sections if section["syncopation"] >= SYNCOPATED]
    rhythm = say["syncopated"].format(labels=_joined([section["label"] for section in syncopated], say["and"])) if syncopated else ""
    for kind, where in (("ostinato", lambda item: say["span"].format(**item)), ("imitation", lambda item: say["at"].format(**item))):
        grouped: dict = {}
        for section in sections:
            for item in section[kind + "s"]:
                grouped.setdefault(item["part"], []).append(where(item))
        for part, places in list(grouped.items())[:4]:
            rhythm += say[kind].format(part=part, places=_joined(places[:5], say["and"]))
    for kind, field in (("hemiola", "hemiolas"), ("displaced", "displaced_accents")):
        marked = [placed(section) for section in sections if section.get(field)]
        rhythm += say[kind].format(labels=_joined(marked[:5], say["and"])) if marked else ""
    rhythm_sections = [section["id"] for section in sections if section in syncopated or section["ostinatos"] or section["imitations"]
                       or section.get("hemiolas") or section.get("displaced_accents")]
    rhythm_topic = _topic(rhythm.strip() or say["rhythm_none"], rhythm_sections)

    climax = evidence["climax"]
    used = [mark for mark in DYNAMICS if any(mark in section["dynamics"] for section in sections)]
    dynamics = say["climax"].format(measure=climax["measure"], label=label.get(climax["section"], "?"),
                                    dynamic=climax["dynamic"], count=climax["playing"]) if climax else say["no_climax"]
    dynamics += say["dynamics_used"].format(low=used[0], high=used[-1]) if len(used) > 1 else ""
    dynamics_topic = _topic(dynamics, [climax["section"]] if climax and climax["section"] else [])

    by_section = []
    for section in sections:
        text = say["section"].format(first=section["first"], last=section["last"], key=section["key"])
        text += say["section_melody"].format(part=section["melody"]) if section["melody"] else ""
        text += say["section_kind"].format(kind=say["kinds"][section["texture_kind"]]) if section["texture_kind"] else ""
        text += say["section_phrases"].format(phrases=section["phrases"]) if section["phrases"] else ""
        by_section.append({"section": section["id"], "text": (text + ".")[:400]})

    advice = []
    if main_kind == "melody_and_accompaniment":
        advice.append(say["advice_balance"])
    if climax:
        advice.append(say["advice_climax"].format(measure=climax["measure"]))
    if counts:
        advice.append(say["advice_cadences"])
    if syncopated:
        advice.append(say["advice_rhythm"])
    if high:
        advice.append(say["advice_high"].format(parts=_joined(high[:3], say["and"])))
    interpretation = say["interpretation"].format(advice=_joined(advice or [say["advice_default"]], say["and"]))

    return {"summary": summary[:500], "form": _topic(form[:900], [section["id"] for section in returns[:6]]),
            "themes": themes_topic, "harmony": harmony_topic, "texture": texture_topic, "rhythm": rhythm_topic,
            "dynamics": dynamics_topic, "by_section": by_section,
            "interpretation": _topic(interpretation, [climax["section"]] if climax and climax["section"] else [])}
