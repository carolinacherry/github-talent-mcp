import json
from unittest.mock import AsyncMock

import pytest

from github_talent_mcp.github_client import GitHubClient
from github_talent_mcp.tools.search import search_developers
from github_talent_mcp.tools.contributors import get_repo_contributors, parse_repo_string


@pytest.fixture
def mock_client():
    client = GitHubClient.__new__(GitHubClient)
    client.search_users = AsyncMock(return_value={
        "total_count": 2,
        "items": [
            {"login": "alice", "avatar_url": "https://a.com/alice.png", "html_url": "https://github.com/alice"},
            {"login": "bob", "avatar_url": "https://a.com/bob.png", "html_url": "https://github.com/bob"},
        ],
    })
    client.get_repo_contributors = AsyncMock(return_value=[
        {"login": "carol", "contributions": 500, "avatar_url": "https://a.com/carol.png", "type": "User"},
        {"login": "dependabot[bot]", "contributions": 200, "avatar_url": "", "type": "Bot"},
        {"login": "dave", "contributions": 100, "avatar_url": "https://a.com/dave.png", "type": "User"},
    ])
    return client


@pytest.mark.asyncio
async def test_search_returns_developers(mock_client):
    result = await search_developers(mock_client, languages=["python"], location="San Francisco")
    data = json.loads(result)
    assert data["total_count"] == 2
    assert len(data["developers"]) == 2
    assert data["developers"][0]["login"] == "alice"


@pytest.mark.asyncio
async def test_search_respects_limit(mock_client):
    result = await search_developers(mock_client, limit=1)
    data = json.loads(result)
    assert data["returned"] == 1


@pytest.mark.asyncio
async def test_contributors_filters_bots(mock_client):
    result = await get_repo_contributors(mock_client, repo="owner/repo")
    data = json.loads(result)
    assert data["total_returned"] == 2
    logins = [c["login"] for c in data["contributors"]]
    assert "carol" in logins
    assert "dave" in logins
    assert "dependabot[bot]" not in logins


def test_parse_repo_string_formats():
    assert parse_repo_string("owner/repo") == ("owner", "repo")
    assert parse_repo_string("https://github.com/owner/repo") == ("owner", "repo")
    assert parse_repo_string("github.com/owner/repo") == ("owner", "repo")
    assert parse_repo_string("https://github.com/owner/repo/") == ("owner", "repo")


def test_parse_repo_string_invalid():
    with pytest.raises(ValueError):
        parse_repo_string("just-a-name")
    with pytest.raises(ValueError):
        parse_repo_string("")
