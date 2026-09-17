import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from intranel.message import parse_message


ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "schema/INTRANEL_MESSAGE_V1.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def base_message(**updates):
    raw = {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-unicode-parity",
        "operation_id": None,
        "target_operation_id": None,
        "parent_message_id": None,
        "conversation_id": "c-unicode-parity",
        "performative": "QUERY",
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
        "effect_class": "READ_ONLY",
        "status": None,
        "error": None,
        "receipt": None,
        "security_profile": "OPEN",
        "capabilities": [],
        "provenance": [],
    }
    raw.update(updates)
    return raw


class UnicodeLengthParityTests(unittest.TestCase):
    def assert_parser_schema_agree(self, raw):
        schema_accepts = not list(VALIDATOR.iter_errors(raw))
        try:
            parse_message(raw)
        except ValueError:
            parser_accepts = False
        else:
            parser_accepts = True
        self.assertEqual(parser_accepts, schema_accepts)

    def test_multibyte_governance_scalar_has_same_limit_in_parser_and_schema(self):
        # 3000 Unicode code points but 6000 UTF-8 bytes. Draft 2020-12
        # maxLength counts code points, not UTF-8 bytes.
        self.assert_parser_schema_agree(base_message(subject="é" * 3000))

    def test_multibyte_json_string_has_same_limit_in_parser_and_schema(self):
        # 5000 Unicode code points but 10000 UTF-8 bytes.
        self.assert_parser_schema_agree(base_message(payload={"text": "é" * 5000}))


if __name__ == "__main__":
    unittest.main()
