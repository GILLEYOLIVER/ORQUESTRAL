from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.modules.agents.models import AgentDataPolicy


class AgentDataPolicyViolation(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InjectionAssessment:
    detected: bool
    indicators: tuple[str, ...]
    fingerprint: str


INJECTION_PATTERNS = {
    "override_instructions": re.compile(
        r"\b(ignore|disregard|bypass|override|esque[cç]a|ignore)\b.{0,40}\b(instructions?|regras?|pol[ií]ticas?|instru[cç][oõ]es)\b",
        re.IGNORECASE,
    ),
    "reveal_system_prompt": re.compile(
        r"\b(reveal|show|print|expose|mostre|revele|imprima)\b.{0,40}\b(system prompt|prompt do sistema|instru[cç][oõ]es internas)\b",
        re.IGNORECASE,
    ),
    "secret_exfiltration": re.compile(
        r"\b(exfiltrate|extract|dump|vaze|extraia|liste)\b.{0,40}\b(secrets?|tokens?|credentials?|senhas?|chaves?)\b",
        re.IGNORECASE,
    ),
    "role_impersonation": re.compile(
        r"\b(you are now|act as system|finja ser o sistema|agora voc[eê] [eé])\b",
        re.IGNORECASE,
    ),
}

SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[EMAIL_MASCARADO]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF_MASCARADO]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ_MASCARADO]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer [TOKEN_MASCARADO]"),
    (
        re.compile(r"(?i)\b(password|senha|secret|token|api[_ -]?key)\s*[:=]\s*[^\s,;]{4,}"),
        r"\1=[SEGREDO_MASCARADO]",
    ),
)

CLASSIFICATION_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


def scan_prompt_injection(text: str) -> InjectionAssessment:
    indicators = tuple(key for key, pattern in INJECTION_PATTERNS.items() if pattern.search(text))
    return InjectionAssessment(
        detected=bool(indicators),
        indicators=indicators,
        fingerprint=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def redact_sensitive_text(text: str) -> tuple[str, bool]:
    redacted = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted, redacted != text


def assert_provider_data_policy(
    policy: AgentDataPolicy,
    *,
    provider: str,
    includes_knowledge: bool,
    includes_memory: bool = False,
    classification: str = "confidential",
) -> None:
    if provider not in policy.allowed_provider_keys:
        raise AgentDataPolicyViolation("O provedor não está autorizado para este agente.")
    if provider == "local":
        return
    if not policy.external_processing_enabled:
        raise AgentDataPolicyViolation("O processamento externo está desativado para este agente.")
    if not policy.allow_message_egress:
        raise AgentDataPolicyViolation("O envio de mensagens ao provedor externo está desativado.")
    if includes_knowledge and not policy.allow_knowledge_egress:
        raise AgentDataPolicyViolation(
            "O envio de conhecimento ao provedor externo está desativado."
        )
    if includes_memory and not policy.allow_memory_egress:
        raise AgentDataPolicyViolation("O envio de memória ao provedor externo está desativado.")
    if CLASSIFICATION_RANK[classification] > CLASSIFICATION_RANK[policy.max_data_classification]:
        raise AgentDataPolicyViolation("A classificação dos dados excede a política do agente.")


def protect_provider_text(policy: AgentDataPolicy, *, provider: str, text: str) -> tuple[str, bool]:
    if provider == "local" or not policy.redact_sensitive_data:
        return text, False
    return redact_sensitive_text(text)
