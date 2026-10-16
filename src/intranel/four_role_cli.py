"""Local INTRANEL/1 four-role observation CLI, not a live transport.

Only locally records supplied packets. Outputs never assert delivery or actor
authentication. Example:
 python -m intranel.four_role_cli ingest --ledger inbox.sqlite \
   --packet request.json --source-ref github:thebrazenbeard/intranel#9/comment/123
 python -m intranel.four_role_cli inspect --ledger inbox.sqlite \
   --conversation-id pilot-1 --message-id request-1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .four_role_ledger import CoordinationError, FourRoleLedger


def run(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("ingest", "inspect", "counts", "poll", "reconcile"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--source-ref")
    parser.add_argument("--pages", type=int, default=1, help="Bounded read-only GitHub PR9 poll")
    parser.add_argument("--conversation-id")
    parser.add_argument("--message-id")
    parser.add_argument("--staging-ledger", type=Path,
                        help="PORTAL's recipient-local inbox for read-only consistency audit")
    parser.add_argument("--expected-target",
                        help="Receiver-owned Intranel role binding")
    args = parser.parse_args(argv)
    if args.command == "reconcile":
        from .four_role_reconcile import audit_local_inbox
        if args.staging_ledger is None or not args.expected_target:
            raise CoordinationError("reconcile requires staging ledger and exact receiver role")
        # Do not initialize a ledger here: audit may not create files/DDL.
        return audit_local_inbox(args.ledger, args.staging_ledger,
                                 expected_target=args.expected_target)
    ledger = FourRoleLedger(args.ledger)
    if args.command == "ingest":
        if args.packet is None or args.packet.is_symlink() or not args.packet.is_file():
            raise CoordinationError("packet must be an existing non-symlink file")
        if args.packet.stat().st_size > 65536:
            raise CoordinationError("packet exceeds Intranel message limit")
        if not args.source_ref:
            raise CoordinationError("source locator required")
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        if type(packet) is not dict:
            raise CoordinationError("packet must be JSON object")
        return ledger.observe(packet, args.source_ref)
    if args.command == "poll":
        from .four_role_github import observe_pr_comments
        return observe_pr_comments(ledger, pages=args.pages)
    if args.command == "inspect":
        if not args.conversation_id or not args.message_id:
            raise CoordinationError("inspection requires conversation and message IDs")
        return ledger.classify(args.conversation_id, args.message_id)
    return ledger.counts()


def main() -> int:
    try:
        print(json.dumps(run(), sort_keys=True))
        return 0
    except (CoordinationError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "HELD", "reason": str(exc)[:250],
                          "delivered": False, "ack_accepted": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
