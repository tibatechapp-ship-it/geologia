"""ASGI-level loopback enforcement tests, independent of the CLI launcher."""
import asyncio

import pytest
from starlette.requests import Request
from starlette.responses import Response

from geologia.api import local_only_guard


def make_request(client_host: str, host_header: str) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/health",
        "raw_path": b"/health",
        "query_string": b"",
        "headers": [(b"host", host_header.encode("ascii"))],
        "client": (client_host, 12345),
        "server": ("127.0.0.1", 8000),
    }
    return Request(scope)


@pytest.mark.parametrize(
    ("client_host", "host_header"),
    [
        ("127.0.0.1", "127.0.0.1:8000"),
        ("::1", "[::1]:8000"),
        ("::ffff:127.0.0.1", "localhost:8000"),
        ("testclient", "testserver"),
    ],
)
def test_local_clients_and_testclient_are_allowed(client_host, host_header):
    async def next_handler(_request):
        return Response("ok", status_code=200)

    response = asyncio.run(
        local_only_guard(make_request(client_host, host_header), next_handler)
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("client_host", "host_header"),
    [
        ("203.0.113.8", "127.0.0.1:8000"),
        ("127.0.0.1", "geologia.example"),
        ("testclient", "geologia.example"),
        ("127.0.0.1", "[malformed"),
    ],
)
def test_nonlocal_clients_and_hosts_are_rejected(client_host, host_header):
    async def next_handler(_request):
        pytest.fail("blocked request must not reach the application")

    response = asyncio.run(
        local_only_guard(make_request(client_host, host_header), next_handler)
    )
    assert response.status_code == 403
