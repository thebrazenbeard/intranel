import json
from dataclasses import replace
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
        "message_id": "m-array-boundary",
        "conversation_id": "c-array-boundary",
        "performative": "QUERY",
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    }
    raw.update(updates)
    return raw


class GovernanceArrayBoundaryTests(unittest.TestCase):
    def test_wire_null_array_items_already_fail_parser_and_schema(self):
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

    def test_direct_message_constructor_rejects_null_array_items(self):
        message = parse_message(base_message())
        for field in (
            "constraints",
            "prohibited_effects",
            "capabilities",
            "provenance",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    replace(message, **{field: (None,)})


if __name__ == "__main__":
    unittest.main()
