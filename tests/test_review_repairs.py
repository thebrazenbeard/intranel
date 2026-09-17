import unittest
from intranel.admission import CancellationEvidence, ReceiverEvidence, admit
from intranel.canonical import canonical_json_bytes, content_digest
from intranel.message import parse_message
from intranel.types import AdmissionDecision, EffectClass

def base_message(**updates):
    raw={
        "protocol":"INTRANEL/1","origin":"vera:primary","actor":"vera:primary","target":"vera:lane/bv","reply_to":"bus:vera-v2",
        "message_id":"m1","operation_id":None,"target_operation_id":None,"parent_message_id":None,"conversation_id":"c1",
        "performative":"QUERY","subject":"repo:intranel","exact_subject":None,"payload":{"q":"status"},"authority_claim_ref":None,
        "constraints":[],"prohibited_effects":[],"expected_response":"REPORT","ack_required":False,"observed_at":None,"expires_at":None,
        "idempotency_key":None,"priority":3,"effect_class":"READ_ONLY","status":None,"error":None,"receipt":None,
        "security_profile":"OPEN","capabilities":[],"provenance":[]}
    raw.update(updates); return parse_message(raw)

def exec_message(**updates):
    raw=dict(message_id="me",operation_id="op1",performative="EXECUTE",exact_subject="sha256:"+"a"*64,
        authority_claim_ref="auth:x",idempotency_key="idem1",effect_class="REVERSIBLE_MUTATION",security_profile="PRIVATE",
        payload={"action":"append"})
    raw.update(updates)
    return base_message(**raw)

def good_evidence(message, effect=None):
    if effect is None:
        effect = message.effect_class if message.performative.value in {"EXECUTE","CANCEL"} else None
    return ReceiverEvidence.bind(message,effective_effect_class=effect,origin_authenticated=True,actor_authenticated=True,
        authority_valid=True,exact_subject_valid=True,replay_fresh=True,capabilities_supported=True,
        constraints_satisfied=True,prohibited_effects_clear=True,transport_security_satisfied=True)

class AdmissionRepairTests(unittest.TestCase):
    def test_sender_read_only_cannot_hide_receiver_computed_mutation(self):
        m=base_message(performative="EXECUTE",effect_class="READ_ONLY",payload={"action":"write"})
        e=good_evidence(m,effect=EffectClass.REVERSIBLE_MUTATION)
        self.assertIs(admit(m,e),AdmissionDecision.CONFLICT)

    def test_receiver_evidence_is_bound_to_exact_message(self):
        m1=exec_message(message_id="one")
        m2=exec_message(message_id="two")
        e=good_evidence(m1)
        self.assertIs(admit(m2,e),AdmissionDecision.CONFLICT)

    def test_constraints_unknown_quarantines_and_false_rejects(self):
        m=exec_message(constraints=["must-hold"])
        e=good_evidence(m).replace(constraints_satisfied=None)
        self.assertIs(admit(m,e),AdmissionDecision.QUARANTINE)
        self.assertIs(admit(m,e.replace(constraints_satisfied=False)),AdmissionDecision.REJECT)

    def test_prohibition_unknown_quarantines(self):
        m=exec_message(prohibited_effects=["MERGE"])
        self.assertIs(admit(m,good_evidence(m).replace(prohibited_effects_clear=None)),AdmissionDecision.QUARANTINE)

    def test_sealed_label_without_transport_attestation_cannot_allow(self):
        m=exec_message(security_profile="SEALED")
        self.assertIs(admit(m,good_evidence(m).replace(transport_security_satisfied=False)),AdmissionDecision.REJECT)

    def test_cancel_requires_bound_cancellable_target(self):
        m=base_message(message_id="mc",operation_id="cancel1",target_operation_id="op-target",performative="CANCEL",
            subject="operation:op-target",exact_subject="receipt:"+"b"*64,authority_claim_ref="auth:x",idempotency_key="cid",
            effect_class="PROTECTED_MUTATION",payload={"reason":"stop"})
        e=good_evidence(m)
        self.assertIs(admit(m,e),AdmissionDecision.QUARANTINE)
        unknown=CancellationEvidence("op-target",m.exact_subject,None)
        self.assertIs(admit(m,e,cancellation=unknown),AdmissionDecision.QUARANTINE)
        no=CancellationEvidence("op-target",m.exact_subject,False)
        self.assertIs(admit(m,e,cancellation=no),AdmissionDecision.REJECT)
        yes=CancellationEvidence("op-target",m.exact_subject,True)
        self.assertIs(admit(m,e,cancellation=yes),AdmissionDecision.ALLOW)

class ImmutabilityTests(unittest.TestCase):
    def test_mutating_original_payload_cannot_change_message_digest(self):
        raw={"nested":[{"x":1}]}
        m=base_message(payload=raw)
        d=content_digest(m)
        raw["nested"][0]["x"]=2
        self.assertEqual(content_digest(m),d)

    def test_mutating_to_mapping_result_cannot_change_message(self):
        m=base_message(payload={"nested":[{"x":1}]})
        d=content_digest(m)
        out=m.to_mapping()
        out["payload"]["nested"][0]["x"]=9
        self.assertEqual(content_digest(m),d)

class CanonicalSubsetTests(unittest.TestCase):
    def test_integral_float_and_negative_zero_normalize_to_integer_form(self):
        self.assertEqual(canonical_json_bytes({"v":1.0}), b'{"v":1}')
        self.assertEqual(canonical_json_bytes({"v":-0.0}), b'{"v":0}')

    def test_nonintegral_exponent_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"non-integral floats"):
            canonical_json_bytes({"v":1e-6})

    def test_large_integer_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"safe range"):
            canonical_json_bytes({"v":9007199254740992})

    def test_unicode_value_and_ascii_key_order_are_stable(self):
        self.assertEqual(canonical_json_bytes({"z":"é","a":1}), b'{"a":1,"z":"\xc3\xa9"}')

    def test_non_ascii_object_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"printable ASCII"):
            canonical_json_bytes({"é":1})

class MessageBindingTests(unittest.TestCase):
    def test_mutating_execute_requires_exact_subject_even_without_subject(self):
        with self.assertRaisesRegex(ValueError,"exact_subject"):
            base_message(performative="EXECUTE",subject=None,exact_subject=None,operation_id="o",idempotency_key="i",
                authority_claim_ref="a",effect_class="REVERSIBLE_MUTATION")

    def test_cancel_requires_distinct_target_operation_id(self):
        with self.assertRaisesRegex(ValueError,"target_operation_id"):
            base_message(operation_id="cancel",performative="CANCEL",subject="operation:x",exact_subject="receipt:x",
                authority_claim_ref="a",idempotency_key="i",effect_class="PROTECTED_MUTATION")

    def test_receipt_is_bound_claim_not_verified_fact(self):
        with self.assertRaisesRegex(ValueError,"operation_id"):
            base_message(performative="RECEIPT",exact_subject="receipt:x",receipt={"status":"ok"})
        m=base_message(performative="RECEIPT",operation_id="opx",exact_subject="receipt:x",receipt={"status":"ok"})
        self.assertEqual(m.operation_id,"opx")

class ResourceLimitTests(unittest.TestCase):
    def test_excessive_depth_rejected(self):
        v=0
        for _ in range(30): v=[v]
        with self.assertRaisesRegex(ValueError,"depth limit"):
            base_message(payload=v)
    def test_excessive_collection_rejected(self):
        with self.assertRaisesRegex(ValueError,"collection limit"):
            base_message(payload=list(range(300)))

if __name__=="__main__":
    unittest.main()
