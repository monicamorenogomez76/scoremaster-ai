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
        summary = "«{}» tiene grado {} ({}) en la escala de ScoreLint, el nivel de: {}.".format(
            evidence["title"], evidence["grade"], evidence["grade_label"], evidence["grade_band"])
        if leading:
            summary += " Lo más exigente está en " + _joined(leading)
            summary += "; hay {} pasajes críticos señalados.".format(len(evidence["passages"])) if evidence["passages"] else "."
        return {"summary": summary, "factors": factors, "study_tip": STUDY_TIPS[factors[0]["dimension"]]}
