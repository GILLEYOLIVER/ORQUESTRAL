from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from uuid import UUID

from app.core.security import utc_now
from app.modules.agents.memory_models import AgentMemoryEntry, AgentMemoryPolicy

DEFAULT_SCOPES = ["conversation", "task", "operational"]
DEFAULT_CLASSIFICATIONS = ["public", "internal"]


def memory_content_fingerprint(
    *, secret: str, company_id: UUID, agent_id: UUID, content: str
) -> str:
    payload = f"{company_id}:{agent_id}:{content}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def memory_is_expired(memory: AgentMemoryEntry, *, now: datetime | None = None) -> bool:
    return memory.expires_at <= (now or utc_now())


def memory_policy_values(policy: AgentMemoryPolicy | None) -> dict[str, object]:
    if policy is None:
        return {
            "default_retention_days": 30,
            "max_retention_days": 365,
            "allowed_scopes": DEFAULT_SCOPES,
            "allowed_classifications": DEFAULT_CLASSIFICATIONS,
            "require_consent_for_user_scope": True,
        }
    return {
        "default_retention_days": policy.default_retention_days,
        "max_retention_days": policy.max_retention_days,
        "allowed_scopes": policy.allowed_scopes,
        "allowed_classifications": policy.allowed_classifications,
        "require_consent_for_user_scope": policy.require_consent_for_user_scope,
    }
