"""Activity capture — keyboard, clipboard, and active window monitoring."""

import ctypes
import ctypes.wintypes
import threading
import time

import pyperclip
from pynput import keyboard

from storage import ActivityStorage

# Modifier keys tracked for shortcut detection
_MODIFIERS = {
    keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.alt_l, keyboard.Key.alt_r,
    keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.cmd_l, keyboard.Key.cmd_r,
}

_SPECIAL_KEYS = {
    keyboard.Key.enter: "[Enter]",
    keyboard.Key.tab: "[Tab]",
    keyboard.Key.backspace: "[Backspace]",
    keyboard.Key.space: " ",
    keyboard.Key.esc: "[Esc]",
    keyboard.Key.delete: "[Delete]",
    keyboard.Key.up: "[Up]",
    keyboard.Key.down: "[Down]",
    keyboard.Key.left: "[Left]",
    keyboard.Key.right: "[Right]",
    keyboard.Key.home: "[Home]",
    keyboard.Key.end: "[End]",
    keyboard.Key.page_up: "[PageUp]",
    keyboard.Key.page_down: "[PageDown]",
}

_MODIFIER_NAMES = {
    keyboard.Key.ctrl_l: "Ctrl", keyboard.Key.ctrl_r: "Ctrl",
    keyboard.Key.alt_l: "Alt", keyboard.Key.alt_r: "Alt",
    keyboard.Key.shift_l: "Shift", keyboard.Key.shift_r: "Shift",
    keyboard.Key.cmd_l: "Win", keyboard.Key.cmd_r: "Win",
}


def _get_active_window() -> str:
    """Get the title of the currently active window."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


class ActivityLogger:
    def __init__(self, storage: ActivityStorage):
        self.storage = storage
        self._running = False
        self._listener = None
        self._poll_thread = None

        # Keyboard state
        self._held_modifiers: set = set()
        self._typing_buffer: list[str] = []
        self._last_key_time: float = 0
        self._buffer_lock = threading.Lock()

        # Window/clipboard state
        self._last_window = ""
        self._last_clipboard = ""

        # Config
        self._flush_interval = 3.0  # seconds of silence before flushing
        self._poll_interval = 1.0
        self._max_buffer = 500

    def start(self):
        if self._running:
            return
        self._running = True

        # Start keyboard listener
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

        # Start polling thread for clipboard/window + buffer flush
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self):
        self._running = False
        self._flush_buffer()
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key):
        if not self._running:
            return

        # Track modifier keys
        if key in _MODIFIERS:
            self._held_modifiers.add(key)
            return

        # Check for shortcut (modifier + key)
        if self._held_modifiers:
            mod_names = sorted(set(_MODIFIER_NAMES.get(m, "") for m in self._held_modifiers))
            mod_str = "+".join(n for n in mod_names if n)

            key_name = ""
            if hasattr(key, 'char') and key.char:
                key_name = key.char.upper()
            elif hasattr(key, 'name'):
                key_name = key.name.capitalize()

            if mod_str and key_name:
                combo = f"{mod_str}+{key_name}"
                app = _get_active_window()
                self.storage.append_event("SHORTCUT", combo, app)
            return

        # Regular key
        self._last_key_time = time.time()

        if hasattr(key, 'char') and key.char:
            with self._buffer_lock:
                self._typing_buffer.append(key.char)
        elif key in _SPECIAL_KEYS:
            with self._buffer_lock:
                self._typing_buffer.append(_SPECIAL_KEYS[key])
        # Ignore other special keys (F1-F12, etc.)

        # Flush if buffer is large
        with self._buffer_lock:
            if len(self._typing_buffer) >= self._max_buffer:
                self._flush_buffer_unlocked()

    def _on_release(self, key):
        if key in _MODIFIERS:
            self._held_modifiers.discard(key)

    def _flush_buffer(self):
        with self._buffer_lock:
            self._flush_buffer_unlocked()

    def _flush_buffer_unlocked(self):
        """Flush typing buffer to storage. Must be called with _buffer_lock held."""
        if not self._typing_buffer:
            return
        text = "".join(self._typing_buffer)
        self._typing_buffer.clear()
        app = _get_active_window()
        self.storage.append_event("TYPED", text, app)

    def _poll_loop(self):
        """Poll clipboard, window changes, and flush typing buffer on idle."""
        while self._running:
            try:
                self._check_window()
                self._check_clipboard()

                # Flush typing buffer after idle period
                if self._typing_buffer and self._last_key_time:
                    if time.time() - self._last_key_time > self._flush_interval:
                        self._flush_buffer()

            except Exception:
                pass

            time.sleep(self._poll_interval)

    def _check_window(self):
        window = _get_active_window()
        if window and window != self._last_window:
            self._flush_buffer()  # Flush typing before switching context
            self.storage.append_event("WINDOW", window)
            self._last_window = window

    def _check_clipboard(self):
        try:
            content = pyperclip.paste()
            if content and content != self._last_clipboard:
                self._last_clipboard = content
                # Truncate long clipboard content
                if len(content) > 2000:
                    content = content[:2000] + "..."
                app = _get_active_window()
                self.storage.append_event("CLIPBOARD", content, app)
        except Exception:
            pass
