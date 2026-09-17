from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Any, Mapping

from .types import Address, EffectClass, Performative, SecurityProfile

PROTOCOL = "INTRANEL/1"

_FIELDS = {
    "protocol",
    "origin",
    "actor",
    "target",
    "reply_to",
    "message_id",
    "operation_id",
    "parent_message_id",
    "conversation_id",
    "performative",
    "subject",
    "exact_subject",
    "payload",
    "authority_claim_ref",
    "constraints",
    "prohibited_effects",
    "expected_response",
    "ack_required",
    "observed_at",
    "expires_at",
    "idempotency_key",
    "priority",
    "effect_class",
    "status",
    "error",
    "receipt",
    "security_profile",
    "capabilities",
    "provenance",
}

_REQUIRED = {
    "protocol",
    "origin",
    "actor",
    "target",
    "reply_to",
    "message_id",
    "conversation_id",
    "performative",
    "effect_class",
    "security_profile",
}


def _require_token(value: str | None, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ch.isspace() for ch in value):
        raise ValueError(f"{field_name} must be a non-empty token without whitespace")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string or null")
    return value


def _parse_timestamp(value: Any, field_name: str) -> tuple[str | None, datetime | None]:
    raw = _optional_string(value, field_name)
    if raw is None:
        return None, None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an offset-aware ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone offset")
    return raw, parsed


def _validate_json_value(value: Any, field_name: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite number")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item, field_name)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} object keys must be strings")
            _validate_json_value(item, field_name)
        return
    raise ValueError(f"{field_name} must be JSON-compatible")


def _tuple_of_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{field_name} must contain non-empty strings")
        result.append(item)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class IntranelMessage:
    protocol: str
    origin: Address
    actor: Address
    target: Address
    reply_to: Address
    message_id: str
    operation_id: str | None
    parent_message_id: str | None
    conversation_id: str
    performative: Performative
    subject: str | None
    exact_subject: str | None
    payload: Any
    authority_claim_ref: str | None
    constraints: tuple[str, ...] = field(default_factory=tuple)
    prohibited_effects: tuple[str, ...] = field(default_factory=tuple)
    expected_response: Performative | None = None
    ack_required: bool = False
    observed_at: str | None = None
    expires_at: str | None = None
    idempotency_key: str | None = None
    priority: int = 3
    effect_class: EffectClass = EffectClass.READ_ONLY
    status: str | None = None
    error: str | None = None
    receipt: Mapping[str, Any] | None = None
    security_profile: SecurityProfile = SecurityProfile.OPEN
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    provenance: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.protocol != PROTOCOL:
            raise ValueError(f"unsupported protocol: {self.protocol!r}")
        _require_token(self.message_id, "message_id")
        _require_token(self.conversation_id, "conversation_id")
        if self.operation_id is not None:
            _require_token(self.operation_id, "operation_id")
        if self.parent_message_id is not None:
            _require_token(self.parent_message_id, "parent_message_id")
        if self.idempotency_key is not None:
            _require_token(self.idempotency_key, "idempotency_key")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or not 0 <= self.priority <= 4:
            raise ValueError("priority must be an integer from 0 through 4")

        if self.performative is Performative.REVIEW and not self.exact_subject:
            raise ValueError("REVIEW requires exact_subject")

        mutating_execute = (
            self.performative is Performative.EXECUTE
            and self.effect_class is not EffectClass.READ_ONLY
        )
        if mutating_execute:
            if not self.operation_id:
                raise ValueError("mutating EXECUTE requires operation_id")
            if not self.idempotency_key:
                raise ValueError("mutating EXECUTE requires idempotency_key")
            if not self.authority_claim_ref:
                raise ValueError("mutating EXECUTE requires authority_claim_ref")
            if self.subject and not self.exact_subject:
                raise ValueError("mutating EXECUTE with subject requires exact_subject")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "origin": str(self.origin),
            "actor": str(self.actor),
            "target": str(self.target),
            "reply_to": str(self.reply_to),
            "message_id": self.message_id,
            "operation_id": self.operation_id,
            "parent_message_id": self.parent_message_id,
            "conversation_id": self.conversation_id,
            "performative": self.performative.value,
            "subject": self.subject,
            "exact_subject": self.exact_subject,
            "payload": self.payload,
            "authority_claim_ref": self.authority_claim_ref,
            "constraints": list(self.constraints),
            "prohibited_effects": list(self.prohibited_effects),
            "expected_response": self.expected_response.value if self.expected_response is not None else None,
            "ack_required": self.ack_required,
            "observed_at": self.observed_at,
            "expires_at": self.expires_at,
            "idempotency_key": self.idempotency_key,
            "priority": self.priority,
            "effect_class": self.effect_class.value,
            "status": self.status,
            "error": self.error,
            "receipt": dict(self.receipt) if self.receipt is not None else None,
            "security_profile": self.security_profile.value,
            "capabilities": list(self.capabilities),
            "provenance": list(self.provenance),
        }


def parse_message(mapping: Mapping[str, Any]) -> IntranelMessage:
    if not isinstance(mapping, Mapping):
        raise ValueError("Intranel message must be a mapping")

    keys = set(mapping)
    unknown = sorted(keys - _FIELDS)
    if unknown:
        raise ValueError("unknown field(s): " + ", ".join(unknown))
    missing = sorted(_REQUIRED - keys)
    if missing:
        raise ValueError("missing required field(s): " + ", ".join(missing))

    protocol = mapping["protocol"]
    if protocol != PROTOCOL:
        raise ValueError(f"unsupported protocol: {protocol!r}")

    try:
        performative = Performative(mapping["performative"])
        effect_class = EffectClass(mapping["effect_class"])
        security_profile = SecurityProfile(mapping["security_profile"])
        expected_raw = mapping.get("expected_response")
        expected_response = Performative(expected_raw) if expected_raw is not None else None
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc

    ack_required = mapping.get("ack_required", False)
    if not isinstance(ack_required, bool):
        raise ValueError("ack_required must be boolean")

    receipt = mapping.get("receipt")
    if receipt is not None and not isinstance(receipt, Mapping):
        raise ValueError("receipt must be an object or null")
    if receipt is not None:
        _validate_json_value(receipt, "receipt")

    payload = mapping.get("payload")
    _validate_json_value(payload, "payload")

    observed_at, observed_dt = _parse_timestamp(mapping.get("observed_at"), "observed_at")
    expires_at, expires_dt = _parse_timestamp(mapping.get("expires_at"), "expires_at")
    if observed_dt is not None and expires_dt is not None and expires_dt <= observed_dt:
        raise ValueError("expires_at must be later than observed_at")

    return IntranelMessage(
        protocol=protocol,
        origin=Address.parse(mapping["origin"]),
        actor=Address.parse(mapping["actor"]),
        target=Address.parse(mapping["target"]),
        reply_to=Address.parse(mapping["reply_to"]),
        message_id=mapping["message_id"],
        operation_id=mapping.get("operation_id"),
        parent_message_id=mapping.get("parent_message_id"),
        conversation_id=mapping["conversation_id"],
        performative=performative,
        subject=_optional_string(mapping.get("subject"), "subject"),
        exact_subject=_optional_string(mapping.get("exact_subject"), "exact_subject"),
        payload=payload,
        authority_claim_ref=_optional_string(mapping.get("authority_claim_ref"), "authority_claim_ref"),
        constraints=_tuple_of_strings(mapping.get("constraints"), "constraints"),
        prohibited_effects=_tuple_of_strings(mapping.get("prohibited_effects"), "prohibited_effects"),
        expected_response=expected_response,
        ack_required=ack_required,
        observed_at=observed_at,
        expires_at=expires_at,
        idempotency_key=mapping.get("idempotency_key"),
        priority=mapping.get("priority", 3),
        effect_class=effect_class,
        status=_optional_string(mapping.get("status"), "status"),
        error=_optional_string(mapping.get("error"), "error"),
        receipt=receipt,
        security_profile=security_profile,
        capabilities=_tuple_of_strings(mapping.get("capabilities"), "capabilities"),
        provenance=_tuple_of_strings(mapping.get("provenance"), "provenance"),
    )
