"""Portable desktop entry point for the local GEOLOGIA API."""
import argparse
import os
from pathlib import Path
import threading
import time
import webbrowser

import uvicorn

from geologia import __version__
from geologia.api import app

LOCAL_HOST = "127.0.0.1"


def configure_storage(home: Path | None = None) -> Path:
    """Place desktop data in a stable user-owned directory, not the bundle folder."""
    data_dir = (home or Path.home()) / ".geologia"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("GEOLOGIA_DB_PATH", str(data_dir / "geologia.sqlite3"))
    os.environ.setdefault("GEOLOGIA_UPLOAD_DIR", str(data_dir / "uploads"))
    os.environ.setdefault("GEOLOGIA_KNOWLEDGE_DB_PATH", str(data_dir / "knowledge.sqlite3"))
    return data_dir


def parse_port(value: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _open_browser_when_ready(server: uvicorn.Server, url: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if server.started:
            if not webbrowser.open(url):
                print(f"Open this local address manually: {url}", flush=True)
            return
        if server.should_exit:
            return
        time.sleep(0.2)
    print(f"Server startup is taking longer than expected. Open: {url}", flush=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the lightweight GEOLOGIA desktop workspace on this computer."
    )
    parser.add_argument("--version", action="version", version=f"GEOLOGIA {__version__}")
    parser.add_argument(
        "--port",
        type=parse_port,
        default=parse_port(os.environ.get("GEOLOGIA_PORT", "8000")),
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser tab")
    args = parser.parse_args(argv)

    configure_storage()
    url = f"http://{LOCAL_HOST}:{args.port}"
    server = uvicorn.Server(
        uvicorn.Config(app, host=LOCAL_HOST, port=args.port, log_level="info")
    )
    print("GEOLOGIA desktop is local-only; do not expose this API to the network.", flush=True)
    print(f"Workspace: {url}", flush=True)
    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready, args=(server, url), daemon=True
        ).start()
    server.run()


if __name__ == "__main__":
    main()
