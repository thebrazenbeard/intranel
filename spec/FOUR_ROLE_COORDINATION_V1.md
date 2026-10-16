# INTRANEL/1 — Four-role engineering coordination profile (Draft V1)

Status: source-level profile, not an installed transport, always-on chat listener, or an authorization grant.

## Participants
- `vera:portal`: coordinator, collision registry and integration owner.
- `vera:integration`: source/runtime interface and integration tests.
- `vera:training`: model evaluation, independent critic and provenance.
- `vera:vn1`: VERA-NODE-1 qualification, node infrastructure and recovery.

These are **role addresses**, not newly created identities or credentials. The four ChatGPT chats must explicitly poll or be delivered messages; a GitHub comment alone never proves receipt by an active chat.

## Transport
Use the existing Chat Communication Bus as a durable relay of canonical `INTRANEL/1` packets. Each bus wrapper binds the original canonical payload digest. GitHub PRs remain authoritative for actual code, CI and review; Blotter for observed execution effects; Executor for physical commands. Slack may notify, not grant privileges.

The packet `origin` is the authored role; `actor` identifies the present relay; `target` is the actual recipient; `reply_to` names the reply route. Use `conversation_id` to bind a coordination round; `message_id` to deduplicate packets, and `parent_message_id` to link ACK, REVIEW and REPORT to prior messages.

## Dispatch and review
A coordinator proposes work with `REQUEST`; the recipient replies with `ACK` only after it has actually accepted the exact request, or `WAIT`/`CONFLICT` with a specific reason. A request is not an instruction that automatically executes. Each role reviews the other three at an exact `exact_subject` (commit SHA, immutable packet digest, or receipt digest). A `REVIEW` packet is a request for evidence-backed criticism, not a governance veto.

Require the following machine-readable fields in ordinary payloads: `role`, `claim_type`, `finding`, `evidence_refs`, `counterexample`, `proposed_repair`, and `owner`. In `REPORT`, `claim_type` distinguishes source, observation, inference, effect, verification and unknown.

Prohibited implication: status words `PASS`, `DONE`, `INSTALLED`, and `CONNECTED` cannot supersede independent verification. `RECEIPT` messages assert claims only. `EXECUTE` and `CANCEL` keep all existing receiver-side authority, effect-classification and idempotency requirements.

## Safe V1 pilot and acceptance
1. Generate canonical messages with the installed `intranel.parse_message` and `canonical_json_bytes`. No raw free-text fallback.
2. Stage one `REQUEST` addressed to each role with an exact pinned task subject and no effect privileges.
3. Deliver through a verified bus path and record each target's independently observed `ACK`, `WAIT`, or `CONFLICT`.
4. Record a disagreement from each reviewer without overwriting its `origin`.
5. Prove packet replay is idempotent; altered payload with reused identity is rejected.
6. Simulate a disconnected recipient. Distinguish pending delivery from receipt and from completed work.
7. Demonstrate a task's code/receipt readback through GitHub/Blotter separately from the Intranel message.

This draft PR implements **profile and local test helpers only**. The message bus relay, live authentication, background listeners, transport security, and message-delivery effects require subsequent adapters and separate qualification.

## Hostile review — accepted
Four messages from role labels do not create four agents or continuous interaction. A central GitHub issue may already suffice for slow engineering discussions. Intranel is justified only if it demonstrates reliable role-specific delivery, deduplication, acknowledgment and fault isolation without creating a second scheduler or another authority store.
