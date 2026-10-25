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

## Experimental intra-machine host-peer data plane

[`INTRANEL_HOST_PEER_V1`](spec/INTRANEL_HOST_PEER_V1.md) documents an opt-in,
bounded `OPEN` / `READ_ONLY` `QUERY`/`REPORT` exchange for independent hosts.
The source implementation provides exact canonical message framing,
receiver-checked configured host/account/fingerprint bindings, durable SQLite
inbox/outbox and stored ACK/readback with cold-restart replay control.
`intranel.ssh_carrier` now supplies a **source-stage, conditional SSH adapter**:
an outbound OpenSSH subprocess with an independently verified exact server
host-key pin, no password/proxy/forwarding fallback, and bounded one-frame
reply; plus a POSIX `intranel-host-peer-receive` forced-command entrypoint
that admits only one `ssh-ed25519` public-key auth record from `SSH_USER_AUTH`,
pins the authenticated **client** key to a logical host, and uses the actual
OS UID/account. These are **two different keys** and two different policies.
The server's host key alone does not prove who connected to it.
The forced receiver requires stream EOF after exactly one framed packet
*before* persisting anything or returning an ACK. Its caller closes stdin;
the required sshd session timeout must independently bound a peer that stalls
instead of closing the stream.

**Not installed or qualified:** The receiver's auth-info file is writable by
its login UID and can be forged if the account permits shell/other commands;
it is **not standalone cryptographic evidence**. Real admission requires an
administrator-verified dedicated restricted OpenSSH account with `ForceCommand`,
`ExposeAuthInfo`, public-key-only authentication, controlled environment,
disabled forwarding, and independently enrolled/pinned client and server keys.
No such Lappy/VN1/VN2 operating-system configuration or live SSH exchange has
been read back or qualified in this source branch. POSIX receiver only;
Windows-host receiver admission is not implemented. This code does not
provision credentials, models, or authority, run a remote query, or establish
a production worker. Remote ACKs remain storage **claims** until separately
read back at the receiver.
The SQLite DB pins its local-host owner; an existing unowned DB with records
requires a reviewed migration. Already-committed exact retries can recover a
lost ACK after packet expiry; new expired packets remain denied. Message IDs
are unique per receiver store across all admitted sender peers.

This host-peer seam is **distinct** from the optional Chat Communication Bus
wire profile, which carries cross-chat coordination and has its own writer
identity, permissions, and delivery state. Neither transport grants action
authority from receipt or route selection.

## Verify locally

```bash
python -m pip install -e ".[test]"
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```

See `spec/INTRANEL_1.md` for normative semantics and `docs/superpowers/specs/2026-09-17-intranel-v1-design.md` for the architecture rationale.
