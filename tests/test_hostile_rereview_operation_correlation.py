import unittest

from intranel.admission import OperationRecord, ReceiverEvidence, admit, operation_digest
from intranel.message import parse_message
from intranel.types import AdmissionDecision, EffectClass


def execute_message():
    return parse_message({
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-execute",
        "operation_id": "op-shared",
        "conversation_id": "c-correlation",
        "performative": "EXECUTE",
        "subject": "repo:intranel",
        "exact_subject": "sha256:" + "a" * 64,
        "payload": {"action": "append"},
        "authority_claim_ref": "auth:patrick/example",
        "idempotency_key": "idem-execute",
        "effect_class": "REVERSIBLE_MUTATION",
        "security_profile": "OPEN",
    })


def receipt_message():
    return parse_message({
        "protocol": "INTRANEL/1",
        "origin": "vera:lane/bv",
        "actor": "vera:lane/bv",
        "target": "vera:primary",
        "reply_to": "bus:vera-v2",
        "message_id": "m-receipt",
        "operation_id": "op-shared",
        "conversation_id": "c-correlation",
        "performative": "RECEIPT",
        "exact_subject": "receipt:" + "b" * 64,
        "receipt": {"effect_state": "observed"},
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    })


def evidence(message):
    return ReceiverEvidence.bind(
        message,
        effective_effect_class=(
            EffectClass.REVERSIBLE_MUTATION
            if message.performative.value == "EXECUTE"
            else None
        ),
        origin_authenticated=True,
        actor_authenticated=True,
        authority_valid=True,
        exact_subject_valid=True,
        replay_fresh=True,
        capabilities_supported=True,
        constraints_satisfied=True,
        prohibited_effects_clear=True,
        transport_security_satisfied=True,
    )


class OperationCorrelationTests(unittest.TestCase):
    def test_receipt_for_completed_operation_is_not_misclassified_as_duplicate_retry(self):
        execute = execute_message()
        prior = OperationRecord(
            operation_id=execute.operation_id or "",
            idempotency_key=execute.idempotency_key or "",
            semantic_digest=operation_digest(execute),
            completed=True,
        )
        receipt = receipt_message()
        self.assertIs(
            admit(receipt, evidence(receipt), prior_operation=prior),
            AdmissionDecision.ALLOW,
        )


if __name__ == "__main__":
    unittest.main()
