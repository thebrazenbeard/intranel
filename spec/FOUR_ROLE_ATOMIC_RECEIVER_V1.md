# Four-role receiver-owned atomic inbox — opt-in source prototype

## Exact scope and owner

Integration lane, stacked on Intranel Integration Draft PR #10
`38d7a4f0902e55c63c914c9236b761e7eae6eaef`, itself stacked on
PORTAL Intranel Draft PR #9 `c35559fa3d33c6a75ad8f00e42a9fbc8b9c6c888`.
PORTAL retains build-lead/production-adoption authority. No merge, deploy,
registration, listener, scheduler, credential change, or prior state migration.

## Corrected failure mode

Legacy `LocalCoordinationInbox` and `FourRoleLedger` write independent SQLite
files. A crash between their transactions makes one-sided observations
possible. The read-only reconciler detects known divergence but cannot
offer atomicity or a single durable receipt.

`AtomicRoleReceiver` in `four_role_receiver.py` opts into ONE receiver-owned
SQLite file. A `receive(envelope, source_ref)` call validates the canonical
INTRANEL/1 read-only packet, its configured recipient, and the causal
four-role constraints BEFORE writing. It commits both `observed`
and `receiver_staged` within one `BEGIN IMMEDIATE` transaction.
The parent REQUEST can be an earlier separately observed *outbound*
coordinator request in that same file. Receiving a reply does not require
a second live staging DB. A raised exception between the two inserts
rolls back the entire transaction; retries deduplicate exact bytes.
Competing same-role replies and parent collisions continue to use
the original `FourRoleLedger.classify` rules.

## Important authority ceilings

- Explicit opt-in only. Existing PR9 inbox and PR10 polling/CLI remain
  unchanged; this is not live wiring, active delivery or installed transport.
- The DB's `receiver_binding` is durable; reopening for a different role HOLDS.
- Existing same-ID observations without a paired receiver receipt HOLD;
  never silently backfill or erase legacy evidence.
- Cross-round message-ID reuse HOLDS. Same-round changed bytes create
  an immutable collision record, not a second accepted packet.
- The result cannot assert sender authentication, recipient session
  processing, ACK acceptance, protected effect or external transaction
  commit. All those fields remain false.
- `FourRoleLedger.observe` is intentionally available for locally
  observed outbound parents. It must NOT be used to bypass
  `receive` for inbound production packet staging.

## Adversarial acceptance and remaining gaps

`tests/test_four_role_atomic_receiver.py` covers transaction fault injection,
cold reopen/replay, forced child-process exit between the two inserts,
role mismatch, legacy unpaired state, cross-round replay, staged-packet
tampering, same-ID mutation/collision, competing reply claims, and
parallel duplicate writers.

> Hostile challenge: One SQLite transaction only closes the local
> observation/staging split. It does NOT atomically couple remote GitHub
> comment polling, source cursor checkpoints, dispatch, ChatGPT session
> receipt, or remote ACK. Multiple polling processes must not mistake
> a local row for delivered or independently authenticated consent.

> Hostile challenge: A forced Python exception before COMMIT demonstrates
> rollback, not power-failure fsync qualification. Any production cut must
> specify durability pragmas, physical-host crash/restart qualification
> and a single receiver-owned route and source-offset commit policy.

Before adoption, PORTAL must decide whether this file replaces the two-store
path, how outbound REQUESTs enter the same authoritative DB, and how
legacy rows are preserved/read without fabricating provenance or ACKs.
Do not automatically migrate, merge databases, or claim installed behavior.

## Receiver-mode CLI and legacy writer fence (draft source only)

Using `--expected-target vera:portal` explicitly selects
`AtomicRoleReceiver` for ingest, inspection, counts and bounded GitHub polling.
`--outbound-request` is a separate locally initiated parent-request path.
The receiver class refuses inherited `observe`, and the legacy
`FourRoleLedger.observe` rejects any SQLite database containing the
`receiver_binding` schema. Legacy direct inspection of receiver-bound
records also fails closed. Standalone unbound legacy ledgers remain supported.

The GitHub scanner accepts an explicit receiver ingress callback. It still
has only bounded page sampling, no durable provider cursor in the atomic
transaction, and no authenticated sender/device/ChatGPT delivery. A final
full page returns incomplete coverage, not an accepted or delivered ACK.
Source/test evidence is distinct from installing a route or activating a
resident watcher. No scheduled task, branch merge or runtime migration
is implied by this draft.

## Explicit bounded comment-page continuation (source only)

`four_role_cli poll --start-page 4 --pages 3` can manually inspect
later comment windows that the prior fixed page-1..3 scan missed. Each call
remains limited to three pages and provider page numbers 1..100. A resumed
window never claims `coverage_complete=true`: it reports
`HOLD_PRECEDING_PAGES_UNVERIFIED` if it sees a short terminal page,
or `HOLD_COMMENT_PAGINATION_LIMIT` with a `next_page` on full pages.
At page 100 the reader returns `HOLD_COMMENT_PAGE_CEILING` without a
fabricated next page. It also supplies `start_page`, `last_page`,
`pages_read` and `terminal_page_observed` to distinguish local sampling
from provider snapshot currentness. This does not persist a cursor,
authenticate the comment origin, obtain a consistent provider snapshot, or
establish delivered or accepted ACKs. Existing receiver-owned SQLite
observation/receipt atomics and actor/effect ceilings are unchanged.

## Receiver-owned comment packet evidence experiment (source only)

When called by the bounded PR9 read-only scanner with a validated
`comment_id`, `AtomicRoleReceiver.receive` now commits three local
facts in the SAME receiver SQLite `BEGIN IMMEDIATE`: canonical
observation, staging receipt and `receiver_comment_packet` marker.
`receiver_comment_highwater` is an upper bound over locally processed
**packet-bearing** comment IDs, **not** all PR comments, source snapshot,
or an authenticated cursor. An existing staged packet without a comment
marker is **never backfilled** as proof. A previously unknown packet from
a smaller comment ID than recorded highwater HOLDS; an exact marker
replay deduplicates without advancing. All comment markers require an
exact PR9 source locator and positive integer comment ID. Test fault
injection after staging but before marker insertion rolls back all
three records; reopened receiver readback verifies this.

This is explicitly an experiment. Page offsets can reorder on
insertion/deletion; some comments have no admissible packet;
GitHub provider consistency and signer identity are unproven; the
checkpoint cannot attest complete scanned coverage or remote
delivery. No background fetcher, cursor-based service, acceptance,
or installation is introduced. PORTAL independent review required.
