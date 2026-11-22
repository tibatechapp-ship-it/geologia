"""Shared runtime configuration regression tests."""
import argparse
import sys

import pytest

from geologia.runtime import parse_port


@pytest.mark.parametrize(("value", "expected"), [("8000", 8000), ("1", 1), ("65535", 65535)])
def test_parse_port_accepts_valid_boundaries(value, expected):
    assert parse_port(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "0", "-1", "65536", "8000.5"])
def test_parse_port_rejects_invalid_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_port(value)


def test_api_entrypoint_uses_shared_port_validation(monkeypatch):
    import geologia.api as api_module

    monkeypatch.setattr(sys, "argv", ["geologia-api", "--port", "65536"])
    with pytest.raises(SystemExit) as error:
        api_module.run()
    assert error.value.code == 2


def test_api_entrypoint_reads_shared_port_environment(monkeypatch):
    import geologia.api as api_module

    captured = {}
    monkeypatch.setattr(sys, "argv", ["geologia-api"])
    monkeypatch.setenv("GEOLOGIA_PORT", "8091")
    monkeypatch.setattr(
        api_module.uvicorn,
        "run",
        lambda *args, **kwargs: captured.update(kwargs),
    )

    api_module.run()

    assert captured == {"host": "127.0.0.1", "port": 8091, "reload": False}


def test_api_entrypoint_reports_invalid_port_environment(monkeypatch):
    import geologia.api as api_module

    monkeypatch.setattr(sys, "argv", ["geologia-api"])
    monkeypatch.setenv("GEOLOGIA_PORT", "invalid")
    with pytest.raises(SystemExit) as error:
        api_module.run()
    assert error.value.code == 2


def test_desktop_entrypoint_reports_invalid_port_environment(monkeypatch):
    import geologia.desktop as desktop_module

    monkeypatch.setattr(sys, "argv", ["geologia-desktop", "--no-browser"])
    monkeypatch.setenv("GEOLOGIA_PORT", "invalid")
    with pytest.raises(SystemExit) as error:
        desktop_module.main()
    assert error.value.code == 2
