"""Opt-in receiver-owned *single SQLite transaction* for causal observation.

Not a transport or an ACK authority. The legacy LocalCoordinationInbox and the
read-only two-DB reconciler remain unchanged, with no automatic migration.
"""
from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from .canonical import canonical_json_bytes, content_digest
from .message import parse_message
from .types import Performative
from .coordination import ROLE_ADDRESSES, unwrap, wrap
from .four_role_ledger import (
    CoordinationError, FourRoleLedger, _now, _validate,
)


class AtomicRoleReceiver(FourRoleLedger):
    """A single receiver-owned DB for observation AND untrusted staging."""

    def __init__(self, path: str | Path, *, expected_target: str) -> None:
        if expected_target not in ROLE_ADDRESSES:
            raise CoordinationError("receiver requires a configured four-role target")
        super().__init__(path)
        self.expected_target = expected_target
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS receiver_binding (
                singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                expected_target TEXT NOT NULL
            )""")
            bound = db.execute(
                "SELECT expected_target FROM receiver_binding WHERE singleton=1"
            ).fetchone()
            if bound is not None and bound["expected_target"] != expected_target:
                raise CoordinationError("receiver role binding changed")
            if bound is None:
                db.execute(
                    "INSERT INTO receiver_binding(singleton,expected_target) VALUES(1,?)",
                    (expected_target,),
                )
            db.execute("""CREATE TABLE IF NOT EXISTS receiver_outbound (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                semantic_sha256 TEXT NOT NULL,
                source_ref TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS receiver_comment_packet (
                comment_id INTEGER NOT NULL,
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                semantic_sha256 TEXT NOT NULL,
                PRIMARY KEY (comment_id,message_id)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS receiver_comment_highwater (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                highest_packet_comment_id INTEGER NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS receiver_staged (
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL PRIMARY KEY,
                semantic_sha256 TEXT NOT NULL,
                target TEXT NOT NULL,
                envelope TEXT NOT NULL,
                source_ref TEXT NOT NULL
            )""")

    def observe(self, packet: Mapping[str, Any], source_ref: str) -> dict[str, Any]:
        """Reject the weaker inherited observer in a receiver-owned ledger."""
        raise CoordinationError("receiver-bound ledger requires receive or outbound request")

    def observe_outbound_request(self, packet: Mapping[str, Any],
                                 source_ref: str) -> dict[str, Any]:
        """Commit observed local PORTAL parent and outbound marker together.

        This marker reflects local origin configuration, not authentication.
        """
        if type(source_ref) is not str or not 1 <= len(source_ref) <= 512:
            raise CoordinationError("outbound source locator required")
        m = parse_message(packet)
        _validate(m)
        if m.performative is not Performative.REQUEST or str(m.origin) != self.expected_target:
            raise CoordinationError("only locally authored coordinator REQUESTs are allowed")
        digest = content_digest(m)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT conversation_id,digest FROM observed WHERE message_id=?",
                (m.message_id,),
            ).fetchone()
            marker = db.execute(
                "SELECT conversation_id,semantic_sha256 FROM receiver_outbound WHERE message_id=?",
                (m.message_id,),
            ).fetchone()
            if old is not None:
                if (marker is None or old["conversation_id"] != m.conversation_id
                        or old["digest"] != digest
                        or marker["conversation_id"] != m.conversation_id
                        or marker["semantic_sha256"] != digest):
                    raise CoordinationError("outbound request conflicts with earlier evidence")
                ingest = "DUPLICATE"
            else:
                if marker is not None:
                    raise CoordinationError("orphaned outbound provenance marker")
                db.execute(
                    """INSERT INTO observed
                       (conversation_id,message_id,content,digest,source_ref,observed_at)
                       VALUES(?,?,?,?,?,?)""",
                    (m.conversation_id, m.message_id, canonical_json_bytes(m),
                     digest, source_ref, _now()),
                )
                db.execute(
                    """INSERT INTO receiver_outbound
                       (message_id,conversation_id,semantic_sha256,source_ref)
                       VALUES(?,?,?,?)""",
                    (m.message_id, m.conversation_id, digest, source_ref),
                )
                ingest = "OBSERVED_NEW"
        return {"ingest": ingest, **self.classify(m.conversation_id, m.message_id)}

    def classify(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        """Public classification requires paired inbound or marked outbound data."""
        with self._db() as db:
            row = db.execute(
                "SELECT content,digest,source_ref FROM observed "
                "WHERE conversation_id=? AND message_id=?",
                (conversation_id, message_id),
            ).fetchone()
            if row is None:
                raise CoordinationError("not observed")
            held = {
                "classification": "HOLD_UNPAIRED_INBOUND",
                "digest": row["digest"], "source_ref": row["source_ref"],
                "origin_authenticated": False, "delivered": False,
                "ack_accepted": False, "executed": False,
            }
            collision = db.execute(
                "SELECT 1 FROM collisions WHERE conversation_id=? AND message_id=? LIMIT 1",
                (conversation_id, message_id),
            ).fetchone()
            if collision is not None:
                held["classification"] = "IDENTITY_COLLISION"
                return held
            try:
                msg = parse_message(json.loads(row["content"]))
                if (msg.message_id != message_id
                        or msg.conversation_id != conversation_id
                        or content_digest(msg) != row["digest"]):
                    held["classification"] = "HOLD_OBSERVATION_TAMPERED"
                    return held
            except (TypeError, ValueError, KeyError):
                held["classification"] = "HOLD_OBSERVATION_TAMPERED"
                return held
            if msg.performative is Performative.REQUEST and str(msg.origin) == self.expected_target:
                marker = db.execute(
                    """SELECT semantic_sha256 FROM receiver_outbound
                       WHERE conversation_id=? AND message_id=?""",
                    (conversation_id, message_id),
                ).fetchone()
                if marker is None or marker["semantic_sha256"] != row["digest"]:
                    held["classification"] = "HOLD_UNMARKED_OUTBOUND_REQUEST"
                    return held
            else:
                staged = db.execute(
                    """SELECT conversation_id,semantic_sha256,target,envelope
                       FROM receiver_staged WHERE message_id=?""",
                    (message_id,),
                ).fetchone()
                if staged is None:
                    return held
                try:
                    packed = json.dumps(wrap(msg), ensure_ascii=False,
                                        sort_keys=True, separators=(",", ":"))
                    self._check_staged(staged, conversation_id, message_id,
                                       row["digest"], packed)
                except (ValueError, TypeError, KeyError):
                    held["classification"] = "HOLD_STAGED_RECEIPT_INVALID"
                    return held
                if msg.performative is not Performative.REQUEST:
                    parent = db.execute(
                        """SELECT o.content,o.digest,p.semantic_sha256
                           FROM observed AS o JOIN receiver_outbound AS p
                             ON p.conversation_id=o.conversation_id
                            AND p.message_id=o.message_id
                           WHERE o.conversation_id=? AND o.message_id=?""",
                        (conversation_id, msg.parent_message_id),
                    ).fetchone()
                    if parent is None or parent["digest"] != parent["semantic_sha256"]:
                        held["classification"] = "HOLD_UNMARKED_PARENT_REQUEST"
                        return held
                    try:
                        parent_msg = parse_message(json.loads(parent["content"]))
                    except (TypeError, ValueError, KeyError):
                        held["classification"] = "HOLD_PARENT_REQUEST_TAMPERED"
                        return held
                    if (parent_msg.performative is not Performative.REQUEST
                            or str(parent_msg.origin) != self.expected_target
                            or content_digest(parent_msg) != parent["digest"]):
                        held["classification"] = "HOLD_PARENT_REQUEST_TAMPERED"
                        return held
        return FourRoleLedger.classify(self, conversation_id, message_id)

    def _after_observation_before_stage(self) -> None:
        """Deterministic fault seam; an exception rolls back BOTH writes."""

    def _after_stage_before_comment_checkpoint(self) -> None:
        """Fault seam: optional local packet progress rolls back with staging."""

    def receive(self, envelope: Mapping[str, Any], source_ref: str, *,
                comment_id: int | None = None) -> dict[str, Any]:
        """Atomic local packet observation/staging plus optional comment marker.

        This cannot prove provider pagination, snapshot stability or sender.
        """
        if type(source_ref) is not str or not 1 <= len(source_ref) <= 512:
            raise CoordinationError("bounded source locator required")
        if comment_id is not None:
            if (type(comment_id) is not int
                    or not 1 <= comment_id <= 9223372036854775807
                    or source_ref !=
                    f"github:thebrazenbeard/intranel#9/comment/{comment_id}"):
                raise CoordinationError("comment ID/locator mismatch")
        m = unwrap(envelope)
        _validate(m)
        if str(m.target) != self.expected_target:
            raise CoordinationError("wrong configured receiving role")
        digest = content_digest(m)
        raw = canonical_json_bytes(m)
        packed = json.dumps(
            wrap(m), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            marker = None
            if comment_id is not None:
                marker = db.execute(
                    """SELECT conversation_id,semantic_sha256
                       FROM receiver_comment_packet
                       WHERE comment_id=? AND message_id=?""",
                    (comment_id,m.message_id),
                ).fetchone()
                high = db.execute(
                    "SELECT highest_packet_comment_id FROM receiver_comment_highwater "
                    "WHERE singleton=1"
                ).fetchone()
                highest = high["highest_packet_comment_id"] if high else None
                if marker is not None:
                    if (marker["conversation_id"] != m.conversation_id
                            or marker["semantic_sha256"] != digest):
                        raise CoordinationError("comment packet marker mismatch")
                elif highest is not None and comment_id < highest:
                    raise CoordinationError("late unrecognized comment packet: HOLD")
            previous = db.execute(
                "SELECT conversation_id,digest FROM observed WHERE message_id=?",
                (m.message_id,),
            ).fetchall()
            if any(row["conversation_id"] != m.conversation_id for row in previous):
                raise CoordinationError("cross-round message identity reused")
            prior = previous[0] if previous else None
            staged = db.execute(
                """SELECT conversation_id,semantic_sha256,target,envelope
                   FROM receiver_staged WHERE message_id=?""",
                (m.message_id,),
            ).fetchone()

            if prior is not None and prior["digest"] != digest:
                db.execute(
                    """INSERT INTO collisions
                       (conversation_id,message_id,prior_digest,incoming_digest,source_ref)
                       VALUES(?,?,?,?,?)""",
                    (m.conversation_id, m.message_id, prior["digest"], digest, source_ref),
                )
                ingest = "CONFLICT"
            elif prior is not None:
                if staged is None:
                    raise CoordinationError("unpaired legacy observation: HOLD")
                self._check_staged(staged, m.conversation_id, m.message_id, digest, packed)
                if comment_id is not None and marker is None:
                    raise CoordinationError("unpaired comment packet marker: HOLD")
                ingest = "DUPLICATE"
            else:
                if staged is not None:
                    raise CoordinationError("staged receipt without observation: HOLD")
                db.execute(
                    """INSERT INTO observed
                       (conversation_id,message_id,content,digest,source_ref,observed_at)
                       VALUES(?,?,?,?,?,?)""",
                    (m.conversation_id, m.message_id, raw, digest, source_ref, _now()),
                )
                self._after_observation_before_stage()
                db.execute(
                    """INSERT INTO receiver_staged
                       (conversation_id,message_id,semantic_sha256,target,envelope,source_ref)
                       VALUES(?,?,?,?,?,?)""",
                    (m.conversation_id, m.message_id, digest, self.expected_target,
                     packed, source_ref),
                )
                ingest = "OBSERVED_NEW"
            if comment_id is not None and ingest == "OBSERVED_NEW":
                # All LOCAL writes belong to the same BEGIN IMMEDIATE.
                # A highwater over packet IDs is not a provider cursor.
                self._after_stage_before_comment_checkpoint()
                db.execute(
                    """INSERT INTO receiver_comment_packet
                       (comment_id,conversation_id,message_id,semantic_sha256)
                       VALUES(?,?,?,?)""",
                    (comment_id,m.conversation_id,m.message_id,digest),
                )
                db.execute(
                    """INSERT INTO receiver_comment_highwater
                       (singleton,highest_packet_comment_id)
                       VALUES(1,?)
                       ON CONFLICT(singleton) DO UPDATE SET
                           highest_packet_comment_id=max(
                               highest_packet_comment_id,
                               excluded.highest_packet_comment_id)""",
                    (comment_id,),
                )
        result = {"ingest": ingest, **self.classify(m.conversation_id, m.message_id)}
        if comment_id is not None:
            result["comment_checkpoint"] = "LOCAL_PACKET_ONLY_UNATTESTED"
        return result

    def _check_staged(
        self, staged: sqlite3.Row, conversation: str, mid: str,
        digest: str, packed: str,
    ) -> None:
        if (staged["conversation_id"] != conversation
                or staged["semantic_sha256"] != digest
                or staged["target"] != self.expected_target
                or staged["envelope"] != packed):
            raise CoordinationError("staged receipt mismatch: HOLD")
        try:
            msg = unwrap(json.loads(staged["envelope"]))
        except (TypeError, ValueError, KeyError) as exc:
            raise CoordinationError("staged receipt invalid: HOLD") from exc
        if msg.message_id != mid or content_digest(msg) != digest:
            raise CoordinationError("staged receipt semantics mismatch: HOLD")

    def read_comment_packet_evidence(self, comment_id: int,
                                     message_id: str) -> dict[str, Any]:
        """Read exact local packet/staging provenance; never authenticate sender.

        A single SELECT within one SQLite read transaction checks the local
        marker, observed packet and receiver stage. No GitHub snapshot proof.
        """
        if (type(comment_id) is not int or not 1 <= comment_id <= 9223372036854775807
                or type(message_id) is not str or not message_id):
            raise CoordinationError("invalid packet evidence key")
        source_ref = f"github:thebrazenbeard/intranel#9/comment/{comment_id}"
        with self._db() as db:
            db.execute("BEGIN")
            row = db.execute(
                """SELECT p.conversation_id,p.semantic_sha256,
                          o.digest AS observation_digest,o.source_ref,
                          s.semantic_sha256 AS staged_digest,s.target
                   FROM receiver_comment_packet AS p
                   LEFT JOIN observed AS o
                     ON o.conversation_id=p.conversation_id
                    AND o.message_id=p.message_id
                   LEFT JOIN receiver_staged AS s
                     ON s.conversation_id=p.conversation_id
                    AND s.message_id=p.message_id
                   WHERE p.comment_id=? AND p.message_id=?""",
                (comment_id, message_id),
            ).fetchone()
            if row is None:
                raise CoordinationError("comment packet not locally checkpointed")
            if (row["observation_digest"] != row["semantic_sha256"]
                    or row["staged_digest"] != row["semantic_sha256"]
                    or row["target"] != self.expected_target
                    or row["source_ref"] != source_ref):
                raise CoordinationError("comment packet evidence does not match local stage")
            return {
                "comment_id": comment_id,
                "conversation_id": row["conversation_id"],
                "message_id": message_id,
                "semantic_sha256": row["semantic_sha256"],
                "source_ref": source_ref,
                "receiver_target": self.expected_target,
                "local_pair_verified": True,
                "origin_authenticated": False,
                "provider_snapshot_attested": False,
                "delivered": False,
                "ack_accepted": False,
                "executed": False,
            }

    def comment_packet_checkpoint(self) -> dict[str, int | None | bool]:
        """Local packet-marker readback, never complete provider coverage."""
        with self._db() as db:
            high = db.execute(
                "SELECT highest_packet_comment_id FROM receiver_comment_highwater "
                "WHERE singleton=1"
            ).fetchone()
            count = db.execute("SELECT count(*) FROM receiver_comment_packet").fetchone()[0]
        return {
            "highest_packet_comment_id": high[0] if high else None,
            "packet_markers": count,
            "coverage_complete": False,
            "origin_authenticated": False,
            "ack_accepted": False,
        }

    def receiver_counts(self) -> dict[str, int]:
        with self._db() as db:
            return {
                "observations": db.execute("SELECT count(*) FROM observed").fetchone()[0],
                "staged": db.execute("SELECT count(*) FROM receiver_staged").fetchone()[0],
                "collisions": db.execute("SELECT count(*) FROM collisions").fetchone()[0],
            }
