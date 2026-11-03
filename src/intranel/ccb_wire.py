"""One-way, no-effect Intranel -> CCB Core Bus-document source adapter.

This emits *untrusted source bytes* consumable by CCB Core's
``radar.message_grammar.parse_bus_document``. It does not append to a Bus,
authenticate a writer, admit a packet, establish delivery, or grant authority.
The caller remains responsible for independently authorizing publication and
the selected Bus writer/recipient lane.
"""

from __future__ import annotations

import json
import re

from .coordination import CoordinationConflict, ROLE_ADDRESSES, wrap
from .message import IntranelMessage
from .types import EffectClass, Performative, SecurityProfile


MAX_BUS_DOCUMENT_BYTES = 65_536
_HEADER_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")


class BusWireError(ValueError):
    """An untrusted source packet cannot be represented on this narrow wire."""


def _header(value: str, name: str) -> str:
    if type(value) is not str or not _HEADER_TOKEN.fullmatch(value):
        raise BusWireError(f"invalid {name} header token")
    return value


def encode_read_only_bus_document(
    message: IntranelMessage,
    *,
    writer: str,
    bus_message_id: str,
    intended_recipient: str,
) -> bytes:
    """Produce a bounded CCB Core document containing a pinned Intranel packet.

    Only OPEN-profile QUERY/REQUEST messages with declared READ_ONLY effects
    are representable. Header identities are caller-supplied *claims*, not
    authenticated principals; a real Bus append must separately validate them.
    This function has no I/O or service/authorization side effects.
    """
    if not isinstance(message, IntranelMessage):
        raise BusWireError("expected parsed Intranel message")
    if (message.performative not in (Performative.QUERY, Performative.REQUEST)
            or message.effect_class is not EffectClass.READ_ONLY):
        raise BusWireError("only read-only query/request source packets are supported")
    if message.security_profile is not SecurityProfile.OPEN:
        raise BusWireError("private or sealed message cannot use plaintext Bus document")
    if message.ack_required or message.expected_response is not None:
        raise BusWireError("ack or response obligations cannot be preserved on observation-only wire")
    if (str(message.actor) not in ROLE_ADDRESSES
            or str(message.reply_to) not in ROLE_ADDRESSES):
        raise BusWireError("actor or reply address outside scoped pilot roles")

    writer = _header(writer, "writer")
    bus_message_id = _header(bus_message_id, "bus_message_id")
    intended_recipient = _header(intended_recipient, "intended_recipient")
    if intended_recipient != str(message.target):
        raise BusWireError("Bus recipient conflicts with Intranel target")

    try:
        envelope = wrap(message)
    except CoordinationConflict as exc:
        raise BusWireError("packet outside scoped coordination profile") from exc

    body = json.dumps(
        envelope, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )
    source = (
        f"message_id: {bus_message_id}\n"
        f"writer: {writer}\n"
        f"intended_recipient: {intended_recipient}\n"
        "subject: INTRANEL/1-source-observation\n"
        "requires_ack: false\n"
        "requires_reply: false\n"
        f"\n```json\n{body}\n```\n"
    ).encode("utf-8")
    if len(source) > MAX_BUS_DOCUMENT_BYTES:
        raise BusWireError("Bus source document exceeds wire size limit")
    return source
