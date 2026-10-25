# INTRANEL_HOST_PEER_V1 — bounded source-stage two-host data plane

Status: **candidate source/tests only; no authenticated Lappy/VN1/VN2 installation or live transport qualification**.

## Separation of responsibility

- `INTRANEL/1` owns semantic origin, actor, target, operation/subject,
  effect class, and receipt claim semantics.
- `INTRANEL_HOST_PEER_V1` owns only the bounded stream frames and durable
  delivery accounting for `OPEN` / `READ_ONLY` `QUERY` and `REPORT` packets.
- An **external, trusted SSH/OS transport adapter** must authenticate the host
  key fingerprint and OS account from the actual session and must supply the
  `ObservedPeer` identity after checking a pinned per-peer local policy.
  An inbound SSH server's own host key does **not** prove the inbound client's
  account/key/host. The adapter additionally needs carrier-attested client-user
  public-key identity, authenticated OS account, and an independently pinned
  peer-host mapping; none of those can come from untrusted `ObservedPeer`
  strings or JSON. Constructing an `ObservedPeer` object is not authentication.
- Receiver admission to any action/effect, model execution, or role authority
  is **not** supplied by SSH, Tailscale, a host name, a message, or this store.
- Chat Communication Bus remains the cross-chat transport. Its writer-local
  message IDs, envelopes and private lanes are independent of this host-peer
  data plane. Lappy must not become a required intermediate hop or CA.

## Wire and persistence

Frame: unsigned 4-byte network-order byte count, then exact canonical UTF-8
`INTRANEL/1` JSON bytes (max 65,536). The receiver rejects partial/oversize,
noncanonical, duplicate-key, invalid, expired, wrong-host, wrong-actor,
non-`QUERY/REPORT`, non-`READ_ONLY`, and non-`OPEN` data before durable commit.
Bounded but excessively nested JSON is a protocol conflict, not an uncaught
parser recursion failure.

`HostPeerStore.queue` transactionally writes an exact sender message/digest and
target as `PENDING`, keyed by semantic message ID. A caller sends the returned
bytes over a separately authenticated duplex stream using `write_frame`.

On receipt, the remote caller must supply a transport-verified `ObservedPeer`;
the store compares host, account, host-key fingerprint, and semantic origin to
receiver-configured trusted policy. A `BEGIN IMMEDIATE` transaction persists
the exact packet/digest and observed binding. After commit, the store returns
an ACK binding local host, sender host, message ID and SHA-256 of the payload.
The sender checks the ACK against **its** observed authenticated peer and the
exact pending record before marking `ACKED` in a durable transaction.

Lost ACK/reconnect → sender resends the **same message ID and bytes**;
receiver recognizes exact duplicate and returns the same receipt without a
second inbox mutation. When the original `expires_at` has elapsed, an **exact
previously committed** packet still gets that stored ACK, but a **new** expired
packet cannot be admitted. The receiver checks the first-admission expiry
inside the inbox transaction; an ACK does not extend the packet's authority.
The message ID is receiver-store-global, **not scoped to each peer**: two
different admitted peers using the same message ID trigger collision HOLD
even if their packets are otherwise valid. Senders must choose unique IDs
across all traffic to a receiver; this avoids ambiguous inbox/ACK identity.

Each SQLite database persists a `local_host` owner binding. Cold opening under
a different local host fails closed without changing queued records. Pre-owner
database files containing any inbox/outbox records cannot be silently adopted:
their origin must be verified through a separately reviewed migration first.
Empty legacy stores can establish their owner on initial open. Sender/receiver
both cold-reopen the same owned SQLite files without inventing delivery success
or deleting pending work. The owner marker is local misuse protection, not a
cryptographic host identity proof against someone able to edit the database.

An ACK is the authenticated endpoint's **claim of inbox durability** only;
without separate receiver DB readback it is not independently verified storage
evidence. It is not evidence a QUERY was answered,
a `REPORT` is true, a model ran, a process performed an action, or a physical
effect occurred. No effect dispatch and no model inference are implemented.

## Remaining live-admission work

1. Implement a host OS/SSH adapter that obtains the authenticated peer account
   and public-key identity, with an independently verified host-key/host
   mapping, from the *actual* carrier, not caller-provided strings. Restrict
   remote commands and validate launched source/version pin on both hosts; no
   credential export or new trust roots.
2. Prove Lappy↔VN1 and VN1↔VN2 over physical peer links, offline-Lappy
   independence, server process restarts, lost ACK, idempotent cold recovery,
   downgrade and wrong-account/fingerprint negatives. Record exact service
   versions and durable receiver inbox readback.
3. Add bounded queue quotas, supervision/operational instrumentation,
   retention, active peer/session revocation, owner migration procedure for
   unbound legacy stores with records, and a credential rotation policy before
   production use.
4. Preserve action authorization and receiver evidence as separate explicit
   gates before adding anything beyond READ_ONLY source transport.

Run source tests with `PYTHONPATH=src python -m unittest discover -s tests -v`.
