# INTRANEL/1 four-role causal inbox — Integration candidate V1

This code is a **durable receiver-side observation and correlation layer**, NOT an automatic transport, authenticated chat-to-chat connection, agent scheduler, execution engine, or receipt of participant consent.

## Implementation

- `intranel.four_role_ledger.FourRoleLedger` uses a local SQLite DB with distinct canonical packet observations and identity collisions.
- First observation wins per `(conversation_id, message_id)`. An exact replay returns DUPLICATE. Reuse of an identity with different canonical bytes returns CONFLICT, retains an immutable collision record, and taints *later* inspection of the original message as IDENTITY_COLLISION, even after database reopen.
- Four roles: `vera:portal`, `vera:integration`, `vera:training`, `vera:vn1`. Only a declared PORTAL REQUEST may target the other three. A declared peer may respond with ACK, WAIT or CONFLICT. These are **asserted roles**, not authenticated senders.
- This adapter requires an exact `git:owner/repo@40hex` subject, a single `conversation_id`, a parent-request message ID, matching `operation_id`, reverse role routing, and a `payload.request_digest` bound to the exact original canonical `content_digest`. Unmatched, wrong-type, wrong-subject, wrong-digest, wrong-role and expired replies never become correlated. Out-of-order replies are reclassified only after the parent request is observed.
- Every classification includes `origin_authenticated=false`, `delivered=false`, `ack_accepted=false` and `executed=false`. **Even a causally matched ACK does not prove acceptance.** Independent transport-origin attestation and receiver polling/readback are required separately.
- The CLI `python -m intranel.four_role_cli ingest|inspect|counts --ledger /path/to/inbox.sqlite3` handles local JSON files. `ingest` requires `--packet` and a separate `--source-ref` locator. That locator is untrusted observation metadata, never a signature.

## Scope and qualification

`python -m unittest discover -s tests -q` runs the baseline INTRANEL/1 parser/admission suite plus the new eight causal-ACK ledger tests and two subprocess/SQLite-restart tests. The isolated exact-head source checkout is based on Intranel PR #9 `9b943a98273a6f0f0c04fa5a642ea002f1c9fc9a`; no existing parser or admission contract was broadened.

The tests prove: valid REQUEST/reply correlation, persistent untrusted replay, wrong-parent/role/round/subject/digest rejection, duplicate and poisoned identity collision, late/expired response, strictly read-only pilot, out-of-order repair without guessing identity, subprocess intake and restart readback. They do **not** prove that actual PORTAL, Training, Integration, or VN1 chats received the packet or are connected through the Communication Bus.

## Next transport gate owned by PORTAL

Connect a **read-only, permission-scoped** GitHub/Communication Bus poller that obtains actual provider event/message identifiers, verifies the wrapper bytes independently and records observations. Existing VN1 polling evidence may be reused only with exact scope and its independent status. Then add authenticated sender binding and explicit recipient-owned processing/acceptance receipts with durable cursor/crash replay; a GitHub comment being visible to a poller does **not** establish acceptance by a ChatGPT session.

PORTAL is lead and owns merge/integration sequencing. This Integration candidate does not edit the PORTAL-owned PR #9 branch, enable services, mutate credentials, grant authority, or perform protected effects.


## Read-only public PR #9 ingress

Run python -m intranel.four_role_cli poll --ledger inbox.sqlite3 --pages 1.
The poller fetches only the public thebrazenbeard/intranel PR #9
GitHub comment endpoint, with bounded pagination, response sizes, and a
bounded count of explicitly fenced JSON packets per comment. Arbitrary prose
and noncausal REPORT messages are not admitted as causal ACKs; malformed or
forged packets are rejected, never executed. Every admitted observation gets
a provider comment-ID locator, but this is still not authenticated source
identity, recipient polling or task acceptance. Re-polling is idempotent
unless a conflicting packet reuses an exact message ID.

This source includes four mocked-provider negative tests plus the live
operator readback path. It does not install a service, schedule polling, grant
permissions or fetch private Chat Communication Bus traffic.

## Causal parent collision invalidation

A REQUEST's (conversation_id, message_id) can become ambiguous after a
conflicting source packet reuses its identity. Even an already correlated ACK,
WAIT or CONFLICT must subsequently classify as PARENT_IDENTITY_COLLISION,
not CAUSALLY_MATCHED_UNAUTHENTICATED. This persists across SQLite reopen,
applies to out-of-order replies, and does not imply recipient acceptance or
authenticated sender. Regression tests cover both matched and late children.

The read-only public PR #9 poll was exercised against live GitHub comments:
12 comments, 8 fenced candidate packets, 5 new causal observations,
3 ignored noncausal reports, zero authenticated origins or deliveries.
The exact R2 Integration REQUEST was observed at comment 6218392575,
digest d4d8a307fbffbf758e475275864200d759ce15a2968f0cd27848df7434aeb67c,
classified REQUEST_STAGED_UNDELIVERED. These are host-observed source readbacks,
not session-to-session message delivery or a live service installation.
No scheduler was installed.
