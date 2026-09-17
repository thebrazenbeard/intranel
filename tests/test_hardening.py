import unittest

from intranel.admission import OperationRecord, ReceiverChecks, admit, operation_digest
from intranel.message import IntranelMessage, parse_message
from intranel.types import Address, AdmissionDecision


def execute_mapping(**updates):
    raw = {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-exec-hardening",
        "operation_id": "op-hardening",
        "conversation_id": "c-hardening",
        "performative": "EXECUTE",
        "subject": "repo:intranel",
        "exact_subject": "sha1:" + "a" * 40,
        "authority_claim_ref": "auth:patrick/intranel-build",
        "idempotency_key": "idem-hardening",
        "effect_class": "REVERSIBLE_MUTATION",
        "security_profile": "OPEN",
    }
    raw.update(updates)
    return raw


def cancel_mapping(**updates):
    raw = {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-cancel-hardening",
        "operation_id": "cancel-op-hardening",
        "conversation_id": "c-hardening",
        "performative": "CANCEL",
        "subject": "operation:op-hardening",
        "exact_subject": "receipt:" + "b" * 64,
        "authority_claim_ref": "auth:patrick/intranel-build",
        "idempotency_key": "cancel-idem-hardening",
        "effect_class": "PROTECTED_MUTATION",
        "security_profile": "OPEN",
    }
    raw.update(updates)
    return raw


class HardeningTests(unittest.TestCase):
    def good_checks(self):
        return ReceiverChecks(
            origin_authenticated=True,
            actor_authenticated=True,
            authority_valid=True,
            exact_subject_valid=True,
            replay_fresh=True,
            capabilities_supported=True,
        )

    def test_direct_address_constructor_rejects_invalid_address(self):
        with self.assertRaisesRegex(ValueError, "address"):
            Address(namespace="bad namespace", node="node")

    def test_direct_message_constructor_rejects_non_json_payload(self):
        message = parse_message(execute_mapping())
        with self.assertRaisesRegex(ValueError, "payload"):
            IntranelMessage(
                protocol=message.protocol,
                origin=message.origin,
                actor=message.actor,
                target=message.target,
                reply_to=message.reply_to,
                message_id=message.message_id,
                operation_id=message.operation_id,
                parent_message_id=message.parent_message_id,
                conversation_id=message.conversation_id,
                performative=message.performative,
                subject=message.subject,
                exact_subject=message.exact_subject,
                payload={"bad": {1, 2}},
                authority_claim_ref=message.authority_claim_ref,
                constraints=message.constraints,
                prohibited_effects=message.prohibited_effects,
                expected_response=message.expected_response,
                ack_required=message.ack_required,
                observed_at=message.observed_at,
                expires_at=message.expires_at,
                idempotency_key=message.idempotency_key,
                priority=message.priority,
                effect_class=message.effect_class,
                status=message.status,
                error=message.error,
                receipt=message.receipt,
                security_profile=message.security_profile,
                capabilities=message.capabilities,
                provenance=message.provenance,
            )

    def test_direct_message_constructor_rejects_string_enum_bypass(self):
        message = parse_message(execute_mapping())
        with self.assertRaisesRegex(ValueError, "performative"):
            IntranelMessage(
                protocol=message.protocol,
                origin=message.origin,
                actor=message.actor,
                target=message.target,
                reply_to=message.reply_to,
                message_id=message.message_id,
                operation_id=None,
                parent_message_id=None,
                conversation_id=message.conversation_id,
                performative="EXECUTE",  # type: ignore[arg-type]
                subject=message.subject,
                exact_subject=None,
                payload=None,
                authority_claim_ref=None,
                effect_class="REVERSIBLE_MUTATION",  # type: ignore[arg-type]
                security_profile="OPEN",  # type: ignore[arg-type]
            )

    def test_receiver_checks_reject_non_boolean_tristate(self):
        with self.assertRaisesRegex(ValueError, "authority_valid"):
            ReceiverChecks(
                origin_authenticated=True,
                actor_authenticated=True,
                authority_valid="yes",  # type: ignore[arg-type]
                exact_subject_valid=True,
                replay_fresh=True,
                capabilities_supported=True,
            )

    def test_incomplete_matching_operation_quarantines(self):
        message = parse_message(execute_mapping())
        prior = OperationRecord(
            operation_id=message.operation_id or "",
            idempotency_key=message.idempotency_key or "",
            semantic_digest=operation_digest(message),
            completed=False,
        )
        self.assertIs(
            admit(message, self.good_checks(), prior),
            AdmissionDecision.QUARANTINE,
        )

    def test_invalid_authority_rejects_before_duplicate_for_mutation(self):
        message = parse_message(execute_mapping())
        prior = OperationRecord(
            operation_id=message.operation_id or "",
            idempotency_key=message.idempotency_key or "",
            semantic_digest=operation_digest(message),
            completed=True,
        )
        checks = self.good_checks().replace(authority_valid=False)
        self.assertIs(admit(message, checks, prior), AdmissionDecision.REJECT)

    def test_cancel_cannot_be_read_only(self):
        with self.assertRaisesRegex(ValueError, "CANCEL"):
            parse_message(cancel_mapping(effect_class="READ_ONLY"))

    def test_cancel_requires_mutation_bindings(self):
        for field in ["operation_id", "idempotency_key", "authority_claim_ref", "subject", "exact_subject"]:
            with self.subTest(field=field):
                raw = cancel_mapping()
                raw[field] = None
                with self.assertRaisesRegex(ValueError, field):
                    parse_message(raw)

    def test_cancel_invalid_authority_rejects(self):
        message = parse_message(cancel_mapping())
        checks = self.good_checks().replace(authority_valid=False)
        self.assertIs(admit(message, checks), AdmissionDecision.REJECT)


if __name__ == "__main__":
    unittest.main()
