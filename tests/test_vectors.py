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


if __name__ == "__main__":
    unittest.main()
