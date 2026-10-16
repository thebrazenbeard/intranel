"""Read-only fail-closed reconciliation of PORTAL staging and causal observation.

This is an audit, NOT an atomic two-store transaction or permission to route.
Two databases remain independently maintained; a snapshot match establishes
neither delivery nor currentness when writers may be running concurrently.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
from typing import Any

from .canonical import content_digest
from .message import parse_message
from .coordination import ROLE_ADDRESSES, unwrap
from .four_role_ledger import CoordinationError, FourRoleLedger

_MAX_ROWS = 10000


def _read_db(file: Path) -> sqlite3.Connection:
    file = Path(file)
    if not file.is_file() or file.is_symlink() or file.stat().st_size > 128 * 1024 * 1024:
        raise CoordinationError("audit source missing, symlinked, or oversized")
    db = sqlite3.connect(file.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("BEGIN")
    return db


def audit_local_inbox(
    observations_path: str | Path, staging_path: str | Path,
    *, expected_target: str,
) -> dict[str, Any]:
    """Compare current *snapshots* of two untrusted stores for one target role."""
    if expected_target not in ROLE_ADDRESSES:
        raise CoordinationError("audit requires exact four-role recipient binding")
    if Path(observations_path).resolve() == Path(staging_path).resolve():
        raise CoordinationError("separate schemas require separately declared store paths")
    differences: list[dict[str, str]] = []

    def flag(kind: str, message_id: str) -> None:
        differences.append({"type": kind, "message_id": message_id})

    try:
        with closing(_read_db(Path(observations_path))) as observed, closing(
            _read_db(Path(staging_path))
        ) as staging:
            found = observed.execute(
                "SELECT conversation_id,message_id,content,digest FROM observed"
            ).fetchmany(_MAX_ROWS + 1)
            staged = staging.execute(
                "SELECT message_id,semantic_sha256,target,packet FROM messages"
            ).fetchmany(_MAX_ROWS + 1)
            if len(found) > _MAX_ROWS or len(staged) > _MAX_ROWS:
                raise CoordinationError("audit rows exceed bounded review limit")

            observer_rows: dict[str, tuple[str, str]] = {}
            # The causal store owns all roles. Only compare messages addressed
            # to the configured local inbox, never others' private state.
            for row in found:
                message_id = row["message_id"]
                try:
                    message = parse_message(json.loads(row["content"]))
                    if (message.message_id != message_id
                        or message.conversation_id != row["conversation_id"]
                        or content_digest(message) != row["digest"]):
                        flag("OBSERVATION_DIGEST_MISMATCH", message_id)
                        continue
                except (TypeError, ValueError, KeyError):
                    flag("OBSERVATION_INVALID", message_id)
                    continue
                if str(message.target) != expected_target:
                    continue
                # PORTAL Inbox keys only by message_id, unlike the causal
                # observer's (conversation_id,message_id). Reused IDs in
                # different rounds must never silently alias.
                if message_id in observer_rows:
                    flag("CROSS_ROUND_MESSAGE_ID_REUSED", message_id)
                    continue
                observer_rows[message_id] = (
                    row["conversation_id"], row["digest"],
                )

            staging_rows: dict[str, str] = {}
            for row in staged:
                mid = row["message_id"]
                if row["target"] != expected_target:
                    # Expected target is a receiver-owned binding. Do not
                    # reinterpret a different role's inbox as this role.
                    raise CoordinationError("staging inbox belongs to another recipient")
                try:
                    m = unwrap(json.loads(row["packet"]))
                except (TypeError, ValueError, KeyError):
                    flag("INVALID_STAGED_ENVELOPE", mid)
                    continue
                if str(m.target) != expected_target or m.message_id != mid:
                    flag("INVALID_STAGED_ENVELOPE", mid)
                    continue
                digest = content_digest(m)
                if digest != row["semantic_sha256"]:
                    flag("INBOX_DIGEST_MISMATCH", mid)
                    continue
                staging_rows[mid] = digest

            for mid, (conversation, digest) in sorted(observer_rows.items()):
                if mid not in staging_rows:
                    flag("OBSERVATION_ONLY", mid)
                elif staging_rows[mid] != digest:
                    flag("STORE_DIGEST_CONFLICT", mid)
                else:
                    # A syntactic digest match does not validate the *causal*
                    # state. Reject multiple self-declared siblings, stale
                    # requests and poisoned parents even if staging agrees.
                    state = FourRoleLedger.classify(
                        # Avoid FourRoleLedger.__init__: it is a writing
                        # initializer. Audit operates on already present data.
                        _ReadOnlyLedgerProxy(Path(observations_path)),
                        conversation, mid,
                    )
                    if state["classification"] not in {
                        "CAUSALLY_MATCHED_UNAUTHENTICATED",
                        "REQUEST_STAGED_UNDELIVERED",
                    }:
                        flag("CAUSAL_REPLY_UNQUALIFIED", mid)
            for mid in sorted(staging_rows.keys() - observer_rows.keys()):
                flag("STAGING_ONLY", mid)
    except sqlite3.DatabaseError as exc:
        raise CoordinationError("source store unreadable or incompatible") from exc
    return {
        "classification": (
            "HOLD_STORE_DIVERGENCE" if differences
            else "HOLD_EMPTY_SNAPSHOT" if not staging_rows
            else "SNAPSHOT_AGREEMENT_UNATTESTED"
        ),
        "compared": len(observer_rows),
        "differences": differences,
        "origin_authenticated": False,
        "delivered": False,
        "ack_accepted": False,
        "executed": False,
        "atomic_cross_store_transaction": False,
    }


class _ReadOnlyLedgerProxy:
    """Provide FourRoleLedger.classify a read-only connection, no DDL effects."""

    def __init__(self, path: Path):
        self.path = path

    def _db(self):
        from contextlib import contextmanager

        @contextmanager
        def reader():
            with closing(_read_db(self.path)) as db:
                yield db

        return reader()
