import unittest
from intranel.admission import CancellationEvidence, OperationRecord, ReceiverEvidence, admit, operation_digest
from intranel.canonical import content_digest
from intranel.message import IntranelMessage, parse_message
from intranel.types import Address, AdmissionDecision, EffectClass

def execute_mapping(**updates):
    raw={"protocol":"INTRANEL/1","origin":"vera:primary","actor":"vera:primary","target":"vera:lane/bv","reply_to":"bus:vera-v2",
         "message_id":"m-exec-hardening","operation_id":"op-hardening","conversation_id":"c-hardening","performative":"EXECUTE",
         "subject":"repo:intranel","exact_subject":"sha1:"+"a"*40,"authority_claim_ref":"auth:patrick/intranel-build",
         "idempotency_key":"idem-hardening","effect_class":"REVERSIBLE_MUTATION","security_profile":"OPEN"}
    raw.update(updates); return raw

def cancel_mapping(**updates):
    raw={"protocol":"INTRANEL/1","origin":"vera:primary","actor":"vera:primary","target":"vera:lane/bv","reply_to":"bus:vera-v2",
         "message_id":"m-cancel-hardening","operation_id":"cancel-op-hardening","target_operation_id":"op-hardening",
         "conversation_id":"c-hardening","performative":"CANCEL","subject":"operation:op-hardening","exact_subject":"receipt:"+"b"*64,
         "authority_claim_ref":"auth:patrick/intranel-build","idempotency_key":"cancel-idem-hardening",
         "effect_class":"PROTECTED_MUTATION","security_profile":"OPEN"}
    raw.update(updates); return raw

class HardeningTests(unittest.TestCase):
    def good_evidence(self,m):
        eff=m.effect_class if m.performative.value in {"EXECUTE","CANCEL"} else None
        return ReceiverEvidence.bind(m,effective_effect_class=eff,origin_authenticated=True,actor_authenticated=True,
            authority_valid=True,exact_subject_valid=True,replay_fresh=True,capabilities_supported=True,
            constraints_satisfied=True,prohibited_effects_clear=True,transport_security_satisfied=True)

    def test_direct_address_constructor_rejects_invalid_address(self):
        with self.assertRaisesRegex(ValueError,"address"):
            Address(namespace="bad namespace",node="node")

    def test_direct_message_constructor_rejects_non_json_payload(self):
        m=parse_message(execute_mapping())
        with self.assertRaisesRegex(ValueError,"payload"):
            IntranelMessage(protocol=m.protocol,origin=m.origin,actor=m.actor,target=m.target,reply_to=m.reply_to,
                message_id=m.message_id,operation_id=m.operation_id,parent_message_id=m.parent_message_id,
                conversation_id=m.conversation_id,performative=m.performative,subject=m.subject,exact_subject=m.exact_subject,
                payload={"bad":{1,2}},authority_claim_ref=m.authority_claim_ref,constraints=m.constraints,
                prohibited_effects=m.prohibited_effects,expected_response=m.expected_response,ack_required=m.ack_required,
                observed_at=m.observed_at,expires_at=m.expires_at,idempotency_key=m.idempotency_key,priority=m.priority,
                effect_class=m.effect_class,status=m.status,error=m.error,receipt=m.receipt,
                security_profile=m.security_profile,capabilities=m.capabilities,provenance=m.provenance)

    def test_receiver_evidence_rejects_non_boolean_tristate(self):
        m=parse_message(execute_mapping())
        with self.assertRaisesRegex(ValueError,"authority_valid"):
            ReceiverEvidence.bind(m,effective_effect_class=m.effect_class,origin_authenticated=True,actor_authenticated=True,
                authority_valid="yes",exact_subject_valid=True,replay_fresh=True,capabilities_supported=True,
                constraints_satisfied=True,prohibited_effects_clear=True,transport_security_satisfied=True)

    def test_incomplete_matching_operation_quarantines(self):
        m=parse_message(execute_mapping()); prior=OperationRecord(m.operation_id or "",m.idempotency_key or "",operation_digest(m),False)
        self.assertIs(admit(m,self.good_evidence(m),prior),AdmissionDecision.QUARANTINE)

    def test_invalid_authority_rejects_before_duplicate_for_mutation(self):
        m=parse_message(execute_mapping()); prior=OperationRecord(m.operation_id or "",m.idempotency_key or "",operation_digest(m),True)
        self.assertIs(admit(m,self.good_evidence(m).replace(authority_valid=False),prior),AdmissionDecision.REJECT)

    def test_cancel_cannot_be_read_only(self):
        with self.assertRaisesRegex(ValueError,"CANCEL"): parse_message(cancel_mapping(effect_class="READ_ONLY"))

    def test_cancel_requires_mutation_bindings(self):
        for field in ["operation_id","target_operation_id","idempotency_key","authority_claim_ref","subject","exact_subject"]:
            with self.subTest(field=field):
                raw=cancel_mapping(); raw[field]=None
                with self.assertRaisesRegex(ValueError,field): parse_message(raw)

    def test_cancel_requires_cancellable_target_evidence(self):
        m=parse_message(cancel_mapping()); e=self.good_evidence(m)
        self.assertIs(admit(m,e,prior_operation=None),AdmissionDecision.QUARANTINE)
        self.assertIs(admit(m,e,prior_operation=None,cancellation=CancellationEvidence("op-hardening",m.exact_subject,False)),AdmissionDecision.REJECT)
        self.assertIs(admit(m,e,prior_operation=None,cancellation=CancellationEvidence("op-hardening",m.exact_subject,True)),AdmissionDecision.ALLOW)

    def test_payload_is_deeply_immutable_from_input(self):
        raw={"n":[{"x":1}]}; m=parse_message(execute_mapping(payload=raw)); d=content_digest(m); raw["n"][0]["x"]=2
        self.assertEqual(content_digest(m),d)

    def test_to_mapping_is_deep_copy(self):
        m=parse_message(execute_mapping(payload={"n":[{"x":1}]})); d=content_digest(m); out=m.to_mapping(); out["payload"]["n"][0]["x"]=2
        self.assertEqual(content_digest(m),d)

if __name__=="__main__": unittest.main()
