"""Host-peer state tests: two endpoints, external authenticated carrier mocked."""

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from intranel.host_peer import (
    HostPeerConflict,
    HostPeerStore,
    ObservedPeer,
    read_frame,
    write_frame,
)
from intranel.message import parse_message


def msg(ident="host-001", *, source="lappy", target="vn1", payload=None):
    return parse_message({
        "protocol": "INTRANEL/1",
        "origin": f"host:{source}",
        "actor": f"host:{source}",
        "target": f"host:{target}",
        "reply_to": f"host:{source}",
        "message_id": ident,
        "conversation_id": "host-conv-1",
        "performative": "QUERY",
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
        "ack_required": True,
        "payload": payload or {"query": "health"},
    })


class HostPeerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        self.alice_path = folder / "alice.sqlite3"
        self.bob_path = folder / "bob.sqlite3"
        self.a = HostPeerStore(self.alice_path, local_host="lappy", trusted_peers={
            "vn1": ("svc-vn1", "SHA256:vn1-fingerprint")
        })
        self.b = HostPeerStore(self.bob_path, local_host="vn1", trusted_peers={
            "lappy": ("svc-lappy", "SHA256:lappy-fingerprint")
        })
        self.obs_a = ObservedPeer("lappy", "svc-lappy", "SHA256:lappy-fingerprint")
        self.obs_b = ObservedPeer("vn1", "svc-vn1", "SHA256:vn1-fingerprint")

    def test_lost_ack_recovery_and_cold_restart(self):
        packet = self.a.queue(msg())
        self.assertEqual(self.a.pending(), [("host-001", packet)])
        ack1 = self.b.receive(packet, observed_peer=self.obs_a)
        self.assertEqual(self.b.received_count(), 1)
        # The first acknowledgement is lost after the receiving commit.
        self.b = HostPeerStore(self.bob_path, local_host="vn1", trusted_peers={
            "lappy": ("svc-lappy", "SHA256:lappy-fingerprint")
        })
        ack2 = self.b.receive(packet, observed_peer=self.obs_a)
        self.assertEqual(ack1, ack2)
        self.assertEqual(self.b.received_count(), 1)
        self.a = HostPeerStore(self.alice_path, local_host="lappy", trusted_peers={
            "vn1": ("svc-vn1", "SHA256:vn1-fingerprint")
        })
        self.a.accept_ack(ack2, observed_peer=self.obs_b)
        self.assertEqual(self.a.pending(), [])
        self.assertTrue(self.a.was_acked("host-001"))

    def test_message_id_collision_blocks_different_semantics(self):
        packet = self.a.queue(msg())
        self.b.receive(packet, observed_peer=self.obs_a)
        with self.assertRaises(HostPeerConflict):
            self.b.receive(self._packet(msg(payload={"query": "delete"})), observed_peer=self.obs_a)
        with self.assertRaises(HostPeerConflict):
            self.a.queue(msg(payload={"query": "different"}))

    def test_forged_origin_on_authenticated_peer_is_rejected(self):
        other = self._packet(msg(source="vn2"))
        with self.assertRaises(HostPeerConflict):
            self.b.receive(other, observed_peer=self.obs_a)
        self.assertEqual(self.b.received_count(), 0)

    def test_changed_ssh_account_or_fingerprint_rejected(self):
        packet = self._packet(msg())
        for obs in [
            ObservedPeer("lappy", "other-account", "SHA256:lappy-fingerprint"),
            ObservedPeer("lappy", "svc-lappy", "SHA256:other-fingerprint"),
            ObservedPeer("vn2", "svc-lappy", "SHA256:lappy-fingerprint"),
        ]:
            with self.subTest(obs=obs), self.assertRaises(HostPeerConflict):
                self.b.receive(packet, observed_peer=obs)
        self.assertEqual(self.b.received_count(), 0)

    def test_wrong_target_and_mutating_execute_rejected(self):
        with self.assertRaises(HostPeerConflict):
            self.b.receive(self._packet(msg(target="vn2")), observed_peer=self.obs_a)
        malicious = msg().to_mapping()
        malicious.update(performative="EXECUTE", effect_class="READ_ONLY")
        with self.assertRaises(HostPeerConflict):
            self.b.receive(self._packet(parse_message(malicious)), observed_peer=self.obs_a)

    def test_ack_requires_authenticated_expected_peer_and_digest(self):
        self.a.queue(msg())
        packet = self.a.pending()[0][1]
        ack = self.b.receive(packet, observed_peer=self.obs_a)
        with self.assertRaises(HostPeerConflict):
            self.a.accept_ack(ack, observed_peer=self.obs_a)
        tampered = ack.replace(b"host-001", b"host-002")
        with self.assertRaises(HostPeerConflict):
            self.a.accept_ack(tampered, observed_peer=self.obs_b)
        self.assertFalse(self.a.was_acked("host-001"))

    def test_length_prefixed_stdio_frames_are_bounded(self):
        bio = io.BytesIO()
        write_frame(bio, b"hello")
        bio.seek(0)
        self.assertEqual(read_frame(bio), b"hello")
        self.assertIsNone(read_frame(bio))
        with self.assertRaises(HostPeerConflict):
            read_frame(io.BytesIO((999999).to_bytes(4, "big")))
        with self.assertRaises(HostPeerConflict):
            read_frame(io.BytesIO((8).to_bytes(4, "big") + b"only 4"))
        with self.assertRaises(HostPeerConflict):
            read_frame(io.BytesIO(b"\x00\x01"))

    def test_noncanonical_duplicate_keys_and_large_frame_rejected(self):
        packet = self._packet(msg())
        with self.assertRaises(HostPeerConflict):
            self.b.receive(packet.replace(b'"protocol":', b'"protocol":"INTRANEL/1","protocol":'),
                           observed_peer=self.obs_a)
        with self.assertRaises(HostPeerConflict):
            self.b.receive(b"{" + b"x" * 65535 + b"}", observed_peer=self.obs_a)
        self.assertEqual(self.b.received_count(), 0)

    def test_expired_packet_never_commits(self):
        now = datetime.now(timezone.utc)
        m = msg().to_mapping()
        m["observed_at"] = (now-timedelta(minutes=2)).isoformat()
        m["expires_at"] = (now-timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(HostPeerConflict, "expired"):
            self.b.receive(self._packet(parse_message(m)), observed_peer=self.obs_a)
        self.assertEqual(self.b.received_count(), 0)

    def test_expired_exact_retry_acknowledges_previously_committed_inbox(self):
        now = datetime.now(timezone.utc)
        record = msg("expiring-001").to_mapping()
        record["observed_at"] = (now-timedelta(seconds=5)).isoformat()
        record["expires_at"] = (now+timedelta(seconds=30)).isoformat()
        packet = self.a.queue(parse_message(record))

        class FrozenClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.current

        FrozenClock.current = now
        with patch("intranel.host_peer.datetime", FrozenClock):
            ack = self.b.receive(packet, observed_peer=self.obs_a)
            FrozenClock.current = now+timedelta(seconds=31)
            restarted = HostPeerStore(self.bob_path, local_host="vn1", trusted_peers={
                "lappy": ("svc-lappy", "SHA256:lappy-fingerprint")
            })
            self.assertEqual(restarted.receive(packet, observed_peer=self.obs_a), ack)
            self.assertEqual(restarted.received_count(), 1)
            other_record = dict(record)
            other_record["message_id"] = "expired-new-001"
            with self.assertRaisesRegex(HostPeerConflict, "expired"):
                restarted.receive(self._packet(parse_message(other_record)),
                                  observed_peer=self.obs_a)
        self.a.accept_ack(ack, observed_peer=self.obs_b)
        self.assertTrue(self.a.was_acked("expiring-001"))

    def test_deep_bounded_json_rejects_as_host_peer_conflict(self):
        packet = b'{"payload":' + b"[" * 10_000 + b"0" + b"]" * 10_000 + b"}"
        self.assertLess(len(packet), 65_536)
        with self.assertRaises(HostPeerConflict):
            self.b.receive(packet, observed_peer=self.obs_a)
        self.assertEqual(self.b.received_count(), 0)

    def test_sqlite_owner_is_persistently_bound_to_local_host(self):
        packet = self.a.queue(msg())
        with self.assertRaisesRegex(HostPeerConflict, "owner"):
            HostPeerStore(self.alice_path, local_host="vn2", trusted_peers={
                "vn1": ("svc-vn1", "SHA256:vn1-fingerprint")
            })
        reopened = HostPeerStore(self.alice_path, local_host="lappy", trusted_peers={
            "vn1": ("svc-vn1", "SHA256:vn1-fingerprint")
        })
        self.assertEqual(reopened.pending(), [("host-001", packet)])

    def test_legacy_unowned_pending_store_cannot_silently_adopt_host(self):
        self.a.queue(msg())
        with sqlite3.connect(self.alice_path) as db:
            if db.execute("SELECT count(*) FROM sqlite_master WHERE "
                          "type='table' AND name='host_peer_meta'").fetchone()[0]:
                db.execute("DELETE FROM host_peer_meta")
        with self.assertRaisesRegex(HostPeerConflict, "owner"):
            HostPeerStore(self.alice_path, local_host="lappy", trusted_peers={
                "vn1": ("svc-vn1", "SHA256:vn1-fingerprint")
            })

    def test_same_message_id_from_other_peer_fails_closed(self):
        admitted = HostPeerStore(self.bob_path, local_host="vn1", trusted_peers={
            "lappy": ("svc-lappy", "SHA256:lappy-fingerprint"),
            "vn2": ("svc-vn2", "SHA256:vn2-fingerprint"),
        })
        admitted.receive(self._packet(msg()), observed_peer=self.obs_a)
        second = self._packet(msg(source="vn2", target="vn1"))
        with self.assertRaisesRegex(HostPeerConflict, "collision"):
            admitted.receive(second, observed_peer=ObservedPeer(
                "vn2", "svc-vn2", "SHA256:vn2-fingerprint"))
        self.assertEqual(admitted.received_count(), 1)

    def test_two_processes_share_durable_inbox_without_duplicate_mutation(self):
        # Separate Python interpreters are not required for SQLite's durable
        # state semantics; two independent store instances read same file.
        packet = self._packet(msg())
        alt = HostPeerStore(self.bob_path, local_host="vn1", trusted_peers={
            "lappy": ("svc-lappy", "SHA256:lappy-fingerprint")
        })
        ack1 = self.b.receive(packet, observed_peer=self.obs_a)
        ack2 = alt.receive(packet, observed_peer=self.obs_a)
        self.assertEqual(ack1, ack2)
        self.assertEqual(alt.received_count(), 1)

    @staticmethod
    def _packet(message):
        from intranel.canonical import canonical_json_bytes
        return canonical_json_bytes(message)


if __name__ == "__main__":
    unittest.main()
