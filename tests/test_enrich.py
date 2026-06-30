import json

import pytest

from github_talent_mcp.tools import profile as profile_mod
from github_talent_mcp.tools.profile import enrich_profiles


@pytest.mark.asyncio
async def test_enrich_profiles_maps_all_usernames(monkeypatch):
    async def fake_profile(client, username):
        if username == "boom":
            return json.dumps({"error": "nope"})
        return json.dumps({"login": username, "activity_score": 1})

    monkeypatch.setattr(profile_mod, "get_developer_profile", fake_profile)

    out = await enrich_profiles(None, ["a", "b", "boom"], concurrency=2)

    assert set(out) == {"a", "b", "boom"}
    assert out["a"]["login"] == "a"
    assert out["b"]["login"] == "b"
    assert "error" in out["boom"]  # failures are returned, not dropped


@pytest.mark.asyncio
async def test_enrich_profiles_runs_concurrently(monkeypatch):
    """With concurrency >= N, all N fetches should be in flight at once."""
    import asyncio

    in_flight = 0
    peak = 0

    async def fake_profile(client, username):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return json.dumps({"login": username})

    monkeypatch.setattr(profile_mod, "get_developer_profile", fake_profile)

    await enrich_profiles(None, ["a", "b", "c", "d"], concurrency=4)
    assert peak >= 2  # genuinely overlapping, not sequential
