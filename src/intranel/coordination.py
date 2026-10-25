"""INTRANEL/1 local durable relay pilot: no authenticated transport or effect authority."""
from __future__ import annotations
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping
from .canonical import canonical_json_bytes, content_digest
from .message import IntranelMessage, parse_message
from .types import EffectClass, Performative

PROFILE = "INTRANEL_BUS_ENVELOPE_V1"
MAX_PACKET_BYTES = 65536
ROLE_ADDRESSES = frozenset({"vera:portal", "vera:integration", "vera:training", "vera:vn1"})

class CoordinationConflict(ValueError):
    """Duplicate identity refers to different content or reply semantics."""

def wrap(message: IntranelMessage) -> dict[str, Any]:
    if message.effect_class is not EffectClass.READ_ONLY or message.performative in (Performative.EXECUTE, Performative.CANCEL):
        raise CoordinationConflict("coordination packets cannot request execution")
    if str(message.origin) not in ROLE_ADDRESSES or str(message.target) not in ROLE_ADDRESSES:
        raise CoordinationConflict("unknown coordination role")
    return {
        "intranel_protocol": "INTRANEL/1",
        "message_id": message.message_id,
        "operation_id": message.operation_id,
        "origin": str(message.origin),
        "target": str(message.target),
        "semantic_sha256": content_digest(message),
        "semantic_message": message.to_mapping(),
        "profile": PROFILE,
    }

def unwrap(envelope: Mapping[str, Any]) -> IntranelMessage:
    expected = {"profile", "intranel_protocol", "message_id", "operation_id",
                "origin", "target", "semantic_sha256", "semantic_message"}
    if not isinstance(envelope, Mapping) or set(envelope) != expected:
        raise CoordinationConflict("unexpected wrapper fields")
    if envelope["profile"] != PROFILE or envelope["intranel_protocol"] != "INTRANEL/1":
        raise CoordinationConflict("unsupported transport profile")
    message = parse_message(envelope["semantic_message"])
    check = wrap(message)
    if any(envelope[k] != check[k] for k in expected if k != "semantic_message"):
        raise CoordinationConflict("wrapper and semantic message conflict")
    if len(canonical_json_bytes(message)) > MAX_PACKET_BYTES:
        raise CoordinationConflict("message too large")
    return message

class LocalCoordinationInbox:
    """SQLite receipt cache; staging is not authenticated delivery.

    Caller supplies expected_target from its own configured local role,
    rather than accepting whatever route the sender claims.
    """
    def __init__(self, path: Path, *, expected_target: str):
        from .types import Address
        self.path = Path(path)
        self.expected_target = str(Address.parse(expected_target))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS messages(
                message_id TEXT PRIMARY KEY,
                semantic_sha256 TEXT NOT NULL,
                origin TEXT NOT NULL,
                target TEXT NOT NULL,
                performative TEXT NOT NULL,
                parent_message_id TEXT,
                packet TEXT NOT NULL
            )""")

    def stage(self, packet: Mapping[str, Any]) -> str:
        message = unwrap(packet)
        if str(message.target) != self.expected_target:
            raise CoordinationConflict("wrong configured receiving role")
        payload = json.dumps(wrap(message), sort_keys=True,
                             ensure_ascii=False, separators=(",", ":"))
        digest = content_digest(message)
        with closing(sqlite3.connect(self.path, timeout=5.0)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT semantic_sha256 FROM messages WHERE message_id=?",
                (message.message_id,),
            ).fetchone()
            if prior:
                if prior[0] != digest:
                    raise CoordinationConflict("same message_id, changed semantics")
                return "DUPLICATE"
            if message.performative is Performative.ACK:
                if not message.parent_message_id:
                    raise CoordinationConflict("ACK requires explicit parent")
                # ACK is observed, not authenticated receipt or task acceptance.
            db.execute(
                """INSERT INTO messages(message_id,semantic_sha256,origin,target,
                   performative,parent_message_id,packet) VALUES (?,?,?,?,?,?,?)""",
                (message.message_id, digest, str(message.origin),
                 str(message.target), message.performative.value,
                 message.parent_message_id, payload),
            )
        return "STAGED_UNATTESTED"

    def get(self, message_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self.path)) as db, db:
            row = db.execute("SELECT packet FROM messages WHERE message_id=?",
                             (message_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def count(self) -> int:
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
