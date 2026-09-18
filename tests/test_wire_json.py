import json
import unittest

import intranel
from intranel.message import MAX_MESSAGE_BYTES, parse_json_message


def minimal_mapping():
    return {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "wire-1",
        "conversation_id": "wire-c",
        "performative": "QUERY",
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    }


class StrictWireJsonTests(unittest.TestCase):
    def test_strict_decoder_is_part_of_public_api(self):
        self.assertIn("parse_json_message", intranel.__all__)
        self.assertIs(intranel.parse_json_message, parse_json_message)

    def test_valid_json_text_and_bytes_parse(self):
        raw = json.dumps(minimal_mapping(), separators=(",", ":"))
        self.assertEqual(parse_json_message(raw).message_id, "wire-1")
        self.assertEqual(parse_json_message(raw.encode("utf-8")).message_id, "wire-1")

    def test_duplicate_top_level_member_is_rejected(self):
        raw = (
            '{"protocol":"INTRANEL/1","origin":"vera:primary","actor":"vera:primary",'
            '"target":"vera:lane/bv","reply_to":"bus:vera-v2","message_id":"wire-1",'
            '"conversation_id":"wire-c","performative":"QUERY",'
            '"effect_class":"READ_ONLY","effect_class":"IRREVERSIBLE",'
            '"security_profile":"OPEN"}'
        )
        with self.assertRaisesRegex(ValueError, "duplicate JSON object member"):
            parse_json_message(raw)

    def test_duplicate_nested_payload_member_is_rejected(self):
        raw = minimal_mapping()
        prefix = json.dumps({k: v for k, v in raw.items() if k != "security_profile"}, separators=(",", ":"))[:-1]
        text = prefix + ',"payload":{"x":1,"x":2},"security_profile":"OPEN"}'
        with self.assertRaisesRegex(ValueError, "duplicate JSON object member"):
            parse_json_message(text)

    def test_nonstandard_json_constant_is_rejected(self):
        raw = json.dumps(minimal_mapping(), separators=(",", ":"))[:-1] + ',"payload":NaN}'
        with self.assertRaisesRegex(ValueError, "invalid JSON constant"):
            parse_json_message(raw)

    def test_non_object_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mapping"):
            parse_json_message('["INTRANEL/1"]')

    def test_invalid_utf8_bytes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            parse_json_message(b'{"protocol":"INTRANEL/1","x":"\xff"}')

    def test_raw_wire_input_is_bounded_before_parse(self):
        with self.assertRaisesRegex(ValueError, "wire message exceeds"):
            parse_json_message(" " * (MAX_MESSAGE_BYTES + 1))


if __name__ == "__main__":
    unittest.main()
