# github-talent-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-8A2BE2)](https://modelcontextprotocol.io)
[![Claude](https://img.shields.io/badge/Built_for-Claude_by_Anthropic-d4a373)](https://claude.ai)
[![GitHub API](https://img.shields.io/badge/GitHub-REST_API_v3-181717?logo=github)](https://docs.github.com/en/rest)
[![PyPI](https://img.shields.io/pypi/v/github-talent-mcp)](https://pypi.org/project/github-talent-mcp/)

MCP server that searches, scores, and ranks GitHub developers for technical recruiting.

## Demo

https://github.com/user-attachments/assets/2dfd82b4-3eb5-4f2b-bc0a-2580b95043e4

### Profile deep dive

> Get the full developer profile and activity score for torvalds on GitHub

Claude calls `get_developer_profile("torvalds")` and returns:

| Field | Value |
|---|---|
| **Activity Score** | **150** (reputation floor applied) |
| Location | Portland, OR |
| Followers | 293,321 |
| Stars Received | 235,068 |
| Primary Language | C (98.1%) |
| Commits (90d) | 742 |
| PRs (90d) | 0 |
| Notable Repos | linux (225K stars), AudioNoise, uemacs, GuitarPedal, test-tlb |
| Profile README | No |
| Hireable | No |

Torvalds has 0 PRs because kernel development flows through mailing lists, not GitHub PRs. The **reputation floor** (293K followers) overrides the behavioral score and sets it to 150.

### Repo contributor ranking

> Get the top contributors to huggingface/transformers and rank them for a founding ML engineer role at an AI startup

Claude calls `get_repo_contributors("huggingface/transformers")` → `rank_candidates` on the top 24 contributors:

| Rank | Developer | Combined Score | Activity | Relevance | Strengths |
|---|---|---|---|---|---|
| 1 | stas00 | 83.4 | 150 | 72 | 4,553 stars, contributes to major OSS, MIT-licensed repos |
| 2 | cyyever | 80.8 | 120 | 64 | 1,217 followers, active contributor, profile README |
| 3 | Cyrilvallez | 77.2 | 120 | 56 | Active: 13 commits + 57 PRs in 90 days, strong OSS presence |
| 4 | ArthurZucker | 74.4 | 120 | 48 | 37 PRs in 90 days, contributes to huggingface/transformers |
| 5 | ydshieh | 72.0 | 120 | 40 | Active: 9 commits + 40 PRs in 90 days |

Combined score = activity × 0.4 + relevance × 0.6. Relevance is keyword overlap with the job description (ML, AI, startup, engineer, etc.).

## Installation

### 1. Install

```bash
pip install github-talent-mcp
```

Or install from source:

```bash
git clone https://github.com/carolinacherry/github-talent-mcp.git
cd github-talent-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Create a GitHub personal access token

Go to [github.com/settings/tokens](https://github.com/settings/tokens) and create a **fine-grained** or **classic** token with these scopes:

| Scope | Why |
|---|---|
| `read:user` | Read user profiles and search users |
| `public_repo` | Read public repo data, languages, contributors |

Create a `.env` file in the project root:

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

### 3. Connect to Claude

#### Claude Code (CLI)

One command:

```bash
claude mcp add github-talent -- /path/to/github-talent-mcp/.venv/bin/python3 -m github_talent_mcp
```

Then set the token as an environment variable. Either:
- Export it in your shell: `export GITHUB_TOKEN=ghp_xxxxxxxxxxxx`
- Or keep it in the `.env` file — the server reads it via `python-dotenv` on startup

Restart Claude Code to pick up the new server. Verify with `/mcp` — you should see 4 tools under `github-talent`.

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github-talent": {
      "command": "/path/to/github-talent-mcp/.venv/bin/python3",
      "args": ["-m", "github_talent_mcp"],
      "cwd": "/path/to/github-talent-mcp",
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxxxxxxxxx"
      }
    }
  }
}
```

Restart Claude Desktop. The tools will appear in the toolbox icon.

## Try It

Once installed, paste these prompts to verify everything works:

**Basic search:**
> Find Python developers in Raleigh active in the last 60 days

**Profile deep dive:**
> Get the full developer profile and activity score for torvalds on GitHub

**Full workflow:**
> Find 10 ML engineers in San Francisco active in the last 30 days, then rank them for a senior LLM inference engineer role

**Repo contributors:**
> Get the top contributors to huggingface/transformers and rank them for a founding ML engineer role at an AI startup

## Tools

| Tool | Description |
|---|---|
| `search_developers` | Search GitHub users by language, location, activity, followers. For topic-based sourcing, use `get_repo_contributors` on relevant repos instead. |
| `get_developer_profile` | Deep profile enrichment: languages, stars, commits + PRs, OSS contributions, license breakdown, profile README, and activity score with breakdown. |
| `rank_candidates` | Rank usernames against a job description. Returns sorted candidates with combined score, strengths, gaps, and reasoning. |
| `get_repo_contributors` | Top contributors for any repo. Accepts `owner/repo` or full URL. The fastest way to source for a specific domain. |

## Scoring

The activity score combines two layers: **behavioral signals** (what you did recently) and a **reputation floor** (what you've built over time).

### Behavioral Score (0-205)

| Signal | Max Points | How |
|---|---|---|
| Commits + PRs (last 90 days) | 60 | Push commits + PR opens (PRs weighted x3). Uses the Events API first; falls back to the Search API when events return zero (see [note](#commit-counting)). |
| Stars on repos | 40 | Personal repo stars + stars on repos you contribute to. Org repo maintainers get credit. |
| Profile README | 20 | Presence of a profile README (github.com/username/username). |
| Followers | 20 | Capped at 20. |
| Repos with descriptions | 20 | Ratio of repos that have descriptions. Signal of care and polish. |
| Permissive license repos | 15 | Has at least one repo with MIT, Apache-2.0, BSD, ISC, or Unlicense. |
| Major OSS contributions | 30 | PRs, pushes, or issues on repos you don't own. Capped at 3 repos (10 pts each). |

### Reputation Floor

The behavioral score alone penalizes developers whose public work is limited — senior maintainers who merge via org bots, engineers who work primarily in private repos, or developers active on non-GitHub platforms.

The reputation floor ensures cumulative impact isn't erased by a quiet quarter:

| Threshold | Floor |
|---|---|
| 10K+ followers **or** 50K+ stars | 150 |
| 1K+ followers **or** 5K+ stars | 120 |
| 500+ followers **or** 1K+ stars | 100 |
| 100+ followers **or** 200+ stars | 80 |

The final score is `max(behavioral_score, reputation_floor)`. If the floor is applied, the breakdown includes a `reputation_floor` field so you know.

### Score Tiers

- **150+** — exceptional (top OSS maintainers, well-known engineers)
- **120-149** — strong signal, worth reaching out
- **80-119** — solid developer with meaningful public work
- **40-79** — active but limited public signal
- **<40** — low signal (likely private work or junior)

### Ranking

`rank_candidates` combines the activity score with a **relevance score** (0-100) based on keyword overlap between the job description and the candidate's profile (bio, languages, repo topics, README). The combined score weights relevance at 60% and activity at 40% — a high-activity developer with no overlap to the job shouldn't outrank a relevant one.

### Commit Counting

Commit and PR counts use a two-pass approach:

1. **Events API** (`/users/{username}/events/public`) — fast, returns up to 300 recent events. Works for most active developers.
2. **Search API fallback** — when the Events API returns zero commits or PRs, we query `/search/commits` and `/search/issues` scoped to the user's own repos (`user:{username}`). This catches activity that doesn't produce `PushEvent` entries, like Torvalds' kernel merges.

The `user:` qualifier is required to avoid counting the same commit across thousands of forks. Without it, Torvalds returns ~2M (every fork of linux); with it, 742.

## Rate Limits

GitHub REST API: 5,000 requests/hour with token. A typical workflow (search + enrich 5 candidates + rank) uses ~60-100 API calls. Profile results are cached within a session to avoid redundant calls during ranking.

## Security

For reproducible installs with pinned versions, use the lockfile:

```bash
pip install -r requirements-lock.txt
pip install github-talent-mcp
```

This pins every transitive dependency to the exact version tested against. If you're security-conscious about supply chain attacks, verify package hashes with [`pip-audit`](https://github.com/pypa/pip-audit) or install with `--require-hashes`.

## License

MIT
