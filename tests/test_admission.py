import unittest
from intranel.admission import CancellationEvidence, OperationRecord, ReceiverEvidence, admit, operation_digest
from intranel.message import parse_message
from intranel.types import AdmissionDecision, EffectClass

def query_message(**updates):
    raw={"protocol":"INTRANEL/1","origin":"vera:primary","actor":"vera:primary","target":"vera:lane/bv","reply_to":"bus:vera-v2",
         "message_id":"m-query","conversation_id":"c-1","performative":"QUERY","effect_class":"READ_ONLY","security_profile":"OPEN"}
    raw.update(updates); return parse_message(raw)

def execute_message(**updates):
    raw={"protocol":"INTRANEL/1","origin":"vera:primary","actor":"vera:primary","target":"vera:lane/bv","reply_to":"bus:vera-v2",
         "message_id":"m-exec","operation_id":"op-1","conversation_id":"c-1","performative":"EXECUTE",
         "subject":"repo:intranel","exact_subject":"sha1:"+"a"*40,"authority_claim_ref":"auth:patrick/intranel-build",
         "idempotency_key":"idem-1","effect_class":"REVERSIBLE_MUTATION","security_profile":"PRIVATE"}
    raw.update(updates); return parse_message(raw)

class AdmissionTests(unittest.TestCase):
    def good_evidence(self, message, effect=None):
        if effect is None and message.performative.value in {"EXECUTE","CANCEL"}:
            effect=message.effect_class
        return ReceiverEvidence.bind(message,effective_effect_class=effect,
            origin_authenticated=True,actor_authenticated=True,authority_valid=True,
            exact_subject_valid=True,replay_fresh=True,capabilities_supported=True,
            constraints_satisfied=True,prohibited_effects_clear=True,transport_security_satisfied=True)

    def test_read_only_query_allows_when_authentication_is_verified(self):
        m=query_message()
        self.assertIs(admit(m,self.good_evidence(m)),AdmissionDecision.ALLOW)

    def test_invalid_authority_rejects_mutating_execute(self):
        m=execute_message(); e=self.good_evidence(m).replace(authority_valid=False)
        self.assertIs(admit(m,e),AdmissionDecision.REJECT)

    def test_unknown_authority_quarantines_mutating_execute(self):
        m=execute_message(); e=self.good_evidence(m).replace(authority_valid=None)
        self.assertIs(admit(m,e),AdmissionDecision.QUARANTINE)

    def test_authentication_uncertainty_quarantines(self):
        m=query_message(); e=self.good_evidence(m).replace(actor_authenticated=None)
        self.assertIs(admit(m,e),AdmissionDecision.QUARANTINE)

    def test_replay_uncertainty_quarantines(self):
        m=query_message(); e=self.good_evidence(m).replace(replay_fresh=None)
        self.assertIs(admit(m,e),AdmissionDecision.QUARANTINE)

    def test_exact_subject_mismatch_conflicts(self):
        m=execute_message(); e=self.good_evidence(m).replace(exact_subject_valid=False)
        self.assertIs(admit(m,e),AdmissionDecision.CONFLICT)

    def test_completed_same_operation_is_duplicate(self):
        m=execute_message()
        prior=OperationRecord("op-1","idem-1",operation_digest(m),True)
        self.assertIs(admit(m,self.good_evidence(m),prior),AdmissionDecision.DUPLICATE)

    def test_same_operation_with_conflicting_semantics_conflicts(self):
        m=execute_message(payload={"value":2}); other=execute_message(payload={"value":1})
        prior=OperationRecord("op-1","idem-1",operation_digest(other),True)
        self.assertIs(admit(m,self.good_evidence(m),prior),AdmissionDecision.CONFLICT)

    def test_relay_retry_with_new_packet_identity_is_duplicate_not_conflict(self):
        original=execute_message(message_id="m-origin",actor="vera:primary")
        relayed=execute_message(message_id="m-relay",actor="radar:relay")
        prior=OperationRecord("op-1","idem-1",operation_digest(original),True)
        self.assertIs(admit(relayed,self.good_evidence(relayed),prior),AdmissionDecision.DUPLICATE)

    def test_same_operation_with_different_idempotency_key_conflicts(self):
        m=execute_message()
        prior=OperationRecord("op-1","idem-other",operation_digest(m),True)
        self.assertIs(admit(m,self.good_evidence(m),prior),AdmissionDecision.CONFLICT)

    def test_unsupported_capability_rejects(self):
        m=query_message(capabilities=["intranel.feature.future-x"])
        self.assertIs(admit(m,self.good_evidence(m).replace(capabilities_supported=False)),AdmissionDecision.REJECT)

    def test_security_profile_does_not_bypass_invalid_authority(self):
        for profile in ("PRIVATE","SEALED"):
            m=execute_message(message_id="m-"+profile.lower(),security_profile=profile)
            self.assertIs(admit(m,self.good_evidence(m).replace(authority_valid=False)),AdmissionDecision.REJECT)

    def test_relay_actor_does_not_inherit_origin_authority(self):
        m=execute_message(actor="radar:relay")
        self.assertIs(admit(m,self.good_evidence(m).replace(authority_valid=False)),AdmissionDecision.REJECT)

    def test_known_failed_actor_authentication_rejects(self):
        m=query_message()
        self.assertIs(admit(m,self.good_evidence(m).replace(actor_authenticated=False)),AdmissionDecision.REJECT)

    def test_effect_underdeclaration_conflicts(self):
        m=query_message(performative="EXECUTE",payload={"action":"write"})
        e=self.good_evidence(m,effect=EffectClass.REVERSIBLE_MUTATION)
        self.assertIs(admit(m,e),AdmissionDecision.CONFLICT)

    def test_cross_message_evidence_conflicts(self):
        one=execute_message(message_id="one"); two=execute_message(message_id="two")
        self.assertIs(admit(two,self.good_evidence(one)),AdmissionDecision.CONFLICT)

if __name__=="__main__": unittest.main()
