# INTRANEL_HOST_PEER_V1 — bounded source-stage two-host data plane

Status: **candidate source/tests with opt-in SSH carrier; no authenticated Lappy/VN1/VN2 installation or live transport qualification**.

## Separation of responsibility

- `INTRANEL/1` owns semantic origin, actor, target, operation/subject,
  effect class, and receipt claim semantics.
- `INTRANEL_HOST_PEER_V1` owns only the bounded stream frames and durable
  delivery accounting for `OPEN` / `READ_ONLY` `QUERY` and `REPORT` packets.
- The opt-in `ssh_carrier` module provides a restricted **client and POSIX
  forced-command receiver adapter**, but source presence does not attest that
  sshd actually enforces the required configuration. The outbound client
  validates one pinned server host key in a literal `known_hosts` record,
  creates an isolated snapshot, and invokes an absolute OpenSSH binary with
  strict host-key/public-key-only/no-forwarding/no-proxy configuration. The
  receiver uses OS UID/account plus OpenSSH `SSH_USER_AUTH` authentication
  record to pin the separate **inbound client-user key** to a logical peer
  host. Each side compares the relevant observed fingerprint/account to its
  distinct `HostPeerStore` trusted-peer policy. The legacy
  `ObservedPeer.host_key_fingerprint` field carries a carrier key fingerprint:
  **outbound ACK = remote server host key; inbound request = client-user key**.
  Those are never interchangeable; a host key alone does not prove the sender.
- Source code **cannot independently prove** the receiver was launched via
  restricted sshd `ForceCommand`. OpenSSH writes `SSH_USER_AUTH` under the
  receiver login UID (see OpenSSH `session.c`), so that account can replace
  the record if it has unrestricted shell/process/file access. Real use is
  conditional on an independently verified locked-down dedicated account,
  root-owned receiver policy, `ExposeAuthInfo yes`, `ForceCommand`,
  public-key-only auth, `DisableForwarding yes`, `PermitTTY no`, controlled
  `AcceptEnv`/`PermitUserEnvironment`, and an SSH session timeout. The
  receiver fails closed on missing, symlinked, non-owned, world-readable,
  malformed, multi-method, and non-ed25519 auth records. `ObservedPeer`
  construction itself is still not authentication. Key possession binds an
  admitted client identity, not independent physical-device custody proof.
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
The SSH forced-command receiver additionally requires EOF immediately after
one complete frame, before SQLite mutation and ACK. A second frame or suffix
is rejected atomically; the configured sshd session timeout must bound a
malicious sender that refuses to close stdin.

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

1. **Install and independently qualify** the conditional SSH adapter on a
   dedicated POSIX receiver account. `intranel-host-peer-receive` reads only
   `/etc/intranel/host-peer.json` (not caller-supplied config arguments),
   which must be root-owned, regular, non-symlink, and not group/other writable.
   The JSON shape is:

   ```json
   {"local_host":"vn2","sqlite_path":"/var/lib/intranel/peer.sqlite3",
    "peers":{"vn1":{"account":"intranelrx",
                     "client_key_fingerprint":"SHA256:REPLACE_WITH_REAL_PUBLIC_KEY_FINGERPRINT"}}}
   ```

   This is **illustrative only**, not a valid enrolled identity. All configured
   peer accounts must equal the OS account running the forced command; each
   client fingerprint must map to exactly one host. `SSH_USER_AUTH` must be
   produced by a reviewed sshd session, not set by a caller. Administrators
   must independently verify the effective `sshd -T -C ...` Match policy,
   forced command, account shell/authorized-keys restrictions, received key
   identity, configured source/version, and database permissions. This source
   does not edit host configurations or access private key material.
   Outbound `SSHClientConfig` requires an absolute SSH binary/identity path,
   an exact one-key known-hosts file, pinned SHA-256 server host fingerprint,
   and target account/network hostname; no TOFU, password, proxy, forwarding,
   multiple host keys, or downgrade fallback is allowed. Sender only commits
   ACK after SSH exits successfully, and unsuccessful exchanges leave pending
   state for resend. Sender has a 30-second process kill deadline; receiver
   relies on independently provisioned sshd deadline and supervision.
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

No Windows sshd auth-info ownership adapter exists yet, so Windows machines
cannot serve as receiver with this module. The Linux/POSIX service is source
only until actual account, sshd, installed binary and version, network route,
and exact on-disk receiver inbox are verified on physical hosts.

Run source tests with `PYTHONPATH=src python -m unittest discover -s tests -v`.
