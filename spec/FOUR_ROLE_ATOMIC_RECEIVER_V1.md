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
