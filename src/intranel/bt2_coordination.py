"""BT2 source-only Intranel role envelope; no transport or effect authority.

The wrapper detects accidental/tampered semantic changes; it does not
authenticate an author, prove recipient delivery, or maintain a replay journal.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .canonical import canonical_json_bytes, content_digest
from .message import IntranelMessage, parse_message
from .types import EffectClass, Performative, SecurityProfile


PROFILE = "BT2_BUS_ENVELOPE_V1"
BT2_ROLES = frozenset({"bt2:one", "bt2:two"})
READ_ONLY_PERFORMATIVES = frozenset({
    Performative.QUERY, Performative.REPORT, Performative.REQUEST,
    Performative.REVIEW, Performative.ACK, Performative.REJECT,
    Performative.WAIT, Performative.CONFLICT,
})
REPLIES = frozenset({Performative.ACK, Performative.REJECT,
                     Performative.WAIT, Performative.CONFLICT})
PIN = re.compile(r"(?:git:[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+@[0-9a-f]{40}|sha256:[0-9a-f]{64})\Z")
MAX_PACKET_BYTES = 65536
ENVELOPE_FIELDS = frozenset({
    "profile", "intranel_protocol", "message_id", "operation_id",
    "origin", "target", "semantic_sha256", "semantic_message",
})


class BT2CoordinationConflict(ValueError):
    """A packet does not meet the no-effect BT2 coordination profile."""


def _validate(message: IntranelMessage) -> None:
    if (str(message.origin) not in BT2_ROLES
        or str(message.target) not in BT2_ROLES
        or str(message.reply_to) != str(message.origin)
        or str(message.actor) != str(message.origin)):
        raise BT2CoordinationConflict("BT2 source-role/route mismatch")
    if (message.performative not in READ_ONLY_PERFORMATIVES
        or message.effect_class is not EffectClass.READ_ONLY
        or message.authority_claim_ref is not None
        or message.security_profile is not SecurityProfile.OPEN):
        raise BT2CoordinationConflict("BT2 profile does not admit effects or authority")
    if not message.exact_subject or not PIN.fullmatch(message.exact_subject):
        raise BT2CoordinationConflict("BT2 profile requires a pinned exact subject")
    if message.performative in REPLIES and not message.parent_message_id:
        raise BT2CoordinationConflict("BT2 reply requires explicit parent message")
    payload = message.to_mapping()["payload"]
    if (type(payload) is not dict
        or payload.get("event_id") != message.conversation_id):
        raise BT2CoordinationConflict("BT2 event correlation mismatch")
    if len(canonical_json_bytes(message)) > MAX_PACKET_BYTES:
        raise BT2CoordinationConflict("BT2 semantic packet too large")


def wrap_bt2(message: IntranelMessage) -> dict[str, Any]:
    """Produce a deterministic no-effect wrapper for an already parsed message."""
    if not isinstance(message, IntranelMessage):
        raise BT2CoordinationConflict("BT2 message must be parsed")
    _validate(message)
    packet = {
        "profile": PROFILE,
        "intranel_protocol": "INTRANEL/1",
        "message_id": message.message_id,
        "operation_id": message.operation_id,
        "origin": str(message.origin),
        "target": str(message.target),
        "semantic_sha256": content_digest(message),
        "semantic_message": message.to_mapping(),
    }
    if len(canonical_json_bytes(packet)) > MAX_PACKET_BYTES:
        raise BT2CoordinationConflict("BT2 envelope too large")
    return packet


def unwrap_bt2(packet: Mapping[str, Any], *, expected_target: str) -> IntranelMessage:
    """Require a receiver-owned address, not the untrusted sender's target."""
    if type(expected_target) is not str or expected_target not in BT2_ROLES:
        raise BT2CoordinationConflict("receiver BT2 role not configured")
    if not isinstance(packet, Mapping) or set(packet) != ENVELOPE_FIELDS:
        raise BT2CoordinationConflict("unknown/missing BT2 envelope fields")
    try:
        if len(canonical_json_bytes(packet)) > MAX_PACKET_BYTES:
            raise BT2CoordinationConflict("BT2 envelope too large")
    except (TypeError, ValueError) as exc:
        raise BT2CoordinationConflict("invalid BT2 envelope encoding") from exc
    if packet["profile"] != PROFILE or packet["intranel_protocol"] != "INTRANEL/1":
        raise BT2CoordinationConflict("unsupported BT2 envelope profile")
    try:
        message = parse_message(packet["semantic_message"])
        expected = wrap_bt2(message)
    except (TypeError, ValueError) as exc:
        raise BT2CoordinationConflict("invalid BT2 semantic message") from exc
    if any(packet[key] != expected[key] for key in ENVELOPE_FIELDS if key != "semantic_message"):
        raise BT2CoordinationConflict("BT2 wrapper/semantic digest mismatch")
    if str(message.target) != expected_target:
        raise BT2CoordinationConflict("wrong configured BT2 recipient")
    return message
