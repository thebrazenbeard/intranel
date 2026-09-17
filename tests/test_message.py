import unittest

from intranel.message import IntranelMessage, parse_message
from intranel.types import Address, EffectClass, Performative, SecurityProfile


class AddressTests(unittest.TestCase):
    def test_namespaced_address_round_trips(self):
        address = Address.parse("vera:lane/bv")
        self.assertEqual(str(address), "vera:lane/bv")
        self.assertEqual(address.namespace, "vera")
        self.assertEqual(address.node, "lane/bv")

    def test_address_without_namespace_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "address"):
            Address.parse("lane/bv")


class MessageTests(unittest.TestCase):
    def base_mapping(self):
        return {
            "protocol": "INTRANEL/1",
            "origin": "vera:primary",
            "actor": "vera:primary",
            "target": "vera:lane/bv",
            "reply_to": "bus:vera-v2",
            "message_id": "m-001",
            "operation_id": None,
            "parent_message_id": None,
            "conversation_id": "c-001",
            "performative": "QUERY",
            "subject": "world-zero/pr/1",
            "exact_subject": None,
            "payload": {"question": "status"},
            "authority_claim_ref": None,
            "constraints": [],
            "prohibited_effects": [],
            "expected_response": "REPORT",
            "ack_required": False,
            "observed_at": None,
            "expires_at": None,
            "idempotency_key": None,
            "priority": 3,
            "effect_class": "READ_ONLY",
            "status": None,
            "error": None,
            "receipt": None,
            "security_profile": "OPEN",
            "capabilities": [],
            "provenance": [],
        }

    def test_relay_preserves_origin_while_actor_changes(self):
        mapping = self.base_mapping()
        mapping["origin"] = "vera:primary"
        mapping["actor"] = "radar:relay"
        message = parse_message(mapping)
        self.assertEqual(str(message.origin), "vera:primary")
        self.assertEqual(str(message.actor), "radar:relay")
        self.assertNotEqual(message.origin, message.actor)

    def test_unknown_field_is_rejected(self):
        mapping = self.base_mapping()
        mapping["surprise_authority"] = True
        with self.assertRaisesRegex(ValueError, "unknown field"):
            parse_message(mapping)

    def test_unsupported_protocol_is_rejected(self):
        mapping = self.base_mapping()
        mapping["protocol"] = "INTRANEL/9"
        with self.assertRaisesRegex(ValueError, "protocol"):
            parse_message(mapping)

    def test_unknown_performative_is_rejected(self):
        mapping = self.base_mapping()
        mapping["performative"] = "DO_WHATEVER"
        with self.assertRaises(ValueError):
            parse_message(mapping)

    def test_mutating_execute_requires_authority_operation_and_idempotency(self):
        mapping = self.base_mapping()
        mapping.update(
            performative="EXECUTE",
            effect_class="REVERSIBLE_MUTATION",
            exact_subject="sha256:" + "a" * 64,
        )
        with self.assertRaisesRegex(ValueError, "operation_id"):
            parse_message(mapping)

        mapping["operation_id"] = "op-001"
        with self.assertRaisesRegex(ValueError, "idempotency_key"):
            parse_message(mapping)

        mapping["idempotency_key"] = "idem-001"
        with self.assertRaisesRegex(ValueError, "authority_claim_ref"):
            parse_message(mapping)

    def test_mutating_execute_with_required_bindings_parses(self):
        mapping = self.base_mapping()
        mapping.update(
            performative="EXECUTE",
            effect_class="REVERSIBLE_MUTATION",
            operation_id="op-001",
            idempotency_key="idem-001",
            authority_claim_ref="auth:patrick/task-001",
            exact_subject="sha256:" + "a" * 64,
            security_profile="PRIVATE",
        )
        message = parse_message(mapping)
        self.assertIsInstance(message, IntranelMessage)
        self.assertIs(message.performative, Performative.EXECUTE)
        self.assertIs(message.effect_class, EffectClass.REVERSIBLE_MUTATION)
        self.assertIs(message.security_profile, SecurityProfile.PRIVATE)

    def test_mutating_execute_with_subject_requires_exact_subject(self):
        mapping = self.base_mapping()
        mapping.update(
            performative="EXECUTE",
            effect_class="PROTECTED_MUTATION",
            operation_id="op-002",
            idempotency_key="idem-002",
            authority_claim_ref="auth:patrick/task-002",
            exact_subject=None,
        )
        with self.assertRaisesRegex(ValueError, "exact_subject"):
            parse_message(mapping)

    def test_priority_outside_zero_to_four_is_rejected(self):
        mapping = self.base_mapping()
        mapping["priority"] = 5
        with self.assertRaisesRegex(ValueError, "priority"):
            parse_message(mapping)


class StrictScalarTests(unittest.TestCase):
    def base_mapping(self):
        return {
            "protocol": "INTRANEL/1",
            "origin": "vera:primary",
            "actor": "vera:primary",
            "target": "vera:lane/bv",
            "reply_to": "bus:vera-v2",
            "message_id": "m-strict",
            "conversation_id": "c-strict",
            "performative": "QUERY",
            "effect_class": "READ_ONLY",
            "security_profile": "OPEN",
        }

    def test_governance_scalar_fields_reject_non_strings(self):
        for field in ["subject", "exact_subject", "authority_claim_ref", "observed_at", "expires_at", "status", "error"]:
            with self.subTest(field=field):
                mapping = self.base_mapping()
                mapping[field] = 123
                with self.assertRaisesRegex(ValueError, field):
                    parse_message(mapping)

    def test_payload_must_be_json_compatible(self):
        mapping = self.base_mapping()
        mapping["payload"] = {"bad": {1, 2}}
        with self.assertRaisesRegex(ValueError, "payload"):
            parse_message(mapping)


class TimestampTests(unittest.TestCase):
    def base_mapping(self):
        return {
            "protocol": "INTRANEL/1",
            "origin": "vera:primary",
            "actor": "vera:primary",
            "target": "vera:lane/bv",
            "reply_to": "bus:vera-v2",
            "message_id": "m-time",
            "conversation_id": "c-time",
            "performative": "REPORT",
            "effect_class": "READ_ONLY",
            "security_profile": "OPEN",
        }

    def test_malformed_observed_at_is_rejected(self):
        mapping = self.base_mapping()
        mapping["observed_at"] = "not-a-timestamp"
        with self.assertRaisesRegex(ValueError, "observed_at"):
            parse_message(mapping)

    def test_naive_expiry_timestamp_is_rejected(self):
        mapping = self.base_mapping()
        mapping["expires_at"] = "2026-09-17T20:00:00"
        with self.assertRaisesRegex(ValueError, "expires_at"):
            parse_message(mapping)

    def test_expiry_must_be_after_observation_when_both_present(self):
        mapping = self.base_mapping()
        mapping["observed_at"] = "2026-09-17T20:30:00Z"
        mapping["expires_at"] = "2026-09-17T20:29:59Z"
        with self.assertRaisesRegex(ValueError, "expires_at"):
            parse_message(mapping)


if __name__ == "__main__":
    unittest.main()
