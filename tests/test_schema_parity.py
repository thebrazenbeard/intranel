import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator, FormatChecker
from intranel.message import parse_message

ROOT=Path(__file__).parents[1]
SCHEMA=json.loads((ROOT/"schema/INTRANEL_MESSAGE_V1.schema.json").read_text())
VALIDATOR=Draft202012Validator(SCHEMA,format_checker=FormatChecker())

def base(**updates):
    raw={
      "protocol":"INTRANEL/1","origin":"vera:primary","actor":"vera:primary","target":"vera:lane/bv","reply_to":"bus:vera-v2",
      "message_id":"m","operation_id":None,"target_operation_id":None,"parent_message_id":None,"conversation_id":"c",
      "performative":"QUERY","subject":None,"exact_subject":None,"payload":None,"authority_claim_ref":None,"constraints":[],
      "prohibited_effects":[],"expected_response":None,"ack_required":False,"observed_at":None,"expires_at":None,
      "idempotency_key":None,"priority":3,"effect_class":"READ_ONLY","status":None,"error":None,"receipt":None,
      "security_profile":"OPEN","capabilities":[],"provenance":[]}
    raw.update(updates); return raw

VALID=[
 base(),
 base(performative="REVIEW",exact_subject="sha256:"+"a"*64),
 base(performative="EXECUTE",effect_class="REVERSIBLE_MUTATION",operation_id="op",idempotency_key="i",authority_claim_ref="a",exact_subject="sha256:"+"a"*64),
 base(performative="EXECUTE",effect_class="READ_ONLY",operation_id="read-op",idempotency_key="read-i"),
 base(performative="CANCEL",effect_class="PROTECTED_MUTATION",operation_id="cancel",target_operation_id="target",idempotency_key="i",authority_claim_ref="a",subject="operation:target",exact_subject="receipt:x"),
 base(performative="RECEIPT",operation_id="target",exact_subject="receipt:x",receipt={"effect_state":"observed"}),
]
INVALID=[
 base(performative="EXECUTE",effect_class="REVERSIBLE_MUTATION",operation_id="op",idempotency_key="i",authority_claim_ref="a",exact_subject=None),
 base(performative="EXECUTE",effect_class="READ_ONLY",operation_id="read-op",idempotency_key=None),
 base(performative="CANCEL",effect_class="READ_ONLY",operation_id="cancel",target_operation_id="target",idempotency_key="i",authority_claim_ref="a",subject="operation:target",exact_subject="receipt:x"),
 base(performative="CANCEL",effect_class="PROTECTED_MUTATION",operation_id="cancel",target_operation_id=None,idempotency_key="i",authority_claim_ref="a",subject="operation:target",exact_subject="receipt:x"),
 base(performative="RECEIPT",operation_id=None,exact_subject="receipt:x",receipt={"x":1}),
 base(payload={"v":1e-6}),
 base(payload={"é":1}),
 base(origin="vera:primary\n"),
 base(message_id="m\n"),
 base(payload={"bad\n":1}),
]

class SchemaParityTests(unittest.TestCase):
    def test_valid_corpus_accepted_by_parser_and_schema(self):
        for raw in VALID:
            with self.subTest(raw=raw["performative"]):
                parse_message(raw)
                self.assertEqual(list(VALIDATOR.iter_errors(raw)),[])
    def test_invalid_corpus_rejected_by_parser_and_schema(self):
        for raw in INVALID:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    parse_message(raw)
                self.assertNotEqual(list(VALIDATOR.iter_errors(raw)),[])

if __name__=="__main__": unittest.main()
