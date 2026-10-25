> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# Intranel

Intranel is Vera's machine-oriented internal coordination protocol family. The current protocol is `INTRANEL/1`.

It exists to reduce ambiguity in chat-to-chat, lane-to-lane, reviewer, relay, and infrastructure coordination by separating message intent, identity, operation correlation, exact subject, authority claims, constraints, effect class, security profile, and receipts into deterministic fields.

Intranel is **not a chain-of-thought transport**. It is **not an authority source**. It is not a claim of shared consciousness or hidden process continuity. It carries explicit coordination data that receivers must validate independently.

## V1 contains

- strict `INTRANEL/1` message parsing and Draft 2020-12 schema parity tests;
- namespaced addressing with distinct `origin`, `actor`, `target`, and `reply_to`;
- closed performative/effect/security vocabularies;
- packet identity separate from logical operation and cancellation-target identity;
- receiver evidence bound to exact message/operation identity;
- receiver-owned effect classification before mutation authority checks;
- hard constraint/prohibition and transport-security admission evidence;
- deep-immutable payload/receipt semantic state;
- bounded canonical UTF-8 JSON and SHA-256 content identity;
- relay-safe operation-semantic digests and fail-closed duplicate handling;
- cancellation state/cancellability evidence;
- completed-operation idempotency that deduplicates an already-completed cancellation without trying to re-cancel its target;
- receipt claims bound to prior operation/state without self-verifying their effect;
- frozen interoperability vectors;
- security-profile and Chat Communication Bus transport specifications.

## V1 deliberately does not contain

- production deployment/cutover;
- encryption or key-management implementation;
- binary wire encoding;
- automatic authority delegation;
- automatic proof that a receipt's claimed effect is true;
- hidden reasoning transfer.

## Optional four-role coordination pilot (not activated)

The source tree includes a bounded local pilot for `vera:portal`,
`vera:integration`, `vera:training`, and `vera:vn1`. Its canonical wrappers,
causal SQLite observation ledger, atomic receiver staging, and read-only
reconciliation preserve message identity, target, and parent relationships.
The opt-in CLI can ingest local JSON packets or explicitly poll public Intranel
PR #9 comments; it does not run a background service.
Its poller rejects duplicate JSON keys and reports incomplete coverage rather
than silently truncating over-limit or undecodable comments.
Stored observation content must still match its recorded canonical digest;
at-rest mismatch causes a local HOLD rather than a correlated reply. Expired
reply envelopes are likewise held as `EXPIRED_REPLY` even when the parent is
unexpired. These are evidence checks, not database-writer authentication.

An observed or causally matched reply remains **unauthenticated and unverified**:
it does not establish delivery, accepted ACK, execution, or authority. A
receiver-bound ledger requires an explicit `--expected-target`; the local
receiver only stages untrusted evidence. No Chat Communication Bus deployment,
credential installation, scheduled polling, or production transport is provided.
`local_pair_verified` describes consistency within a SQLite read snapshot only:
a concurrent writer can commit a collision after that snapshot. It is not
currentness or acceptance authority. Any future protected effect must perform
its own transactionally synchronized currentness and authorization check; an
uncoordinated readback would still race.

See [four-role coordination](spec/FOUR_ROLE_COORDINATION_V1.md),
[causal inbox](spec/FOUR_ROLE_CAUSAL_INBOX_V1.md), and
[atomic receiver](spec/FOUR_ROLE_ATOMIC_RECEIVER_V1.md) for the bounded
contracts; [Integration's V1 continuation](docs/continuation/INTRANEL_INTEGRATION_CONTINUATION_20261016_V1.md)
records the historical pilot context, not live operation.

## Verify locally

```bash
python -m pip install -e ".[test]"
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```

See `spec/INTRANEL_1.md` for normative semantics and `docs/superpowers/specs/2026-09-17-intranel-v1-design.md` for the architecture rationale.

## Source-only editor startup safety

CI checks the checked-out source before installing dependencies on Ubuntu and Windows. The test workflow runs for pull requests and pushes to `main` (and the existing V1 work branch). It rejects folder-open editor tasks, repository-supplied automatic task consent, symlinked editor/font surfaces, and executable-like files in `public/fonts`. Run `python scripts/check_editor_startup_source.py` locally to repeat the check; `python -m unittest discover -s tests -p test_editor_startup_guard.py -v` exercises inert regression fixtures. Neither command runs editor tasks or font assets.

This is source containment for the checked-out tree. It does not establish whether any previous local checkout opened in an editor executed an unsafe task; that requires separate host investigation. A CI pass is not deployment or runtime authority.
