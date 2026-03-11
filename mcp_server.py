"""MCP server exposing Chronicle activity log tools."""

from fastmcp import FastMCP

from storage import ActivityStorage

mcp = FastMCP("chronicle")
_storage: ActivityStorage = None


def init(storage: ActivityStorage):
    global _storage
    _storage = storage


@mcp.tool
def get_recent_activity(minutes: int = 30) -> str:
    """Get recent computer activity from the last N minutes.
    Shows keystrokes, clipboard copies, window switches, and shortcuts."""
    return _storage.get_recent(minutes)


@mcp.tool
def search_activity(query: str, start_date: str = "", end_date: str = "") -> str:
    """Search activity history for specific text in typed content,
    clipboard data, or window titles. Dates in YYYY-MM-DD format."""
    return _storage.search(query, start_date, end_date)


@mcp.tool
def get_activity_summary(hours: int = 24) -> str:
    """Get raw activity logs from the last N hours.
    Returns timestamped events for the AI to summarize."""
    return _storage.get_summary(hours)


VERSION = "1.0.0"


def run_server(host: str = "127.0.0.1", port: int = 29172):
    """Run the MCP server with a health endpoint. Blocking — call from a daemon thread."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route, Mount

    async def health(request):
        return JSONResponse({"status": "ok", "version": VERSION})

    sse_app = mcp.sse_app()
    app = Starlette(routes=[
        Route("/health", health),
        Mount("/", app=sse_app),
    ])

    uvicorn.run(app, host=host, port=port, log_level="warning")
