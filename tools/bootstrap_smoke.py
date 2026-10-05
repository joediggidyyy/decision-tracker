"""Controlled subprocess evidence for environment/package/SQLite readiness."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from decision_tracker import __version__

result = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True, timeout=30)
if result.returncode:
    raise SystemExit(result.stdout + result.stderr)
with sqlite3.connect(":memory:") as db:
    db.execute("PRAGMA foreign_keys=ON")
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    db.execute("CREATE TABLE readiness (id INTEGER PRIMARY KEY, value TEXT) STRICT")
    db.execute("INSERT INTO readiness VALUES (1, 'ready')")
    assert db.execute("SELECT value FROM readiness").fetchone()[0] == "ready"
assert sys.prefix != sys.base_prefix
print(json.dumps({"status": "pass", "package_version": __version__,
                  "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                  "scope": "environment bootstrap, not application behavior"}))
