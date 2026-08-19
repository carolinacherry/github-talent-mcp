# github-talent-mcp

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-8A2BE2)](https://modelcontextprotocol.io)
[![Claude](https://img.shields.io/badge/Built_for-Claude_by_Anthropic-d4a373)](https://claude.ai)
[![GitHub Copilot](https://img.shields.io/badge/Works_with-GitHub_Copilot-8957E5?logo=githubcopilot&logoColor=white)](https://github.com/features/copilot)
[![GitHub API](https://img.shields.io/badge/GitHub-REST_API_v3-181717?logo=github)](https://docs.github.com/en/rest)

MCP server that searches, scores, and ranks GitHub developers for technical recruiting.

Works with **Claude** (Code & Desktop) and **GitHub Copilot** (CLI & desktop app) — any MCP client that speaks stdio.

## Demo

https://github.com/user-attachments/assets/b2dbe9e0-26ee-4849-861a-4b5cb268facc

Sourcing candidates for a real Anthropic JD, live in Claude Cowork.

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
| Commits (90d) | 0 |
| PRs (90d) | 0 |
| Notable Repos | linux (183K stars), libdc-for-dirk, subsurface-for-dirk, uemacs, pesern-resolve |
| Profile README | No |
| Hireable | No |

Torvalds has zero recent GitHub activity because kernel development flows through mailing lists, not GitHub PRs. The **reputation floor** (293K followers) overrides the behavioral score and sets it to 150.

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

### 1. Install `uv`

The server runs through `uvx`, which downloads and launches it for you — no clone, no
virtualenv, and you get updates automatically.

```bash
brew install uv
```

No Homebrew? `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2. Create a GitHub personal access token

Without a token GitHub allows **60 requests per hour**, and a single candidate profile
costs 6-15 of them. You will run out mid-search and profiles will come back empty. With a
token you get 5,000/hour.

Go to [github.com/settings/tokens](https://github.com/settings/tokens) and create a
**fine-grained** or **classic** token with these scopes:

| Scope | Why |
|---|---|
| `read:user` | Read user profiles and search users |
| `public_repo` | Read public repo data, languages, contributors |

Copy the token — you cannot view it again after leaving the page.

### 3. Connect it

**Put the token itself in the config, not `${GITHUB_TOKEN}`.** Desktop apps are launched by
the operating system, not by your shell, so they never read `.zshrc` and an environment
variable reference expands to nothing. The server then starts fine, runs unauthenticated,
and quietly fails a few candidates in. A `.env` file has the same problem unless the config
also sets `cwd` to the project directory, because it is read relative to the working
directory.

#### GitHub Copilot (CLI and desktop app)

Both share one config. Paste this in a terminal — it fills in your token for you:

```bash
mkdir -p ~/.copilot
TOKEN=$(gh auth token)   # or: TOKEN=github_pat_xxxxxxxx
cat > ~/.copilot/mcp-config.json <<EOF
{
  "mcpServers": {
    "github-talent": {
      "type": "local",
      "command": "uvx",
      "args": ["github-talent-mcp"],
      "env": { "GITHUB_TOKEN": "$TOKEN" },
      "tools": ["*"]
    }
  }
}
EOF
chmod 600 ~/.copilot/mcp-config.json
```

Quit Copilot completely and reopen it, then run `/mcp show` — you should see 9 tools under
`github-talent`. The app also accepts servers under Settings → MCP if you would rather not
touch a file.

If `uvx` is not found, give its full path as `command` (`which uvx` prints it).

#### Claude Code

```bash
claude mcp add github-talent --env GITHUB_TOKEN=github_pat_xxxxxxxx -- uvx github-talent-mcp
```

Restart Claude Code and verify with `/mcp`.

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github-talent": {
      "command": "uvx",
      "args": ["github-talent-mcp"],
      "env": {
        "GITHUB_TOKEN": "github_pat_xxxxxxxx"
      }
    }
  }
}
```

Restart Claude Desktop.

#### Checking it actually works

Run a search and look at the size of each `get_developer_profile` result. A real profile is
120-170 lines. **Three lines means the call failed** — almost always a missing or
unreadable token. Every tool returning three lines while the server still shows as
connected is the signature of running unauthenticated.

### Running from source

Only needed if you want to modify the server:

```bash
git clone https://github.com/carolinacherry/github-talent-mcp.git
cd github-talent-mcp
uv sync
```

Then use `uv run --directory /path/to/github-talent-mcp github-talent-mcp` as the command in
any config above.

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

**JD scoring:**
> Score these candidates against this job description: [paste JD]. Candidates: tiangolo, karpathy, hwchase17

**Compare candidates:**
> Compare tiangolo and hwchase17 for a Senior Python AI Engineer role

**Bulk scoring:**
> Score these 10 GitHub usernames and give me a ranked table: [paste list]

**Outreach:**
> Generate a casual recruiter message for tiangolo about a Senior Python role at Acme. My name is Daniel.

## Interview-first sourcing

Vague prompts produce vague shortlists, so the server is built to **interview you before it searches**. Ask it to "find candidates for a role" and it calls `plan_search` first — it detects the role family and asks targeted follow-ups (seniority, must-have skills, location, dealbreakers) and, most importantly, for the **job description**: paste the full text, or share a public link and paste what it shows. It only sources once it has real criteria.

> **Try it:** *"Find me senior security engineers."* → the assistant should ask for the JD and your must-haves before running anything.

Want a fast, repeatable run instead? Give it everything up front — *"Rank these 15 usernames against this JD: …"* — or pin the sourcing to specific repos, and it'll skip the interview.

## Tools

| Tool | Description |
|---|---|
| `plan_search` | Intake step — parses a sourcing request, detects the role family, and returns targeted follow-up questions (including: paste the JD or share a public link) to ask before searching. Call this first. |
| `search_developers` | Search GitHub users by language, location, activity, followers. For topic-based sourcing, use `get_repo_contributors` on relevant repos instead. |
| `get_developer_profile` | Deep profile enrichment: languages, stars, commits + PRs, OSS contributions, license breakdown, profile README, and activity score with breakdown. |
| `rank_candidates` | Rank usernames against a job description. Returns sorted candidates with combined score, strengths, gaps, and reasoning. |
| `score_against_jd` | Score candidates against a JD with per-dimension breakdown (tech stack, experience level, OSS signal, leadership). Returns gaps and personalized interview questions. |
| `compare_candidates` | Side-by-side comparison of 2-5 candidates. Shows dimension winners and a recommendation. Optionally scored against a JD. |
| `bulk_score` | Score up to 100 GitHub usernames in one call. Returns a ranked markdown table or CSV. Supports optional JD matching. |
| `generate_outreach` | Generate personalized recruiter messages (short/medium/detailed) that reference the candidate's actual repos and contributions. Requires your company name and sender name. Casual or formal tone. |
| `get_repo_contributors` | Top contributors for any repo. Accepts `owner/repo` or full URL. The fastest way to source for a specific domain. |

## Scoring

The activity score combines two layers: **behavioral signals** (what you did recently) and a **reputation floor** (what you've built over time).

### Behavioral Score (0-205)

| Signal | Max Points | How |
|---|---|---|
| Commits + PRs (last 90 days) | 60 | Push commits + PR opens (PRs weighted x3). Captures both push-based and PR-based workflows. |
| Stars on repos | 40 | Personal repo stars + stars on repos you contribute to. Org repo maintainers get credit. |
| Profile README | 20 | Presence of a profile README (github.com/username/username). |
| Followers | 20 | Capped at 20. |
| Repos with descriptions | 20 | Ratio of repos that have descriptions. Signal of care and polish. |
| Permissive license repos | 15 | Has at least one repo with MIT, Apache-2.0, BSD, ISC, or Unlicense. |
| Major OSS contributions | 30 | PRs, pushes, or issues on repos you don't own. Capped at 3 repos (10 pts each). |

### Reputation Floor

The behavioral score alone penalizes developers whose work doesn't produce GitHub events — Torvalds works through mailing lists, senior maintainers merge via org bots, and many engineers work in private repos.

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

## Rate Limits

GitHub REST API: 5,000 requests/hour with token. A typical workflow (search + enrich 5 candidates + rank) uses ~60-100 API calls. Profile results are cached within a session to avoid redundant calls during ranking.

## Limitations & responsible use

This tool scores **public GitHub activity** as *one* signal for technical sourcing. Know its limits before you rely on it:

- **Results vary between runs.** It's AI-driven — the assistant decides which repos and searches to explore, so the same prompt can surface a different shortlist each time. The scoring itself is deterministic for a given set of candidates; the variation comes from sourcing. For repeatable runs, constrain the sourcing: name the repos to pull contributors from, or hand it an explicit list of usernames to rank.
- **GitHub is not the whole engineer.** Public activity is strong evidence of *technical* work but blind to private-repo and internal/enterprise contributions, and to non-GitHub ecosystems (mailing lists, GitLab, etc.). It **cannot** verify people-management or leadership history — confirm those off-GitHub. (The reputation floor exists precisely because low recent activity ≠ low capability.)
- **Use it as a lead generator, not a filter.** Public OSS visibility correlates with free time, tenure, and circumstance — not just skill — and that skews across demographics. Treat scores as a starting point for outreach and human judgment. Don't use them to automatically exclude candidates, and always pair them with equitable, role-relevant evaluation.
- **Data is live and rate-limited.** Scores reflect GitHub at query time and shift as activity changes; an unauthenticated server is capped at 60 requests/hour.

## License

[Apache License 2.0](LICENSE) © 2026 Daniel An. Released versions up to and including 0.4.0 remain under the MIT License; 0.4.1 onward is Apache-2.0.
