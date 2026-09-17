import json
from pathlib import Path
import re
import unittest

from intranel.canonical import content_digest
from intranel.message import parse_message


ROOT = Path(__file__).parents[1]
VECTOR_DIR = ROOT / "vectors"
SCHEMA = ROOT / "schema" / "INTRANEL_MESSAGE_V1.schema.json"


class VectorTests(unittest.TestCase):
    def expected_digests(self):
        text = (VECTOR_DIR / "README.md").read_text(encoding="utf-8")
        pairs = re.findall(r"`([^`]+\.json)`\s+`sha256:([0-9a-f]{64})`", text)
        return dict(pairs)

    def test_all_registered_vectors_parse_and_match_digest(self):
        expected = self.expected_digests()
        self.assertEqual(set(expected), {"query-open.json", "relay-review.json", "execute-private.json"})
        for filename, digest in expected.items():
            with self.subTest(filename=filename):
                raw = json.loads((VECTOR_DIR / filename).read_text(encoding="utf-8"))
                message = parse_message(raw)
                self.assertEqual(content_digest(message), digest)

    def test_schema_is_strict_and_protocol_is_fixed(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["protocol"]["const"], "INTRANEL/1")
        self.assertIn("origin", schema["required"])
        self.assertIn("actor", schema["required"])
        self.assertIn("performative", schema["required"])

    def test_schema_performative_vocabulary_matches_protocol(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(
            set(schema["properties"]["performative"]["enum"]),
            {"QUERY", "REPORT", "REQUEST", "EXECUTE", "REVIEW", "ACK", "REJECT", "WAIT", "CONFLICT", "CANCEL", "RECEIPT"},
        )

    def test_schema_conditionals_require_non_null_exact_and_mutation_bindings(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        review_then = schema["allOf"][0]["then"]
        self.assertEqual(review_then["properties"]["exact_subject"]["type"], "string")
        mutation_then = schema["allOf"][1]["then"]
        for field in ["operation_id", "idempotency_key", "authority_claim_ref", "exact_subject"]:
            with self.subTest(field=field):
                self.assertEqual(mutation_then["properties"][field]["type"], "string")
                self.assertEqual(mutation_then["properties"][field]["minLength"], 1)

    def test_schema_marks_timestamps_as_date_time(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["observed_at"]["anyOf"][0]["format"], "date-time")
        self.assertEqual(schema["properties"]["expires_at"]["anyOf"][0]["format"], "date-time")


if __name__ == "__main__":
    unittest.main()
