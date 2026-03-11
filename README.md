# Chronicle

A system tray application that records your computer usage history and exposes it via an MCP server for AI assistants to query.

## What it captures

- **Keystrokes** — grouped into typing sessions (flushed after 3s of inactivity)
- **Clipboard** — copy/paste content changes
- **Window switches** — active window title changes
- **Shortcuts** — keyboard shortcuts (Ctrl+C, Alt+Tab, etc.)

## Storage

Daily text files in `logs/`:

```
logs/
  2026-03-10.txt
  2026-03-11.txt
  ...
```

Each line is a timestamped event:
```
[14:23:05] WINDOW: VS Code - project.py
[14:23:08] TYPED [VS Code - project.py]: def hello_world():
[14:24:01] SHORTCUT [VS Code - project.py]: Ctrl+S
[14:24:15] CLIPBOARD [Chrome - Stack Overflow]: import asyncio...
```

## Setup

```bash
pip install -r requirements.txt
python main.py
```

Or download `Chronicle.exe` from [Releases](../../releases).

The app runs in the system tray:
- **Green icon** — logging active
- **Red icon** — logging paused
- **Double-click** — toggle logging
- **Right-click** — Pause/Resume, Exit

## MCP Server

Runs on `http://127.0.0.1:29172/sse` with three tools:

| Tool | Description |
|------|-------------|
| `get_recent_activity(minutes=30)` | Events from the last N minutes |
| `search_activity(query, start_date?, end_date?)` | Search typed text, clipboard, window titles |
| `get_activity_summary(hours=24)` | Raw logs for AI summarization |

### Connect to KurisuAssistant

Add as an MCP server (External, SSE transport):
- **URL**: `http://127.0.0.1:29172/sse`

Or install via the Extensions page in KurisuAssistant.

## Privacy

- All data stays local in `logs/` text files
- MCP server only listens on localhost
- No data is transmitted anywhere
- Delete log files anytime to clear history
