"""Executable adversarial tests of Intranel four-role causal observations."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from intranel import parse_message, content_digest
from intranel.four_role_ledger import FourRoleLedger, CoordinationError

SUBJECT = "git:thebrazenbeard/intranel@9b943a98273a6f0f0c04fa5a642ea002f1c9fc9a"
CONVERSATION = "pilot-intranel-round-001"

def request(target: str = "vera:integration", **changes) -> dict:
    p = {
        "protocol": "INTRANEL/1", "origin": "vera:portal",
        "actor": "vera:portal", "target": target, "reply_to": "vera:portal",
        "message_id": "request-1", "conversation_id": CONVERSATION,
        "performative": "REQUEST", "exact_subject": SUBJECT,
        "operation_id": "four-role-pilot-1", "payload": {"task": "review exact PR head"},
        "ack_required": True, "expected_response": "ACK",
        "effect_class": "READ_ONLY", "security_profile": "OPEN"
    }
    p.update(changes)
    return p

def reply(req: dict, performative: str = "ACK", **changes) -> dict:
    from_role = req["target"]
    p = {
        "protocol": "INTRANEL/1", "origin": from_role,
        "actor": from_role, "target": "vera:portal", "reply_to": from_role,
        "message_id": "reply-1", "conversation_id": req["conversation_id"],
        "parent_message_id": req["message_id"], "operation_id": req["operation_id"],
        "performative": performative, "exact_subject": req["exact_subject"],
        "payload": {"request_digest": content_digest(parse_message(req)),
                    "finding": "saw proposed source; no authority"},
        "effect_class": "READ_ONLY", "security_profile": "OPEN"
    }
    p.update(changes)
    return p

class FourRoleLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "observed.sqlite3"
        self.ledger = FourRoleLedger(self.file)

    def test_request_then_reply_and_process_restart_remain_untrusted(self):
        req=request()
        self.assertEqual(self.ledger.observe(req, "github:intranel/pr9/comment1")["classification"],
                         "REQUEST_STAGED_UNDELIVERED")
        ans=self.ledger.observe(reply(req), "github:intranel/pr9/comment2")
        self.assertEqual(ans["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")
        self.assertFalse(ans["ack_accepted"])
        self.assertFalse(ans["origin_authenticated"])
        self.assertFalse(ans["delivered"])
        self.assertFalse(ans["executed"])
        replay=FourRoleLedger(self.file).classify(CONVERSATION, "reply-1")
        self.assertEqual(replay["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")
        self.assertEqual(replay["parent_request_digest"], content_digest(parse_message(req)))

    def test_out_of_order_reply_reclassified_only_after_parent_observed(self):
        req=request()
        first=self.ledger.observe(reply(req), "github:comment2")
        self.assertEqual(first["classification"], "UNMATCHED_REPLY")
        self.ledger.observe(req,"github:comment1")
        self.assertEqual(self.ledger.classify(CONVERSATION,"reply-1")["classification"],
                         "CAUSALLY_MATCHED_UNAUTHENTICATED")

    def test_wrong_parent_wrong_subject_wrong_origin_and_wrong_digest(self):
        req=request()
        self.ledger.observe(req,"github:req")
        wrongs=[
            reply(req,parent_message_id="made-up",message_id="r1"),
            reply(req,exact_subject="git:thebrazenbeard/intranel@"+"a"*40,message_id="r2"),
            reply(req,origin="vera:training",actor="vera:training",
                  reply_to="vera:training",message_id="r3"),
            reply(req,payload={"request_digest":"f"*64},message_id="r4"),
            reply(req,operation_id="wrong-operation",message_id="r5"),
            reply(req,conversation_id="different-round",message_id="r6"),
        ]
        expected=[
            "UNMATCHED_REPLY", "CAUSAL_CONFLICT", "CAUSAL_CONFLICT",
            "CAUSAL_CONFLICT", "CAUSAL_CONFLICT", "UNMATCHED_REPLY"
        ]
        for item, want in zip(wrongs,expected):
            with self.subTest(item=item["message_id"]):
                got=self.ledger.observe(item,"github:reply")
                self.assertEqual(got["classification"],want)
                self.assertFalse(got["ack_accepted"])

    def test_replay_and_same_identity_new_bytes_are_distinct(self):
        req=request()
        self.assertEqual(self.ledger.observe(req,"github:1")["ingest"],"OBSERVED_NEW")
        self.assertEqual(self.ledger.observe(req,"github:1-new-path")["ingest"],"DUPLICATE")
        change=deepcopy(req)
        change["payload"]["task"]="opposite instruction"
        denied=self.ledger.observe(change,"github:collision")
        self.assertEqual(denied["ingest"],"CONFLICT")
        self.assertEqual(denied["classification"],"IDENTITY_COLLISION")
        self.assertEqual(self.ledger.counts(),{"observations":1,"collisions":1})
        self.assertEqual(self.ledger.classify(CONVERSATION,"request-1")["classification"],
                         "IDENTITY_COLLISION")
        self.assertEqual(FourRoleLedger(self.file).classify(CONVERSATION,"request-1")["classification"],
                         "IDENTITY_COLLISION")

    def test_poisoned_parent_request_revokes_earlier_matched_ack(self):
        # A replayed REQUEST identity with conflicting semantics must poison
        # every child response, including already recorded/cached-looking ACKs.
        req = request()
        child = reply(req)
        self.ledger.observe(req, "github:portal-original")
        first = self.ledger.observe(child, "github:untrusted-ack")
        self.assertEqual(first["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")
        forged = deepcopy(req)
        forged["payload"]["task"] = "attacker changed coordinator request"
        collision = self.ledger.observe(forged, "github:spoofed-portal")
        self.assertEqual(collision["classification"], "IDENTITY_COLLISION")
        refreshed = self.ledger.classify(CONVERSATION, "reply-1")
        self.assertEqual(refreshed["classification"], "PARENT_IDENTITY_COLLISION")
        self.assertFalse(refreshed["ack_accepted"])
        self.assertFalse(refreshed["delivered"])
        restarted = FourRoleLedger(self.file).classify(CONVERSATION, "reply-1")
        self.assertEqual(restarted["classification"], "PARENT_IDENTITY_COLLISION")

    def test_out_of_order_child_of_poisoned_parent_never_correlates(self):
        req = request()
        child = reply(req)
        self.assertEqual(self.ledger.observe(child, "github:reply")["classification"],
                         "UNMATCHED_REPLY")
        self.ledger.observe(req, "github:request")
        forged = deepcopy(req)
        forged["payload"]["task"] = "conflicting request"
        self.ledger.observe(forged, "github:collision")
        self.assertEqual(self.ledger.classify(CONVERSATION, "reply-1")["classification"],
                         "PARENT_IDENTITY_COLLISION")

    def test_two_distinct_reply_claims_same_role_and_parent_require_reconciliation(self):
        req = request()
        self.ledger.observe(req, "github:portal-request")
        first = reply(req, message_id="ack-integration-original")
        second = reply(req, message_id="ack-integration-update",
                       payload={"request_digest": content_digest(parse_message(req)),
                                "finding": "updated evidence, same responder"})
        self.assertEqual(
            self.ledger.observe(first, "github:first")["classification"],
            "CAUSALLY_MATCHED_UNAUTHENTICATED")
        second_seen = self.ledger.observe(second, "github:second")
        self.assertEqual(second_seen["classification"],
                         "MULTIPLE_REPLY_CLAIMS_RECONCILIATION_REQUIRED")
        original = FourRoleLedger(self.file).classify(CONVERSATION, "ack-integration-original")
        self.assertEqual(original["classification"],
                         "MULTIPLE_REPLY_CLAIMS_RECONCILIATION_REQUIRED")
        for seen in (second_seen, original):
            self.assertFalse(seen["ack_accepted"])
            self.assertFalse(seen["delivered"])
        self.assertEqual(self.ledger.counts()["observations"], 3)

    def test_unparented_ack_protected_effect_and_unpinned_subject_fail_closed(self):
        req=request()
        for item in (
            reply(req,parent_message_id=None),
            reply(req,payload={"finding":"no digest"}),
            request(exact_subject="main"),
            request(effect_class="PROTECTED_MUTATION"),
            request(authority_claim_ref="self-approval"),
            request(origin="vera:training",actor="vera:training"),
        ):
            with self.subTest(payload=item):
                with self.assertRaises((CoordinationError,ValueError)):
                    self.ledger.observe(item,"github:untrusted")
        self.assertEqual(self.ledger.counts()["observations"],0)

    def test_cannot_crossbind_other_peer_or_forge_completion(self):
        req=request(target="vera:vn1")
        self.ledger.observe(req,"github:portal-request")
        other=reply(req,origin="vera:training",actor="vera:training",reply_to="vera:training")
        self.assertEqual(self.ledger.observe(other,"github:training")["classification"],
                         "CAUSAL_CONFLICT")
        proper=reply(req,message_id="reply-vn1",performative="WAIT")
        got=self.ledger.observe(proper,"github:vn1")
        self.assertEqual(got["reply_performative"],"WAIT")
        self.assertFalse(got["delivered"])
        self.assertFalse(got["ack_accepted"])

    def test_composes_with_portal_existing_local_coordination_inbox(self):
        # PORTAL's PR #9 added a different recipient-owned inbox. This test
        # proves source envelope interoperability without treating either
        # local STAGED_UNATTESTED receipt as delivery or acceptance.
        from intranel.coordination import LocalCoordinationInbox, wrap, unwrap
        req = request()
        receiver = LocalCoordinationInbox(
            self.file.parent / "integration-stage.sqlite3",
            expected_target="vera:integration",
        )
        self.assertEqual(receiver.stage(wrap(parse_message(req))), "STAGED_UNATTESTED")
        stored = receiver.get("request-1")
        self.assertIsNotNone(stored)
        observed = self.ledger.observe(
            unwrap(stored).to_mapping(), "integration:local-stage",
        )
        self.assertEqual(observed["classification"], "REQUEST_STAGED_UNDELIVERED")
        ack = reply(req)
        portal = LocalCoordinationInbox(
            self.file.parent / "portal-stage.sqlite3",
            expected_target="vera:portal",
        )
        self.assertEqual(portal.stage(wrap(parse_message(ack))), "STAGED_UNATTESTED")
        seen = self.ledger.observe(
            unwrap(portal.get("reply-1")).to_mapping(), "portal:local-stage",
        )
        self.assertEqual(seen["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")
        self.assertFalse(seen["ack_accepted"])
        self.assertFalse(seen["delivered"])

    def test_expired_request_cannot_be_accepted_as_fresh(self):
        before=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        req=request(expires_at=before)
        self.ledger.observe(req,"github:stale")
        result=self.ledger.observe(reply(req),"github:late")
        self.assertEqual(result["classification"],"EXPIRED_REQUEST")

    def test_expired_reply_is_not_causally_matched_to_live_request(self):
        req = request()
        self.ledger.observe(req, "github:request")
        stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        result = self.ledger.observe(reply(req, expires_at=stale), "github:late-reply")
        self.assertEqual(result["classification"], "EXPIRED_REPLY")
        self.assertFalse(result["ack_accepted"])

    def test_modified_persisted_content_never_reuses_original_digest(self):
        for altered in ("request-1", "reply-1"):
            with self.subTest(altered=altered):
                db_path = self.file.parent / (altered + ".sqlite3")
                ledger = FourRoleLedger(db_path)
                req = request()
                ledger.observe(req, "github:parent")
                ledger.observe(reply(req), "github:child")
                self.assertEqual(ledger.classify(CONVERSATION, "reply-1")["classification"],
                                 "CAUSALLY_MATCHED_UNAUTHENTICATED")
                mutated = deepcopy(req if altered == "request-1" else reply(req))
                mutated["payload"]["task" if altered == "request-1" else "finding"] = "tampered"
                with closing(sqlite3.connect(db_path)) as db, db:
                    db.execute("UPDATE observed SET content=? WHERE conversation_id=? AND message_id=?",
                               (json.dumps(mutated).encode("utf-8"), CONVERSATION, altered))
                with self.assertRaisesRegex(CoordinationError, "stored observation integrity"):
                    ledger.classify(CONVERSATION, "reply-1")
                cmd = [sys.executable, "-B", "-m", "intranel.four_role_cli", "inspect",
                       "--ledger", str(db_path), "--conversation-id", CONVERSATION,
                       "--message-id", "reply-1"]
                proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(json.loads(proc.stderr)["status"], "HELD")

    def test_mutated_sibling_cannot_erase_competing_reply_claim(self):
        req = request()
        first = reply(req)
        second = reply(req, message_id="reply-2")
        self.ledger.observe(req, "github:parent")
        self.ledger.observe(first, "github:one")
        self.ledger.observe(second, "github:two")
        self.assertEqual(self.ledger.classify(CONVERSATION, "reply-1")["classification"],
                         "MULTIPLE_REPLY_CLAIMS_RECONCILIATION_REQUIRED")
        altered = deepcopy(second)
        altered["parent_message_id"] = "another-parent"
        with closing(sqlite3.connect(self.file)) as db, db:
            db.execute("UPDATE observed SET content=? WHERE message_id=?",
                       (json.dumps(altered).encode("utf-8"), "reply-2"))
        with self.assertRaisesRegex(CoordinationError, "stored observation integrity"):
            self.ledger.classify(CONVERSATION, "reply-1")

    def test_case_sensitive_subject_aliases_stay_separate(self):
        req=request()
        self.ledger.observe(req,"github:portal")
        got=self.ledger.observe(
            reply(req,exact_subject="git:thebrazenbeard/intranel@"+"9b943a98273a6f0f0c04fa5a642ea002f1c9fc9a",
                  message_id="same"),"github:matching")
        self.assertEqual(got["classification"],"CAUSALLY_MATCHED_UNAUTHENTICATED")
        alias=reply(req,exact_subject="git:other-team/intranel@"+"9b943a98273a6f0f0c04fa5a642ea002f1c9fc9a",
                    message_id="alias")
        self.assertEqual(self.ledger.observe(alias,"github:alias")["classification"],
                         "CAUSAL_CONFLICT")

if __name__ == "__main__":
    unittest.main()
