"""SSH session evidence parsing and restricted, one-frame endpoint tests.

These tests intentionally do NOT qualify a real sshd forced-command session.
"""

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from intranel.host_peer import HostPeerConflict, HostPeerStore, ObservedPeer, read_frame, write_frame
from intranel.ssh_carrier import (
    SSHClientConfig, build_ssh_command, exchange_pending_over_ssh,
    peer_from_sshd_auth_info, receive_forced_command, verified_known_hosts_line,
    parse_receiver_policy,
)
from test_host_peer import msg


_KEY = b"\x00\x00\x00\x0bssh-ed25519" + b"\x00\x00\x00\x20" + b"z" * 32
_KEY_TEXT = base64.b64encode(_KEY).decode("ascii")
_FINGERPRINT = "SHA256:" + base64.b64encode(hashlib.sha256(_KEY).digest()).decode("ascii").rstrip("=")


class SSHCarrierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.auth = Path(self.tmp.name) / "sshauth.test"
        self.auth.write_text(f"publickey ssh-ed25519 {_KEY_TEXT}\n", encoding="ascii")
        self.auth.chmod(0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX sshd receiver only")
    def test_actual_account_and_admitted_authentication_key_bound_to_host(self):
        observed = peer_from_sshd_auth_info(self.auth, {_FINGERPRINT: "lappy"})
        self.assertIsInstance(observed, ObservedPeer)
        self.assertEqual(observed.host, "lappy")
        self.assertEqual(observed.host_key_fingerprint, _FINGERPRINT)
        self.assertTrue(observed.os_account)

    @unittest.skipUnless(os.name == "posix", "POSIX sshd receiver only")
    def test_wrong_unrecognized_or_multiple_authentication_rejected(self):
        with self.assertRaises(HostPeerConflict):
            peer_from_sshd_auth_info(self.auth, {"SHA256:other": "lappy"})
        for invalid in [
            "password\n",
            f"publickey ssh-ed25519 {_KEY_TEXT}\npassword\n",
            f"publickey ssh-ed25519 {_KEY_TEXT}\npublickey ssh-ed25519 {_KEY_TEXT}\n",
            f"publickey ssh-rsa {_KEY_TEXT}\n",
            f"publickey ssh-ed25519 {_KEY_TEXT} unexpected\n",
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(HostPeerConflict):
                self.auth.write_text(invalid, encoding="ascii")
                peer_from_sshd_auth_info(self.auth, {_FINGERPRINT: "lappy"})

    @unittest.skipUnless(os.name == "posix", "POSIX sshd receiver only")
    def test_missing_unsafe_auth_info_file_rejected(self):
        with self.assertRaises(HostPeerConflict):
            peer_from_sshd_auth_info(self.auth.parent / "missing", {_FINGERPRINT: "lappy"})
        self.auth.chmod(0o644)
        with self.assertRaises(HostPeerConflict):
            peer_from_sshd_auth_info(self.auth, {_FINGERPRINT: "lappy"})
        if hasattr(os, "symlink"):
            link = self.auth.parent / "linked"
            link.symlink_to(self.auth)
            with self.assertRaises(HostPeerConflict):
                peer_from_sshd_auth_info(link, {_FINGERPRINT: "lappy"})

    @unittest.skipUnless(os.name == "posix", "POSIX sshd receiver only")
    def test_forced_command_durable_receive_ack_and_duplicate(self):
        # The local OS account must be pinned separately from caller input.
        from intranel.ssh_carrier import current_os_account
        receiver = HostPeerStore(Path(self.tmp.name) / "real.db", local_host="vn1",
                                 trusted_peers={"lappy": (current_os_account(), _FINGERPRINT)})
        packet = __import__("intranel.canonical", fromlist=["canonical_json_bytes"]).canonical_json_bytes(msg())
        wire = io.BytesIO()
        write_frame(wire, packet)
        for _ in range(2):
            wire.seek(0)
            out = io.BytesIO()
            receive_forced_command(receiver, wire, out, self.auth,
                                   {_FINGERPRINT: "lappy"})
            out.seek(0)
            ack = read_frame(out)
            self.assertIn(b'"status":"STORED"', ack)
            self.assertEqual(receiver.received_count(), 1)

    @unittest.skipUnless(os.name == "posix", "POSIX sshd receiver only")
    def test_forced_command_rejects_noncanonical_packet_without_commit(self):
        from intranel.ssh_carrier import current_os_account
        receiver = HostPeerStore(Path(self.tmp.name) / "deny.db", local_host="vn1",
                                 trusted_peers={"lappy": (current_os_account(), _FINGERPRINT)})
        wire = io.BytesIO()
        write_frame(wire, b'{"protocol":"INTRANEL/1", "origin":"host:lappy"}')
        wire.seek(0)
        with self.assertRaises(HostPeerConflict):
            receive_forced_command(receiver, wire, io.BytesIO(), self.auth,
                                   {_FINGERPRINT: "lappy"})
        self.assertEqual(receiver.received_count(), 0)

    @unittest.skipUnless(os.name == "posix", "POSIX sshd receiver only")
    def test_forced_command_rejects_second_frame_and_trailing_bytes_atomically(self):
        from intranel.ssh_carrier import current_os_account
        from intranel.canonical import canonical_json_bytes

        receiver = HostPeerStore(Path(self.tmp.name) / "trailing.db", local_host="vn1",
                                 trusted_peers={"lappy": (current_os_account(), _FINGERPRINT)})
        packet = canonical_json_bytes(msg())
        first = io.BytesIO()
        write_frame(first, packet)
        first_bytes = first.getvalue()
        second = io.BytesIO()
        write_frame(second, packet)
        for suffix in (second.getvalue(), b"ignored"):
            with self.subTest(suffix=suffix[:8]), self.assertRaises(HostPeerConflict):
                receive_forced_command(receiver, io.BytesIO(first_bytes + suffix),
                                       io.BytesIO(), self.auth, {_FINGERPRINT: "lappy"})
            self.assertEqual(receiver.received_count(), 0)

    def test_client_pins_exact_server_host_key_and_rejects_alias_collision(self):
        known_hosts = Path(self.tmp.name) / "known_hosts"
        line = f"vn1.tail.test ssh-ed25519 {_KEY_TEXT}\n"
        known_hosts.write_text(line, encoding="ascii")
        config = SSHClientConfig(peer_host="vn1", network_host="vn1.tail.test",
                                 remote_account="svc-vn1", port=22,
                                 ssh_executable=Path("/usr/bin/ssh"),
                                 identity_file=Path("/tmp/intranel-test-private-key"),
                                 known_hosts=known_hosts,
                                 server_host_key_fingerprint=_FINGERPRINT)
        self.assertEqual(verified_known_hosts_line(config), line.encode("ascii"))
        known_hosts.write_bytes(line.replace("\n", "\r\n").encode("ascii"))
        self.assertEqual(verified_known_hosts_line(config), line.encode("ascii"))
        known_hosts.write_text(line.replace("vn1.tail.test", "wrong"), encoding="ascii")
        with self.assertRaises(HostPeerConflict):
            verified_known_hosts_line(config)
        known_hosts.write_text(line + "wrong ssh-ed25519 " + _KEY_TEXT + "\n", encoding="ascii")
        with self.assertRaises(HostPeerConflict):
            verified_known_hosts_line(config)
        known_hosts.write_text(line, encoding="ascii")
        wrong = SSHClientConfig(peer_host="vn1", network_host="vn1.tail.test",
                                remote_account="svc-vn1", port=22,
                                ssh_executable=Path("/usr/bin/ssh"),
                                identity_file=Path("/tmp/intranel-test-private-key"),
                                known_hosts=known_hosts,
                                server_host_key_fingerprint="SHA256:wrong")
        with self.assertRaises(HostPeerConflict):
            verified_known_hosts_line(wrong)

    def test_ssh_command_fences_config_proxy_password_and_host_key_downgrade(self):
        path_root = Path(self.tmp.name)
        config = SSHClientConfig(peer_host="vn1", network_host="vn1.tail.test",
                                 remote_account="svc-vn1", port=22,
                                 ssh_executable=path_root / "ssh",
                                 identity_file=path_root / "intranel-test-private-key",
                                 known_hosts=path_root / "intranel-pinned-known-hosts",
                                 server_host_key_fingerprint=_FINGERPRINT)
        pin_snapshot = path_root / "pin-snapshot"
        command = build_ssh_command(config, known_hosts_snapshot=pin_snapshot)
        joined = " ".join(command)
        for required in ["StrictHostKeyChecking=yes", "PasswordAuthentication=no",
                         "PreferredAuthentications=publickey", "BatchMode=yes",
                         "ProxyCommand=none", "ProxyJump=none", "HostKeyAlgorithms=ssh-ed25519",
                         f"UserKnownHostsFile={pin_snapshot}", "-F none", "-T",
                         "svc-vn1@vn1.tail.test", "intranel-host-peer-receive"]:
            self.assertIn(required, joined)

    def test_outbound_wrong_host_pin_denied_before_ssh_process_launch(self):
        from unittest.mock import patch
        known_hosts = Path(self.tmp.name) / "known_hosts"
        known_hosts.write_text(f"vn1.tail.test ssh-ed25519 {_KEY_TEXT}\n", encoding="ascii")
        config = SSHClientConfig(peer_host="vn1", network_host="vn1.tail.test",
                                 remote_account="svc-vn1", port=22,
                                 ssh_executable=Path("/usr/bin/ssh"),
                                 identity_file=Path("/tmp/intranel-test-private-key"),
                                 known_hosts=known_hosts,
                                 server_host_key_fingerprint="SHA256:wrong")
        sender = HostPeerStore(Path(self.tmp.name) / "sender.db", local_host="lappy",
                               trusted_peers={"vn1": ("svc-vn1", "SHA256:wrong")})
        packet = sender.queue(msg())
        with patch("intranel.ssh_carrier.subprocess.Popen") as launch:
            with self.assertRaises(HostPeerConflict):
                exchange_pending_over_ssh(sender, packet, config)
            launch.assert_not_called()
        self.assertEqual(len(sender.pending()), 1)

    def test_outbound_cannot_send_queued_packet_to_other_peer(self):
        known_hosts = Path(self.tmp.name) / "known_hosts"
        known_hosts.write_text(f"vn2.tail.test ssh-ed25519 {_KEY_TEXT}\n", encoding="ascii")
        config = SSHClientConfig(peer_host="vn2", network_host="vn2.tail.test",
                                 remote_account="svc-vn2", port=22,
                                 ssh_executable=Path("/usr/bin/ssh"),
                                 identity_file=Path("/tmp/intranel-test-private-key"),
                                 known_hosts=known_hosts,
                                 server_host_key_fingerprint=_FINGERPRINT)
        sender = HostPeerStore(Path(self.tmp.name) / "sender-misroute.db",
                               local_host="lappy", trusted_peers={
                                   "vn1": ("svc-vn1", _FINGERPRINT),
                                   "vn2": ("svc-vn2", _FINGERPRINT)})
        packet = sender.queue(msg(target="vn1"))
        with patch("intranel.ssh_carrier.subprocess.Popen") as launch:
            with self.assertRaisesRegex(HostPeerConflict, "target"):
                exchange_pending_over_ssh(sender, packet, config)
            launch.assert_not_called()

    def test_outbound_stale_account_binding_denied_before_ssh_process_launch(self):
        known_hosts = Path(self.tmp.name) / "known_hosts"
        known_hosts.write_text(f"vn1.tail.test ssh-ed25519 {_KEY_TEXT}\n", encoding="ascii")
        config = SSHClientConfig(peer_host="vn1", network_host="vn1.tail.test",
                                 remote_account="attacker", port=22,
                                 ssh_executable=Path("/usr/bin/ssh"),
                                 identity_file=Path("/tmp/intranel-test-private-key"),
                                 known_hosts=known_hosts,
                                 server_host_key_fingerprint=_FINGERPRINT)
        sender = HostPeerStore(Path(self.tmp.name) / "sender-stale.db",
                               local_host="lappy", trusted_peers={
                                   "vn1": ("svc-vn1", _FINGERPRINT)})
        packet = sender.queue(msg())
        with patch("intranel.ssh_carrier.subprocess.Popen") as launch:
            with self.assertRaisesRegex(HostPeerConflict, "admitted"):
                exchange_pending_over_ssh(sender, packet, config)
            launch.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX sshd receiver only")
    def test_receiver_policy_requires_exact_pinned_accounts_and_keys(self):
        base = {"local_host": "vn2", "sqlite_path": "/var/lib/intranel/host-peer.db",
                "peers": {"vn1": {"account": "intranelrx", "client_key_fingerprint":
                                   _FINGERPRINT}}}
        validated = parse_receiver_policy(json.dumps(base).encode("utf-8"))
        self.assertIsNotNone(validated)
        self.assertEqual(validated[0], "vn2")
        self.assertEqual(validated[2], {"vn1": ("intranelrx", _FINGERPRINT)})
        self.assertEqual(validated[3], {_FINGERPRINT: "vn1"})
        for mutation in [
            {**base, "peers": {}},
            {**base, "extra": "accept-me"},
            {**base, "peers": {"vn1": {"account": "intranelrx"}}},
            {**base, "peers": {"vn2": base["peers"]["vn1"]}},
            {**base, "peers": {"vn1": base["peers"]["vn1"],
                                  "lappy": base["peers"]["vn1"]}},
        ]:
            with self.subTest(mutation=mutation), self.assertRaises(HostPeerConflict):
                parse_receiver_policy(json.dumps(mutation).encode("utf-8"))

    def test_simulated_ssh_stdio_ack_requires_successful_ssh_exit(self):
        """Subprocess is a mock transport; this is not a physical host qualification."""
        known_hosts = Path(self.tmp.name) / "known_hosts"
        known_hosts.write_text(f"vn1.tail.test ssh-ed25519 {_KEY_TEXT}\n", encoding="ascii")
        identity = Path(self.tmp.name) / "dummy-unusable-private-key"
        identity.write_text("not-a-real-private-key", encoding="ascii")
        executable = Path("/usr/bin/ssh")
        if not executable.is_file():
            self.skipTest("unit exercise requires a local SSH executable path")
        config = SSHClientConfig(peer_host="vn1", network_host="vn1.tail.test",
                                 remote_account="svc-vn1", port=22,
                                 ssh_executable=executable, identity_file=identity,
                                 known_hosts=known_hosts,
                                 server_host_key_fingerprint=_FINGERPRINT)
        sender = HostPeerStore(Path(self.tmp.name) / "sender.db", local_host="lappy",
                               trusted_peers={"vn1": ("svc-vn1", _FINGERPRINT)})
        receiver = HostPeerStore(Path(self.tmp.name) / "receiver.db", local_host="vn1",
                                 trusted_peers={"lappy": ("svc-lappy", _FINGERPRINT)})
        packet = sender.queue(msg())
        ack = receiver.receive(packet, observed_peer=ObservedPeer(
            "lappy", "svc-lappy", _FINGERPRINT))
        framed = io.BytesIO()
        write_frame(framed, ack)

        class CapturePipe(io.BytesIO):
            def close(self):
                self.recorded = self.getvalue()
                super().close()

        class FakeProcess:
            def __init__(self, status):
                self.status = status
                self.stdin = CapturePipe()
                self.stdout = io.BytesIO(framed.getvalue())

            def poll(self):
                return self.status

            def wait(self, timeout=None):
                return self.status

            def kill(self):
                self.status = -9

        failed_process = FakeProcess(255)
        with patch("intranel.ssh_carrier.subprocess.Popen", return_value=failed_process):
            with self.assertRaises(HostPeerConflict):
                exchange_pending_over_ssh(sender, packet, config)
        self.assertFalse(sender.was_acked("host-001"))

        succeeded_process = FakeProcess(0)
        with patch("intranel.ssh_carrier.subprocess.Popen", return_value=succeeded_process):
            result = exchange_pending_over_ssh(sender, packet, config)
        self.assertEqual(result, ack)
        self.assertEqual(read_frame(io.BytesIO(succeeded_process.stdin.recorded)), packet)
        self.assertTrue(sender.was_acked("host-001"))


if __name__ == "__main__":
    unittest.main()
