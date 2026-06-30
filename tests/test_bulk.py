import json
from unittest.mock import AsyncMock, patch

import pytest

from github_talent_mcp.tools.bulk import bulk_score


def _mock_profile(username, **overrides):
    base = {
        "login": username,
        "name": username.title(),
        "html_url": f"https://github.com/{username}",
        "top_languages": ["Python", "TypeScript"],
        "followers": 100,
        "total_stars_received": 50,
        "activity_score": 80,
        "commits_last_90_days": 20,
        "prs_opened_last_90_days": 5,
        "notable_repos": [{"name": "my-repo", "description": "A project", "language": "Python", "topics": [], "stars": 10}],
        "major_oss_contributions": [],
        "has_profile_readme": True,
        "repos_with_description_ratio": 0.7,
        "has_permissive_license_repos": True,
        "account_age_days": 2000,
        "bio": "Developer",
        "profile_readme_summary": "",
        "contributed_repo_stars": 0,
        "hireable": False,
    }
    base.update(overrides)
    return json.dumps(base)


@pytest.mark.asyncio
async def test_bulk_markdown():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.profile.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.side_effect = [
            _mock_profile("alice", activity_score=150, total_stars_received=500),
            _mock_profile("bob", activity_score=60, total_stars_received=10),
            _mock_profile("carol", activity_score=100, total_stars_received=200),
        ]
        result = await bulk_score(client, usernames=["alice", "bob", "carol"])

    data = json.loads(result)
    assert data["total_scored"] == 3
    assert data["format"] == "markdown"
    assert "| # |" in data["table"]
    # alice should rank first (highest activity)
    assert "| 1 | [alice]" in data["table"]


@pytest.mark.asyncio
async def test_bulk_csv():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.profile.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.side_effect = [
            _mock_profile("alice", activity_score=100),
            _mock_profile("bob", activity_score=50),
        ]
        result = await bulk_score(client, usernames=["alice", "bob"], export_format="csv")

    data = json.loads(result)
    assert data["format"] == "csv"
    assert "rank,username" in data["table"]
    assert "alice" in data["table"]


@pytest.mark.asyncio
async def test_bulk_with_jd():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.profile.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.side_effect = [
            _mock_profile("alice", top_languages=["Python", "Rust"], activity_score=120,
                          followers=500, total_stars_received=300, account_age_days=3000),
            _mock_profile("bob", top_languages=["Java"], activity_score=40),
        ]
        result = await bulk_score(
            client, usernames=["alice", "bob"], job_description="Senior Python Rust engineer"
        )

    data = json.loads(result)
    assert "JD Fit" in data["table"]
    # alice should rank higher with Python+Rust match
    assert data["table"].index("alice") < data["table"].index("bob")


@pytest.mark.asyncio
async def test_bulk_handles_errors():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.profile.get_developer_profile", new_callable=AsyncMock) as mock:
        mock.side_effect = [
            json.dumps({"error": "Not found"}),
            _mock_profile("bob"),
        ]
        result = await bulk_score(client, usernames=["ghost", "bob"])

    data = json.loads(result)
    assert data["total_scored"] == 1
    assert data["total_errors"] == 1
    assert data["errors"][0]["username"] == "ghost"


@pytest.mark.asyncio
async def test_bulk_rejects_over_100():
    client = AsyncMock()
    result = await bulk_score(client, usernames=[f"u{i}" for i in range(101)])
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_bulk_rejects_empty():
    client = AsyncMock()
    result = await bulk_score(client, usernames=[])
    data = json.loads(result)
    assert "error" in data
