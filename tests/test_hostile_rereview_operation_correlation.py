import unittest

from intranel.admission import (
    CancellationEvidence,
    OperationRecord,
    ReceiverEvidence,
    admit,
    operation_digest,
)
from intranel.message import parse_message
from intranel.types import AdmissionDecision


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


def read_only_execute_without_operation_id():
    return parse_message({
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-read",
        "conversation_id": "c-correlation",
        "performative": "EXECUTE",
        "payload": {"action": "inspect"},
        "effect_class": "READ_ONLY",
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


def cancel_message(*, operation_id="cancel-op", target_operation_id="target-op"):
    return parse_message({
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-cancel",
        "operation_id": operation_id,
        "target_operation_id": target_operation_id,
        "conversation_id": "c-correlation",
        "performative": "CANCEL",
        "subject": f"operation:{target_operation_id}",
        "exact_subject": "receipt:" + "c" * 64,
        "payload": {"reason": "stop"},
        "authority_claim_ref": "auth:patrick/example",
        "idempotency_key": "idem-cancel",
        "effect_class": "PROTECTED_MUTATION",
        "security_profile": "OPEN",
    })


def evidence(message):
    effect = (
        message.effect_class
        if message.performative.value in {"EXECUTE", "CANCEL"}
        else None
    )
    return ReceiverEvidence.bind(
        message,
        effective_effect_class=effect,
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
    def test_operation_request_without_duplicate_lookup_quarantines(self):
        execute = execute_message()
        self.assertIs(
            admit(execute, evidence(execute)),
            AdmissionDecision.QUARANTINE,
        )

    def test_explicit_receiver_confirmed_absence_allows_fresh_operation(self):
        execute = execute_message()
        self.assertIs(
            admit(execute, evidence(execute), prior_operation=None),
            AdmissionDecision.ALLOW,
        )

    def test_read_only_execute_without_operation_identity_needs_no_duplicate_lookup(self):
        execute = read_only_execute_without_operation_id()
        self.assertIs(
            admit(execute, evidence(execute)),
            AdmissionDecision.ALLOW,
        )

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

    def test_cancel_request_cannot_target_its_own_operation_id(self):
        cancel = cancel_message(operation_id="same-op", target_operation_id="same-op")
        cancellation = CancellationEvidence(
            target_operation_id="same-op",
            exact_subject=cancel.exact_subject or "",
            cancellable=True,
        )
        self.assertIs(
            admit(cancel, evidence(cancel), prior_operation=None, cancellation=cancellation),
            AdmissionDecision.CONFLICT,
        )


if __name__ == "__main__":
    unittest.main()
