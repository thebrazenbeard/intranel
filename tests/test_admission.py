import unittest

from intranel.admission import OperationRecord, ReceiverChecks, admit, operation_digest
from intranel.message import parse_message
from intranel.types import AdmissionDecision


def query_message(**updates):
    raw = {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-query",
        "conversation_id": "c-1",
        "performative": "QUERY",
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    }
    raw.update(updates)
    return parse_message(raw)


def execute_message(**updates):
    raw = {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-exec",
        "operation_id": "op-1",
        "conversation_id": "c-1",
        "performative": "EXECUTE",
        "subject": "repo:intranel",
        "exact_subject": "sha1:" + "a" * 40,
        "authority_claim_ref": "auth:patrick/intranel-build",
        "idempotency_key": "idem-1",
        "effect_class": "REVERSIBLE_MUTATION",
        "security_profile": "PRIVATE",
    }
    raw.update(updates)
    return parse_message(raw)


class AdmissionTests(unittest.TestCase):
    def good_checks(self):
        return ReceiverChecks(
            origin_authenticated=True,
            actor_authenticated=True,
            authority_valid=True,
            exact_subject_valid=True,
            replay_fresh=True,
            capabilities_supported=True,
        )

    def test_read_only_query_allows_when_authentication_is_verified(self):
        self.assertIs(admit(query_message(), self.good_checks()), AdmissionDecision.ALLOW)

    def test_invalid_authority_rejects_mutating_execute(self):
        checks = self.good_checks().replace(authority_valid=False)
        self.assertIs(admit(execute_message(), checks), AdmissionDecision.REJECT)

    def test_unknown_authority_quarantines_mutating_execute(self):
        checks = self.good_checks().replace(authority_valid=None)
        self.assertIs(admit(execute_message(), checks), AdmissionDecision.QUARANTINE)

    def test_authentication_uncertainty_quarantines(self):
        checks = self.good_checks().replace(actor_authenticated=None)
        self.assertIs(admit(query_message(), checks), AdmissionDecision.QUARANTINE)

    def test_replay_uncertainty_quarantines(self):
        checks = self.good_checks().replace(replay_fresh=None)
        self.assertIs(admit(query_message(), checks), AdmissionDecision.QUARANTINE)

    def test_exact_subject_mismatch_conflicts(self):
        checks = self.good_checks().replace(exact_subject_valid=False)
        self.assertIs(admit(execute_message(), checks), AdmissionDecision.CONFLICT)

    def test_completed_same_operation_is_duplicate(self):
        message = execute_message()
        prior = OperationRecord(
            operation_id="op-1",
            idempotency_key="idem-1",
            semantic_digest=operation_digest(message),
            completed=True,
        )
        self.assertIs(admit(message, self.good_checks(), prior), AdmissionDecision.DUPLICATE)

    def test_same_operation_with_conflicting_semantics_conflicts(self):
        message = execute_message(payload={"value": 2})
        other = execute_message(payload={"value": 1})
        prior = OperationRecord(
            operation_id="op-1",
            idempotency_key="idem-1",
            semantic_digest=operation_digest(other),
            completed=True,
        )
        self.assertIs(admit(message, self.good_checks(), prior), AdmissionDecision.CONFLICT)

    def test_relay_retry_with_new_packet_identity_is_duplicate_not_conflict(self):
        original = execute_message(message_id="m-origin", actor="vera:primary")
        relayed = execute_message(message_id="m-relay", actor="radar:relay")
        prior = OperationRecord(
            operation_id="op-1",
            idempotency_key="idem-1",
            semantic_digest=operation_digest(original),
            completed=True,
        )
        self.assertIs(admit(relayed, self.good_checks(), prior), AdmissionDecision.DUPLICATE)

    def test_same_operation_with_different_idempotency_key_conflicts(self):
        message = execute_message()
        prior = OperationRecord(
            operation_id="op-1",
            idempotency_key="idem-other",
            semantic_digest=operation_digest(message),
            completed=True,
        )
        self.assertIs(admit(message, self.good_checks(), prior), AdmissionDecision.CONFLICT)

    def test_unsupported_capability_rejects(self):
        message = query_message(capabilities=["intranel.feature.future-x"])
        checks = self.good_checks().replace(capabilities_supported=False)
        self.assertIs(admit(message, checks), AdmissionDecision.REJECT)

    def test_security_profile_does_not_bypass_invalid_authority(self):
        checks = self.good_checks().replace(authority_valid=False)
        private = execute_message(security_profile="PRIVATE")
        sealed = execute_message(message_id="m-sealed", security_profile="SEALED")
        self.assertIs(admit(private, checks), AdmissionDecision.REJECT)
        self.assertIs(admit(sealed, checks), AdmissionDecision.REJECT)


if __name__ == "__main__":
    unittest.main()
