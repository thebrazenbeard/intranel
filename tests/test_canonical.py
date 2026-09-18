import math
import unittest

from intranel.canonical import canonical_json_bytes, content_digest
from intranel.message import parse_message


class CanonicalTests(unittest.TestCase):
    def test_mapping_key_order_does_not_change_digest(self):
        self.assertEqual(content_digest({"b": 2, "a": 1}), content_digest({"a": 1, "b": 2}))

    def test_array_order_changes_digest(self):
        self.assertNotEqual(content_digest([1, 2]), content_digest([2, 1]))

    def test_semantic_change_changes_digest(self):
        self.assertNotEqual(content_digest({"performative": "QUERY"}), content_digest({"performative": "REVIEW"}))

    def test_omitted_defaults_and_explicit_defaults_have_same_identity(self):
        minimal = {
            "protocol": "INTRANEL/1",
            "origin": "vera:primary",
            "actor": "vera:primary",
            "target": "vera:lane/bv",
            "reply_to": "bus:vera-v2",
            "message_id": "m-default",
            "conversation_id": "c-default",
            "performative": "QUERY",
            "effect_class": "READ_ONLY",
            "security_profile": "OPEN",
        }
        explicit = {
            **minimal,
            "operation_id": None,
            "target_operation_id": None,
            "parent_message_id": None,
            "subject": None,
            "exact_subject": None,
            "payload": None,
            "authority_claim_ref": None,
            "constraints": [],
            "prohibited_effects": [],
            "expected_response": None,
            "ack_required": False,
            "observed_at": None,
            "expires_at": None,
            "idempotency_key": None,
            "priority": 3,
            "status": None,
            "error": None,
            "receipt": None,
            "capabilities": [],
            "provenance": [],
        }
        a = parse_message(minimal)
        b = parse_message(explicit)
        self.assertEqual(canonical_json_bytes(a), canonical_json_bytes(b))
        self.assertEqual(content_digest(a), content_digest(b))

    def test_utf8_is_not_ascii_escaped(self):
        self.assertEqual(canonical_json_bytes({"label": "é"}), b'{"label":"\xc3\xa9"}')

    def test_non_finite_numbers_are_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonical_json_bytes({"value": value})

    def test_message_to_mapping_uses_wire_values(self):
        message = parse_message({
            "protocol": "INTRANEL/1",
            "origin": "vera:primary",
            "actor": "radar:relay",
            "target": "vera:lane/bv",
            "reply_to": "bus:vera-v2",
            "message_id": "m-002",
            "conversation_id": "c-001",
            "performative": "QUERY",
            "effect_class": "READ_ONLY",
            "security_profile": "OPEN",
        })
        mapping = message.to_mapping()
        self.assertEqual(mapping["origin"], "vera:primary")
        self.assertEqual(mapping["actor"], "radar:relay")
        self.assertEqual(mapping["performative"], "QUERY")
        self.assertEqual(mapping["effect_class"], "READ_ONLY")
        self.assertEqual(mapping["security_profile"], "OPEN")

    def test_message_digest_is_stable_across_reparse(self):
        raw = {
            "protocol": "INTRANEL/1",
            "origin": "vera:primary",
            "actor": "vera:primary",
            "target": "vera:lane/bv",
            "reply_to": "bus:vera-v2",
            "message_id": "m-003",
            "conversation_id": "c-002",
            "performative": "REPORT",
            "effect_class": "READ_ONLY",
            "security_profile": "PRIVATE",
            "payload": {"b": 2, "a": 1},
        }
        one = parse_message(raw)
        two = parse_message(one.to_mapping())
        self.assertEqual(content_digest(one), content_digest(two))


if __name__ == "__main__":
    unittest.main()
