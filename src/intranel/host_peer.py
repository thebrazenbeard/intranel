"""Opt-in INTRANEL_HOST_PEER_V1 durable, read-only message exchange.

This module supplies the data plane for *already authenticated* duplex streams
(for example a carefully constrained SSH remote command). It does not create,
authenticate, or authorize an SSH connection. ``ObservedPeer`` must be obtained
from a separately trusted session/OS-account/host-key binding, never copied
from an inbound message or supplied by an untrusted network client.

An ACK here is the remote peer's claim that exact bytes were committed to its
SQLite inbox, not independently verified receiver readback or an effect proof.
No EXECUTE, mutation, private/sealed profile, or receiver-side processing is
implemented by this source-stage primitive.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import BinaryIO, Mapping

from .canonical import canonical_json_bytes
from .message import MAX_MESSAGE_BYTES, IntranelMessage, parse_message
from .types import EffectClass, Performative, SecurityProfile

_HOST = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ACK_PROTOCOL = "INTRANEL_HOST_PEER_ACK/1"
MAX_WIRE_BYTES = 65_536


class HostPeerConflict(ValueError):
    """Fail-closed rejection of an invalid, ambiguous, or untrusted exchange."""


def _host(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not _HOST.fullmatch(value):
        raise HostPeerConflict(f"invalid {name}")
    return value


@dataclass(frozen=True, slots=True)
class ObservedPeer:
    """Identity supplied by an externally authenticated transport adapter.

    Instantiating this class is not authentication. A trusted *host caller*
    must hold the session's actual authenticated client account and public-key
    identity, bind those to a pinned peer host identity, and independently
    validate the applicable host key. This container attests none of them.
    """

    host: str
    os_account: str
    host_key_fingerprint: str

    def __post_init__(self) -> None:
        _host(self.host, name="observed peer host")
        for name in ("os_account", "host_key_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not 1 <= len(value) <= 256:
                raise HostPeerConflict(f"invalid {name}")
            if any(ch in value for ch in "\r\n\x00"):
                raise HostPeerConflict(f"invalid {name}")


def _strict_json(data: bytes) -> dict:
    if type(data) is not bytes or not 0 < len(data) <= MAX_WIRE_BYTES:
        raise HostPeerConflict("wire packet size invalid")

    def pairs(seq):
        out = {}
        for key, value in seq:
            if key in out:
                raise HostPeerConflict("duplicate JSON key")
            out[key] = value
        return out

    try:
        obj = json.loads(data.decode("utf-8", "strict"), object_pairs_hook=pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             HostPeerConflict("nonfinite JSON value")))
    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
        raise HostPeerConflict("invalid wire JSON") from exc
    if type(obj) is not dict:
        raise HostPeerConflict("wire payload must be an object")
    try:
        canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise HostPeerConflict("invalid canonical JSON") from exc
    if canonical != data:
        raise HostPeerConflict("wire JSON must be canonical")
    return obj


def _ack_bytes(*, source: str, target: str, message_id: str, digest: str) -> bytes:
    return json.dumps({"protocol": _ACK_PROTOCOL, "source_host": source,
                       "target_host": target, "message_id": message_id,
                       "message_sha256": digest, "status": "STORED"},
                      ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


class HostPeerStore:
    """SQLite durable inbox/outbox; one configured local host per store.

    The caller controls stream authentication and remote execution boundaries;
    this class provides neither TCP listeners nor command/action dispatch.
    """

    def __init__(self, db_path: str | Path, *, local_host: str,
                 trusted_peers: Mapping[str, tuple[str, str]]) -> None:
        self.local_host = _host(local_host, name="local host")
        if not isinstance(trusted_peers, Mapping) or not trusted_peers:
            raise HostPeerConflict("trusted peer policy required")
        self._peers: dict[str, tuple[str, str]] = {}
        for host, pair in trusted_peers.items():
            host = _host(host, name="configured peer host")
            if host == self.local_host or type(pair) is not tuple or len(pair) != 2:
                raise HostPeerConflict("invalid trusted peer binding")
            obs = ObservedPeer(host, pair[0], pair[1])
            self._peers[host] = (obs.os_account, obs.host_key_fingerprint)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS host_peer_outbox (
                message_id TEXT PRIMARY KEY, digest TEXT NOT NULL,
                packet BLOB NOT NULL, target_host TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('PENDING', 'ACKED')),
                ack BLOB)""")
            db.execute("""CREATE TABLE IF NOT EXISTS host_peer_inbox (
                message_id TEXT PRIMARY KEY, digest TEXT NOT NULL,
                packet BLOB NOT NULL, source_host TEXT NOT NULL,
                os_account TEXT NOT NULL, host_key_fingerprint TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS host_peer_meta (
                name TEXT PRIMARY KEY, value TEXT NOT NULL)""")
            try:
                db.execute("BEGIN IMMEDIATE")
                owner = db.execute("SELECT value FROM host_peer_meta "
                                   "WHERE name='local_host'").fetchone()
                if owner is None:
                    # A legacy inbox/outbox with committed work has no proven
                    # local-owner binding; silent adoption could misroute ACKs.
                    has_records = any(db.execute(
                        f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                        for table in ("host_peer_inbox", "host_peer_outbox"))
                    if has_records:
                        raise HostPeerConflict("database owner unbound with existing records")
                    db.execute("INSERT INTO host_peer_meta VALUES ('local_host', ?)",
                               (self.local_host,))
                elif owner[0] != self.local_host:
                    raise HostPeerConflict("database owner differs from configured local host")
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=5000")
            yield db
        finally:
            db.close()

    def _observed(self, observed: ObservedPeer) -> str:
        if type(observed) is not ObservedPeer:
            raise HostPeerConflict("verified carrier peer identity required")
        expected = self._peers.get(observed.host)
        if expected is None or expected != (observed.os_account,
                                             observed.host_key_fingerprint):
            raise HostPeerConflict("authenticated carrier identity not admitted")
        return observed.host

    @staticmethod
    def _require_fresh(message: IntranelMessage) -> None:
        if message.expires_at is not None:
            expiry = datetime.fromisoformat(message.expires_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) >= expiry:
                raise HostPeerConflict("host-peer message expired")

    def _parse_read_only(self, packet: bytes, *, require_fresh: bool = True) -> IntranelMessage:
        obj = _strict_json(packet)
        try:
            message = parse_message(obj)
        except (ValueError, TypeError, RecursionError) as exc:
            raise HostPeerConflict("invalid Intranel semantics") from exc
        try:
            canonical = canonical_json_bytes(message)
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise HostPeerConflict("invalid Intranel canonical encoding") from exc
        if canonical != packet:
            raise HostPeerConflict("Intranel canonical message mismatch")
        if (message.performative not in (Performative.QUERY, Performative.REPORT)
                or message.effect_class is not EffectClass.READ_ONLY
                or message.security_profile is not SecurityProfile.OPEN
                or message.authority_claim_ref is not None
                or str(message.actor) != str(message.origin)
                or str(message.reply_to) != str(message.origin)):
            raise HostPeerConflict("host-peer v1 is OPEN/READ_ONLY QUERY or REPORT only")
        if require_fresh:
            self._require_fresh(message)
        return message

    def queue(self, message: IntranelMessage) -> bytes:
        if type(message) is not IntranelMessage:
            raise HostPeerConflict("IntranelMessage required")
        packet = canonical_json_bytes(message)
        checked = self._parse_read_only(packet)
        if str(checked.origin) != f"host:{self.local_host}":
            raise HostPeerConflict("sender must use local host identity")
        if checked.target.namespace != "host" or checked.target.node not in self._peers:
            raise HostPeerConflict("destination not in trusted peer policy")
        digest = hashlib.sha256(packet).hexdigest()
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT digest, packet FROM host_peer_outbox "
                                 "WHERE message_id=?", (checked.message_id,)).fetchone()
                if row is not None:
                    if row[0] != digest or row[1] != packet:
                        raise HostPeerConflict("outbox message ID semantic collision")
                else:
                    db.execute("INSERT INTO host_peer_outbox VALUES (?,?,?,?,?,NULL)",
                               (checked.message_id, digest, packet,
                                checked.target.node, "PENDING"))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return packet

    def pending(self) -> list[tuple[str, bytes]]:
        with self._connect() as db:
            rows = db.execute("SELECT message_id, packet FROM host_peer_outbox "
                              "WHERE state='PENDING' ORDER BY rowid").fetchall()
        return [(row[0], row[1]) for row in rows]

    def receive(self, packet: bytes, *, observed_peer: ObservedPeer) -> bytes:
        peer = self._observed(observed_peer)
        # Freshness is checked only for first admission under the inbox lock.
        # After a receiver has committed an exact packet, a lost ACK must be
        # recoverable even when the original packet has since expired.
        message = self._parse_read_only(packet, require_fresh=False)
        if (str(message.origin) != f"host:{peer}"
                or str(message.target) != f"host:{self.local_host}"):
            raise HostPeerConflict("inbound origin/target do not match carrier binding")
        digest = hashlib.sha256(packet).hexdigest()
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT digest, packet, source_host, os_account, "
                                 "host_key_fingerprint FROM host_peer_inbox "
                                 "WHERE message_id=?", (message.message_id,)).fetchone()
                if row is not None:
                    if tuple(row) != (digest, packet, peer, observed_peer.os_account,
                                      observed_peer.host_key_fingerprint):
                        raise HostPeerConflict("inbox message ID semantic/identity collision")
                else:
                    self._require_fresh(message)
                    db.execute("INSERT INTO host_peer_inbox VALUES (?,?,?,?,?,?)",
                               (message.message_id, digest, packet, peer,
                                observed_peer.os_account,
                                observed_peer.host_key_fingerprint))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return _ack_bytes(source=self.local_host, target=peer,
                          message_id=message.message_id, digest=digest)

    def accept_ack(self, ack_packet: bytes, *, observed_peer: ObservedPeer) -> None:
        peer = self._observed(observed_peer)
        ack = _strict_json(ack_packet)
        if (set(ack) != {"protocol", "source_host", "target_host", "message_id",
                        "message_sha256", "status"}
                or ack["protocol"] != _ACK_PROTOCOL
                or ack["source_host"] != peer
                or ack["target_host"] != self.local_host
                or ack["status"] != "STORED"
                or not isinstance(ack["message_id"], str)
                or not isinstance(ack["message_sha256"], str)
                or _DIGEST.fullmatch(ack["message_sha256"]) is None):
            raise HostPeerConflict("invalid or untrusted host peer ACK")
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT digest, target_host, ack FROM host_peer_outbox "
                                 "WHERE message_id=?", (ack["message_id"],)).fetchone()
                if (row is None or row[0] != ack["message_sha256"]
                        or row[1] != peer
                        or (row[2] is not None and row[2] != ack_packet)):
                    raise HostPeerConflict("ACK does not bind to exact pending packet")
                db.execute("UPDATE host_peer_outbox SET state='ACKED', ack=? "
                           "WHERE message_id=?", (ack_packet, ack["message_id"]))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    def was_acked(self, message_id: str) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT state FROM host_peer_outbox WHERE message_id=?",
                             (message_id,)).fetchone()
        return row is not None and row[0] == "ACKED"

    def received_count(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT count(*) FROM host_peer_inbox").fetchone()[0]


def read_frame(stream: BinaryIO) -> bytes | None:
    """Read one bounded length-prefixed frame; clean EOF means no new frame."""
    header = bytearray()
    while len(header) < 4:
        chunk = stream.read(4 - len(header))
        if not chunk:
            break
        header.extend(chunk)
    if not header:
        return None
    if len(header) != 4:
        raise HostPeerConflict("partial frame header")
    size = int.from_bytes(header, "big")
    if not 0 < size <= MAX_WIRE_BYTES:
        raise HostPeerConflict("frame length exceeds bound")
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise HostPeerConflict("truncated host peer frame")
        data.extend(chunk)
    return bytes(data)


def write_frame(stream: BinaryIO, packet: bytes) -> None:
    if type(packet) is not bytes or not 0 < len(packet) <= MAX_WIRE_BYTES:
        raise HostPeerConflict("outbound frame size invalid")
    frame = len(packet).to_bytes(4, "big") + packet
    cursor = 0
    while cursor < len(frame):
        written = stream.write(frame[cursor:])
        if not isinstance(written, int) or written <= 0:
            raise HostPeerConflict("transport did not accept full frame")
        cursor += written
    stream.flush()
