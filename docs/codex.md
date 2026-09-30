# Codex

The plugin uses the existing stdio server. Its Codex-specific launch configuration is
inline in `.codex-plugin/plugin.json`, so the token syntax in the existing Claude and
Cursor configuration files does not need to change. The plugin pins
`github-talent-mcp==0.5.0`; update the pin and test the new release together.

## Install the local plugin

1. Install `uv` and make sure `uvx` is on the PATH of the process running Codex.
2. Supply `GITHUB_TOKEN` through your local environment or secret manager before
   starting Codex. The manifest's `env_vars` forwards the variable without storing its
   value. It also forwards the optional `GITHUB_TALENT_DASHBOARD_PROMPT` setting.
3. Clone this repository and use the built-in `$plugin-creator` skill in Codex to
   register the existing plugin in your personal marketplace. For example:

   > Use $plugin-creator to install my existing github-talent-mcp checkout as a local
   > personal plugin. Preserve its .codex-plugin/plugin.json, .mcp.json, and assets.
   > Copy the plugin to ~/plugins/github-talent-mcp and register it in my personal
   > marketplace. Do not put credentials in the plugin.

4. Once the personal marketplace entry exists, install it with:

   ```bash
   codex plugin add github-talent-mcp@personal
   codex plugin list --marketplace personal --json
   ```

   If your personal marketplace has a different name, use the name returned by
   plugin-creator instead of `personal`.
5. Start a new chat so Codex loads the installed tools. Approve the intended tool
   calls when prompted.

The personal marketplace is for local testing; this does not publish the plugin or
claim a listing in the public plugin directory.

## Direct MCP configuration

For a direct connection without the plugin, add this to `~/.codex/config.toml`:

```toml
[mcp_servers.github-talent]
command = "uvx"
args = ["github-talent-mcp==0.5.0"]
env_vars = ["GITHUB_TOKEN", "GITHUB_TALENT_DASHBOARD_PROMPT"]
startup_timeout_sec = 60
tool_timeout_sec = 180
```

Choose either the plugin or the direct configuration to avoid duplicate tools.
Neither configuration provides a GitHub sign-in screen. The GitHub token must already
be available to the Codex process. A GUI app opened from the Dock may have a different
environment from your terminal; exporting a variable in another terminal does not
change an already-running app's environment. A fresh chat reloads tools, but does not
change the parent process's environment.

If `uvx` cannot be found, use its absolute path from `command -v uvx` in your local
configuration. Keep machine-specific paths and tokens out of the public manifest.

## Live acceptance test

Use a real, currently open technical job posting. Record its URL and the test date,
then supply the role requirements, location, experience requirement, and any sourcing
choices explicitly. Do not invent missing hiring criteria.

1. Verify Codex discovers all nine `github-talent` tools from the installed plugin.
2. Call `plan_search` with the sourcing request and job description.
3. Call `search_developers` with a small limit and `get_repo_contributors` on a
   relevant repository. Confirm both return usernames rather than an error object.
4. Enrich one returned account with `get_developer_profile`.
5. Evaluate the same bounded pool with `rank_candidates` and `score_against_jd`.
   Check both the MCP call status and the returned JSON for errors, including
   per-candidate errors.
6. Compare reported scores and profile links with the actual MCP responses. Keep the
   local transcript as evidence. A shell call, Python import, or a generated shortlist
   does not prove that Codex used MCP.

An unattended `codex exec` run can refuse tool calls if its approval policy is
`never`. Use an interactive session to approve calls, or `--approve-for-me` for
automatic approval review where supported. An approval refusal is not a successful
server test.

### Verified run: 2026-09-29

The local Codex plugin was tested through native Codex CLI MCP calls using the live
[OpenAI Software Engineer, Model Inference posting](https://openai.com/careers/software-engineer-model-inference-san-francisco/).
The test supplied a paraphrase of the posting's role requirements and explicit test
criteria, searched Python accounts in San Francisco, and fetched contributors to
`vllm-project/vllm`.

- Codex's app-server inventory attributed all nine tools to `github-talent-mcp@personal`.
- All six calls in the workflow above completed successfully.
- Both sourcing routes returned five accounts. Five distinct returned accounts were
  evaluated by both scoring tools, without per-candidate errors.
- No outreach or applications were sent. Candidate data and credentials are not
  included in this repository.

This verifies the installed plugin through Codex CLI. The user also reported a
successful desktop test on the same date: intake requested role criteria, the
OpenAI job-description search returned five prospects with evidence and gaps,
and an interactive dashboard was created. This desktop observation is separate
from the audited CLI MCP transcript. A hosted integration has not been tested.

### Scoring and intake limitations observed

The current intake parser can request seniority and location again when a JD provides
an experience requirement and a city instead of one of its recognized keywords.
The structured scorer may report the required level as `unknown` for a “5+ years”
requirement. Inspect the supplied criteria instead of inventing an answer.

The two scoring tools use different heuristics and can rank the same pool differently.
Their scores are research signals, not probabilities of job fit. Public GitHub data
does not establish work authorization, years of professional experience, relocation
willingness, or current interest in the role.

## References

- [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)
- [OpenAI plugin MCP environment variables](https://developers.openai.com/api/docs/guides/agents-api/tools/plugins)
