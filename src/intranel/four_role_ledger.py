"""Durable *observations* for four-role Intranel coordination, not a transport.

Neither a syntactically valid packet nor a causally matched reply proves
authentic origin, successful delivery, acceptance, execution, or permission.
"""
from __future__ import annotations

from contextlib import contextmanager, closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from .canonical import canonical_json_bytes, content_digest
from .message import IntranelMessage, parse_message
from .types import EffectClass, Performative

_ROLES = frozenset({"vera:portal", "vera:integration", "vera:training", "vera:vn1"})
_PEERS = _ROLES - {"vera:portal"}
_EXACT = re.compile(r"^git:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REPLIES = frozenset({Performative.ACK, Performative.WAIT, Performative.CONFLICT})
_SCHEMA = """
CREATE TABLE IF NOT EXISTS observed (
 conversation_id TEXT NOT NULL, message_id TEXT NOT NULL,
 content BLOB NOT NULL, digest TEXT NOT NULL, source_ref TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 PRIMARY KEY (conversation_id, message_id)
);
CREATE TABLE IF NOT EXISTS collisions (
 id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, message_id TEXT NOT NULL,
 prior_digest TEXT NOT NULL, incoming_digest TEXT NOT NULL, source_ref TEXT NOT NULL
);
"""

class CoordinationError(ValueError):
    pass

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _validate(m: IntranelMessage) -> None:
    if (m.effect_class is not EffectClass.READ_ONLY
            or m.authority_claim_ref is not None
            or m.performative not in _REPLIES | {Performative.REQUEST}):
        raise CoordinationError("four-role pilot allows only non-authoritative read-only requests/replies")
    if str(m.origin) not in _ROLES or str(m.target) not in _ROLES:
        raise CoordinationError("unknown four-role address")
    if not m.exact_subject or _EXACT.fullmatch(m.exact_subject) is None:
        raise CoordinationError("exact source must be git:owner/repo@40hex")
    if m.performative is Performative.REQUEST:
        if (str(m.origin) != "vera:portal" or str(m.actor) != "vera:portal"
                or str(m.reply_to) != "vera:portal"
                or str(m.target) not in _PEERS
                or m.parent_message_id is not None
                or m.ack_required is not True or m.expected_response is not Performative.ACK):
            raise CoordinationError("request not correctly staged by declared PORTAL coordinator")
    else:
        payload = m.to_mapping().get("payload")
        if (str(m.origin) not in _PEERS or str(m.target) != "vera:portal"
                or str(m.reply_to) not in _PEERS or not m.parent_message_id
                or type(payload) is not dict
                or type(payload.get("request_digest")) is not str
                or _DIGEST.fullmatch(payload["request_digest"]) is None):
            raise CoordinationError("reply lacks required causal request reference")
    # These are shape checks on self-declared identities, never authentication.

class FourRoleLedger:
    """SQLite inbox of observations; a matched reply never becomes an ACK grant."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.parent.is_dir() or self.path.is_dir():
            raise CoordinationError("ledger path is unsafe or parent missing")
        with self._db() as db:
            db.executescript(_SCHEMA)

    @contextmanager
    def _db(self):
        # sqlite3.Connection.__exit__ commits, but does NOT close on Windows.
        # Closing is required before ephemeral SQLite database cleanup.
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.row_factory = sqlite3.Row
            with db:
                yield db

    def observe(self, packet: Mapping[str, Any], source_ref: str) -> dict[str, Any]:
        if type(source_ref) is not str or not 1 <= len(source_ref) <= 512:
            raise CoordinationError("bounded observation locator required")
        m = parse_message(packet)
        _validate(m)
        raw = canonical_json_bytes(m)
        digest = content_digest(m)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT digest FROM observed WHERE conversation_id=? AND message_id=?",
                (m.conversation_id, m.message_id)
            ).fetchone()
            if prior:
                if prior["digest"] != digest:
                    db.execute(
                        "INSERT INTO collisions(conversation_id,message_id,prior_digest,incoming_digest,source_ref)"
                        " VALUES(?,?,?,?,?)",
                        (m.conversation_id, m.message_id, prior["digest"], digest, source_ref)
                    )
                    return {"ingest": "CONFLICT", "classification": "IDENTITY_COLLISION",
                            "origin_authenticated": False, "delivered": False,
                            "ack_accepted": False, "incoming_digest": digest}
                ingest = "DUPLICATE"
            else:
                db.execute(
                    "INSERT INTO observed(conversation_id,message_id,content,digest,source_ref,observed_at)"
                    " VALUES(?,?,?,?,?,?)",
                    (m.conversation_id, m.message_id, raw, digest, source_ref, _now())
                )
                ingest = "OBSERVED_NEW"
        return {"ingest": ingest, **self.classify(m.conversation_id, m.message_id)}

    def classify(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT content,digest,source_ref FROM observed "
                             "WHERE conversation_id=? AND message_id=?",
                             (conversation_id, message_id)).fetchone()
            if row is None:
                raise CoordinationError("not observed")
            m = parse_message(json.loads(row["content"]))
            collision = db.execute(
                "SELECT 1 FROM collisions WHERE conversation_id=? AND message_id=? LIMIT 1",
                (conversation_id, message_id)
            ).fetchone()
            result = {
                "classification": "REQUEST_STAGED_UNDELIVERED",
                "digest": row["digest"],
                "source_ref": row["source_ref"],
                "origin_authenticated": False, "delivered": False, "ack_accepted": False,
                "executed": False
            }
            if collision is not None:
                result["classification"] = "IDENTITY_COLLISION"
                return result
            if m.performative is Performative.REQUEST:
                return result
            result["classification"] = "UNMATCHED_REPLY"
            parent = db.execute(
                "SELECT content,digest FROM observed WHERE conversation_id=? AND message_id=?",
                (m.conversation_id, m.parent_message_id)
            ).fetchone()
            if parent is None:
                return result
            req = parse_message(json.loads(parent["content"]))
            if req.performative is not Performative.REQUEST:
                result["classification"] = "WRONG_PARENT_TYPE"
                return result
            if (req.target != m.origin or req.origin != m.target
                    or req.reply_to != m.target
                    or req.exact_subject != m.exact_subject
                    or req.conversation_id != m.conversation_id
                    or req.operation_id != m.operation_id
                    or m.to_mapping()["payload"]["request_digest"] != parent["digest"]):
                result["classification"] = "CAUSAL_CONFLICT"
                return result
            if req.expires_at is not None:
                expiry = datetime.fromisoformat(req.expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expiry:
                    result["classification"] = "EXPIRED_REQUEST"
                    return result
            result["classification"] = "CAUSALLY_MATCHED_UNAUTHENTICATED"
            result["parent_request_digest"] = parent["digest"]
            result["reply_performative"] = m.performative.value
            return result

    def counts(self) -> dict[str, int]:
        with self._db() as db:
            return {
                "observations": db.execute("SELECT count(*) FROM observed").fetchone()[0],
                "collisions": db.execute("SELECT count(*) FROM collisions").fetchone()[0],
            }
