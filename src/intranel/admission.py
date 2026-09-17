from __future__ import annotations

from dataclasses import dataclass, replace

from .canonical import content_digest
from .message import IntranelMessage
from .types import AdmissionDecision, EffectClass, Performative


@dataclass(frozen=True, slots=True)
class ReceiverChecks:
    origin_authenticated: bool | None
    actor_authenticated: bool | None
    authority_valid: bool | None
    exact_subject_valid: bool | None
    replay_fresh: bool | None
    capabilities_supported: bool | None

    def replace(self, **changes: bool | None) -> "ReceiverChecks":
        return replace(self, **changes)


@dataclass(frozen=True, slots=True)
class OperationRecord:
    operation_id: str
    idempotency_key: str
    semantic_digest: str
    completed: bool


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

    if prior_operation is not None and message.operation_id == prior_operation.operation_id:
        if message.idempotency_key != prior_operation.idempotency_key:
            return AdmissionDecision.CONFLICT
        if operation_digest(message) != prior_operation.semantic_digest:
            return AdmissionDecision.CONFLICT
        return AdmissionDecision.DUPLICATE

    mutating_execute = (
        message.performative is Performative.EXECUTE
        and message.effect_class is not EffectClass.READ_ONLY
    )
    if mutating_execute:
        if checks.authority_valid is None:
            return AdmissionDecision.QUARANTINE
        if checks.authority_valid is False:
            return AdmissionDecision.REJECT

    return AdmissionDecision.ALLOW
