from __future__ import annotations

import re
from typing import Any

PERMISSIVE_LICENSES = frozenset({
    "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc", "unlicense",
})


def _compute_reputation_floor(followers: int, stars: int, account_age_days: int) -> int:
    """Compute a minimum score floor based on cumulative reputation.

    Prevents well-known developers from scoring low just because their
    recent GitHub activity doesn't match behavioral scoring expectations
    (e.g., Torvalds works via mailing lists, not GitHub PRs).
    """
    if followers >= 10_000 or stars >= 50_000:
        return 150
    if followers >= 1_000 or stars >= 5_000:
        return 120
    if followers >= 500 or stars >= 1_000:
        return 100
    if followers >= 100 or stars >= 200:
        return 80
    return 0


def compute_activity_score(profile: dict[str, Any]) -> tuple[int, dict[str, int]]:
    """Compute activity score with per-dimension breakdown.

    The score combines behavioral signals (recent commits, PRs, OSS contributions)
    with a reputation floor (followers, stars) so that well-known developers
    aren't penalized for workflows that don't produce GitHub events.

    Returns (total_score, breakdown_dict).
    """
    breakdown: dict[str, int] = {}

    commits_90d = profile.get("commits_last_90_days", 0)
    breakdown["commits_last_90_days"] = min(commits_90d * 3, 60)

    breakdown["has_profile_readme"] = 20 if profile.get("has_profile_readme") else 0

    stars = profile.get("total_stars_received", 0)
    breakdown["stars_on_own_repos"] = min(stars * 2, 40)

    followers = profile.get("followers", 0)
    breakdown["followers"] = min(followers, 20)

    desc_ratio = profile.get("repos_with_description_ratio", 0.0)
    breakdown["repos_with_description"] = int(desc_ratio * 20)

    breakdown["permissive_license_repos"] = 15 if profile.get("has_permissive_license_repos") else 0

    oss = profile.get("major_oss_contributions", [])
    breakdown["major_oss_contributions"] = min(len(oss) * 10, 30)

    behavioral_score = sum(breakdown.values())

    # Apply reputation floor — cumulative impact shouldn't be erased by a quiet quarter
    account_age_days = profile.get("account_age_days", 0)
    reputation_floor = _compute_reputation_floor(followers, stars, account_age_days)
    total = max(behavioral_score, reputation_floor)

    if reputation_floor > behavioral_score:
        breakdown["reputation_floor"] = reputation_floor

    return total, breakdown


def extract_keywords(job_description: str) -> list[str]:
    """Extract meaningful keywords from a job description."""
    noise = {
        "the", "a", "an", "and", "or", "is", "are", "was", "were", "be", "been",
        "with", "for", "to", "of", "in", "on", "at", "by", "from", "as", "we",
        "you", "our", "your", "this", "that", "will", "can", "should", "must",
        "have", "has", "had", "do", "does", "did", "not", "but", "if", "about",
        "experience", "team", "work", "working", "looking", "join", "role",
        "ability", "strong", "plus", "years", "knowledge", "skills", "required",
        "preferred", "etc", "including", "such", "also", "may", "would", "could",
    }
    words = re.findall(r"[a-zA-Z#+.]+", job_description.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        if len(w) >= 2 and w not in noise and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords


def compute_relevance_score(profile: dict[str, Any], job_keywords: list[str]) -> int:
    """Score 0-100 based on keyword overlap between profile and job description."""
    if not job_keywords:
        return 50

    searchable_parts = [
        profile.get("bio") or "",
        " ".join(profile.get("top_languages", [])),
        " ".join(profile.get("major_oss_contributions", [])),
        profile.get("profile_readme_summary") or "",
        profile.get("company") or "",
    ]
    for repo in profile.get("notable_repos", []):
        if isinstance(repo, dict):
            searchable_parts.append(repo.get("description") or "")
            searchable_parts.extend(repo.get("topics") or [])
            searchable_parts.append(repo.get("language") or "")

    searchable = " ".join(searchable_parts).lower()

    matches = sum(1 for kw in job_keywords if kw in searchable)
    return min(int((matches / len(job_keywords)) * 100), 100)


def generate_strengths_gaps(profile: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Generate human-readable strengths and gaps from profile data."""
    strengths: list[str] = []
    gaps: list[str] = []

    commits_90d = profile.get("commits_last_90_days", 0)
    prs_90d = profile.get("prs_opened_last_90_days", 0)
    if commits_90d > 20 or prs_90d > 10:
        parts = []
        if commits_90d > 0:
            parts.append(f"{commits_90d} commits")
        if prs_90d > 0:
            parts.append(f"{prs_90d} PRs opened")
        strengths.append(f"Active contributor: {', '.join(parts)} in last 90 days")
    elif commits_90d == 0 and prs_90d == 0:
        gaps.append("No recent public commit or PR activity")

    contributed_stars = profile.get("contributed_repo_stars", 0)
    if contributed_stars > 1000:
        strengths.append(f"Contributes to repos with {contributed_stars:,} combined stars")

    if profile.get("has_profile_readme"):
        strengths.append("Maintains a profile README")

    stars = profile.get("total_stars_received", 0)
    if stars > 50:
        strengths.append(f"Popular open source work: {stars} total stars received")
    elif stars == 0:
        gaps.append("No starred repositories")

    oss = profile.get("major_oss_contributions", [])
    if oss:
        strengths.append(f"Contributes to {len(oss)} external OSS project(s): {', '.join(oss[:3])}")

    if not profile.get("has_permissive_license_repos"):
        gaps.append("No repos with permissive open-source licenses")

    followers = profile.get("followers", 0)
    if followers >= 10_000:
        strengths.append(f"Exceptional community presence: {followers:,} followers")
    elif followers >= 1_000:
        strengths.append(f"Strong community presence: {followers:,} followers")
    elif followers > 100:
        strengths.append(f"Notable community presence: {followers:,} followers")

    if profile.get("hireable"):
        strengths.append("Marked as hireable on GitHub")

    langs = profile.get("top_languages", [])
    if langs:
        strengths.append(f"Primary languages: {', '.join(langs[:5])}")

    return strengths, gaps
