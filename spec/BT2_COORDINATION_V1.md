# BT2 no-effect coordination profile (research V1)

Status: **source-only**. This profile neither installs nor authenticates a
ChatGPT agent, listener, sender, Bus transport, or reviewer. It does not grant
execution authority or claim a participant has read an issued request.

## Scope and source binding

`intranel.bt2_coordination` creates/checks `BT2_BUS_ENVELOPE_V1` envelopes
around canonical `INTRANEL/1` messages. Only semantic `origin`, `actor`,
`reply_to`, and `target` in the two declared role addresses `bt2:one` and
`bt2:two` are accepted. These are **unauthenticated claims**, not credentials.
The actor must equal the origin for this first direct-author pilot; a relay
adapter requires separately qualified actor provenance.

Every packet is `READ_ONLY`, `OPEN`, carries an immutable
`git:<owner>/<repo>@<40-lowercase-hex>` or `sha256:<64-lowercase-hex>`
`exact_subject`, and binds `payload.event_id` to `conversation_id`.
`EXECUTE`, `CANCEL`, `RECEIPT`, mutations and asserted authority references
are rejected. `ACK`, `WAIT`, `REJECT`, and `CONFLICT` require a causal
`parent_message_id`. A syntactically valid ACK is still not accepted delivery.

Envelope identity fields and SHA-256 are recomputed from the canonical
semantic message; mismatched or additional wrapper keys are rejected.
The complete serialized envelope, not only its nested semantic message,
is byte-limited before carriage.
`unwrap_bt2` also requires the receiver to supply its own configured
`expected_target` and fails closed when the packet names someone else.
This validates internal packet consistency **only**; a malicious author can
create an internally consistent packet claiming someone else's role.

## Relation to Chat Communication Bus

`adapters/BUS_PROFILE_V1.md` remains the intended carrier contract. The
existing Bus issue #387 can be read manually as an *untrusted observation*
using the event correlation `bt2_live_coordination_intranel`. A Bus comment
containing similar field names is **not** a packet accepted by this code
until parsed through `unwrap_bt2` and receiver policy.

There is no live Bus observer, durable inbox, replay ledger, credential
attestation, recipient session binding, ACK acceptance, background polling,
encryption implementation, or trusted authority. The legacy four-role
Intranel pilot in Draft PRs #9/#10/#12 is distinct; its Vera role allowlist
must not be globally widened to admit BT2 by accident.

## Required later qualification

1. Identify and attest distinct One/Two sender and receiver sessions and
   their authorizing human/agent principals; validate sender-controlled keys
   or transport tokens at the receiver before interpreting role claims.
2. Build a receiver-owned exact-target ingress and durable replay/collision
   journal. Same `message_id` with changed semantics must fail closed after
   restart; an identical packet may be idempotently observed.
3. Prove source cursor completeness, remote comment edits/reordering gaps,
   duplicate delivery and lost/delayed messages without claiming remote/local
   atomicity where none exists.
4. Demonstrate a receiver-observed and independently attested response to a
   pinned exact request, then reconcile code/test/effect evidence separately.
5. Independently review source and tests at the exact PR head, with the
   concealed editor-startup execution hazard remediated before any installed
   or auto-executing editor workflow.

No merge, production deployment, protected action or Blotter append is
authorized by this source profile.
