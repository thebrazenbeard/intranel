from __future__ import annotations

from dataclasses import dataclass, fields, replace
import re

from .canonical import content_digest
from .message import IntranelMessage
from .types import AdmissionDecision, EffectClass, Performative

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ReceiverChecks:
    origin_authenticated: bool | None
    actor_authenticated: bool | None
    authority_valid: bool | None
    exact_subject_valid: bool | None
    replay_fresh: bool | None
    capabilities_supported: bool | None

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if value is not None and type(value) is not bool:
                raise ValueError(f"{item.name} must be true, false, or null")

    def replace(self, **changes: bool | None) -> "ReceiverChecks":
        return replace(self, **changes)


@dataclass(frozen=True, slots=True)
class OperationRecord:
    operation_id: str
    idempotency_key: str
    semantic_digest: str
    completed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id or any(ch.isspace() for ch in self.operation_id):
            raise ValueError("operation_id must be a non-empty token")
        if not isinstance(self.idempotency_key, str) or not self.idempotency_key or any(ch.isspace() for ch in self.idempotency_key):
            raise ValueError("idempotency_key must be a non-empty token")
        if not isinstance(self.semantic_digest, str) or _DIGEST_RE.fullmatch(self.semantic_digest) is None:
            raise ValueError("semantic_digest must be a lowercase SHA-256 digest")
        if type(self.completed) is not bool:
            raise ValueError("completed must be boolean")


def operation_digest(message: IntranelMessage) -> str:
    """Digest operation semantics while excluding packet/relay/security metadata."""
    operation = {
        "protocol": message.protocol,
        "origin": str(message.origin),
        "target": str(message.target),
        "operation_id": message.operation_id,
        "conversation_id": message.conversation_id,
        "performative": message.performative.value,
        "subject": message.subject,
        "exact_subject": message.exact_subject,
        "payload": message.payload,
        "authority_claim_ref": message.authority_claim_ref,
        "constraints": list(message.constraints),
        "prohibited_effects": list(message.prohibited_effects),
        "idempotency_key": message.idempotency_key,
        "effect_class": message.effect_class.value,
        "capabilities": list(message.capabilities),
        "provenance": list(message.provenance),
    }
    return content_digest(operation)


def _authentication_decision(checks: ReceiverChecks) -> AdmissionDecision | None:
    auth_values = (checks.origin_authenticated, checks.actor_authenticated)
    if any(value is None for value in auth_values):
        return AdmissionDecision.QUARANTINE
    if any(value is False for value in auth_values):
        return AdmissionDecision.REJECT
    if checks.replay_fresh is not True:
        return AdmissionDecision.QUARANTINE
    if checks.capabilities_supported is None:
        return AdmissionDecision.QUARANTINE
    if checks.capabilities_supported is False:
        return AdmissionDecision.REJECT
    return None


def _requires_authority(message: IntranelMessage) -> bool:
    if message.performative is Performative.CANCEL:
        return True
    return (
        message.performative is Performative.EXECUTE
        and message.effect_class is not EffectClass.READ_ONLY
    )


def admit(
    message: IntranelMessage,
    checks: ReceiverChecks,
    prior_operation: OperationRecord | None = None,
) -> AdmissionDecision:
    """Return a fail-closed receiver decision without granting authority itself."""
    authentication = _authentication_decision(checks)
    if authentication is not None:
        return authentication

    if message.exact_subject is not None:
        if checks.exact_subject_valid is None:
            return AdmissionDecision.QUARANTINE
        if checks.exact_subject_valid is False:
            return AdmissionDecision.CONFLICT

    if _requires_authority(message):
        if checks.authority_valid is None:
            return AdmissionDecision.QUARANTINE
        if checks.authority_valid is False:
            return AdmissionDecision.REJECT

    if prior_operation is not None and message.operation_id == prior_operation.operation_id:
        if message.idempotency_key != prior_operation.idempotency_key:
            return AdmissionDecision.CONFLICT
        if operation_digest(message) != prior_operation.semantic_digest:
            return AdmissionDecision.CONFLICT
        if not prior_operation.completed:
            return AdmissionDecision.QUARANTINE
        return AdmissionDecision.DUPLICATE

    return AdmissionDecision.ALLOW
