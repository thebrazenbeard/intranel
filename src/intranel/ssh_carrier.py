"""Narrow POSIX/OpenSSH forced-command receiver for OPEN/READ_ONLY packets.

This module reads sshd's ``ExposeAuthInfo`` authentication record and the
actual process UID. Its caller MUST be a trusted sshd ForceCommand under a
locked-down dedicated account, with client-controlled environment disabled.
The record alone is NOT cryptographic attestation: OpenSSH writes it under the
authenticated login UID, which could otherwise replace or forge the file.
No process deployment or sshd policy verification is implemented here.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import threading
from typing import BinaryIO, Mapping

from .host_peer import HostPeerConflict, HostPeerStore, ObservedPeer, read_frame, write_frame


MAX_AUTH_INFO_BYTES = 4096
_HOSTNAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,253}$")
_ACCOUNT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9._-]{0,127}$")


@dataclass(frozen=True)
class SSHClientConfig:
    peer_host: str
    network_host: str
    remote_account: str
    port: int
    ssh_executable: Path
    identity_file: Path
    known_hosts: Path
    server_host_key_fingerprint: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, Path) for value in (
                self.ssh_executable, self.identity_file, self.known_hosts)):
            raise HostPeerConflict("SSH executable/credential/host-pin paths required")
        if not _HOSTNAME.fullmatch(self.network_host) or not _ACCOUNT.fullmatch(self.remote_account):
            raise HostPeerConflict("invalid SSH host/account")
        if not isinstance(self.port, int) or not 0 < self.port <= 65535:
            raise HostPeerConflict("invalid SSH port")
        ObservedPeer(self.peer_host, self.remote_account, self.server_host_key_fingerprint)


def current_os_account() -> str:
    """Use kernel UID, not the caller-editable LOGNAME/USER environment."""
    if os.name != "posix":
        raise HostPeerConflict("POSIX sshd account admission required")
    import pwd

    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError as exc:
        raise HostPeerConflict("current UID has no account name") from exc


def _auth_file_bytes(filename: str | Path) -> bytes:
    """Read an owned, private, non-symlink OpenSSH auth-info record once."""
    if os.name != "posix":
        raise HostPeerConflict("POSIX auth-info ownership check required")
    try:
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except (OSError, ValueError, TypeError) as exc:
        raise HostPeerConflict("missing or unsafe SSH_USER_AUTH file") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or info.st_mode & 0o077):
            raise HostPeerConflict("SSH_USER_AUTH file ownership or mode unsafe")
        with os.fdopen(fd, "rb", closefd=False) as source:
            payload = source.read(MAX_AUTH_INFO_BYTES + 1)
    except OSError as exc:
        raise HostPeerConflict("unreadable SSH_USER_AUTH file") from exc
    finally:
        os.close(fd)
    if not 0 < len(payload) <= MAX_AUTH_INFO_BYTES:
        raise HostPeerConflict("SSH_USER_AUTH record exceeds bound or empty")
    return payload


def _ed25519_fingerprint(auth_info: bytes) -> str:
    """Accept only a single completed ssh-ed25519 public-key authentication."""
    try:
        text = auth_info.decode("ascii", "strict")
        if not text.endswith("\n") or text.count("\n") != 1:
            raise HostPeerConflict("ambiguous SSH authentication methods")
        parts = text[:-1].split(" ")
        if len(parts) != 3 or parts[:2] != ["publickey", "ssh-ed25519"]:
            raise HostPeerConflict("SSH authentication must be one ed25519 publickey")
        blob = base64.b64decode(parts[2], validate=True)
        if base64.b64encode(blob).decode("ascii") != parts[2]:
            raise HostPeerConflict("noncanonical SSH public key")
        # SSH ed25519 key blob = SSH string algorithm + SSH string 32-byte key.
        prefix = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"
        if len(blob) != len(prefix) + 32 or not blob.startswith(prefix):
            raise HostPeerConflict("invalid SSH ed25519 key blob")
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise HostPeerConflict("invalid SSH auth-info public key") from exc
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
    return "SHA256:" + digest


def peer_from_sshd_auth_info(auth_info_file: str | Path,
                             key_to_host: Mapping[str, str]) -> ObservedPeer:
    """Map successful sshd client-user key to configured host identity.

    This is a conditional trust adapter: the entrypoint must have been forced
    and its authentication record/environment protected by a reviewed sshd
    account policy. It cannot independently establish those deployment facts.
    """
    if not isinstance(key_to_host, Mapping) or not key_to_host:
        raise HostPeerConflict("SSH client key admission policy required")
    fingerprint = _ed25519_fingerprint(_auth_file_bytes(auth_info_file))
    host = key_to_host.get(fingerprint)
    if host is None:
        raise HostPeerConflict("SSH authenticated client key not admitted")
    return ObservedPeer(host=host, os_account=current_os_account(),
                        host_key_fingerprint=fingerprint)


def receive_forced_command(store: HostPeerStore, source: BinaryIO, sink: BinaryIO,
                           auth_info_file: str | Path,
                           key_to_host: Mapping[str, str]) -> None:
    """Receive exactly one framed packet; ACK only after durable SQLite commit.

    The operator is responsible for enforcing this function as the only SSH
    command available to the account and setting a session deadline.
    """
    peer = peer_from_sshd_auth_info(auth_info_file, key_to_host)
    packet = read_frame(source)
    if packet is None:
        raise HostPeerConflict("missing SSH host-peer frame")
    ack = store.receive(packet, observed_peer=peer)
    write_frame(sink, ack)


def verified_known_hosts_line(config):
    """Pin an exact single OpenSSH ed25519 server-host key, no TOFU or CA.

    Deliberately rejects hashed/wildcard/multiple known-host entries until a
    stricter identity-aware verifier is implemented. The public key is not a
    secret; this function never opens a private identity key.
    """
    if not isinstance(config, SSHClientConfig):
        raise HostPeerConflict("SSH client config required")
    try:
        if config.known_hosts.is_symlink():
            raise HostPeerConflict("symlink known-hosts file refused")
        with config.known_hosts.open("rb") as f:
            content = f.read(MAX_AUTH_INFO_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise HostPeerConflict("SSH pinned known-hosts unavailable") from exc
    if not 0 < len(content) <= MAX_AUTH_INFO_BYTES or content.count(b"\n") != 1:
        raise HostPeerConflict("pinned known-hosts must contain one entry")
    try:
        fields = content[:-1].decode("ascii", "strict").split(" ")
        if len(fields) != 3 or fields[:2] != [config.network_host, "ssh-ed25519"]:
            raise HostPeerConflict("SSH host alias/key algorithm mismatch")
        fingerprint = _ed25519_fingerprint(
            f"publickey ssh-ed25519 {fields[2]}\n".encode("ascii"))
    except UnicodeError as exc:
        raise HostPeerConflict("invalid SSH pinned known-host encoding") from exc
    if fingerprint != config.server_host_key_fingerprint:
        raise HostPeerConflict("SSH server host key fingerprint mismatch")
    return content


def build_ssh_command(config, *, known_hosts_snapshot):
    """Construct a no-shell, no-password, direct-link SSH invocation."""
    if not isinstance(config, SSHClientConfig):
        raise HostPeerConflict("SSH client config required")
    if not (config.ssh_executable.is_absolute() and config.identity_file.is_absolute()
            and Path(known_hosts_snapshot).is_absolute()):
        raise HostPeerConflict("SSH paths must be absolute")
    opts = [
        "BatchMode=yes", "NumberOfPasswordPrompts=0",
        "PreferredAuthentications=publickey", "PasswordAuthentication=no",
        "KbdInteractiveAuthentication=no", "GSSAPIAuthentication=no",
        "StrictHostKeyChecking=yes", "UpdateHostKeys=no",
        "VerifyHostKeyDNS=no", "CheckHostIP=no",
        "HostKeyAlgorithms=ssh-ed25519", "IdentitiesOnly=yes",
        "ForwardAgent=no", "ClearAllForwardings=yes", "RequestTTY=no",
        "ProxyCommand=none", "ProxyJump=none", "ConnectionAttempts=1",
        "ConnectTimeout=10", f"HostKeyAlias={config.network_host}",
        f"UserKnownHostsFile={known_hosts_snapshot}",
        "GlobalKnownHostsFile=none",
    ]
    return ([str(config.ssh_executable), "-F", "none", "-T"]
            + [f"-o{option}" for option in opts]
            + ["-p", str(config.port), "-i", str(config.identity_file),
               f"{config.remote_account}@{config.network_host}",
               "intranel-host-peer-receive"])


def exchange_pending_over_ssh(store, packet, config):
    """Send one *already queued* packet and commit ACK after SSH exit 0.

    A timer bounds hung stdout, process exit, and pipe deadlocks. Only one
    bounded framed ACK is read; no stderr buffering or shell interpolation.
    """
    if not isinstance(store, HostPeerStore) or type(packet) is not bytes:
        raise HostPeerConflict("queued host-peer packet required")
    if not any(row_packet == packet for _, row_packet in store.pending()):
        raise HostPeerConflict("outbound packet not durably pending")
    destination = store._parse_read_only(packet, require_fresh=False).target
    if str(destination) != f"host:{config.peer_host}":
        raise HostPeerConflict("queued packet target differs from SSH peer")
    observed_server = ObservedPeer(config.peer_host, config.remote_account,
                                   config.server_host_key_fingerprint)
    store._observed(observed_server)
    pin = verified_known_hosts_line(config)  # fail before launching ssh
    if not config.ssh_executable.is_file() or not os.access(config.ssh_executable, os.X_OK):
        raise HostPeerConflict("trusted SSH executable unavailable")
    if not config.identity_file.is_file():
        raise HostPeerConflict("configured SSH private-key path unavailable")
    with tempfile.TemporaryDirectory(prefix="intranel-ssh-pin-") as tmp:
        known = Path(tmp) / "known_hosts"
        known.write_bytes(pin)
        known.chmod(0o600)
        argv = build_ssh_command(config, known_hosts_snapshot=known)
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise HostPeerConflict("SSH launch failed") from exc
        timed_out = threading.Event()

        def deadline() -> None:
            if proc.poll() is None:
                timed_out.set()
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass

        timer = threading.Timer(30.0, deadline)
        timer.daemon = True
        timer.start()
        try:
            assert proc.stdin is not None and proc.stdout is not None
            write_frame(proc.stdin, packet)
            proc.stdin.close()
            ack = read_frame(proc.stdout)
            if ack is None:
                raise HostPeerConflict("SSH receiver sent no ACK")
            # Require EOF rather than accepting an ACK plus covert extra data.
            if proc.stdout.read(1):
                raise HostPeerConflict("SSH receiver sent extra response frames")
            result = proc.wait(timeout=3.0)
            if timed_out.is_set() or result != 0:
                raise HostPeerConflict("SSH did not complete authenticated exchange")
        except HostPeerConflict:
            raise
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise HostPeerConflict("SSH transport I/O failed") from exc
        finally:
            timer.cancel()
            if proc.poll() is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            proc.wait()
            if proc.stdin is not None and not proc.stdin.closed:
                proc.stdin.close()
            if proc.stdout is not None and not proc.stdout.closed:
                proc.stdout.close()
    store.accept_ack(ack, observed_peer=observed_server)
    return ack


def parse_receiver_policy(data: bytes):
    """Validate source-configured client key/account to host mapping."""
    if type(data) is not bytes or not 0 < len(data) <= 16_384:
        raise HostPeerConflict("invalid SSH receiver config size")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise HostPeerConflict("duplicate SSH receiver config key")
            result[key] = value
        return result

    try:
        policy = json.loads(data.decode("utf-8", "strict"),
                            object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HostPeerConflict("invalid SSH receiver config") from exc
    if (type(policy) is not dict
            or set(policy) != {"local_host", "sqlite_path", "peers"}
            or type(policy["peers"]) is not dict or not policy["peers"]):
        raise HostPeerConflict("invalid SSH receiver policy fields")
    local = policy["local_host"]
    if (type(local) is not str or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", local)):
        raise HostPeerConflict("invalid local SSH receiver host")
    db_path = policy["sqlite_path"]
    if (type(db_path) is not str or not Path(db_path).is_absolute()
            or "\x00" in db_path):
        raise HostPeerConflict("SSH receiver database path must be absolute")
    trusted = {}
    client_keys = {}
    for host, peer in policy["peers"].items():
        if (type(peer) is not dict
                or set(peer) != {"account", "client_key_fingerprint"}
                or type(peer["account"]) is not str
                or not _ACCOUNT.fullmatch(peer["account"])
                or type(peer["client_key_fingerprint"]) is not str):
            raise HostPeerConflict("invalid SSH receiver peer policy")
        fingerprint = peer["client_key_fingerprint"]
        if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", fingerprint):
            raise HostPeerConflict("invalid SSH client key fingerprint")
        ObservedPeer(host, peer["account"], fingerprint)
        if host == local or fingerprint in client_keys:
            raise HostPeerConflict("ambiguous SSH client-key host mapping")
        trusted[host] = (peer["account"], fingerprint)
        client_keys[fingerprint] = host
    return local, Path(db_path), trusted, client_keys


_RECEIVER_CONFIG_PATH = Path("/etc/intranel/host-peer.json")


def _read_root_owned_receiver_policy() -> bytes:
    """Never use env or remote command arguments to locate receiver policy."""
    if os.name != "posix":
        raise HostPeerConflict("root-owned POSIX SSH receiver required")
    try:
        fd = os.open(_RECEIVER_CONFIG_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise HostPeerConflict("root-owned SSH receiver policy unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or info.st_mode & 0o022):
            raise HostPeerConflict("SSH receiver policy not root-owned/immutable")
        return os.read(fd, 16_385)
    finally:
        os.close(fd)


def main() -> int:
    """Entrypoint for root-configured sshd ForceCommand, not an admin shell."""
    try:
        if len(sys.argv) != 1:
            raise HostPeerConflict("SSH receiver refuses command arguments")
        if os.environ.get("SSH_ORIGINAL_COMMAND") not in (None, "intranel-host-peer-receive"):
            raise HostPeerConflict("SSH receiver remote command differs from fixed protocol")
        auth_info = os.environ.get("SSH_USER_AUTH")
        if not auth_info or not Path(auth_info).is_absolute():
            raise HostPeerConflict("sshd authentication info not exposed")
        local, db_path, trusted, key_to_host = parse_receiver_policy(
            _read_root_owned_receiver_policy())
        if any(account != current_os_account() for account, _ in trusted.values()):
            raise HostPeerConflict("SSH receiver policy account not current login")
        receiver = HostPeerStore(db_path, local_host=local, trusted_peers=trusted)
        receive_forced_command(receiver, sys.stdin.buffer, sys.stdout.buffer,
                               auth_info, key_to_host)
        return 0
    except (HostPeerConflict, OSError, ValueError):
        # Stdio is the binary protocol. Avoid leaking keys/policy on stderr.
        print("Intranel SSH receiver: admission or transport denied", file=sys.stderr)
        return 1
