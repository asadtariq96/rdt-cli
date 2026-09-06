from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from rdt_cli.auth import Credential
from rdt_cli.client import RedditClient
from rdt_cli.config import DEFAULT_CONFIG
from rdt_cli.constants import BASE_URL
from rdt_cli.exceptions import ForbiddenError
from rdt_cli.fingerprint import BrowserFingerprint
from rdt_cli.session import SessionState
from rdt_cli.transports import ReadTransport


def test_absolute_url_joins_relative_paths() -> None:
    assert ReadTransport._absolute_url("/api/me.json") == f"{BASE_URL}/api/me.json"
    assert ReadTransport._absolute_url("api/me.json") == f"{BASE_URL}/api/me.json"
    assert ReadTransport._absolute_url("https://old.reddit.com/.json") == "https://old.reddit.com/.json"


def test_read_transport_uses_requests_session() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    session = SessionState.from_credential(cred)
    transport = ReadTransport(
        session,
        config=DEFAULT_CONFIG,
        fingerprint=BrowserFingerprint.chrome133_mac(),
        request_delay=0,
    )
    try:
        assert isinstance(transport.client, requests.Session)
        assert "httpx" not in type(transport.client).__module__
    finally:
        transport.close()


def test_request_sends_absolute_url_and_timeout() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    session = SessionState.from_credential(cred)
    transport = ReadTransport(
        session,
        config=DEFAULT_CONFIG,
        fingerprint=BrowserFingerprint.chrome133_mac(),
        request_delay=0,
    )
    try:
        resp = MagicMock()
        resp.status_code = 200
        resp.cookies = {}
        resp.headers = {}
        resp.text = '{"name":"spez"}'
        resp.json.return_value = {"name": "spez"}

        with patch.object(transport.client, "request", return_value=resp) as mock_request:
            data = transport.request("GET", "/api/me.json", params={"raw_json": 1})

        assert data == {"name": "spez"}
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert args[1] == f"{BASE_URL}/api/me.json"
        assert kwargs["timeout"] == DEFAULT_CONFIG.timeout
        assert kwargs["params"] == {"raw_json": 1}
    finally:
        transport.close()


def test_client_does_not_import_httpx() -> None:
    import rdt_cli.transports as transports

    assert not hasattr(transports, "httpx")
    with RedditClient(Credential(cookies={"reddit_session": "abc"})) as client:
        assert isinstance(client.client, requests.Session)


def test_forbidden_still_maps_403() -> None:
    cred = Credential(cookies={"reddit_session": "abc"})
    session = SessionState.from_credential(cred)
    transport = ReadTransport(
        session,
        config=DEFAULT_CONFIG,
        fingerprint=BrowserFingerprint.chrome133_mac(),
        request_delay=0,
    )
    try:
        resp = MagicMock()
        resp.status_code = 403
        resp.cookies = {}
        resp.headers = {}
        resp.text = "<html>Blocked</html>"
        with patch.object(transport.client, "request", return_value=resp):
            try:
                transport.request("GET", "/.json")
            except ForbiddenError as exc:
                assert str(exc) == "Access forbidden: Resource"
            else:
                raise AssertionError("expected ForbiddenError")
    finally:
        transport.close()
