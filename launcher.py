"""
Desktop launcher for InvestTrack.

Starts the Streamlit server in a child process on a free localhost port and
shows it in a native window (pywebview). Closing the window stops the server.

    python launcher.py            # desktop window
    python launcher.py --server PORT   # internal: run only the server
"""
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP_NAME = "InvestTrack"
SERVER_FLAG = "--server"
STARTUP_TIMEOUT = 60  # seconds


def resource_dir():
    """Folder holding app.py: the PyInstaller bundle or the project folder."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def user_data_dir():
    """Per-user folder for saved transactions."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
        return Path(base) / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / APP_NAME


def configure_data_file():
    """In the packaged app, save transactions in the user data folder."""
    if getattr(sys, "frozen", False) and not os.environ.get("INVESTTRACK_DATA_FILE"):
        folder = user_data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        os.environ["INVESTTRACK_DATA_FILE"] = str(folder / "transactions.csv")


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def watch_parent(parent_pid):
    """Exit when the window process goes away, so no server is left running."""
    def loop():
        while True:
            time.sleep(2)
            if os.getppid() != parent_pid:
                os._exit(0)
    threading.Thread(target=loop, daemon=True).start()


def run_server(port):
    """Run Streamlit in this process (main thread: it installs signal handlers)."""
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit", "run", str(resource_dir() / "app.py"),
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--server.fileWatcherType", "none",
        "--global.developmentMode", "false",
        "--browser.gatherUsageStats", "false",
        "--client.toolbarMode", "minimal",
    ]
    sys.exit(stcli.main())


def server_command(port):
    if getattr(sys, "frozen", False):
        return [sys.executable, SERVER_FLAG, str(port)]
    return [sys.executable, str(Path(__file__).resolve()), SERVER_FLAG, str(port)]


def wait_until_ready(url, proc):
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.25)
    return False


def run_window():
    import webview

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    env = dict(os.environ, INVESTTRACK_PARENT_PID=str(os.getpid()))
    proc = subprocess.Popen(server_command(port), env=env, **kwargs)
    try:
        if not wait_until_ready(url, proc):
            webview.create_window(
                APP_NAME,
                html="<h3 style='font-family:sans-serif'>InvestTrack could not start.</h3>",
            )
        else:
            webview.create_window(APP_NAME, url, width=1400, height=900, min_size=(900, 600))
        webview.start()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    configure_data_file()
    if len(sys.argv) >= 3 and sys.argv[1] == SERVER_FLAG:
        parent = os.environ.get("INVESTTRACK_PARENT_PID")
        if parent:
            watch_parent(int(parent))
        run_server(int(sys.argv[2]))
    else:
        run_window()


if __name__ == "__main__":
    main()
