"""Negative tests: PORTAL's staging store versus Integration's causal observer."""
from __future__ import annotations
import sqlite3
import subprocess
import os
import sys
import json
from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from intranel import content_digest, parse_message
from intranel.coordination import LocalCoordinationInbox, wrap
from intranel.four_role_ledger import FourRoleLedger
from intranel.four_role_reconcile import audit_local_inbox
from test_four_role_ledger import request, reply, CONVERSATION


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.observed = self.dir / "observed.sqlite3"
        self.staged = self.dir / "portal.sqlite3"
        self.ledger = FourRoleLedger(self.observed)
        self.inbox = LocalCoordinationInbox(self.staged, expected_target="vera:portal")

    def stage_reply(self, message):
        self.assertEqual(self.inbox.stage(wrap(parse_message(message))),
                         "STAGED_UNATTESTED")

    def audit(self):
        return audit_local_inbox(self.observed, self.staged, expected_target="vera:portal")

    def test_both_stores_agree_only_as_untrusted_source_view(self):
        req = request()
        ack = reply(req)
        self.ledger.observe(req, "github:request")
        self.ledger.observe(ack, "github:ack")
        self.stage_reply(ack)
        result = self.audit()
        self.assertEqual(result["classification"], "SNAPSHOT_AGREEMENT_UNATTESTED")
        self.assertEqual(result["compared"], 1)
        self.assertEqual(result["differences"], [])
        self.assertFalse(result["delivered"])
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["ack_accepted"])
        self.assertFalse(result["atomic_cross_store_transaction"])

    def test_crash_between_observe_and_staging_holds_then_recovers(self):
        req = request()
        ack = reply(req)
        self.ledger.observe(req, "github:request")
        self.ledger.observe(ack, "github:ack")
        self.assertEqual(self.audit()["classification"], "HOLD_STORE_DIVERGENCE")
        self.assertIn("OBSERVATION_ONLY", {i["type"] for i in self.audit()["differences"]})
        self.stage_reply(ack)
        self.assertEqual(self.audit()["classification"], "SNAPSHOT_AGREEMENT_UNATTESTED")

    def test_staging_only_never_counts_as_causal_observation(self):
        ack = reply(request())
        self.stage_reply(ack)
        result = self.audit()
        self.assertEqual(result["classification"], "HOLD_STORE_DIVERGENCE")
        self.assertIn("STAGING_ONLY", {i["type"] for i in result["differences"]})

    def test_conflicting_parent_identity_revokes_apparent_store_agreement(self):
        req = request()
        ack = reply(req)
        self.ledger.observe(req, "github:original")
        self.ledger.observe(ack, "github:reply")
        self.stage_reply(ack)
        self.assertEqual(self.audit()["classification"], "SNAPSHOT_AGREEMENT_UNATTESTED")
        changed = request(payload={"task": "same id with changed source"})
        self.ledger.observe(changed, "github:collision")
        result = self.audit()
        self.assertEqual(result["classification"], "HOLD_STORE_DIVERGENCE")
        self.assertIn("CAUSAL_REPLY_UNQUALIFIED", {i["type"] for i in result["differences"]})

    def test_tampered_inbox_digest_is_not_trusted(self):
        req = request()
        ack = reply(req)
        self.ledger.observe(req, "github:parent")
        self.ledger.observe(ack, "github:reply")
        self.stage_reply(ack)
        with closing(sqlite3.connect(self.staged)) as db, db:
            db.execute("UPDATE messages SET semantic_sha256=? WHERE message_id=?",
                       ("0" * 64, "reply-1"))
        self.assertEqual(self.audit()["classification"], "HOLD_STORE_DIVERGENCE")
        self.assertIn("INBOX_DIGEST_MISMATCH", {i["type"] for i in self.audit()["differences"]})

    def test_missing_files_must_not_be_created_by_audit(self):
        absent = self.dir / "not-created.sqlite"
        with self.assertRaises(ValueError):
            audit_local_inbox(self.observed, absent, expected_target="vera:portal")
        self.assertFalse(absent.exists())

    def test_duplicate_claim_from_same_role_blocks_store_agreement(self):
        req = request()
        first = reply(req, message_id="one")
        second = reply(req, message_id="two")
        self.ledger.observe(req, "github:request")
        self.ledger.observe(first, "github:first")
        self.stage_reply(first)
        self.assertEqual(self.audit()["classification"], "SNAPSHOT_AGREEMENT_UNATTESTED")
        self.ledger.observe(second, "github:second")
        result = self.audit()
        self.assertEqual(result["classification"], "HOLD_STORE_DIVERGENCE")
        types = {d["type"] for d in result["differences"]}
        self.assertIn("CAUSAL_REPLY_UNQUALIFIED", types)
        self.assertIn("OBSERVATION_ONLY", types)

    def test_global_message_id_reuse_across_rounds_is_detected(self):
        req = request()
        ack = reply(req)
        self.ledger.observe(req, "github:req")
        self.ledger.observe(ack, "github:ack")
        self.stage_reply(ack)
        another = reply(request(conversation_id="other-round"),
                        conversation_id="other-round")
        self.ledger.observe(another, "github:other-round")
        result = self.audit()
        self.assertEqual(result["classification"], "HOLD_STORE_DIVERGENCE")
        self.assertIn("CROSS_ROUND_MESSAGE_ID_REUSED",
                      {d["type"] for d in result["differences"]})

    def test_two_empty_stores_cannot_establish_coordination(self):
        empty = self.audit()
        self.assertEqual(empty["classification"], "HOLD_EMPTY_SNAPSHOT")
        self.assertFalse(empty["ack_accepted"])

    def test_subprocess_reconciliation_readback_and_missing_path(self):
        req = request()
        ack = reply(req)
        self.ledger.observe(req, "github:req")
        self.ledger.observe(ack, "github:ack")
        self.stage_reply(ack)
        command = [
            sys.executable, "-B", "-m", "intranel.four_role_cli", "reconcile",
            "--ledger", str(self.observed),
            "--staging-ledger", str(self.staged),
            "--expected-target", "vera:portal",
        ]
        env = {**os.environ, "PYTHONDONTWRITEBYTE": "1"}
        result = subprocess.run(command, capture_output=True, text=True,
                                env=env, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["classification"], "SNAPSHOT_AGREEMENT_UNATTESTED")
        self.assertFalse(data["atomic_cross_store_transaction"])
        self.assertFalse(data["ack_accepted"])
        # Opening a nonexistent ledger in reconciliation mode must not create it.
        missing = self.dir / "absent-db.sqlite"
        bad = list(command)
        bad[bad.index("--ledger") + 1] = str(missing)
        denied = subprocess.run(bad, capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(json.loads(denied.stderr)["status"], "HELD")
        self.assertFalse(missing.exists())

    def test_wrong_target_binding_is_rejected(self):
        req = request()
        ack = reply(req)
        self.ledger.observe(req, "github:parent")
        self.ledger.observe(ack, "github:reply")
        self.stage_reply(ack)
        with self.assertRaises(ValueError):
            audit_local_inbox(self.observed, self.staged, expected_target="vera:integration")


if __name__ == "__main__":
    unittest.main()
