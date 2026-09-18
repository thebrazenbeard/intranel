from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class DocsContractTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_protocol_spec_names_exact_protocol_and_all_performatives(self):
        text = self.read("spec/INTRANEL_1.md")
        self.assertIn("INTRANEL/1", text)
        for token in ["QUERY", "REPORT", "REQUEST", "EXECUTE", "REVIEW", "ACK", "REJECT", "WAIT", "CONFLICT", "CANCEL", "RECEIPT"]:
            with self.subTest(token=token):
                self.assertIn(f"`{token}`", text)

    def test_protocol_spec_forbids_transport_authority_transfer(self):
        text = self.read("spec/INTRANEL_1.md").lower()
        self.assertIn("transport does not grant authority", text)
        self.assertIn("origin", text)
        self.assertIn("actor", text)
        self.assertIn("operation_id", text)
        self.assertIn("idempotency", text)

    def test_security_profiles_are_explicit_and_not_crypto_implementation(self):
        text = self.read("spec/SECURITY_PROFILES_V1.md")
        for profile in ["OPEN", "PRIVATE", "SEALED"]:
            self.assertIn(f"`{profile}`", text)
        self.assertIn("does not implement cryptography", text.lower())
        self.assertIn("authority", text.lower())

    def test_bus_profile_preserves_semantic_digest_and_append_only_posture(self):
        text = self.read("adapters/BUS_PROFILE_V1.md")
        self.assertIn("chat-communication-bus", text)
        self.assertIn("semantic_sha256", text)
        self.assertIn("messages/", text)
        self.assertIn("append-only", text.lower())
        self.assertIn("does not grant authority", text.lower())

    def test_readme_states_core_boundaries(self):
        text = self.read("README.md").lower()
        self.assertIn("intranel/1", text)
        self.assertIn("not a chain-of-thought", text)
        self.assertIn("not an authority", text)

    def test_security_doc_forbids_committing_real_keys(self):
        text = self.read("SECURITY.md").lower()
        self.assertIn("do not commit", text)
        self.assertIn("private keys", text)
        self.assertIn("credentials", text)

    def test_timestamp_contract_is_explicit(self):
        text = self.read("spec/INTRANEL_1.md").lower()
        self.assertIn("offset-aware iso 8601", text)
        self.assertIn("`expires_at` must be later than `observed_at`", text)

    def test_idempotency_requires_atomic_operation_reservation(self):
        text = self.read("spec/INTRANEL_1.md").lower()
        self.assertIn("atomic", text)
        self.assertIn("reserve", text)
        self.assertIn("operation", text)

    def test_architecture_rationale_matches_receipt_and_subject_semantics(self):
        text = self.read("docs/superpowers/specs/2026-09-17-intranel-v1-design.md")
        lower = text.lower()
        self.assertIn("receipt claim", lower)
        self.assertIn("does not prove", lower)
        self.assertIn("every mutating `execute` requires `exact_subject`", lower)
        self.assertIn("target_operation_id", text)

    def test_hostile_repair_boundaries_are_explicit(self):
        text = self.read("spec/INTRANEL_1.md").lower()
        for phrase in [
            "receiver-owned effect",
            "target_operation_id",
            "transport_security_satisfied",
            "receipt claim",
            "non-integral floats",
            "65536 bytes",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
