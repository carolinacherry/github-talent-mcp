import json
from unittest.mock import AsyncMock, patch

import pytest

from github_talent_mcp.tools.outreach import generate_outreach


def _mock_profile(username, **overrides):
    base = {
        "login": username,
        "name": "Alice Chen",
        "html_url": f"https://github.com/{username}",
        "top_languages": ["Python", "Rust"],
        "followers": 500,
        "total_stars_received": 200,
        "activity_score": 120,
        "notable_repos": [
            {"name": "fast-inference", "description": "GPU inference engine", "language": "Rust", "topics": ["ml", "cuda"], "stars": 350},
        ],
        "major_oss_contributions": ["vllm-project/vllm"],
        "has_profile_readme": True,
        "bio": "ML infrastructure engineer",
    }
    base.update(overrides)
    return json.dumps(base)


@pytest.mark.asyncio
async def test_casual_outreach():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.outreach.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.return_value = _mock_profile("alicechen")
        result = await generate_outreach(
            client, username="alicechen", job_description="Senior ML Engineer at Acme",
            company_name="Acme", sender_name="Daniel", tone="casual",
        )

    data = json.loads(result)
    assert data["tone"] == "casual"
    assert "short" in data["messages"]
    assert "medium" in data["messages"]
    assert "detailed" in data["messages"]
    assert "Alice" in data["messages"]["short"]
    assert "fast-inference" in data["candidate"]["hook_used"]
    assert "Acme" in data["messages"]["short"]


@pytest.mark.asyncio
async def test_formal_outreach():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.outreach.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.return_value = _mock_profile("alicechen")
        result = await generate_outreach(
            client, username="alicechen", job_description="Senior ML Engineer",
            company_name="Acme", sender_name="Daniel", tone="formal",
        )

    data = json.loads(result)
    assert data["tone"] == "formal"
    assert "Dear Alice Chen" in data["messages"]["short"]


@pytest.mark.asyncio
async def test_outreach_references_oss():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.outreach.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.return_value = _mock_profile("alicechen")
        result = await generate_outreach(
            client, username="alicechen", job_description="ML infra role",
            company_name="Acme", sender_name="Daniel",
        )

    data = json.loads(result)
    assert "vllm" in data["messages"]["detailed"].lower()


@pytest.mark.asyncio
async def test_outreach_invalid_tone():
    client = AsyncMock()
    result = await generate_outreach(
        client, username="x", job_description="x",
        company_name="x", sender_name="x", tone="aggressive",
    )
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_outreach_profile_error():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.outreach.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.return_value = json.dumps({"error": "Not found"})
        result = await generate_outreach(
            client, username="ghost", job_description="x",
            company_name="x", sender_name="x",
        )

    data = json.loads(result)
    assert "error" in data
