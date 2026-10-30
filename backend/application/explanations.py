"""What every explanation shares (step 20): ask the provider, validate its answer against the
evidence, fall back to the demo saying why, and record who wrote it."""
import hashlib
import json
import logging
import re

from backend.application import ai_usage
from backend.application.ai import ProviderFailure
from backend.domain.text import MAX_TEXT, evidence_text  # noqa: F401 (used by the explanations)

logger = logging.getLogger(__name__)


class InvalidExplanation(ValueError):
    """The answer does not follow the schema or cites what is not in the evidence."""


def cache_key(evidence: dict, provider, prompt_version: str) -> str:
    """Step 23: the exact evidence (with its version), provider, model and prompt version."""
    payload = json.dumps({"evidence": evidence, "provider": provider.info.name, "model": provider.info.model,
                          "prompt": prompt_version}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cached(cache, key, evidence, validate):
    try:
        kept = cache.load(key)
        return validate(kept, evidence) if kept else None
    except InvalidExplanation:
        return None          # kept by an older schema: asked again
    except Exception:
        logger.warning("No se pudo leer la caché de explicaciones.", exc_info=True)
        return None


def run_explanation(evidence: dict, ask, validate, provider, demo, prompt_version: str, polish=None, cache=None,
                    purpose: str = "explanation") -> dict:
    """ask(provider, evidence) → raw answer; validate(answer, evidence) → model or InvalidExplanation;
    polish(model, evidence) → the same model with a text the director can read. With a cache, a valid
    answer of a real provider is kept and reused (step 23); errors, fallbacks and the demo never are."""
    used, fallback_reason, cached = provider, None, False
    llm = provider.info.kind == "llm"
    key = cache_key(evidence, provider, prompt_version) if cache is not None and llm else None
    explanation = _cached(cache, key, evidence, validate) if key else None
    usage = lambda event, outcome: ai_usage.record(ai_usage.UsageEvent(purpose, provider.info.model or provider.info.name,
                                                                       prompt_version, event, outcome))
    if explanation is not None:
        cached = True
        usage("cache_hit", "ok")
    else:
        try:
            explanation = validate(ask(provider, evidence), evidence)
            if key:
                try:
                    cache.save(key, explanation.model_dump())
                except Exception:
                    logger.warning("No se pudo guardar la explicación en la caché.", exc_info=True)
        except ProviderFailure as failure:
            fallback_reason = str(failure) if str(failure) in ("timeout", "rate_limit") else "error"
        except InvalidExplanation as invalid:
            fallback_reason = "invalid"
            if llm:
                usage("rejected", "invalid")
            logger.warning("Explicación de IA descartada: %s", str(invalid)[:300])
        except Exception:
            fallback_reason = "error"
            logger.warning("El proveedor de IA falló al explicar.", exc_info=True)
    if fallback_reason:
        used = demo
        explanation = validate(ask(demo, evidence), evidence)
    llm = used.info.kind == "llm"
    return {"mode": used.info.kind, "provider": used.info.name, "model": used.info.model,
            "prompt_version": prompt_version if llm else None, "evidence_version": evidence["version"],
            "fallback_reason": fallback_reason, "cached": cached,
            "explanation": (polish(explanation, evidence) if polish else explanation).model_dump()}


def replace_terms(text: str, terms: dict) -> str:
    """Whole-word replacement, longest terms first (so «Clarinet 1» wins over «Clarinet»)."""
    for term in sorted(terms, key=len, reverse=True):
        if term and term != terms[term]:
            text = re.sub(r"(?<![\w])" + re.escape(term) + r"(?![\w])", lambda _: terms[term], text)
    return text
