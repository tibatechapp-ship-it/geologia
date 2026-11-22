"""Safe, atomic SQLite snapshots and offline restore helpers.

The SQLite online-backup API captures a consistent snapshot, including committed
transactions in WAL mode. Restore is deliberately file-level: callers must stop
writers and ensure the destination database is offline before replacing it.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


def _database_file(path: str | os.PathLike[str], *, must_exist: bool) -> Path:
    resolved = Path(path).expanduser().absolute()
    if resolved.is_symlink():
        raise ValueError("database paths must not be symbolic links")
    if must_exist and (not resolved.exists() or not resolved.is_file()):
        raise ValueError("database file does not exist")
    return resolved


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)


def _integrity_check(path: Path) -> None:
    try:
        with closing(_connect_readonly(path)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise ValueError("SQLite integrity check failed")
    except sqlite3.DatabaseError as exc:
        raise ValueError("file is not a valid readable SQLite database") from exc


def _snapshot(
    source: Path,
    destination: Path,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    if source == destination:
        raise ValueError("source and destination must be different files")
    if not source.exists() or not source.is_file():
        raise ValueError("source database file does not exist")
    if source.is_symlink() or destination.is_symlink():
        raise ValueError("database paths must not be symbolic links")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    if (
        Path(str(destination) + "-wal").exists()
        or Path(str(destination) + "-shm").exists()
    ):
        raise RuntimeError("destination has SQLite sidecars; stop the app before replacing it")

    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".sqlite-tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with closing(_connect_readonly(source)) as source_connection:
            with closing(sqlite3.connect(temporary, timeout=10)) as target_connection:
                source_connection.backup(target_connection)
                target_connection.commit()
                check = target_connection.execute("PRAGMA integrity_check").fetchone()
                if check is None or check[0] != "ok":
                    raise ValueError("SQLite snapshot failed integrity check")
        with temporary.open("rb+") as snapshot:
            os.fsync(snapshot.fileno())
        os.replace(temporary, destination)
        digest = hashlib.sha256()
        with destination.open("rb") as snapshot:
            for chunk in iter(lambda: snapshot.read(1024 * 1024), b""):
                digest.update(chunk)
        return {
            "status": "created",
            "size_bytes": destination.stat().st_size,
            "sha256": digest.hexdigest(),
            "integrity": "ok",
        }
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def backup_database(
    source: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create an atomic, consistent SQLite backup; WAL transactions are included."""
    source_path = _database_file(source, must_exist=True)
    destination_path = _database_file(destination, must_exist=False)
    return _snapshot(
        source_path,
        destination_path,
        overwrite=overwrite,
    )


def restore_database_backup(
    backup: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Restore a verified backup to a database path.

    The destination must be offline. Existing files are never overwritten unless
    overwrite=True, and active SQLite WAL/SHM sidecars cause a safe refusal.
    """
    backup_path = _database_file(backup, must_exist=True)
    destination_path = _database_file(destination, must_exist=False)
    _integrity_check(backup_path)
    return _snapshot(
        backup_path,
        destination_path,
        overwrite=overwrite,
    )
