"""No-effect Intranel four-role inbox tests."""
import concurrent.futures
import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from intranel.coordination import (
    CoordinationConflict, LocalCoordinationInbox, unwrap, wrap,
)
from intranel.message import parse_message
from intranel.types import EffectClass, Performative

def request(target="vera:integration"):
    return parse_message({
        "protocol":"INTRANEL/1",
        "origin":"vera:portal",
        "actor":"vera:portal",
        "target":target,
        "reply_to":"vera:portal",
        "message_id":"coord-msg-1",
        "conversation_id":"coord-20261016",
        "performative":"REQUEST",
        "exact_subject":"sha256:"+"a"*64,
        "payload":{"role":"integration","claim_type":"source",
                   "finding":"Review pinned branch, no effects"},
        "effect_class":"READ_ONLY",
        "security_profile":"OPEN",
    })

class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"inbox.sqlite3"
        self.inbox = LocalCoordinationInbox(self.path,expected_target="vera:integration")

    def test_canonical_round_trip(self):
        msg=request()
        self.assertEqual(unwrap(wrap(msg)),msg)

    def test_staging_is_explicitly_not_delivery(self):
        data=wrap(request())
        self.assertEqual(self.inbox.stage(data),"STAGED_UNATTESTED")
        self.assertEqual(self.inbox.count(),1)
        self.assertEqual(self.inbox.get("coord-msg-1"),data)
        reopened=LocalCoordinationInbox(self.path,expected_target="vera:integration")
        self.assertEqual(reopened.count(),1)

    def test_repeat_same_packet_idempotent(self):
        data=wrap(request())
        self.assertEqual(self.inbox.stage(data),"STAGED_UNATTESTED")
        self.assertEqual(self.inbox.stage(data),"DUPLICATE")
        self.assertEqual(self.inbox.count(),1)

    def test_edited_payload_without_new_digest_rejected(self):
        data=wrap(request())
        data["semantic_message"]["payload"]["finding"]="Injected effect"
        with self.assertRaises(CoordinationConflict):
            self.inbox.stage(data)

    def test_reused_message_identity_different_semantics_conflicts(self):
        data=wrap(request())
        self.inbox.stage(data)
        changed=copy.deepcopy(data["semantic_message"])
        changed["payload"]["finding"]="different wording"
        with self.assertRaises(CoordinationConflict):
            self.inbox.stage(wrap(parse_message(changed)))
        self.assertEqual(self.inbox.count(),1)

    def test_wrong_recipient_is_rejected(self):
        with self.assertRaisesRegex(CoordinationConflict,"wrong configured"):
            self.inbox.stage(wrap(request("vera:training")))

    def test_mutating_effect_and_execution_request_rejected(self):
        with self.assertRaises(CoordinationConflict):
            wrap(replace(request(),effect_class=EffectClass.REVERSIBLE_MUTATION))
        with self.assertRaises(CoordinationConflict):
            wrap(replace(request(),performative=Performative.EXECUTE))

    def test_unadmitted_role_rejected(self):
        with self.assertRaises(CoordinationConflict):
            wrap(replace(request(),origin=type(request().origin).parse('vera:rogue')))

    def test_unknown_wrapper_field_rejected(self):
        data=wrap(request())
        data["privilege"]="ROOT"
        with self.assertRaises(CoordinationConflict):
            self.inbox.stage(data)

    def test_missing_ack_parent_rejected(self):
        data=request().to_mapping()
        data.update(message_id="ack-1",origin="vera:integration",
                    target="vera:integration",actor="vera:integration",
                    performative="ACK",parent_message_id=None)
        with self.assertRaisesRegex(CoordinationConflict,"ACK requires"):
            self.inbox.stage(wrap(parse_message(data)))

    def test_parallel_relay_is_idempotent(self):
        data=wrap(request())
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results=list(pool.map(self.inbox.stage,[data]*12))
        self.assertEqual(results.count("STAGED_UNATTESTED"),1)
        self.assertEqual(results.count("DUPLICATE"),11)
        self.assertEqual(self.inbox.count(),1)

if __name__=="__main__":
    unittest.main()
