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
