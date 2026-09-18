import unittest

from intranel.message import parse_message


def base_message(observed_at, expires_at):
    return {
        "protocol": "INTRANEL/1",
        "origin": "review:one",
        "actor": "review:one",
        "target": "review:target",
        "reply_to": "review:one",
        "message_id": "fractional-time",
        "conversation_id": "intranel-r3",
        "performative": "QUERY",
        "observed_at": observed_at,
        "expires_at": expires_at,
        "effect_class": "READ_ONLY",
        "security_profile": "OPEN",
    }


class FractionalTimestampPrecisionHostileTest(unittest.TestCase):
    def test_sub_microsecond_ordering_remains_distinguishable(self):
        message = base_message(
            "2026-09-18T00:00:00.0000001Z",
            "2026-09-18T00:00:00.0000002Z",
        )
        parsed = parse_message(message)
        self.assertEqual(parsed.observed_at, message["observed_at"])
        self.assertEqual(parsed.expires_at, message["expires_at"])


if __name__ == "__main__":
    unittest.main()
