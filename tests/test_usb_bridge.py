import ctypes as c
import errno
import importlib.util
from pathlib import Path
import queue
import socket
import struct
import threading
import unittest

spec = importlib.util.spec_from_file_location("bridge", Path(__file__).resolve().parents[1] / "usb/bridge.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

# Representative CDC ACM descriptors, not captured from the user's board.
BODY = bytes.fromhex("090400000102020100 0524060001 07058103100010 "
                     "09040100020a000000 07058202400000 07050302400000")
CONFIG = bytes([9, 2]) + struct.pack("<H", 9 + len(BODY)) + bytes([2, 1, 0, 0x80, 50]) + BODY
DEVICE = bytes.fromhex("1201000202000040861ad355000101020301")


class Kernel:
    def __init__(self, device=DEVICE):
        self.device, self.calls, self.output = device, [], bytearray()
        self.fail_claim = False
        self.rx_timeout = False
        self.owner = b"usbfs"
        self.busy = set()
        self.handoff_denied = False

    def __call__(self, fd, code, pointer):
        assert fd == 42
        number = code & 255
        if number in (15, 16):
            interface = c.cast(pointer, c.POINTER(c.c_uint)).contents.value
            self.calls.append((number, interface))
            if number == 15 and ((interface == 1 and self.fail_claim) or interface in self.busy):
                c.set_errno(errno.EBUSY)
                return -1
            return 0
        if number == 8:
            d = c.cast(pointer, c.POINTER(b.Driver)).contents
            self.calls.append((8, d.interface))
            d.driver = self.owner
            return 0
        if number == 27:
            d = c.cast(pointer, c.POINTER(b.DisconnectClaim)).contents
            assert d.flags == 1 and bytes(d.driver) == b"cdc_acm"
            self.calls.append((27, d.interface))
            if self.handoff_denied:
                c.set_errno(errno.EACCES)
                return -1
            self.busy.clear()  # CDC releases the paired interface too.
            return 0
        if number == 18:
            d = c.cast(pointer, c.POINTER(b.InterfaceIoctl)).contents
            assert d.code == 0x5517 and not d.data
            self.calls.append((18, d.interface))
            return 0
        if number == 0:
            t = c.cast(pointer, c.POINTER(b.Control)).contents
            if t.kind == 0x80 and t.request == 6:
                data = self.device if t.value == 0x100 else CONFIG[:t.length]
            elif t.kind == 0x80 and t.request == 8:
                data = b"\x01"
            elif t.kind == 0x21 and t.request in (0x20, 0x22):
                self.calls.append((t.request, t.value, t.index, c.string_at(t.data, t.length)))
                return t.length
            else:
                raise AssertionError("Unexpected control request")
            c.memmove(t.data, data, len(data))
            return len(data)
        if number == 2:
            t = c.cast(pointer, c.POINTER(b.Bulk)).contents
            if t.endpoint == 0x82:
                assert t.length == 64
                if self.rx_timeout:
                    c.set_errno(errno.ETIMEDOUT)
                    return -1
                c.memmove(t.data, b"\xc0\xdb\x00\xff", 4)
                return 4
            assert t.endpoint == 3
            count = min(3, t.length)  # Exercise successful short bulk writes.
            self.output.extend(c.string_at(t.data, count))
            return count
        raise AssertionError("Unexpected ioctl")


class BridgeTests(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(b.cdc_layout(CONFIG), (0, 1, 0x82, 3, 64))
        for invalid in (b"", CONFIG[:-1], CONFIG[:9] + b"\x00\x04" + CONFIG[11:]):
            with self.assertRaises(ValueError):
                b.cdc_layout(invalid)

    def test_refuse_wrong_pid_before_claim(self):
        device = bytearray(DEVICE)
        device[10] = 0
        k = Kernel(bytes(device))
        with self.assertRaises(ValueError):
            b.USB(42, k).open()
        self.assertEqual(k.calls, [])

    def test_uart_and_binary_transfers(self):
        k = Kernel()
        usb = b.USB(42, k)
        usb.open()
        self.assertEqual(k.calls, [(15, 0), (15, 1),
                                  (0x20, 0, 0, struct.pack("<IBBB", 115200, 0, 0, 8)),
                                  (0x22, 0, 0, b"")])
        self.assertEqual(usb.read(), b"\xc0\xdb\x00\xff")
        k.rx_timeout = True
        self.assertEqual(usb.read(), b"")
        payload = bytes(range(256)) * 20
        usb.write(payload)
        self.assertEqual(bytes(k.output), payload)
        usb.close()
        self.assertEqual(k.calls[-2:], [(16, 1), (16, 0)])

    def test_partial_claim_cleanup_without_forced_detach(self):
        k = Kernel()
        k.fail_claim = True
        usb = b.USB(42, k)
        with self.assertRaises(OSError):
            usb.open()
        self.assertEqual(k.calls, [(15, 0), (15, 1), (8, 1), (16, 0)])
        self.assertEqual(usb.claimed, [])

    def test_cdc_handoff_and_reattach_after_all_releases(self):
        k = Kernel()
        k.owner, k.busy = b"cdc_acm", {0, 1}
        usb = b.USB(42, k)
        usb.open()
        self.assertEqual(k.calls[:4], [(15, 0), (8, 0), (27, 0), (15, 1)])
        usb.close()
        self.assertEqual(k.calls[-3:], [(16, 1), (16, 0), (18, 0)])
        calls = list(k.calls)
        usb.close()
        self.assertEqual(k.calls, calls)

    def test_unknown_driver_not_detached(self):
        k = Kernel()
        k.owner, k.busy = b"unknown", {0}
        with self.assertRaises(OSError):
            b.USB(42, k).open()
        self.assertEqual(k.calls, [(15, 0), (8, 0)])

    def test_android_denial_no_uart_configuration(self):
        k = Kernel()
        k.owner, k.busy, k.handoff_denied = b"cdc_acm", {0}, True
        with self.assertRaises(PermissionError):
            b.USB(42, k).open()
        self.assertEqual(k.calls, [(15, 0), (8, 0), (27, 0), (18, 0)])

    def test_binary_socket_relay_and_client_disconnect(self):
        class EchoUSB:
            def __init__(self):
                self.q = queue.Queue()
            def read(self):
                try:
                    return self.q.get(timeout=0.02)
                except queue.Empty:
                    return b""
            def write(self, data):
                self.q.put(data)
        usb = EchoUSB()
        server, client = socket.socketpair()
        failures = []
        def run():
            try:
                b.relay(usb, server)
            except Exception as error:
                failures.append(error)
            finally:
                server.close()
        thread = threading.Thread(target=run)
        thread.start()
        with client:
            client.settimeout(3)
            payload = bytes(range(256)) * 32
            client.sendall(payload)
            result = b""
            while len(result) < len(payload):
                chunk = client.recv(4096)
                self.assertTrue(chunk)
                result += chunk
            self.assertEqual(result, payload)
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures)

    def test_usb_disconnect_ends_client_connection(self):
        class GoneUSB:
            def read(self):
                raise OSError(errno.ENODEV, "Disconnected")
            def write(self, data):
                raise AssertionError("No data should be written")
        server, client = socket.socketpair()
        failures = []
        def run():
            try:
                b.relay(GoneUSB(), server)
            except OSError as error:
                failures.append(error.errno)
            finally:
                server.close()
        thread = threading.Thread(target=run)
        thread.start()
        with client:
            client.settimeout(3)
            self.assertEqual(client.recv(1), b"")
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [errno.ENODEV])


if __name__ == "__main__":
    unittest.main()
