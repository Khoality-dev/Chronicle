"""Chronicle — system tray activity logger with MCP server."""

import threading

import pystray
from PIL import Image, ImageDraw

from storage import ActivityStorage
from logger import ActivityLogger
import mcp_server


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
    mcp_thread = threading.Thread(target=mcp_server.run_server, daemon=True)
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

    def on_exit(icon, item):
        activity_logger.stop()
        icon.stop()

    def get_toggle_text(item):
        return "Pause Logging" if is_logging[0] else "Resume Logging"

    menu = pystray.Menu(
        pystray.MenuItem(get_toggle_text, toggle_logging, default=True),
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
