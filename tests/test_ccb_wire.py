"""No-effect Intranel -> CCB Core source compatibility boundary."""

from dataclasses import replace
import json
import unittest

from intranel.ccb_wire import BusWireError, encode_read_only_bus_document
from intranel.message import parse_message
from intranel.coordination import unwrap
from intranel.types import EffectClass, Performative, SecurityProfile


def query():
    return parse_message({
        "protocol": "INTRANEL/1",
        "origin": "vera:portal",
        "actor": "vera:portal",
        "target": "vera:integration",
        "reply_to": "vera:portal",
        "message_id": "intranel-001",
        "conversation_id": "proof-001",
        "performative": "QUERY",
        "payload": {"question": "Which revision?"},
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    })


def wire(message=None, **kwargs):
    return encode_read_only_bus_document(
        message or query(),
        writer="vera-integration-pilot",
        bus_message_id="vera-integration-pilot-001",
        intended_recipient="vera:integration",
        **kwargs,
    )


class WireTests(unittest.TestCase):
    def test_read_only_query_produces_bounded_byte_document(self):
        content = wire()
        self.assertIsInstance(content, bytes)
        self.assertLessEqual(len(content), 65536)
        self.assertIn(b"message_id: vera-integration-pilot-001\n", content)
        self.assertIn(b"writer: vera-integration-pilot\n", content)
        self.assertIn(b"requires_ack: false\n", content)
        self.assertIn(b"requires_reply: false\n", content)
        body = content.split(b"\n\n", 1)[1]
        self.assertTrue(body.startswith(b"```json\n"))
        self.assertTrue(body.endswith(b"\n```\n"))
        self.assertEqual(unwrap(json.loads(body[8:-5])), query())

    def test_only_read_only_query_and_request_are_exportable(self):
        self.assertIsInstance(wire(replace(query(), performative=Performative.REQUEST)), bytes)
        variants = (
            replace(query(), performative=Performative.ACK),
            replace(query(), performative=Performative.WAIT),
            replace(query(), performative=Performative.RECEIPT,
                    operation_id="op-1", exact_subject="sha256:" + "a" * 64,
                    receipt={"status": "CLAIM_ONLY"}),
            replace(query(), performative=Performative.REVIEW,
                    exact_subject="sha256:" + "a" * 64),
            replace(query(), performative=Performative.EXECUTE),
        )
        for message in variants:
            with self.subTest(performative=message.performative), self.assertRaises(BusWireError):
                wire(message)
        with self.assertRaises(BusWireError):
            wire(replace(query(), effect_class=EffectClass.REVERSIBLE_MUTATION))

    def test_private_or_sealed_plaintext_rejected(self):
        for profile in (SecurityProfile.PRIVATE, SecurityProfile.SEALED):
            with self.subTest(profile=profile), self.assertRaises(BusWireError):
                wire(replace(query(), security_profile=profile))

    def test_ack_and_response_obligations_rejected_instead_of_silently_dropped(self):
        # The CCB document declares both obligations false. Preserve semantics
        # by rejecting a packet that requires an acknowledgement or response.
        for altered in (
            replace(query(), ack_required=True),
            replace(query(), expected_response=Performative.ACK),
            replace(query(), ack_required=True, expected_response=Performative.ACK),
        ):
            with self.subTest(ack=altered.ack_required,
                              response=altered.expected_response):
                with self.assertRaisesRegex(BusWireError, "obligations"):
                    wire(altered)

    def test_header_injection_and_unbounded_wire_rejected(self):
        for invalid in ("", "writer\nadmin: yes", "other\rrole", "contains spaces"):
            with self.subTest(invalid=invalid), self.assertRaises(BusWireError):
                encode_read_only_bus_document(
                    query(), writer=invalid, bus_message_id="msg-1",
                    intended_recipient="vera:integration",
                )
        with self.assertRaises(BusWireError):
            wire(replace(query(), payload={"records": ["a" * 3230] * 20}))

    def test_recipient_identity_must_match_semantic_target(self):
        with self.assertRaisesRegex(BusWireError, "recipient conflicts"):
            encode_read_only_bus_document(
                query(), writer="operator-claimed-writer", bus_message_id="msg-2",
                intended_recipient="vera:training",
            )
        with self.assertRaises(BusWireError):
            wire(replace(query(), origin=type(query().origin).parse("agent:unregistered")))
        for field in ("actor", "reply_to"):
            with self.subTest(field=field), self.assertRaises(BusWireError):
                wire(replace(query(), **{field: type(query().origin).parse("agent:unregistered")}))

    def test_cross_repo_ccb_core_real_parser(self):
        try:
            from radar.message_grammar import parse_bus_document
        except ImportError:
            self.skipTest("Install/point PYTHONPATH to pinned CCB Core source for interop gate")
        content = wire()
        parsed = parse_bus_document(content)
        self.assertEqual(parsed.message_id, "vera-integration-pilot-001")
        self.assertEqual(parsed.writer, "vera-integration-pilot")
        self.assertEqual(parsed.intended_recipient, "vera:integration")
        self.assertFalse(parsed.requires_ack)
        self.assertFalse(parsed.requires_reply)
        self.assertEqual(unwrap(json.loads(parsed.body.strip()[8:-3])), query())


if __name__ == "__main__":
    unittest.main()
