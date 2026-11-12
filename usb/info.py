"""Read only the USB device descriptor from a termux-usb inherited fd.

Run with native Termux Python, not Debian/PRoot. No serial number is requested,
no interface is claimed and no reset, UART configuration or flash write occurs.
"""
import ctypes as c
import os
import sys


class Transfer(c.Structure):
    _fields_ = [("kind", c.c_uint8), ("request", c.c_uint8),
                ("value", c.c_uint16), ("index", c.c_uint16),
                ("length", c.c_uint16), ("timeout", c.c_uint32),
                ("data", c.c_void_p)]


def identify(fd, ioctl):
    buffer = c.create_string_buffer(18)
    transfer = Transfer(0x80, 6, 0x0100, 0, 18, 3000, c.addressof(buffer))
    # Linux USBDEVFS_CONTROL = _IOWR('U', 0, struct usbdevfs_ctrltransfer).
    request = (3 << 30) | (c.sizeof(Transfer) << 16) | (ord("U") << 8)
    count = ioctl(fd, request, c.byref(transfer))
    if count < 0:
        error = c.get_errno()
        raise OSError(error, os.strerror(error))
    data = buffer.raw
    if count != 18 or data[:2] != b"\x12\x01":
        raise ValueError("Incomplete or invalid USB device descriptor")
    vendor = int.from_bytes(data[8:10], "little")
    product = int.from_bytes(data[10:12], "little")
    return f"USB VID:PID = {vendor:04x}:{product:04x}"


def main():
    try:
        if len(sys.argv) != 2 or not sys.argv[1].isdigit():
            raise ValueError("Run through termux-usb -e; it supplies the USB fd")
        fd = int(sys.argv[1])
        os.fstat(fd)
        libc = c.CDLL(None, use_errno=True)
        libc.ioctl.argtypes = [c.c_int, c.c_ulong, c.c_void_p]
        libc.ioctl.restype = c.c_int
        print(identify(fd, libc.ioctl))
        print("Read-only diagnostic complete. Firmware unchanged.")
    except (OSError, ValueError) as error:
        print(f"USB diagnostic: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
