"""Real subprocess/SQLite readback for the bounded four-role CLI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_four_role_ledger import CONVERSATION, request, reply


class FourRoleCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.db = self.directory / "inbox.sqlite3"

    def invoke(self, *args):
        p = subprocess.run(
            [sys.executable, "-B", "-m", "intranel.four_role_cli",
             *args, "--ledger", str(self.db)],
            capture_output=True, text=True, timeout=20,
            env={**os.environ, "PYTHONDONTWRITEBYTE": "1"},
        )
        text = p.stdout if p.returncode == 0 else p.stderr
        return p.returncode, json.loads(text)

    def packet(self, name, data):
        path = self.directory / name
        path.write_text(json.dumps(data), encoding="utf8")
        return str(path)

    def test_persist_out_of_order_and_restart_then_reject_collision(self):
        req = request()
        ans = reply(req)
        resp = self.packet("reply.json", ans)
        parent = self.packet("request.json", req)
        code, first = self.invoke("ingest", "--packet", resp, "--source-ref", "github:comment2")
        self.assertEqual(code, 0, first)
        self.assertEqual(first["classification"], "UNMATCHED_REPLY")
        code, parent_observed = self.invoke(
            "ingest", "--packet", parent, "--source-ref", "github:comment1"
        )
        self.assertEqual(code, 0, parent_observed)
        code, matched = self.invoke(
            "inspect", "--conversation-id", CONVERSATION,
            "--message-id", "reply-1"
        )
        self.assertEqual(code, 0, matched)
        self.assertEqual(matched["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")
        self.assertFalse(matched["ack_accepted"])
        self.assertFalse(matched["delivered"])
        code, replay = self.invoke(
            "ingest", "--packet", resp, "--source-ref", "github:comment2"
        )
        self.assertEqual(code, 0, replay)
        self.assertEqual(replay["ingest"], "DUPLICATE")
        modified = dict(ans)
        modified["payload"] = dict(ans["payload"], finding="different bytes, same ID")
        changed = self.packet("modified.json", modified)
        code, collision = self.invoke(
            "ingest", "--packet", changed, "--source-ref", "github:conflict"
        )
        self.assertEqual(code, 0, collision)
        self.assertEqual(collision["classification"], "IDENTITY_COLLISION")
        code, poisoned = self.invoke(
            "inspect", "--conversation-id", CONVERSATION, "--message-id", "reply-1"
        )
        self.assertEqual(code, 0, poisoned)
        self.assertEqual(poisoned["classification"], "IDENTITY_COLLISION")
        code, totals = self.invoke("counts")
        self.assertEqual(code, 0, totals)
        self.assertEqual(totals, {"observations": 2, "collisions": 1})

    def test_unparented_ack_fails_without_creating_receipt(self):
        message = reply(request(), parent_message_id=None)
        path = self.packet("unparented.json", message)
        code, denied = self.invoke(
            "ingest", "--packet", path, "--source-ref", "github:untrusted"
        )
        self.assertEqual(code, 2, denied)
        self.assertEqual(denied["status"], "HELD")
        code, counts = self.invoke("counts")
        self.assertEqual(counts["observations"], 0)


    def test_bound_receiver_cli_rejects_legacy_and_explicit_ingest_works(self):
        from contextlib import closing
        import sqlite3
        from intranel.four_role_receiver import AtomicRoleReceiver
        AtomicRoleReceiver(self.db, expected_target="vera:portal")
        req = self.packet("bound-request.json", request())
        ans = self.packet("bound-reply.json", reply(request()))
        for command in (
            ("ingest", "--packet", ans, "--source-ref", "github:legacy"),
            ("poll",),
            ("inspect", "--conversation-id", CONVERSATION, "--message-id", "reply-1"),
        ):
            code, result = self.invoke(*command)
            self.assertEqual(code, 2, result)
            self.assertEqual(result["status"], "HELD")
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM observed").fetchone()[0], 0)
        code, parent = self.invoke(
            "ingest", "--expected-target", "vera:portal", "--outbound-request",
            "--packet", req, "--source-ref", "local:coordinator"
        )
        self.assertEqual(code, 0, parent)
        code, received = self.invoke(
            "ingest", "--expected-target", "vera:portal", "--packet", ans,
            "--source-ref", "github:peer"
        )
        self.assertEqual(code, 0, received)
        self.assertEqual(received["classification"], "CAUSALLY_MATCHED_UNAUTHENTICATED")
        self.assertFalse(received["ack_accepted"])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM receiver_staged").fetchone()[0], 1)
        code, replay = self.invoke(
            "ingest", "--expected-target", "vera:portal", "--packet", ans,
            "--source-ref", "github:peer"
        )
        self.assertEqual(code, 0, replay)
        self.assertEqual(replay["ingest"], "DUPLICATE")

if __name__ == "__main__":
    unittest.main()
