"""Descriptor ioctl tests with a mock fd; no Android USB device required."""
import ctypes as c
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("usb_info", Path(__file__).resolve().parents[1] / "usb/info.py")
usb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usb)


class DescriptorTest(unittest.TestCase):
    def test_only_read_descriptor(self):
        calls = []

        def ioctl(fd, request, pointer):
            t = c.cast(pointer, c.POINTER(usb.Transfer)).contents
            calls.append(request)
            self.assertEqual(fd, 42)
            self.assertEqual(request, 0xC0185500 if c.sizeof(c.c_void_p) == 8 else 0xC0105500)
            self.assertEqual((t.kind, t.request, t.value, t.index, t.length, t.timeout),
                             (0x80, 6, 0x100, 0, 18, 3000))
            descriptor = bytes.fromhex("1201000200000040861a2375000101020301")
            c.memmove(t.data, descriptor, 18)
            return 18

        self.assertEqual(usb.identify(42, ioctl), "USB VID:PID = 1a86:7523")
        self.assertEqual(len(calls), 1)

    def test_short_descriptor(self):
        with self.assertRaises(ValueError):
            usb.identify(42, lambda *args: 8)

    def test_permission_error(self):
        def denied(*args):
            c.set_errno(13)
            return -1
        with self.assertRaises(PermissionError):
            usb.identify(42, denied)


if __name__ == "__main__":
    unittest.main()
