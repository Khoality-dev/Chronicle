"""File-based activity storage — one text file per day."""

import threading
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "logs"


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
