import win32api
import win32gui
import win32process

import ctypes
import ctypes.wintypes

from ctypes import c_char, c_byte, c_ulong, c_void_p
from ctypes.wintypes import DWORD, HMODULE

import os
import time
import random
import struct

from collections import namedtuple
from contextlib import contextmanager

import statinfo

"""
Data structure: 48 bytes

AC 00 00 00 45 00 00 00 04 00 00 00 08 00 00 00
00 01 0F 0A 01 00 0E 07 00 09 0C 00 00 08 0B 0E
04 10 0D 06 00 00 00 00 15 00 00 00 01 00 00 00

Weight (long)
Height (long)
Physique (long) (obsolete?)
Unknown stat (long)

Unknown null (byte)
Unknown (sex?) (byte)
Strength (byte)
Agility (byte)
Unknown (short or byte+null)
Dexterity (byte)
Speed (byte)
Unknown null (byte)
Endurance (byte)
Smell/Taste (byte)
Unknown (short/2 nulls)
Eyesight (byte)
Touch (byte)
Will (byte)

Unknown (short/2 bytes)
Intelligence (byte)
Hearing (byte)
Unknown (long/4 bytes)
Unknown (long)
Unknown (long)

Struct code: LLLLxBBBHBBxBBxxBBBxxBBxxxxLL
"""

_Address = namedtuple("Address", "address size")

_statmap = {
    'Intelligence': _Address(0xA2BF232, 1),
    'Will':         _Address(0xA2BF22F, 1),

    'Strength':     _Address(0xA2BF222, 1),
    'Endurance':    _Address(0xA2BF229, 1),
    'Dexterity':    _Address(0xA2BF226, 1),
    'Agility':      _Address(0xA2BF223, 1),
    'Speed':        _Address(0xA2BF227, 1),
    'Eyesight':     _Address(0xA2BF22D, 1),
    'Hearing':      _Address(0xA2BF233, 1),
    'Smell/Taste':  _Address(0xA2BF22A, 1),
    'Touch':        _Address(0xA2BF22E, 1),

    'Height':       _Address(0xA2BF214, 4),
    'Weight':       _Address(0xA2BF210, 4),
    'Physique':     _Address(0xA2BF218, 4)
}

_size_to_struct = {
    1: 'B',
    4: 'L'
}

_TH32CS_SNAPMODULE = 8
_PROCESS_ALL_ACCESS = 0x1F0FFF


class _MODULEENTRY32(ctypes.Structure):
    _fields_ = [('dwSize',        DWORD),
                ('th32ModuleID',  DWORD),
                ('th32ProcessID', DWORD),
                ('GlblcntUsage',  DWORD),
                ('ProccntUsage',  DWORD),
                ('modBaseAddr',   c_void_p),
                ('modBaseSize',   DWORD),
                ('hModule',       HMODULE),
                ('szModule',      c_char * 256),
                ('szExePath',     c_char * 260)]


@contextmanager
def _open_proc(pid):
    handle = None

    try:
        handle = ctypes.windll.kernel32.OpenProcess(_PROCESS_ALL_ACCESS, False, pid)
        yield handle
    finally:
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)



class Hook:
    def __init__(self, load=True):
        self.pid = None
        self.hwnd = None
        self.base_addr = None

        self._delay = 0.05

        self._own_pid = os.getpid()
        self._own_hwnd = ctypes.windll.kernel32.GetConsoleWindow()

        if load:
            self.reload()

    @property
    def GAME(self):
        return self.hwnd

    @property
    def THIS(self):
        return self._own_hwnd

    def _get_base_addr(self):
        hModuleSnap = c_void_p(0)
        me32 = _MODULEENTRY32()
        me32.dwSize = ctypes.sizeof(_MODULEENTRY32)
        hModuleSnap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPMODULE, self.pid)

        ret = ctypes.windll.kernel32.Module32First(hModuleSnap, ctypes.pointer(me32))
        ctypes.windll.kernel32.CloseHandle(hModuleSnap)

        if ret == 0:
            raise RuntimeError('ListProcessModules() Error on Module32First[{}]'.format(
                ctypes.windll.kernel32.GetLastError()))

        return me32.modBaseAddr

    def _get_hwnd(self):
        toplist, winlist = [], []

        def enum_cb(hwnd, results):
            winlist.append((hwnd, win32gui.GetWindowText(hwnd)))

        win32gui.EnumWindows(enum_cb, toplist)
        urw = [(hwnd, title) for hwnd, title in winlist if 'UnReal World' in title]

        return urw[0][0] if urw else None

    def _get_hwnds_for_pid(self, pid):
        def cb(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)

                if found_pid == pid:
                    hwnds.append(hwnd)

            return True

        hwnds = []
        win32gui.EnumWindows(cb, hwnds)

        return hwnds

    def _get_pid(self):
        return win32process.GetWindowThreadProcessId(self.hwnd)[1]

    def _press_n(self, delay=None):
        win32api.keybd_event(78, 0, 1, 0)
        time.sleep(delay or self._delay)
        win32api.keybd_event(78, 0, 2, 0)

    def _read_address(self, address, handle):
        size = address.size
        buf = (c_byte * size)()
        bytesRead = c_ulong(0)

        try:
            result = ctypes.windll.kernel32.ReadProcessMemory(
                handle, address.address + self.base_addr, buf, size, ctypes.byref(bytesRead))

            if result:
                return struct.unpack(_size_to_struct[size], buf)[0]

        except Exception as e:
            err = ctypes.windll.kernel32.GetLastError()
            raise RuntimeError(f"Could not read address (err {err})") from e

    def read_address(self, address):
        with _open_proc(self.pid) as handle:
            return self._read_address(address, handle)

    def is_running(self):
        return bool(self.hwnd)

    def is_foreground(self):
        return win32gui.GetForegroundWindow() == self.hwnd


    def reload(self):
        self.hwnd = self._get_hwnd()

        if self.hwnd is None:
            self.hwnd = None
            self.pid = None
            self.base_addr = None

            return False

        self.pid = self._get_pid()
        self.base_addr = self._get_base_addr()

        return True

    def read_stat(self, stat):
        if not self.is_running():
            raise RuntimeError("Process is not running")

        return self.read_address(_statmap[stat])

    def _read_all(self):
        with _open_proc(self.pid) as handle:
            for stat in statinfo.names:
                yield self._read_address(_statmap[stat], handle)

    def read_all(self):
        if not self.is_running():
            raise RuntimeError("Process is not running")

        return list(self._read_all())

    def reroll(self, *, delay=None):
        if not self.is_foreground():
            self.focus_game()

        self._press_n(delay)
        return self.read_all()

    def zip(self, statlist):
        return dict(zip(statinfo.names, statlist))

    def focus_game(self):
        if self.hwnd:
            win32gui.SetForegroundWindow(self.hwnd)

    def focus_this(self):
        win32gui.SetForegroundWindow(self._own_hwnd)

    # TODO: proper context manager for this
    @contextmanager
    def focus(self, thing):
        orig_window = self.hwnd if thing == self.THIS else self._own_hwnd

        win32gui.SetForegroundWindow(thing)
        yield
        win32gui.SetForegroundWindow(orig_window)


def get_random_stats():
    return {name: random.randrange(1,5) for name in statinfo.names}
