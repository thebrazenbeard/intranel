import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from intranel.message import parse_message


ROOT = Path(__file__).parents[1]
SCHEMA = json.loads(
    (ROOT / "schema/INTRANEL_MESSAGE_V1.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)


def base_message(**updates):
    raw = {
        "protocol": "INTRANEL/1",
        "origin": "vera:primary",
        "actor": "vera:primary",
        "target": "vera:lane/bv",
        "reply_to": "bus:vera-v2",
        "message_id": "m-null-array",
        "conversation_id": "c-null-array",
        "performative": "QUERY",
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    }
    raw.update(updates)
    return raw


class GovernanceArrayParityTests(unittest.TestCase):
    def test_null_array_items_fail_parser_and_schema(self):
        for field in (
            "constraints",
            "prohibited_effects",
            "capabilities",
            "provenance",
        ):
            with self.subTest(field=field):
                raw = base_message(**{field: [None]})
                self.assertNotEqual(list(VALIDATOR.iter_errors(raw)), [])
                with self.assertRaises(ValueError):
                    parse_message(raw)


if __name__ == "__main__":
    unittest.main()
