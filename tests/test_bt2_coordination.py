"""No-effect BT2 role-profile tests; publication is not delivery."""

import copy
import unittest

from intranel.bt2_coordination import (
    BT2CoordinationConflict,
    unwrap_bt2,
    wrap_bt2,
)
from intranel.message import parse_message
from intranel.canonical import canonical_json_bytes


def review(*, origin="bt2:one", target="bt2:two", message_id="bt2-review-1"):
    return parse_message({
        "protocol": "INTRANEL/1",
        "origin": origin,
        "actor": origin,
        "target": target,
        "reply_to": origin,
        "message_id": message_id,
        "conversation_id": "bt2_live_coordination_intranel",
        "performative": "REVIEW",
        "exact_subject": "git:thebrazenbeard/intranel@" + "a" * 40,
        "payload": {"event_id": "bt2_live_coordination_intranel", "finding": "source only"},
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    })


class BT2CoordinationTests(unittest.TestCase):
    def test_canonical_round_trip_preserves_author_and_recipient(self):
        msg = review()
        packet = wrap_bt2(msg)
        self.assertEqual(unwrap_bt2(packet, expected_target="bt2:two"), msg)
        self.assertEqual(packet["origin"], "bt2:one")
        self.assertEqual(packet["target"], "bt2:two")

    def test_other_roles_cannot_cross_into_bt2_profile(self):
        for origin, target in (("vera:portal", "bt2:two"), ("bt2:one", "vera:vn1")):
            with self.subTest(origin=origin, target=target), self.assertRaises(BT2CoordinationConflict):
                wrap_bt2(review(origin=origin, target=target))

    def test_no_execution_or_mutating_effect_even_if_declared_read_only(self):
        for change in ({"performative": "EXECUTE"},
                       {"performative": "CANCEL", "effect_class": "PROTECTED_MUTATION"},
                       {"performative": "RECEIPT"},
                       {"effect_class": "REVERSIBLE_MUTATION"},
                       {"authority_claim_ref": "self-asserted-grant"}):
            with self.subTest(change=change):
                data = review().to_mapping()
                data.update(change)
                try:
                    candidate = parse_message(data)
                except ValueError:
                    continue
                with self.assertRaises(BT2CoordinationConflict):
                    wrap_bt2(candidate)

    def test_strict_envelope_rejects_forged_fields_or_content(self):
        packet = wrap_bt2(review())
        for change in (lambda d: d["semantic_message"]["payload"].update(finding="effect!"),
                       lambda d: d.update(privilege="admin"),
                       lambda d: d.update(origin="bt2:two"),
                       lambda d: d.update(semantic_sha256="0" * 64)):
            damaged = copy.deepcopy(packet)
            change(damaged)
            with self.assertRaises(BT2CoordinationConflict):
                unwrap_bt2(damaged, expected_target="bt2:two")

    def test_receiver_owned_target_must_match_message(self):
        packet = wrap_bt2(review())
        with self.assertRaises(BT2CoordinationConflict):
            unwrap_bt2(packet, expected_target="bt2:one")
        with self.assertRaises(BT2CoordinationConflict):
            unwrap_bt2(packet, expected_target="vera:portal")

    def test_bounded_semantic_message_cannot_expand_past_envelope_limit(self):
        data = review().to_mapping()
        data["payload"]["fill"] = ["z" * 4030 for _ in range(16)]
        message = parse_message(data)
        self.assertLess(len(canonical_json_bytes(message)), 65536)
        with self.assertRaises(BT2CoordinationConflict):
            wrap_bt2(message)

    def test_exact_subject_must_be_pinned(self):
        for subject in (None, "git:thebrazenbeard/intranel@main", "https://github.com/thebrazenbeard/intranel"):
            data = review().to_mapping()
            data["exact_subject"] = subject
            try:
                candidate = parse_message(data)
            except ValueError:
                continue
            with self.assertRaises(BT2CoordinationConflict):
                wrap_bt2(candidate)

    def test_invalid_ack_parent_is_not_a_proven_ack(self):
        data = review(origin="bt2:two", target="bt2:one", message_id="ack-1").to_mapping()
        data["performative"] = "ACK"
        data["parent_message_id"] = None
        with self.assertRaises(BT2CoordinationConflict):
            wrap_bt2(parse_message(data))


if __name__ == "__main__":
    unittest.main()
