"""Chronicle — system tray activity logger with MCP server."""

import sys
import os
import threading
import winreg

import pystray
from PIL import Image, ImageDraw

from storage import ActivityStorage
from logger import ActivityLogger
import mcp_server

APP_NAME = "Chronicle"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_exe_path() -> str:
    """Return the path to the running executable."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def set_startup(enabled: bool):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def create_icon(color: str = "green") -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=color)
    return img


def main():
    storage = ActivityStorage()
    activity_logger = ActivityLogger(storage)
    mcp_server.init(storage)

    # Start MCP server in daemon thread
    def _run_mcp():
        try:
            mcp_server.run_server()
        except Exception as e:
            import traceback
            err_path = storage.data_dir / "mcp_error.log"
            with open(err_path, "w") as f:
                traceback.print_exc(file=f)

    mcp_thread = threading.Thread(target=_run_mcp, daemon=True)
    mcp_thread.start()

    # Start activity logger
    activity_logger.start()

    is_logging = [True]

    def toggle_logging(icon, item):
        if is_logging[0]:
            activity_logger.stop()
            icon.icon = create_icon("red")
            icon.title = "Chronicle (Paused)"
        else:
            activity_logger.start()
            icon.icon = create_icon("green")
            icon.title = "Chronicle (Running)"
        is_logging[0] = not is_logging[0]

    def toggle_startup(icon, item):
        set_startup(not is_startup_enabled())

    def open_logs(icon, item):
        os.startfile(str(storage.data_dir))

    def on_exit(icon, item):
        activity_logger.stop()
        icon.stop()

    def get_toggle_text(item):
        return "Pause Logging" if is_logging[0] else "Resume Logging"

    menu = pystray.Menu(
        pystray.MenuItem(get_toggle_text, toggle_logging, default=True),
        pystray.MenuItem("Open Logs", open_logs),
        pystray.MenuItem("Run on Startup", toggle_startup, checked=lambda item: is_startup_enabled()),
        pystray.MenuItem("Exit", on_exit),
    )

    icon = pystray.Icon(
        "Chronicle",
        create_icon("green"),
        "Chronicle (Running)",
        menu,
    )
    icon.run()


if __name__ == "__main__":
    main()
