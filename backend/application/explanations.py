"""What every explanation shares (step 20): ask the provider, validate its answer against the
evidence, fall back to the demo saying why, and record who wrote it."""
import logging

from backend.application.ai import ProviderFailure

logger = logging.getLogger(__name__)


class InvalidExplanation(ValueError):
    """The answer does not follow the schema or cites what is not in the evidence."""


def run_explanation(evidence: dict, ask, validate, provider, demo, prompt_version: str) -> dict:
    """ask(provider, evidence) → raw answer; validate(answer, evidence) → model or InvalidExplanation."""
    used, fallback_reason = provider, None
    try:
        explanation = validate(ask(provider, evidence), evidence)
    except ProviderFailure as failure:
        fallback_reason = str(failure) if str(failure) in ("timeout", "rate_limit") else "error"
    except InvalidExplanation as invalid:
        fallback_reason = "invalid"
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
            "fallback_reason": fallback_reason, "explanation": explanation.model_dump()}
