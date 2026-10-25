"""Receiver-owned atomic staging and observation: crash/replay adversarial tests."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import sqlite3

from intranel import parse_message
from intranel.canonical import canonical_json_bytes, content_digest
from intranel.coordination import wrap
from intranel.four_role_ledger import CoordinationError
from intranel.four_role_receiver import AtomicRoleReceiver
from test_four_role_ledger import request, reply, CONVERSATION


class AtomicRoleReceiverTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "receiver.sqlite3"
        self.receiver = AtomicRoleReceiver(self.path, expected_target="vera:portal")
        self.req = request()
        self.reply = reply(self.req)
        self.receiver.observe_outbound_request(self.req, "outgoing:portal/request")

    def _packet(self, native):
        return wrap(parse_message(native))

    def _rows(self):
        with closing(sqlite3.connect(self.path)) as db:
            return (
                db.execute("SELECT count(*) FROM observed WHERE message_id='reply-1'").fetchone()[0],
                db.execute("SELECT count(*) FROM receiver_staged WHERE message_id='reply-1'").fetchone()[0],
            )

    def test_one_receiver_db_commits_reply_and_receipt_or_neither(self):
        with patch.object(self.receiver, "_after_observation_before_stage", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                self.receiver.receive(self._packet(self.reply), "github:comment/1")
        self.assertEqual(self._rows(), (0, 0))
        recovered = AtomicRoleReceiver(self.path, expected_target="vera:portal")
        first = recovered.receive(self._packet(self.reply), "github:comment/1")
        self.assertEqual(first["ingest"], "OBSERVED_NEW")
        self.assertEqual(first["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")
        self.assertEqual(self._rows(), (1, 1))
        replay = recovered.receive(self._packet(self.reply), "github:comment/1")
        self.assertEqual(replay["ingest"], "DUPLICATE")
        self.assertFalse(replay["ack_accepted"])
        self.assertFalse(replay["delivered"])

    def test_existing_unpaired_observation_holds_not_backfilled(self):
        with self.assertRaises(CoordinationError):
            self.receiver.observe(self.reply, "legacy:observer-only")
        # Existing orphan evidence can still be present after a migration.
        m = parse_message(self.reply)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO observed "
                "(conversation_id,message_id,content,digest,source_ref,observed_at) "
                "VALUES(?,?,?,?,?,?)",
                (m.conversation_id, m.message_id, canonical_json_bytes(m),
                 content_digest(m), "legacy:observer-only", "prior-to-migration"),
            )
        with self.assertRaisesRegex(CoordinationError, "unpaired"):
            self.receiver.receive(self._packet(self.reply), "github:comment/2")
        self.assertEqual(self._rows(), (1, 0))

    def test_changed_message_id_preserves_collision_and_poisoned_reply(self):
        self.receiver.receive(self._packet(self.reply), "github:comment/3")
        altered = deepcopy(self.reply)
        altered["payload"]["finding"] = "changed"
        result = self.receiver.receive(self._packet(altered), "github:edited/3")
        self.assertEqual(result["ingest"], "CONFLICT")
        self.assertEqual(result["classification"], "IDENTITY_COLLISION")
        self.assertEqual(self._rows(), (1, 1))
        self.assertEqual(self.receiver.counts()["collisions"], 1)

    def test_wrong_receiver_and_cross_round_reuse_fail_closed(self):
        other = AtomicRoleReceiver(self.path, expected_target="vera:portal")
        with self.assertRaises(CoordinationError):
            other.receive(self._packet(self.req), "github:wrong-target")
        with self.assertRaises(CoordinationError):
            AtomicRoleReceiver(self.path, expected_target="vera:training")
        self.receiver.receive(self._packet(self.reply), "github:comment/4")
        later = deepcopy(self.reply)
        later["conversation_id"] = "second-round"
        with self.assertRaisesRegex(CoordinationError, "cross-round"):
            self.receiver.receive(self._packet(later), "github:comment/5")
        self.assertEqual(self._rows(), (1, 1))

    def test_staged_packet_tampering_blocks_replay(self):
        self.receiver.receive(self._packet(self.reply), "github:comment/6")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE receiver_staged SET envelope='{}' WHERE message_id='reply-1'")
        with self.assertRaisesRegex(CoordinationError, "staged receipt"):
            self.receiver.receive(self._packet(self.reply), "github:comment/6")
        self.assertEqual(self._rows(), (1, 1))

    def test_no_attested_identity_or_effect_even_when_causally_matched(self):
        status = self.receiver.receive(self._packet(self.reply), "github:comment/7")
        for key in ("origin_authenticated", "delivered", "ack_accepted", "executed"):
            self.assertIs(status[key], False)
        self.assertEqual(status["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")

    def test_expired_reply_is_held_even_with_valid_staging_and_parent(self):
        expired = deepcopy(self.reply)
        expired["expires_at"] = "2000-01-01T00:00:00Z"
        outcome = self.receiver.receive(self._packet(expired), "github:late")
        self.assertEqual(outcome["classification"], "EXPIRED_REPLY")
        self.assertFalse(outcome["ack_accepted"])
        self.assertEqual(self.receiver.classify(CONVERSATION, "reply-1")["classification"],
                         "EXPIRED_REPLY")


    def test_parallel_same_packet_exactly_one_initial_commit(self):
        from concurrent.futures import ThreadPoolExecutor
        packet = self._packet(self.reply)
        with ThreadPoolExecutor(max_workers=8) as workers:
            outcomes = list(workers.map(
                lambda n: self.receiver.receive(packet, f"github:comment/{n}"),
                range(8),
            ))
        self.assertEqual(sum(r["ingest"] == "OBSERVED_NEW" for r in outcomes), 1)
        self.assertEqual(sum(r["ingest"] == "DUPLICATE" for r in outcomes), 7)
        self.assertEqual(self._rows(), (1, 1))

    def test_competing_replies_remain_distinct_and_unaccepted(self):
        other = deepcopy(self.reply)
        other["message_id"] = "reply-2"
        self.receiver.receive(self._packet(self.reply), "github:comment/11")
        self.receiver.receive(self._packet(other), "github:comment/12")
        for mid in ("reply-1", "reply-2"):
            current = AtomicRoleReceiver(self.path, expected_target="vera:portal")
            self.assertEqual(
                current.classify(CONVERSATION, mid)["classification"],
                "MULTIPLE_REPLY_CLAIMS_RECONCILIATION_REQUIRED",
            )
        self.assertEqual(self.receiver.receiver_counts()["staged"], 2)

    def test_actual_child_process_death_between_inserts_rolls_back(self):
        import json
        import subprocess
        import sys
        script = (
            "import json,os,sys;"
            "from intranel.four_role_receiver import AtomicRoleReceiver;"
            "r=AtomicRoleReceiver(sys.argv[1],expected_target='vera:portal');"
            "r._after_observation_before_stage=lambda:os._exit(77);"
            "r.receive(json.loads(sys.argv[2]),'child:before-commit')"
        )
        child = subprocess.run(
            [sys.executable, "-B", "-c", script, str(self.path),
             json.dumps(self._packet(self.reply))],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(child.returncode, 77, child.stderr)
        self.assertEqual(self._rows(), (0, 0))
        recovered = AtomicRoleReceiver(self.path, expected_target="vera:portal")
        self.assertEqual(
            recovered.receive(self._packet(self.reply), "child:replay")["ingest"],
            "OBSERVED_NEW",
        )
        self.assertEqual(self._rows(), (1, 1))


    def test_atomic_local_comment_marker_crash_and_replay(self):
        source = "github:thebrazenbeard/intranel#9/comment/42"
        before = self.receiver.comment_packet_checkpoint()
        self.assertEqual(before["packet_markers"], 0)
        self.assertIsNone(before["highest_packet_comment_id"])
        with patch.object(self.receiver, "_after_stage_before_comment_checkpoint",
                          side_effect=RuntimeError("checkpoint crash")):
            with self.assertRaisesRegex(RuntimeError, "checkpoint crash"):
                self.receiver.receive(self._packet(self.reply), source, comment_id=42)
        self.assertEqual(self._rows(), (0, 0))
        self.assertEqual(
            AtomicRoleReceiver(self.path, expected_target="vera:portal")
                .comment_packet_checkpoint()["packet_markers"], 0,
        )
        reopened = AtomicRoleReceiver(self.path, expected_target="vera:portal")
        out = reopened.receive(self._packet(self.reply), source, comment_id=42)
        self.assertEqual(out["ingest"], "OBSERVED_NEW")
        self.assertEqual(out["comment_checkpoint"], "LOCAL_PACKET_ONLY_UNATTESTED")
        self.assertEqual(self._rows(), (1, 1))
        after = reopened.comment_packet_checkpoint()
        self.assertEqual(after["packet_markers"], 1)
        self.assertEqual(after["highest_packet_comment_id"], 42)
        self.assertFalse(after["coverage_complete"])
        self.assertFalse(after["origin_authenticated"])
        replay = reopened.receive(self._packet(self.reply), source, comment_id=42)
        self.assertEqual(replay["ingest"], "DUPLICATE")
        self.assertEqual(reopened.comment_packet_checkpoint(), after)

    def test_unknown_older_comment_and_unpaired_checkpoint_hold(self):
        source = "github:thebrazenbeard/intranel#9/comment/50"
        self.receiver.receive(self._packet(self.reply), source, comment_id=50)
        other = deepcopy(self.reply)
        other["message_id"] = "reply-2"
        with self.assertRaisesRegex(CoordinationError, "late unrecognized"):
            self.receiver.receive(
                self._packet(other),
                "github:thebrazenbeard/intranel#9/comment/49",
                comment_id=49,
            )
        self.assertEqual(self.receiver.comment_packet_checkpoint()["packet_markers"], 1)
        with self.assertRaisesRegex(CoordinationError, "locator mismatch"):
            self.receiver.receive(self._packet(other), "github:comment/51", comment_id=51)
        with self.assertRaisesRegex(CoordinationError, "locator mismatch"):
            self.receiver.receive(self._packet(other), source, comment_id=True)

    def test_legacy_staged_reply_cannot_acquire_comment_marker_on_replay(self):
        packet = self._packet(self.reply)
        source = "github:thebrazenbeard/intranel#9/comment/60"
        self.receiver.receive(packet, source)
        with self.assertRaisesRegex(CoordinationError, "unpaired comment"):
            self.receiver.receive(packet, source, comment_id=60)
        self.assertEqual(self._rows(), (1, 1))
        self.assertEqual(self.receiver.comment_packet_checkpoint()["packet_markers"], 0)


    def test_exact_comment_packet_evidence_does_not_claim_sender_or_provider(self):
        ref = "github:thebrazenbeard/intranel#9/comment/81"
        self.receiver.receive(self._packet(self.reply), ref, comment_id=81)
        current = self.receiver.read_comment_packet_evidence(81, "reply-1")
        self.assertEqual(current["conversation_id"], CONVERSATION)
        self.assertEqual(current["receiver_target"], "vera:portal")
        self.assertTrue(current["local_pair_verified"])
        self.assertFalse(current["origin_authenticated"])
        self.assertFalse(current["provider_snapshot_attested"])
        self.assertFalse(current["ack_accepted"])
        with self.assertRaisesRegex(CoordinationError, "not locally checkpointed"):
            self.receiver.read_comment_packet_evidence(82, "reply-1")
        with self.assertRaisesRegex(CoordinationError, "invalid packet evidence key"):
            self.receiver.read_comment_packet_evidence(True, "reply-1")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE receiver_staged SET semantic_sha256=? WHERE message_id='reply-1'",
                       ("0"*64,))
        with self.assertRaisesRegex(CoordinationError, "does not match"):
            self.receiver.read_comment_packet_evidence(81, "reply-1")

    def test_collided_message_must_not_return_clean_local_packet_evidence(self):
        from copy import deepcopy
        source = "github:thebrazenbeard/intranel#9/comment/91"
        self.receiver.receive(self._packet(self.reply), source, comment_id=91)
        self.assertTrue(
            self.receiver.read_comment_packet_evidence(91, "reply-1")["local_pair_verified"]
        )
        edited = deepcopy(self.reply)
        edited["payload"]["finding"] = "edited packet identity"
        conflict = self.receiver.receive(
            self._packet(edited),
            "github:thebrazenbeard/intranel#9/comment/92", comment_id=92,
        )
        self.assertEqual(conflict["ingest"], "CONFLICT")
        self.assertEqual(conflict["classification"], "IDENTITY_COLLISION")
        with self.assertRaisesRegex(CoordinationError, "collision"):
            self.receiver.read_comment_packet_evidence(91, "reply-1")


    def test_local_checkpoint_readback_rechecks_staged_and_observed_payloads(self):
        # An at-rest mutation can leave digest + marker strings untouched.
        # The bridge must not see clean evidence from unverified body bytes.
        source = "github:thebrazenbeard/intranel#9/comment/93"
        self.receiver.receive(self._packet(self.reply), source, comment_id=93)
        with closing(sqlite3.connect(self.path)) as db:
            old_envelope = db.execute(
                "SELECT envelope FROM receiver_staged WHERE message_id='reply-1'"
            ).fetchone()[0]
            old_content = db.execute(
                "SELECT content FROM observed WHERE message_id='reply-1'"
            ).fetchone()[0]
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "UPDATE receiver_staged SET envelope=? WHERE message_id='reply-1'",
                ('{"spoofed":"frame"}',),
            )
        with self.assertRaisesRegex(CoordinationError, "staged|tampered|observation"):
            self.receiver.read_comment_packet_evidence(93, "reply-1")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "UPDATE receiver_staged SET envelope=? WHERE message_id='reply-1'",
                (old_envelope,),
            )
            db.execute(
                "UPDATE observed SET content=? WHERE message_id='reply-1'",
                ('{"spoofed":"observation"}',),
            )
        with self.assertRaisesRegex(CoordinationError, "staged|tampered|observation"):
            self.receiver.read_comment_packet_evidence(93, "reply-1")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "UPDATE observed SET content=? WHERE message_id='reply-1'",
                (old_content,),
            )
        self.assertTrue(
            self.receiver.read_comment_packet_evidence(93, "reply-1")["local_pair_verified"]
        )

    def test_staged_source_locator_tampering_blocks_pair_readback(self):
        source = "github:thebrazenbeard/intranel#9/comment/94"
        self.receiver.receive(self._packet(self.reply), source, comment_id=94)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "UPDATE receiver_staged SET source_ref=? WHERE message_id='reply-1'",
                ("forged:origin",),
            )
        with self.assertRaisesRegex(CoordinationError, "staged|source|evidence"):
            self.receiver.read_comment_packet_evidence(94, "reply-1")
        self.assertEqual(
            self.receiver.classify(CONVERSATION, "reply-1")["classification"],
            "HOLD_STAGED_RECEIPT_INVALID",
        )
        with self.assertRaisesRegex(CoordinationError, "staged|source"):
            self.receiver.receive(self._packet(self.reply), source, comment_id=94)

    def test_outbound_marker_source_locator_tamper_holds_request_and_reply(self):
        self.receiver.receive(self._packet(self.reply), "github:reply")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE receiver_outbound SET source_ref=? WHERE message_id='request-1'",
                       ("forged:outbound",))
        self.assertEqual(
            self.receiver.classify(CONVERSATION, "request-1")["classification"],
            "HOLD_UNMARKED_OUTBOUND_REQUEST",
        )
        self.assertEqual(
            self.receiver.classify(CONVERSATION, "reply-1")["classification"],
            "HOLD_UNMARKED_PARENT_REQUEST",
        )
        with self.assertRaisesRegex(CoordinationError, "outbound request conflicts"):
            self.receiver.observe_outbound_request(self.req, "outgoing:portal/request")
