import os
import time
import socket
import threading
import webbrowser
from pathlib import Path
from io import StringIO

# Force PyInstaller to include waitress
import waitress  # noqa: F401

BASE_DIR = Path(__file__).resolve().parent
FLAG_FILE = BASE_DIR / ".first_run_done"
LOG_FILE = BASE_DIR / "app.log"


def log(msg: str):
    try:
        prev = LOG_FILE.read_text(encoding="utf-8") if LOG_FILE.exists() else ""
        LOG_FILE.write_text(prev + msg + "\n", encoding="utf-8")
    except Exception:
        pass


def find_free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_until_listening(port: int, timeout_sec: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        import django
        django.setup()
    except Exception as e:
        log(f"[BOOT] django.setup failed: {repr(e)}")
        raise

    # migrate only first time (or if db missing) WITHOUT stdout
    db_path = BASE_DIR / "db.sqlite3"
    try:
        if (not FLAG_FILE.exists()) or (not db_path.exists()):
            from django.core.management import call_command
            call_command(
                "migrate",
                interactive=False,
                verbosity=0,
                stdout=StringIO(),
                stderr=StringIO(),
            )
            FLAG_FILE.write_text("ok", encoding="utf-8")
    except Exception as e:
        log(f"[MIGRATE] failed: {repr(e)}")
        raise

    port = find_free_port()

    def run_server():
        try:
            from config.wsgi import application
            from waitress import serve
            serve(application, host="127.0.0.1", port=port, threads=8)
        except Exception as e:
            log(f"[SERVER] crashed: {repr(e)}")
            raise

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    if wait_until_listening(port, 12.0):
        webbrowser.open(f"http://127.0.0.1:{port}/")
    else:
        log("[SERVER] did not start listening in time.")
        raise RuntimeError("Server failed to start. Check app.log")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
    