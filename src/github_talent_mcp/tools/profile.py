from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from github_talent_mcp.github_client import GitHubClient, PERMISSIVE_LICENSES
from github_talent_mcp.models import DeveloperProfile, NotableRepo
from github_talent_mcp.scoring import compute_activity_score


async def get_developer_profile(client: GitHubClient, username: str) -> str:
    try:
        return await _build_profile(client, username)
    except Exception as e:
        return json.dumps({"error": f"Failed to build profile for {username}: {e}"})


async def _build_profile(client: GitHubClient, username: str) -> str:
    # 1. Base user data
    user = await client.get_user(username)
    now = datetime.now(timezone.utc)

    created_at = user.get("created_at", "")
    account_age_days = 0
    if created_at:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        account_age_days = (now - created).days

    # 2. Repos (owner's non-fork repos for analysis)
    all_repos = await client.get_user_repos(username)
    owned_repos = [r for r in all_repos if not r.get("fork")]

    # 3. Language breakdown from top 10 repos by stars
    sorted_by_stars = sorted(owned_repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
    lang_totals: dict[str, int] = {}
    for repo in sorted_by_stars[:10]:
        langs = await client.get_repo_languages(username, repo["name"])
        for lang, byte_count in langs.items():
            lang_totals[lang] = lang_totals.get(lang, 0) + byte_count

    total_bytes = sum(lang_totals.values()) or 1
    language_breakdown = {
        lang: round(bytes_ / total_bytes, 3)
        for lang, bytes_ in sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)
    }
    top_languages = list(language_breakdown.keys())[:10]

    # 4. Stars and forks
    total_stars = sum(r.get("stargazers_count", 0) for r in owned_repos)
    total_forks = sum(r.get("forks_count", 0) for r in owned_repos)

    # 5. Description ratio
    if owned_repos:
        with_desc = sum(1 for r in owned_repos if r.get("description"))
        desc_ratio = round(with_desc / len(owned_repos), 2)
    else:
        desc_ratio = 0.0

    # 6. License analysis
    license_counts: dict[str, int] = {}
    for repo in owned_repos:
        lic = repo.get("license")
        spdx = lic.get("spdx_id", "NOASSERTION") if lic else "none"
        license_counts[spdx] = license_counts.get(spdx, 0) + 1

    has_permissive = any(
        spdx.lower() in PERMISSIVE_LICENSES for spdx in license_counts
    )
    licensed_repos = sum(v for k, v in license_counts.items() if k not in ("none", "NOASSERTION"))
    license_ratio = round(licensed_repos / len(owned_repos), 2) if owned_repos else 0.0

    # 7. Events: commits, PRs, and OSS contributions
    events = await client.get_user_events(username)
    commits_30d = 0
    commits_90d = 0
    prs_opened_30d = 0
    prs_opened_90d = 0
    last_active: str | None = None
    oss_contributions: set[str] = set()

    for event in events:
        created_str = event.get("created_at", "")
        if not created_str:
            continue
        created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        age_days = (now - created).days

        if last_active is None:
            last_active = created_str

        if event["type"] == "PushEvent":
            num_commits = len(event.get("payload", {}).get("commits", []))
            if age_days <= 30:
                commits_30d += num_commits
            if age_days <= 90:
                commits_90d += num_commits

        # Count PR opens as activity (catches PR-based workflows that PushEvents miss)
        if event["type"] == "PullRequestEvent":
            action = event.get("payload", {}).get("action", "")
            if action == "opened":
                if age_days <= 30:
                    prs_opened_30d += 1
                if age_days <= 90:
                    prs_opened_90d += 1

        if event["type"] in ("PullRequestEvent", "PushEvent", "IssuesEvent", "IssueCommentEvent"):
            repo_name = event.get("repo", {}).get("name", "")
            if repo_name and not repo_name.lower().startswith(f"{username.lower()}/"):
                oss_contributions.add(repo_name)

    # 7b. Fall back to Search API if Events API missed commits/PRs
    if commits_90d == 0:
        since_90d = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        commits_90d = await client.search_commit_count(username, since_90d)
    if commits_30d == 0:
        since_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        commits_30d = await client.search_commit_count(username, since_30d)
    if prs_opened_90d == 0:
        since_90d = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        prs_opened_90d = await client.search_pr_count(username, since_90d)
    if prs_opened_30d == 0:
        since_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        prs_opened_30d = await client.search_pr_count(username, since_30d)

    # 7c. Fetch star counts for contributed repos (captures org repo impact)
    contributed_stars = 0
    for contrib_repo in sorted(oss_contributions)[:5]:  # cap at 5 to limit API calls
        parts = contrib_repo.split("/")
        if len(parts) == 2:
            try:
                repo_info = await client.get_repo_info(parts[0], parts[1])
                contributed_stars += repo_info.get("stargazers_count", 0)
            except Exception as e:
                logging.getLogger("github-talent-mcp").debug(
                    "Failed to fetch repo info for %s: %s", contrib_repo, e,
                )

    # 8. Profile README
    readme_content = await client.get_profile_readme(username)
    has_readme = readme_content is not None
    readme_length = len(readme_content) if readme_content else 0
    readme_summary = None
    if readme_content:
        # Take first ~500 chars as summary (the calling LLM can summarize further)
        readme_summary = readme_content[:500].strip()
        if len(readme_content) > 500:
            readme_summary += "..."

    # 9. Notable repos
    notable_repos = []
    for repo in sorted_by_stars[:5]:
        lic = repo.get("license")
        notable_repos.append(NotableRepo(
            name=repo["name"],
            description=repo.get("description"),
            stars=repo.get("stargazers_count", 0),
            forks=repo.get("forks_count", 0),
            language=repo.get("language"),
            license=lic.get("spdx_id") if lic else None,
            topics=repo.get("topics", []),
            last_updated=repo.get("pushed_at"),
        ))

    # 10. Linked profiles
    linked_profiles = {
        "twitter": user.get("twitter_username"),
        "personal_site": user.get("blog") or None,
    }

    # 11. Activity score
    # Combine push commits + PR opens for total activity signal
    # PRs weighted x3 (each PR represents more effort than a single commit)
    total_activity_90d = commits_90d + (prs_opened_90d * 3)
    # Combine personal repo stars + contributed repo stars
    combined_stars = total_stars + contributed_stars

    score_input = {
        "commits_last_90_days": total_activity_90d,
        "has_profile_readme": has_readme,
        "total_stars_received": combined_stars,
        "followers": user.get("followers", 0),
        "repos_with_description_ratio": desc_ratio,
        "has_permissive_license_repos": has_permissive,
        "major_oss_contributions": sorted(oss_contributions),
        "account_age_days": account_age_days,
    }
    activity_score, score_breakdown = compute_activity_score(score_input)

    # 12. Build the full profile
    profile = DeveloperProfile(
        login=user["login"],
        name=user.get("name"),
        bio=user.get("bio"),
        location=user.get("location"),
        email=user.get("email"),
        blog=user.get("blog"),
        company=user.get("company"),
        twitter_username=user.get("twitter_username"),
        hireable=user.get("hireable"),
        followers=user.get("followers", 0),
        following=user.get("following", 0),
        public_repos=user.get("public_repos", 0),
        account_age_days=account_age_days,
        avatar_url=user.get("avatar_url", ""),
        html_url=user.get("html_url", f"https://github.com/{username}"),
        has_profile_readme=has_readme,
        profile_readme_length=readme_length,
        profile_readme_summary=readme_summary,
        top_languages=top_languages,
        language_breakdown=language_breakdown,
        total_stars_received=total_stars,
        total_forks_received=total_forks,
        notable_repos=notable_repos,
        repos_with_description_ratio=desc_ratio,
        open_source_license_ratio=license_ratio,
        license_breakdown=license_counts,
        has_permissive_license_repos=has_permissive,
        commits_last_30_days=commits_30d,
        commits_last_90_days=commits_90d,
        prs_opened_last_30_days=prs_opened_30d,
        prs_opened_last_90_days=prs_opened_90d,
        contributed_repo_stars=contributed_stars,
        last_active=last_active,
        contributes_to_major_oss=bool(oss_contributions),
        major_oss_contributions=sorted(oss_contributions),
        linked_profiles=linked_profiles,
        activity_score=activity_score,
        activity_score_breakdown=score_breakdown,
    )

    return json.dumps(profile.model_dump(), indent=2)
