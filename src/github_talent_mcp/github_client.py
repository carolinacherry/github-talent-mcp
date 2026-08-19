from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
# When GitHub sends Retry-After it is telling us exactly when the throttle lifts,
# so honour it — waiting less than it asks guarantees the retry fails too. Capped
# so a single tool call can't stall past an MCP client's request timeout; a longer
# wait than this fails fast with a clear error instead of burning an attempt early.
MAX_BACKOFF_SECONDS = 30.0
# Total time one call may spend sleeping across all its retries.
MAX_TOTAL_BACKOFF_SECONDS = 35.0
PERMISSIVE_LICENSES = frozenset({
    "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc", "unlicense",
})

log = logging.getLogger("github-talent-mcp")


class GitHubClient:
    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API,
            headers=headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # -- Cache helpers --

    def _cache_get(self, key: str) -> Any | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.monotonic() - ts < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _cache_set(self, key: str, data: Any) -> None:
        self._cache[key] = (time.monotonic(), data)

    def _check_rate_limit(self, resp: httpx.Response) -> None:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 100:
            reset = resp.headers.get("X-RateLimit-Reset", "unknown")
            log.warning(f"Rate limit low: {remaining} remaining, resets at {reset}")

    # -- Request wrapper with rate-limit backoff --

    async def _get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        max_retries: int = 2,
    ) -> httpx.Response:
        """GET with backoff on GitHub rate limits (primary + secondary) and 5xx.

        Respects Retry-After and X-RateLimit-Reset so a broad sourcing run paces
        itself instead of erroring out mid-job. Waits are capped, and a throttle
        longer than the cap fails fast rather than retrying too early.
        """
        resp = await self._client.get(url, params=params, headers=headers)
        slept = 0.0
        for attempt in range(max_retries):
            if not self._should_retry(resp):
                return resp
            delay = self._retry_after_seconds(resp, attempt)
            if slept + delay > MAX_TOTAL_BACKOFF_SECONDS:
                log.warning(
                    f"GitHub {resp.status_code} on {url} — throttle needs {delay:.0f}s "
                    f"more than this call can wait; giving up"
                )
                return resp
            log.warning(
                f"GitHub {resp.status_code} on {url} — backing off {delay:.0f}s "
                f"(retry {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(delay)
            slept += delay
            resp = await self._client.get(url, params=params, headers=headers)
        return resp

    @staticmethod
    def _should_retry(resp: httpx.Response) -> bool:
        if resp.status_code >= 500:
            return True
        if resp.status_code in (403, 429):
            # Secondary limit sends Retry-After; primary limit zeroes Remaining.
            retry_after = resp.headers.get("Retry-After", "")
            if retry_after.isdigit():
                # Retrying before the window lifts just burns the attempt.
                return float(retry_after) <= MAX_BACKOFF_SECONDS
            if retry_after:
                return True
            if resp.headers.get("X-RateLimit-Remaining") == "0":
                return True
        return False

    @staticmethod
    def _retry_after_seconds(resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return min(float(retry_after), MAX_BACKOFF_SECONDS)
        if resp.headers.get("X-RateLimit-Remaining") == "0":
            reset = resp.headers.get("X-RateLimit-Reset", "")
            if reset.isdigit():
                wait = float(reset) - time.time() + 1.0
                return min(max(wait, 0.0), MAX_BACKOFF_SECONDS)
        return min(2.0 ** attempt, MAX_BACKOFF_SECONDS)

    # -- API methods --

    async def search_users(
        self,
        *,
        languages: list[str] | None = None,
        location: str | None = None,
        min_followers: int | None = None,
        min_repos: int | None = None,
        per_page: int = 30,
        page: int = 1,
    ) -> dict:
        parts: list[str] = ["type:user"]
        if languages:
            for lang in languages:
                parts.append(f"language:{lang}")
        if location:
            parts.append(f'location:"{location}"')
        if min_followers is not None:
            parts.append(f"followers:>={min_followers}")
        if min_repos is not None:
            parts.append(f"repos:>={min_repos}")
        # Note: pushed:> is NOT a valid qualifier for /search/users — it silently
        # returns 0 results. Use created:> for account age filtering instead.
        # Recent activity should be verified via get_developer_profile.

        q = " ".join(parts)
        resp = await self._get(
            "/search/users",
            params={"q": q, "per_page": per_page, "page": page, "sort": "followers", "order": "desc"},
        )
        self._check_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()

    async def get_repo_info(self, owner: str, repo: str) -> dict:
        cache_key = f"repo:{owner}/{repo}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        resp = await self._get(f"/repos/{owner}/{repo}")
        self._check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        self._cache_set(cache_key, data)
        return data

    async def get_user(self, username: str) -> dict:
        cache_key = f"user:{username}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        resp = await self._get(f"/users/{username}")
        self._check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        self._cache_set(cache_key, data)
        return data

    async def get_user_repos(self, username: str, per_page: int = 100) -> list[dict]:
        cache_key = f"repos:{username}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        resp = await self._get(
            f"/users/{username}/repos",
            params={"per_page": per_page, "sort": "pushed", "direction": "desc", "type": "owner"},
        )
        self._check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        self._cache_set(cache_key, data)
        return data

    async def get_repo_languages(self, owner: str, repo: str) -> dict[str, int]:
        cache_key = f"langs:{owner}/{repo}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        resp = await self._get(f"/repos/{owner}/{repo}/languages")
        self._check_rate_limit(resp)
        resp.raise_for_status()
        data = resp.json()
        self._cache_set(cache_key, data)
        return data

    async def get_user_events(self, username: str, max_pages: int = 3) -> list[dict]:
        cache_key = f"events:{username}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        all_events: list[dict] = []
        for page in range(1, max_pages + 1):
            resp = await self._get(
                f"/users/{username}/events/public",
                params={"per_page": 100, "page": page},
            )
            self._check_rate_limit(resp)
            resp.raise_for_status()
            events = resp.json()
            if not events:
                break
            all_events.extend(events)
        self._cache_set(cache_key, all_events)
        return all_events

    async def search_commit_count(self, username: str, since_date: str) -> int:
        """Count commits by username since a date using the Search API.

        More accurate than Events API for users whose commits don't
        surface as PushEvents (e.g. Torvalds' kernel merges).
        """
        cache_key = f"commit_count:{username}:{since_date}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        resp = await self._get(
            "/search/commits",
            params={
                "q": f"author:{username} user:{username} committer-date:>={since_date}",
                "per_page": 1,
            },
        )
        self._check_rate_limit(resp)
        resp.raise_for_status()
        count = resp.json().get("total_count", 0)
        self._cache_set(cache_key, count)
        return count

    async def search_pr_count(self, username: str, since_date: str) -> int:
        """Count PRs opened by username since a date using the Search API."""
        cache_key = f"pr_count:{username}:{since_date}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        resp = await self._get(
            "/search/issues",
            params={
                "q": f"author:{username} type:pr created:>={since_date}",
                "per_page": 1,
            },
        )
        self._check_rate_limit(resp)
        resp.raise_for_status()
        count = resp.json().get("total_count", 0)
        self._cache_set(cache_key, count)
        return count

    async def get_profile_readme(self, username: str) -> str | None:
        cache_key = f"readme:{username}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            resp = await self._get(
                f"/repos/{username}/{username}/readme",
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            if resp.status_code == 200:
                content = resp.text[:3000]
                self._cache_set(cache_key, content)
                return content
        except httpx.HTTPError:
            pass
        self._cache_set(cache_key, None)
        return None

    async def get_repo_contributors(
        self, owner: str, repo: str, per_page: int = 30,
    ) -> list[dict]:
        resp = await self._get(
            f"/repos/{owner}/{repo}/contributors",
            params={"per_page": per_page},
        )
        self._check_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()
