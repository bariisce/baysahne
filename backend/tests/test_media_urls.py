"""Local media URLs follow the request's address in development and are fixed elsewhere."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.config import Settings
from app.storage import LocalStorage, RequestOrigin


def _client(tmp_path: Path, configured: str = "") -> TestClient:
    storage = LocalStorage(tmp_path, configured)

    async def media_url(_request):
        return PlainTextResponse(storage.url("images/a.jpg"))

    return TestClient(RequestOrigin(Starlette(routes=[Route("/", media_url)])))


def test_phone_on_the_lan_gets_the_address_it_used(tmp_path):
    r = _client(tmp_path).get("/", headers={"host": "172.20.10.4:8100"})
    assert r.text == "http://172.20.10.4:8100/media/images/a.jpg"


def test_admin_behind_its_proxy_gets_its_own_origin(tmp_path):
    r = _client(tmp_path).get("/", headers={"host": "127.0.0.1:8100", "x-forwarded-host": "localhost:3100"})
    assert r.text == "http://localhost:3100/media/images/a.jpg"


def test_malformed_host_falls_back(tmp_path):
    r = _client(tmp_path).get("/", headers={"host": "evil.example/x?"})
    assert r.text == "http://localhost:8100/media/images/a.jpg"


def test_stale_fixed_address_cannot_pin_development_urls(tmp_path):
    # The API was started with yesterday's LAN address; the computer has since moved to another network.
    r = _client(tmp_path, "http://192.168.1.208:8100").get("/", headers={"host": "172.20.10.4:8100"})
    assert r.text == "http://172.20.10.4:8100/media/images/a.jpg"


def test_deployed_api_uses_its_configured_address_whatever_the_host_header_says(tmp_path):
    # Outside development RequestOrigin is not installed, so request headers cannot influence URLs.
    storage = LocalStorage(tmp_path, "https://api.example.com")

    async def media_url(_request):
        return PlainTextResponse(storage.url("images/a.jpg"))

    client = TestClient(Starlette(routes=[Route("/", media_url)]))
    r = client.get("/", headers={"host": "172.20.10.4:8100", "x-forwarded-host": "evil.example"})
    assert r.text == "https://api.example.com/media/images/a.jpg"


def test_request_origin_is_only_installed_in_development(monkeypatch):
    from app import main
    from app.config import get_settings

    def installed() -> bool:
        return any(m.cls is RequestOrigin for m in main.create_app().user_middleware)

    assert installed()  # the test environment counts as development
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert not installed()


@pytest.mark.parametrize("env", ["staging", "production"])
def test_deployed_environments_require_a_fixed_base_url(env):
    with pytest.raises(ValidationError, match="PUBLIC_API_BASE_URL"):
        Settings(_env_file=None, app_env=env, public_api_base_url="")
