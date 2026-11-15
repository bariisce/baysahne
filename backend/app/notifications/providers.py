"""Push providers.

expo — Expo Push Service (https://docs.expo.dev/push-notifications/sending-notifications/). Expo relays
       to FCM v1 (Android) and APNs (iOS) using credentials uploaded to the Expo project via EAS.
log  — development: logs and records messages, returns synthetic tickets, sends nothing.
fake — tests: in-memory, scriptable failures.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

import httpx

from app.config import get_settings

log = logging.getLogger("baysahne.push")

EXPO_SEND_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
EXPO_TOKEN_RE = re.compile(r"^Expo(nent)?PushToken\[[A-Za-z0-9_\-]{10,200}\]$")
BATCH_SIZE = 100  # Expo's maximum messages per request


class ProviderUnavailable(Exception):
    """The request as a whole failed (network / 5xx / 429). Nothing in the batch was accepted."""


@dataclass
class PushMessage:
    to: str
    title: str
    body: str
    data: dict = field(default_factory=dict)


@dataclass
class Ticket:
    ok: bool
    ticket_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def is_valid_token(token: str) -> bool:
    return bool(EXPO_TOKEN_RE.match(token))


class ExpoProvider:
    name = "expo"

    def __init__(self, access_token: str | None = None, client: httpx.Client | None = None):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        self.client = client or httpx.Client(timeout=20, headers=headers)

    def send(self, messages: list[PushMessage]) -> list[Ticket]:
        payload = [
            {"to": m.to, "title": m.title, "body": m.body, "data": m.data, "sound": "default",
             "priority": "high", "channelId": "default"}
            for m in messages
        ]
        try:
            r = self.client.post(EXPO_SEND_URL, json=payload)
        except httpx.HTTPError as e:
            raise ProviderUnavailable(f"network: {e.__class__.__name__}") from e
        if r.status_code == 429 or r.status_code >= 500:
            raise ProviderUnavailable(f"http {r.status_code}")
        if r.status_code >= 400:
            # A 4xx for the whole request is a programming/config error; retrying will not help,
            # but treat it as provider-level so the job records the error and retries are bounded.
            raise ProviderUnavailable(f"http {r.status_code}: {r.text[:300]}")
        data = r.json().get("data", [])
        tickets = []
        for item in data:
            if item.get("status") == "ok":
                tickets.append(Ticket(ok=True, ticket_id=item.get("id")))
            else:
                details = item.get("details") or {}
                tickets.append(Ticket(ok=False, error_code=details.get("error") or "Error",
                                      error_message=(item.get("message") or "")[:500]))
        if len(tickets) != len(messages):
            raise ProviderUnavailable("ticket count mismatch")
        return tickets

    def get_receipts(self, ticket_ids: list[str]) -> dict[str, dict]:
        try:
            r = self.client.post(EXPO_RECEIPTS_URL, json={"ids": ticket_ids})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderUnavailable(str(e)) from e
        return r.json().get("data", {})


class LogProvider:
    """Development provider: never contacts a push service."""

    name = "log"
    outbox: list[PushMessage] = []

    def send(self, messages: list[PushMessage]) -> list[Ticket]:
        for m in messages:
            log.info("[PUSH:log] to=%s… title=%r body=%r data=%s", m.to[:24], m.title, m.body, m.data)
        LogProvider.outbox.extend(messages)
        del LogProvider.outbox[:-500]
        return [Ticket(ok=True, ticket_id=f"log-{uuid.uuid4()}") for _ in messages]

    def get_receipts(self, ticket_ids: list[str]) -> dict[str, dict]:
        return {t: {"status": "ok"} for t in ticket_ids}


class FakeProvider:
    """Test provider. Configure `fail_next_requests` or `device_errors` to simulate failures."""

    name = "fake"

    def __init__(self) -> None:
        self.sent: list[PushMessage] = []
        self.requests = 0
        self.fail_next_requests = 0
        self.device_errors: dict[str, str] = {}
        self.receipt_errors: dict[str, str] = {}
        self._ticket_to_token: dict[str, str] = {}

    def send(self, messages: list[PushMessage]) -> list[Ticket]:
        self.requests += 1
        if self.fail_next_requests > 0:
            self.fail_next_requests -= 1
            raise ProviderUnavailable("simulated outage")
        tickets = []
        for m in messages:
            if m.to in self.device_errors:
                tickets.append(Ticket(ok=False, error_code=self.device_errors[m.to], error_message="simulated"))
            else:
                self.sent.append(m)
                tid = f"fake-{uuid.uuid4()}"
                self._ticket_to_token[tid] = m.to
                tickets.append(Ticket(ok=True, ticket_id=tid))
        return tickets

    def get_receipts(self, ticket_ids: list[str]) -> dict[str, dict]:
        out = {}
        for t in ticket_ids:
            token = self._ticket_to_token.get(t)
            if token in self.receipt_errors:
                out[t] = {"status": "error", "details": {"error": self.receipt_errors[token]}}
            else:
                out[t] = {"status": "ok"}
        return out


_provider = None


def get_provider():
    global _provider
    if _provider is None:
        s = get_settings()
        if s.push_provider == "expo":
            _provider = ExpoProvider(s.expo_access_token or None)
        elif s.push_provider == "fake":
            _provider = FakeProvider()
        else:
            _provider = LogProvider()
    return _provider


def set_provider(provider) -> None:
    """Test hook."""
    global _provider
    _provider = provider
