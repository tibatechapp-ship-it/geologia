import argparse
import os
from pathlib import Path

import pytest

from geologia.desktop import LOCAL_HOST, configure_storage, parse_port


def test_desktop_storage_uses_persistent_user_directory(tmp_path, monkeypatch):
    for key in (
        "GEOLOGIA_DB_PATH",
        "GEOLOGIA_UPLOAD_DIR",
        "GEOLOGIA_KNOWLEDGE_DB_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    data_dir = configure_storage(tmp_path)
    assert data_dir == tmp_path / ".geologia"
    assert os.environ["GEOLOGIA_DB_PATH"] == str(data_dir / "geologia.sqlite3")
    assert os.environ["GEOLOGIA_UPLOAD_DIR"] == str(data_dir / "uploads")
    assert os.environ["GEOLOGIA_KNOWLEDGE_DB_PATH"] == str(data_dir / "knowledge.sqlite3")


def test_desktop_port_validation():
    assert parse_port("8000") == 8000
    with pytest.raises(argparse.ArgumentTypeError):
        parse_port("not-a-port")
    with pytest.raises(argparse.ArgumentTypeError):
        parse_port("0")
    with pytest.raises(argparse.ArgumentTypeError):
        parse_port("65536")


def test_desktop_entrypoint_is_loopback_only():
    assert LOCAL_HOST == "127.0.0.1"
