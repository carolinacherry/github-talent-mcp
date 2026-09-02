# Grok Build Plugin Marketplace Submission

This document contains the draft marketplace entry for submitting `github-talent-mcp` to the official [xai-org/plugin-marketplace](https://github.com/xai-org/plugin-marketplace) catalog.

## Status

**NOT YET SUBMITTED** — This is a draft entry ready to be added to `.grok-plugin/marketplace.json` in the xai-org/plugin-marketplace repository.

## Submission Steps

1. Fork [xai-org/plugin-marketplace](https://github.com/xai-org/plugin-marketplace)
2. Get the latest commit SHA from this repository:
   ```bash
   git rev-parse HEAD
   ```
3. Copy the plugin entry below and add it to `.grok-plugin/marketplace.json` in the `plugins` array
4. Replace `FULL_40_CHAR_COMMIT_SHA_HERE` with the actual 40-character SHA from step 2
5. Run the validation script:
   ```bash
   python3 scripts/validate-catalog.py
   ```
6. If validation passes, regenerate the plugin index:
   ```bash
   python3 scripts/generate-plugin-index.py
   ```
7. Commit both files:
   ```bash
   git add .grok-plugin/marketplace.json .grok-plugin/plugin-index.json
   git commit -m "Add github-talent-mcp plugin"
   ```
8. Open a pull request to xai-org/plugin-marketplace

## Draft Plugin Entry

Add this to the `plugins` array in `.grok-plugin/marketplace.json`:

```json
{
  "name": "github-talent-mcp",
  "description": "Search, score, and rank GitHub developers for technical recruiting. 9 tools: plan_search, search_developers, get_developer_profile, rank_candidates, score_against_jd, compare_candidates, bulk_score, generate_outreach, get_repo_contributors.",
  "category": "development",
  "source": {
    "source": "url",
    "url": "https://github.com/carolinacherry/github-talent-mcp.git",
    "sha": "FULL_40_CHAR_COMMIT_SHA_HERE"
  },
  "version": "0.5.0",
  "author": {
    "name": "Daniel An"
  },
  "homepage": "https://github.com/carolinacherry/github-talent-mcp",
  "keywords": [
    "talent-mcp",
    "github-talent",
    "github talent search",
    "recruiting",
    "developer sourcing",
    "technical hiring"
  ]
}
```

## Important Notes

### Source Repository Under Personal Account

The plugin source is currently hosted under a personal GitHub account (`carolinacherry`). xAI may prefer plugins to be hosted under organization accounts for better discoverability and trust signals. Consider:

1. Moving the repository to an organization account (e.g., `talent-mcp/github-talent-mcp`)
2. Or noting in the PR that this is a personal project maintained by Daniel An

### Prerequisites for Installation

Users installing this plugin will need:

1. **`uvx` on PATH** — The plugin uses `uvx github-talent-mcp` to run the MCP server. Users must have `uv` installed and `uvx` available in their PATH.
   
   Installation: `brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`

2. **GitHub Personal Access Token** — The plugin requires a GitHub PAT with `read:user` and `public_repo` scopes set as the `GITHUB_TOKEN` environment variable. Without this token, the API is rate-limited to 60 requests/hour (vs 5,000/hour with authentication), which will cause failures mid-search.

   Users should set this token when installing or enabling the plugin in Grok Build.

### Keywords and Discoverability

The keywords are **brand-scoped** to the talent-mcp/github-talent domain:
- `talent-mcp`, `github-talent`, `github talent search` — specific to this tool
- `recruiting`, `developer sourcing`, `technical hiring` — related use cases

We intentionally **avoided generic keywords** like `api`, `cli`, `database`, `search` that would cause false-positive suggestions.

## Testing Before Submission

Before submitting to the xAI marketplace, test the plugin locally:

```bash
# Install the plugin directly from GitHub
grok plugin install carolinacherry/github-talent-mcp --trust

# Verify it loaded
grok plugin list

# Test with a simple prompt
# "Get the developer profile for torvalds on GitHub"
```

If the plugin loads successfully and all 9 tools are available, it's ready for marketplace submission.
