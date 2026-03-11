"""File-based activity storage — one text file per day."""

import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

_base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
DATA_DIR = _base / "logs"


class ActivityStorage:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def _get_file_path(self, dt: datetime = None) -> Path:
        dt = dt or datetime.now()
        return self.data_dir / f"{dt.strftime('%Y-%m-%d')}.txt"

    def append_event(self, event_type: str, data: str, app_name: str = ""):
        """Append a timestamped event to today's log file."""
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        app_part = f" [{app_name}]" if app_name else ""
        line = f"[{timestamp}] {event_type}{app_part}: {data}\n"

        with self._lock:
            with open(self._get_file_path(now), "a", encoding="utf-8") as f:
                f.write(line)

    def get_recent(self, minutes: int = 30) -> str:
        """Get events from the last N minutes."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=minutes)
        lines = []

        dates = {cutoff.date(), now.date()}
        for d in sorted(dates):
            dt = datetime(d.year, d.month, d.day)
            path = self._get_file_path(dt)
            if path.exists():
                lines.extend(self._read_lines_after(path, cutoff))

        return "\n".join(lines) if lines else "No recent activity."

    def search(self, query: str, start_date: str = "", end_date: str = "") -> str:
        """Search log files for matching text."""
        results = []
        query_lower = query.lower()

        files = sorted(self.data_dir.glob("*.txt"))
        for path in files:
            date_str = path.stem
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue

            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if query_lower in line.lower():
                        results.append(f"[{date_str}] {line.rstrip()}")

            if len(results) >= 200:
                break

        return "\n".join(results) if results else f"No results for '{query}'."

    def get_summary(self, hours: int = 24) -> str:
        """Get raw log content from the last N hours for LLM summarization."""
        now = datetime.now()
        cutoff = now - timedelta(hours=hours)
        lines = []

        dates = set()
        d = cutoff.date()
        while d <= now.date():
            dates.add(d)
            d += timedelta(days=1)

        for d in sorted(dates):
            dt = datetime(d.year, d.month, d.day)
            path = self._get_file_path(dt)
            if path.exists():
                file_lines = self._read_lines_after(path, cutoff)
                if file_lines:
                    lines.append(f"=== {d.strftime('%Y-%m-%d')} ===")
                    lines.extend(file_lines)

        if not lines:
            return "No activity recorded in this period."

        text = "\n".join(lines)
        if len(text) > 15000:
            text = text[:15000] + "\n... (truncated)"
        return text

    def get_readable(self, minutes: int = 30) -> str:
        """Get normalized, human-readable activity from the last N minutes.

        Interprets raw keystrokes: [Backspace] removes previous char,
        [Enter] becomes newline, Shift+X shortcuts become letters,
        consecutive typing in the same window is merged.
        """
        raw = self.get_recent(minutes)
        if raw == "No recent activity.":
            return raw
        return self._normalize(raw.split("\n"))

    def _normalize(self, lines: list[str]) -> str:
        """Process raw log lines into readable output."""
        import re

        result = []
        # Pending typing buffer: (start_time, app, chars)
        pending_time = ""
        pending_app = ""
        pending_chars: list[str] = []

        line_re = re.compile(
            r"^\[(\d{2}:\d{2}:\d{2})\] (\w+)"
            r"(?: \[([^\]]*)\])?: (.*)$"
        )

        def flush_pending():
            if not pending_chars:
                return
            text = self._interpret_keys(pending_chars)
            if text.strip():
                app_part = f" [{pending_app}]" if pending_app else ""
                result.append(f"[{pending_time}] TYPED{app_part}: {text}")

        for line in lines:
            m = line_re.match(line)
            if not m:
                flush_pending()
                pending_chars.clear()
                result.append(line)
                continue

            timestamp, event_type, app, data = m.groups()
            app = app or ""

            if event_type == "TYPED":
                if app != pending_app and pending_chars:
                    flush_pending()
                    pending_chars.clear()
                if not pending_chars:
                    pending_time = timestamp
                    pending_app = app
                pending_chars.append(data)

            elif event_type == "SHORTCUT":
                # Shift+X → treat as typed letter
                if data.startswith("Shift+") and len(data) == 7:
                    letter = data[6]
                    if app != pending_app and pending_chars:
                        flush_pending()
                        pending_chars.clear()
                    if not pending_chars:
                        pending_time = timestamp
                        pending_app = app
                    pending_chars.append(letter)
                else:
                    flush_pending()
                    pending_chars.clear()
                    app_part = f" [{app}]" if app else ""
                    result.append(f"[{timestamp}] SHORTCUT{app_part}: {data}")

            else:
                flush_pending()
                pending_chars.clear()
                result.append(line)

        flush_pending()
        return "\n".join(result)

    @staticmethod
    def _interpret_keys(chunks: list[str]) -> str:
        """Interpret a list of raw typed chunks into final text.

        Processes [Backspace], [Enter], [Tab], [Delete], etc.
        """
        buf: list[str] = []
        cursor = 0  # index into buf where next char is inserted

        for chunk in chunks:
            i = 0
            while i < len(chunk):
                if chunk[i] == "[":
                    end = chunk.find("]", i)
                    if end != -1:
                        tag = chunk[i:end + 1]
                        i = end + 1
                        if tag == "[Backspace]":
                            if cursor > 0:
                                cursor -= 1
                                buf.pop(cursor)
                        elif tag == "[Delete]":
                            if cursor < len(buf):
                                buf.pop(cursor)
                        elif tag == "[Enter]":
                            buf.insert(cursor, "\n")
                            cursor += 1
                        elif tag == "[Tab]":
                            buf.insert(cursor, "\t")
                            cursor += 1
                        elif tag == "[Left]":
                            if cursor > 0:
                                cursor -= 1
                        elif tag == "[Right]":
                            if cursor < len(buf):
                                cursor += 1
                        elif tag == "[Home]":
                            # Move to start of current line
                            while cursor > 0 and buf[cursor - 1] != "\n":
                                cursor -= 1
                        elif tag == "[End]":
                            while cursor < len(buf) and buf[cursor] != "\n":
                                cursor += 1
                        # Ignore [Esc], [PageUp], [PageDown], [Up], [Down]
                        continue
                buf.insert(cursor, chunk[i])
                cursor += 1
                i += 1

        return "".join(buf)

    def _read_lines_after(self, path: Path, cutoff: datetime) -> list[str]:
        """Read lines from a file that have timestamps after the cutoff."""
        cutoff_time = cutoff.strftime("%H:%M:%S")
        cutoff_date = cutoff.date()
        file_date_str = path.stem
        results = []

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip()
                if not line:
                    continue
                if file_date_str == cutoff_date.strftime("%Y-%m-%d"):
                    if line.startswith("[") and "]" in line:
                        time_str = line[1:line.index("]")]
                        if time_str < cutoff_time:
                            continue
                results.append(line)

        return results
