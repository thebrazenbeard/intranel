import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from intranel.message import parse_message


ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "schema/INTRANEL_MESSAGE_V1.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def base_message(observed_at):
    return {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-time-parity",
        "conversation_id": "c-time-parity",
        "performative": "REPORT",
        "observed_at": observed_at,
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    }


class TimestampParityTests(unittest.TestCase):
    def assert_parser_schema_agree(self, value):
        raw = base_message(value)
        schema_accepts = not list(VALIDATOR.iter_errors(raw))
        try:
            parse_message(raw)
        except ValueError:
            parser_accepts = False
        else:
            parser_accepts = True
        self.assertEqual(parser_accepts, schema_accepts, value)

    def test_space_separator_is_rejected_by_both(self):
        self.assert_parser_schema_agree("2026-09-17 20:30:00+00:00")

    def test_reduced_precision_time_is_rejected_by_both(self):
        self.assert_parser_schema_agree("2026-09-17T20:30+00:00")

    def test_lowercase_z_is_accepted_by_both(self):
        self.assert_parser_schema_agree("2026-09-17T20:30:00z")


if __name__ == "__main__":
    unittest.main()
