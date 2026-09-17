import unittest

from intranel.admission import OperationRecord, ReceiverEvidence, admit, operation_digest
from intranel.message import parse_message
from intranel.types import AdmissionDecision


def cancel_message():
    return parse_message(
        {
            "protocol": "INTRANEL/1",
            "origin": "vera:primary",
            "actor": "vera:primary",
            "target": "vera:lane/bv",
            "reply_to": "bus:vera-v2",
            "message_id": "cancel-retry-2",
            "operation_id": "cancel-op-1",
            "target_operation_id": "target-op-1",
            "conversation_id": "cancel-conv-1",
            "performative": "CANCEL",
            "subject": "operation:target-op-1",
            "exact_subject": "receipt:target-state-1",
            "authority_claim_ref": "auth:patrick/cancel",
            "idempotency_key": "cancel-idem-1",
            "effect_class": "PROTECTED_MUTATION",
            "security_profile": "OPEN",
        }
    )


def good_evidence(message):
    return ReceiverEvidence.bind(
        message,
        effective_effect_class=message.effect_class,
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


class CancelIdempotencyTests(unittest.TestCase):
    def test_completed_cancel_retry_deduplicates_without_rechecking_cancellability(self):
        message = cancel_message()
        prior = OperationRecord(
            operation_id=message.operation_id or "",
            idempotency_key=message.idempotency_key or "",
            semantic_digest=operation_digest(message),
            completed=True,
        )

        self.assertIs(
            admit(message, good_evidence(message), prior_operation=prior),
            AdmissionDecision.DUPLICATE,
        )


if __name__ == "__main__":
    unittest.main()
