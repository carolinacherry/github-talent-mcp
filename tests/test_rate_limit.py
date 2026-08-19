import asyncio
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from github_talent_mcp.github_client import GitHubClient


def _resp(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        headers=headers or {},
        request=httpx.Request("GET", "https://api.github.com/x"),
    )


def _client_with(responses: list[httpx.Response]) -> GitHubClient:
    client = GitHubClient.__new__(GitHubClient)
    client._client = type("FakeHTTP", (), {})()
    client._client.get = AsyncMock(side_effect=list(responses))
    return client


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Capture backoff durations without actually waiting."""
    slept: list[float] = []

    async def fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return slept


@pytest.mark.asyncio
async def test_retries_on_primary_rate_limit(no_sleep):
    reset = str(int(time.time()) + 2)
    client = _client_with([
        _resp(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset}),
        _resp(200),
    ])
    resp = await client._get("/x")
    assert resp.status_code == 200
    assert client._client.get.await_count == 2
    assert no_sleep and no_sleep[0] <= 61.0


@pytest.mark.asyncio
async def test_retries_on_secondary_rate_limit_retry_after(no_sleep):
    client = _client_with([
        _resp(429, {"Retry-After": "3"}),
        _resp(200),
    ])
    resp = await client._get("/x")
    assert resp.status_code == 200
    assert no_sleep == [3.0]


@pytest.mark.asyncio
async def test_retries_on_5xx(no_sleep):
    client = _client_with([_resp(502), _resp(200)])
    resp = await client._get("/x")
    assert resp.status_code == 200
    assert client._client.get.await_count == 2


@pytest.mark.asyncio
async def test_no_retry_on_404(no_sleep):
    client = _client_with([_resp(404)])
    resp = await client._get("/x")
    assert resp.status_code == 404
    assert client._client.get.await_count == 1
    assert no_sleep == []


@pytest.mark.asyncio
async def test_no_retry_on_403_with_quota_remaining(no_sleep):
    # A 403 that is NOT a rate limit (e.g. permissions) should not retry.
    client = _client_with([_resp(403, {"X-RateLimit-Remaining": "4999"})])
    resp = await client._get("/x")
    assert resp.status_code == 403
    assert client._client.get.await_count == 1


@pytest.mark.asyncio
async def test_gives_up_after_max_retries(no_sleep):
    client = _client_with([_resp(403, {"Retry-After": "1"})] * 10)
    resp = await client._get("/x", max_retries=3)
    assert resp.status_code == 403
    assert client._client.get.await_count == 4  # initial + 3 retries


@pytest.mark.asyncio
async def test_waits_the_full_retry_after_not_a_shorter_cap(no_sleep):
    """GitHub's "retry after 23s" was being served with an 8s wait, so the retry
    landed inside the throttle window and failed — three attempts, no data."""
    client = _client_with([
        _resp(403, {"Retry-After": "23"}),
        _resp(200),
    ])
    resp = await client._get("https://api.github.com/search/users")

    assert resp.status_code == 200
    assert no_sleep, "no backoff happened at all"
    assert no_sleep[0] == pytest.approx(23.0), (
        f"slept {no_sleep[0]}s when GitHub asked for 23s"
    )


@pytest.mark.asyncio
async def test_gives_up_rather_than_retrying_before_the_window_lifts(no_sleep):
    """A throttle longer than we can wait: retrying early is strictly worse than
    returning the error, since it burns the attempt and still fails."""
    client = _client_with([
        _resp(403, {"Retry-After": "600"}),
        _resp(200),
    ])
    resp = await client._get("https://api.github.com/search/users")

    assert resp.status_code == 403, "retried into a throttle it could not outlast"
    assert not no_sleep, "slept before giving up"


@pytest.mark.asyncio
async def test_total_backoff_is_bounded_across_retries(no_sleep):
    """Two long-ish waits must not stack past an MCP client's request timeout."""
    client = _client_with([
        _resp(403, {"Retry-After": "25"}),
        _resp(403, {"Retry-After": "25"}),
        _resp(200),
    ])
    await client._get("https://api.github.com/search/users")

    assert sum(no_sleep) <= 35.0, f"slept {sum(no_sleep)}s in one call"
