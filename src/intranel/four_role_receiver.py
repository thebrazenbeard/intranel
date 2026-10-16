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
            db.execute("""CREATE TABLE IF NOT EXISTS receiver_staged (
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL PRIMARY KEY,
                semantic_sha256 TEXT NOT NULL,
                target TEXT NOT NULL,
                envelope TEXT NOT NULL,
                source_ref TEXT NOT NULL
            )""")

    def _after_observation_before_stage(self) -> None:
        """Deterministic fault seam; an exception rolls back BOTH writes."""

    def receive(self, envelope: Mapping[str, Any], source_ref: str) -> dict[str, Any]:
        """Commit observed packet + staging record together; never assert delivery."""
        if type(source_ref) is not str or not 1 <= len(source_ref) <= 512:
            raise CoordinationError("bounded source locator required")
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
        return {"ingest": ingest, **self.classify(m.conversation_id, m.message_id)}

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

    def receiver_counts(self) -> dict[str, int]:
        with self._db() as db:
            return {
                "observations": db.execute("SELECT count(*) FROM observed").fetchone()[0],
                "staged": db.execute("SELECT count(*) FROM receiver_staged").fetchone()[0],
                "collisions": db.execute("SELECT count(*) FROM collisions").fetchone()[0],
            }
