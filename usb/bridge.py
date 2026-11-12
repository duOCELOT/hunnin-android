"""Experimental CH343 (1a86:55d3) CDC-ACM bridge for native Termux Python.

termux-usb -e supplies an authorized usbfs fd. Only stdlib is used. One local
TCP client, fixed 115200 8N1, manual BOOT/RESET. This program does not itself
send ESP ROM commands. The esptool client determines read/write operations.
Protocol reference: Linux drivers/usb/class/cdc-acm.c, CH343 device entry.
"""
import argparse
import ctypes as c
import errno
import os
import socket
import struct
import sys
import threading


class Control(c.Structure):
    _fields_ = [("kind", c.c_uint8), ("request", c.c_uint8),
                ("value", c.c_uint16), ("index", c.c_uint16),
                ("length", c.c_uint16), ("timeout", c.c_uint32),
                ("data", c.c_void_p)]


class Bulk(c.Structure):
    _fields_ = [("endpoint", c.c_uint), ("length", c.c_uint),
                ("timeout", c.c_uint), ("data", c.c_void_p)]


class Driver(c.Structure):
    _fields_ = [("interface", c.c_uint), ("driver", c.c_char * 256)]


class DisconnectClaim(c.Structure):
    _fields_ = [("interface", c.c_uint), ("flags", c.c_uint),
                ("driver", c.c_char * 256)]


class InterfaceIoctl(c.Structure):
    _fields_ = [("interface", c.c_int), ("code", c.c_int), ("data", c.c_void_p)]


def ioctl_code(direction, number, size):
    return (direction << 30) | (size << 16) | (ord("U") << 8) | number


def cdc_layout(data):
    """Select exactly one CDC ACM pair, altsetting zero, from descriptors."""
    if len(data) < 9 or data[:2] != b"\x09\x02" or int.from_bytes(data[2:4], "little") != len(data):
        raise ValueError("Invalid USB configuration descriptor")
    interfaces, unions, current = {}, [], None
    pos = 0
    while pos < len(data):
        if pos + 2 > len(data) or data[pos] < 2 or pos + data[pos] > len(data):
            raise ValueError("Truncated USB descriptor")
        d = data[pos:pos + data[pos]]
        if d[1] == 4:
            if len(d) < 9:
                raise ValueError("Short interface descriptor")
            current = d[2] if d[3] == 0 else None
            if current is not None:
                if current in interfaces:
                    raise ValueError("Duplicate USB interface")
                interfaces[current] = (d[5], d[6], [])
        elif d[1] == 0x24 and len(d) >= 5 and d[2] == 6 and current is not None:
            if len(d) != 5 or d[3] != current:
                raise ValueError("Unsupported CDC union")
            unions.append((d[3], d[4]))
        elif d[1] == 5 and current is not None:
            if len(d) < 7:
                raise ValueError("Short endpoint descriptor")
            if d[3] & 3 == 2:
                size = int.from_bytes(d[4:6], "little") & 0x7ff
                if not 1 <= size <= 512 or d[2] & 0x0f == 0:
                    raise ValueError("Invalid bulk endpoint")
                interfaces[current][2].append((d[2], size))
        pos += len(d)
    controls = [i for i, (cls, sub, _) in interfaces.items() if (cls, sub) == (2, 2)]
    datas = [i for i, (cls, _, _) in interfaces.items() if cls == 10]
    if len(controls) != 1 or len(datas) != 1:
        raise ValueError("Expected one CDC ACM control and one CDC data interface")
    control, serial = controls[0], datas[0]
    if unions and unions != [(control, serial)]:
        raise ValueError("CDC union does not match the data interface")
    endpoints = interfaces[serial][2]
    incoming = [ep for ep in endpoints if ep[0] & 0x80]
    outgoing = [ep for ep in endpoints if not ep[0] & 0x80]
    if len(incoming) != 1 or len(outgoing) != 1:
        raise ValueError("Expected one bulk IN and one bulk OUT endpoint")
    return control, serial, incoming[0][0], outgoing[0][0], incoming[0][1]


class USB:
    def __init__(self, fd, ioctl=None):
        self.fd, self.claimed, self.reconnect = fd, [], []
        if ioctl is None:
            self.libc = c.CDLL(None, use_errno=True)
            self.libc.ioctl.argtypes = [c.c_int, c.c_ulong, c.c_void_p]
            self.libc.ioctl.restype = c.c_int
            ioctl = self.libc.ioctl
        self.ioctl = ioctl

    def call(self, code, value):
        result = self.ioctl(self.fd, code, c.byref(value))
        if result < 0:
            error = c.get_errno()
            raise OSError(error, os.strerror(error))
        return result

    def control(self, kind, request, value, index, payload):
        length = payload if isinstance(payload, int) else len(payload)
        buf = c.create_string_buffer(max(1, length))
        if isinstance(payload, bytes):
            c.memmove(buf, payload, length)
        transfer = Control(kind, request, value, index, length, 3000, c.addressof(buf))
        count = self.call(ioctl_code(3, 0, c.sizeof(Control)), transfer)
        if count != length:
            raise ValueError("Short USB control transfer")
        return buf.raw[:count]

    def open(self):
        device = self.control(0x80, 6, 0x100, 0, 18)
        if device[:2] != b"\x12\x01" or device[8:12] != bytes.fromhex("861ad355"):
            raise ValueError("This bridge supports only CH343 USB 1a86:55d3")
        if device[17] != 1:
            raise ValueError("Multiple USB configurations are not supported")
        header = self.control(0x80, 6, 0x200, 0, 9)
        length = int.from_bytes(header[2:4], "little")
        if not 9 <= length <= 4096:
            raise ValueError("Invalid USB descriptor length")
        config = self.control(0x80, 6, 0x200, 0, length)
        ctrl, serial, self.ep_in, self.ep_out, self.packet = cdc_layout(config)
        if self.control(0x80, 8, 0, 0, 1) != config[5:6] or config[5] == 0:
            raise ValueError("Android has not activated this USB configuration")
        try:
            for interface in (ctrl, serial):
                self.claim(interface)
            # CDC SET_LINE_CODING: 115200 baud, one stop bit, no parity, 8 bits.
            self.control(0x21, 0x20, 0, ctrl, struct.pack("<IBBB", 115200, 0, 0, 8))
            # DTR/RTS deasserted. Do manual BOOT/RESET AFTER this step.
            self.control(0x21, 0x22, 0, ctrl, b"")
        except BaseException:
            self.close()
            raise

    def claim(self, interface):
        try:
            self.call(ioctl_code(2, 15, 4), c.c_uint(interface))
        except OSError as error:
            if error.errno != errno.EBUSY:
                raise
            info = Driver(interface)
            try:
                self.call(ioctl_code(1, 8, c.sizeof(Driver)), info)
            except OSError as inspection:
                raise OSError(inspection.errno,
                              f"Interface {interface} busy; cannot identify owner: {inspection}") from inspection
            name = bytes(info.driver)
            print(f"Interface {interface} occupied by driver: {name.decode('ascii', 'replace')}", flush=True)
            # Never detach usbfs (another app) or an unidentified kernel driver.
            if name != b"cdc_acm":
                raise OSError(errno.EBUSY, f"Interface {interface}: owner is not supported cdc_acm")
            # IF_DRIVER makes the ownership check atomic with detach/claim.
            request = DisconnectClaim(interface, 1, name)
            self.reconnect.append(interface)
            try:
                self.call(ioctl_code(2, 27, c.sizeof(DisconnectClaim)), request)
            except OSError as takeover:
                raise OSError(takeover.errno,
                              f"Android refused CDC handoff on interface {interface}: {takeover}") from takeover
            print(f"Interface {interface}: temporary CDC handoff acquired", flush=True)
        self.claimed.append(interface)

    def close(self):
        for interface in reversed(self.claimed):
            try:
                self.call(ioctl_code(2, 16, 4), c.c_uint(interface))
            except OSError:
                pass  # A disconnected device no longer has claims to release.
        self.claimed.clear()
        # Release both interfaces before asking the CDC driver to bind again.
        for interface in self.reconnect:
            request = InterfaceIoctl(interface, ioctl_code(0, 23, 0), None)
            try:
                self.call(ioctl_code(3, 18, c.sizeof(InterfaceIoctl)), request)
            except OSError as error:
                if error.errno != errno.ENODEV:
                    print(f"CDC reattach: {error}. Unplug/reconnect USB to restore Android ownership.", file=sys.stderr)
        self.reconnect.clear()

    def bulk(self, endpoint, payload):
        size = payload if isinstance(payload, int) else len(payload)
        buf = c.create_string_buffer(size)
        if isinstance(payload, bytes):
            c.memmove(buf, payload, size)
        transfer = Bulk(endpoint, size, 250 if endpoint & 0x80 else 3000, c.addressof(buf))
        count = self.call(ioctl_code(3, 2, c.sizeof(Bulk)), transfer)
        if not 0 <= count <= size:
            raise ValueError("Invalid USB bulk transfer length")
        return buf.raw[:count] if endpoint & 0x80 else count

    def read(self):
        # One packet avoids losing partial data on a synchronous usbfs timeout.
        try:
            return self.bulk(self.ep_in, self.packet)
        except OSError as error:
            if error.errno == errno.ETIMEDOUT:
                return b""
            raise

    def write(self, data):
        while data:
            sent = self.bulk(self.ep_out, data[:4096])
            if not sent:
                raise OSError("Zero-length USB write")
            data = data[sent:]


def relay(usb, connection):
    """Binary-transparent full duplex. Exit on client close or USB failure."""
    stop, failures = threading.Event(), []
    connection.settimeout(2)

    def receive():
        try:
            while not stop.is_set():
                data = usb.read()
                if data:
                    connection.sendall(data)
        except (OSError, ValueError) as error:
            if not stop.is_set():
                failures.append(error)
                stop.set()
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    worker = threading.Thread(target=receive)
    worker.start()
    try:
        while not stop.is_set():
            try:
                data = connection.recv(4096)
            except socket.timeout:
                continue
            if not data:
                break
            usb.write(data)
    finally:
        stop.set()
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        worker.join()  # read ioctl is bounded to 250 ms; send timeout is 2 s.
    if failures:
        raise failures[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fd", type=int, help="Supplied by termux-usb -e, not a device path")
    parser.add_argument("--port", type=int, default=3333)
    args = parser.parse_args()
    if args.fd < 0 or not 1024 <= args.port <= 65535:
        parser.error("Invalid fd or port")
    usb = USB(args.fd)
    try:
        print("HUNINN USB bridge v2 (CDC owner detection)", flush=True)
        os.fstat(args.fd)
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", args.port))
            server.listen(1)
            server.settimeout(180)
            usb.open()
            print(f"CH343 ready: socket://127.0.0.1:{args.port}, fixed 115200 8N1", flush=True)
            print("Hold BOOT, press/release RESET, release BOOT. Then run esptool in the other session.", flush=True)
            print("One client only; closes after disconnect. Waiting up to 180 seconds.", flush=True)
            with server.accept()[0] as connection:
                # Close listener now: this bridge serves exactly one connection.
                server.close()
                print("Client connected", flush=True)
                relay(usb, connection)
            print("Client disconnected; bridge closed.")
        return 0
    except (OSError, ValueError) as error:
        print(f"USB bridge: {error}", file=sys.stderr)
        if isinstance(error, OSError) and error.errno == errno.EBUSY:
            print("Check the interface owner above; close other USB apps if it is usbfs.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        usb.close()


if __name__ == "__main__":
    sys.exit(main())
