# -*- coding: utf-8 -*-
"""Clipboard-preserving GUI text entry on Windows.

Unlike copying text to the clipboard and sending Ctrl+V, this module creates
keyboard input events. This preserves an image captured using Win+Shift+S so
that the agent can type 'mspaint' into Run and still paste the image into Paint.

The only side effects are simulated keyboard events; there are no filesystem,
window-inspection, clipboard-read, or direct file-creation operations.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable, Any

_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_INPUT_KEYBOARD = 1

# Match the actual Windows INPUT layout, including 64-bit alignment of unions.
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]

class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD),
                ('wParamH', wintypes.WORD)]

class _INPUTUNION(ctypes.Union):
    _fields_ = [('mi', _MOUSEINPUT), ('ki', _KEYBDINPUT), ('hi', _HARDWAREINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('payload', _INPUTUNION)]


def unicode_units(text: str) -> list[int]:
    """A Windows Unicode keyboard event operates on 16-bit UTF-16 units."""
    encoded = text.encode('utf-16-le', errors='surrogatepass')
    return [int.from_bytes(encoded[i:i+2], 'little') for i in range(0, len(encoded), 2)]


def _win_send_unicode(text: str) -> None:
    """Emit virtual keyboard input through user32.SendInput (no clipboard)."""
    if not text:
        return
    if sys.platform != 'win32':
        raise RuntimeError('Windows Unicode keyboard input requires Windows.')
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    units = unicode_units(text)
    # Windows typically accepts batches; bound sizes so long text is responsive.
    for start in range(0, len(units), 64):
        batch = units[start:start + 64]
        events = (_INPUT * (len(batch) * 2))()
        for i, unit in enumerate(batch):
            events[2 * i].type = _INPUT_KEYBOARD
            events[2 * i].payload.ki = _KEYBDINPUT(0, unit, _KEYEVENTF_UNICODE, 0, 0)
            events[2 * i + 1].type = _INPUT_KEYBOARD
            events[2 * i + 1].payload.ki = _KEYBDINPUT(0, unit, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP, 0, 0)
        count = len(events)
        written = user32.SendInput(count, events, ctypes.sizeof(_INPUT))
        if written != count:
            error = ctypes.get_last_error()
            raise OSError(error, f'SendInput 仅发送 {written}/{count} 次键盘事件；未调用剪贴板回退。')


def type_text(pg: Any, value: str, *, platform: str | None = None,
              unicode_sender: Callable[[str], None] | None = None) -> str:
    """Type without touching the clipboard on Windows.

    Printable ASCII is sent via PyAutoGUI.write (layout-aware key presses).
    CJK and other Unicode characters are sent via KEYEVENTF_UNICODE.
    Enter/tab are real key presses, which is compatible with Notepad's multiline
    text and Run/Save As inputs. No clipboard-copy fallback is permitted.
    """
    platform = sys.platform if platform is None else platform
    send_unicode = _win_send_unicode if unicode_sender is None else unicode_sender
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    i = 0
    while i < len(value):
        ch = value[i]
        if ch in '\n\t':
            pg.press('enter' if ch == '\n' else 'tab')
            i += 1
            continue
        is_ascii = 32 <= ord(ch) <= 126
        j = i + 1
        while j < len(value) and value[j] not in '\n\t' and (32 <= ord(value[j]) <= 126) == is_ascii:
            j += 1
        segment = value[i:j]
        if is_ascii:
            pg.write(segment, interval=0.006)
        elif platform == 'win32':
            send_unicode(segment)
        else:
            # Never silently corrupt an existing image by copying the text.
            raise RuntimeError('非 Windows 环境无法执行无剪贴板 Unicode 输入；没有覆盖剪贴板。')
        i = j
    return f'type {len(value)} characters (keyboard-only, clipboard preserved)'
