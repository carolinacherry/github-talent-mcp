"""Interactive candidate dashboard: result cache, offer block, and HTML renderer.

The scoring tools stash their payload here so the dashboard can be rebuilt from
the exact data the server computed, rather than from a re-transmitted (and
possibly paraphrased) copy sent back through the model.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, OrderedDict
from pathlib import Path
from urllib.parse import urlparse

PROMPT_ENV = "GITHUB_TALENT_DASHBOARD_PROMPT"
DIR_ENV = "GITHUB_TALENT_DASHBOARD_DIR"

_MAX_CACHED = 20
_cache: OrderedDict[str, dict] = OrderedDict()
_counter = 0

ASK_USER = (
    "Would you like me to open an interactive candidate dashboard — with search, "
    "skill filters, rankings, evidence, and GitHub profile links?"
)

INSTRUCTION = (
    "REQUIRED: end your next reply to the user with the exact text in ask_user, on its "
    "own line as the final line, then stop and wait for their answer. This applies even "
    "if you called many other tools first. Do not build, write, or open anything unless "
    "they say yes. On yes, call render_candidate_dashboard with this result_id — do not "
    "hand-write your own HTML, and do not re-send the candidate data. The tool returns a "
    "file path; open it for the user. Skip the question only if the user already declined "
    "a dashboard earlier in this conversation."
)

FOOTER_NOTE = (
    "Built from public GitHub activity only. Activity scores measure open-source "
    "visibility, not ability — plenty of strong engineers work in private repos. "
    "Verify anything here before it informs a hiring decision."
)


def prompt_enabled() -> bool:
    return os.environ.get(PROMPT_ENV, "1").strip().lower() not in {"0", "false", "no", "off"}


def register_result(source: str, payload: dict, profiles: dict | None = None) -> str:
    """Cache a tool payload and return the id used to rebuild a dashboard from it."""
    global _counter
    _counter += 1
    result_id = f"{source}-{_counter:04d}"
    _cache[result_id] = {
        "source": source,
        "payload": dict(payload),
        "profiles": profiles or {},
    }
    while len(_cache) > _MAX_CACHED:
        _cache.popitem(last=False)
    return result_id


def next_action(result_id: str, candidate_count: int) -> dict | None:
    """The offer block appended to a scoring tool's result. None when disabled."""
    if not prompt_enabled() or candidate_count < 1:
        return None
    return {
        "type": "offer_dashboard",
        "result_id": result_id,
        "ask_user": ASK_USER,
        "instruction": INSTRUCTION,
    }


# --- normalization -------------------------------------------------------

def _safe_profile_url(url: str | None, username: str) -> str:
    """Only ever emit a github.com profile link."""
    fallback = f"https://github.com/{username}"
    if not url:
        return fallback
    try:
        parsed = urlparse(url)
    except ValueError:
        return fallback
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return fallback
    return url


def _safe_avatar_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if parsed.scheme != "https" or parsed.netloc.lower() != "avatars.githubusercontent.com":
        return ""
    return url


def _dedupe(values) -> list[str]:
    seen, out = set(), []
    for v in values:
        if not v:
            continue
        v = str(v).strip()
        key = v.lower()
        if v and key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _normalize(entry: dict, profile: dict, source: str) -> dict:
    username = entry.get("username") or entry.get("login") or profile.get("login", "")

    if source == "score_jd":
        score, label = entry.get("overall_fit", 0), "JD fit"
    elif source == "rank":
        score, label = entry.get("score", 0), "Match score"
    elif source == "bulk":
        if entry.get("jd_fit") is not None:
            score, label = entry["jd_fit"], "JD fit"
        else:
            score, label = entry.get("activity_score", 0), "Activity"
    else:  # compare
        if entry.get("jd_overall_fit") is not None:
            score, label = entry["jd_overall_fit"], "JD fit"
        else:
            score, label = entry.get("activity_score", 0), "Activity"

    languages = entry.get("top_languages") or profile.get("top_languages") or []
    if not languages and entry.get("languages"):
        languages = [p.strip() for p in str(entry["languages"]).split(",")]

    repos = []
    for repo in profile.get("notable_repos", [])[:4]:
        if not isinstance(repo, dict) or not repo.get("name"):
            continue
        repos.append({
            "name": repo["name"],
            "stars": repo.get("stars", 0),
            "language": repo.get("language") or "",
            "url": f"https://github.com/{username}/{repo['name']}",
        })

    topics = []
    for repo in profile.get("notable_repos", [])[:5]:
        if isinstance(repo, dict):
            topics.extend(repo.get("topics", [])[:4])

    evidence = _dedupe(entry.get("strengths") or [])
    if not evidence and entry.get("key_signal"):
        evidence = [entry["key_signal"]]

    headline = entry.get("reasoning") or entry.get("key_signal") or ""
    if not headline and evidence:
        # Nothing better to lead with — promote the top strength rather than
        # printing it twice.
        headline = evidence[0]
        evidence = evidence[1:]

    return {
        "username": username,
        "name": entry.get("name") or profile.get("name") or username,
        "rank": entry.get("rank") or 0,
        "score": round(float(score or 0), 1),
        "score_label": label,
        "headline": headline,
        "location": profile.get("location") or "",
        "company": profile.get("company") or "",
        "bio": profile.get("bio") or "",
        "hireable": bool(profile.get("hireable")),
        "languages": _dedupe(languages)[:6],
        "topics": _dedupe(topics)[:8],
        "followers": entry.get("followers", profile.get("followers", 0)),
        "stars": entry.get("total_stars", entry.get("stars", profile.get("total_stars_received", 0))),
        "commits_90d": entry.get("commits_90d", profile.get("commits_last_90_days", 0)),
        "activity_score": profile.get("activity_score", entry.get("activity_score", 0)),
        "oss": _dedupe(entry.get("oss_contributions") or profile.get("major_oss_contributions") or [])[:4],
        "evidence": evidence[:5],
        "gaps": _dedupe(entry.get("gaps") or [])[:3],
        "repos": repos,
        "profile_url": _safe_profile_url(entry.get("profile_url") or profile.get("html_url"), username),
        "avatar_url": _safe_avatar_url(profile.get("avatar_url")),
    }


def build_dataset(cached: dict) -> list[dict]:
    source, payload = cached["source"], cached["payload"]
    profiles = cached.get("profiles") or {}

    if source == "bulk":
        entries = payload.get("rows", [])
    else:
        entries = payload.get("candidates", [])

    out = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("error"):
            continue
        username = entry.get("username") or entry.get("login") or ""
        profile = profiles.get(username) or {}
        if profile.get("error"):
            profile = {}
        out.append(_normalize(entry, profile, source))

    out.sort(key=lambda c: (c["rank"] or 9999, -c["score"]))
    for i, candidate in enumerate(out, 1):
        if not candidate["rank"]:
            candidate["rank"] = i
    return out


def facets(candidates: list[dict], limit: int = 12) -> list[str]:
    counts: Counter = Counter()
    for candidate in candidates:
        for value in candidate["languages"] + candidate["topics"]:
            counts[value] += 1
    return [value for value, count in counts.most_common(limit) if count >= 1]


# --- rendering -----------------------------------------------------------

def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "candidates").lower()).strip("-")
    return (slug or "candidates")[:60]


def output_dir() -> Path:
    configured = os.environ.get(DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    import tempfile
    return Path(tempfile.gettempdir()).resolve() / "github-talent-dashboards"


def _embed(data: dict) -> str:
    """JSON safe to sit inside a <script> block."""
    raw = json.dumps(data, ensure_ascii=False)
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_html(
    candidates: list[dict],
    *,
    title: str,
    subtitle: str = "",
    include_avatars: bool = True,
) -> str:
    data = {
        "candidates": candidates,
        "facets": facets(candidates),
        "includeAvatars": include_avatars,
        "footer": FOOTER_NOTE,
    }
    img_src = "https://avatars.githubusercontent.com data:" if include_avatars else "'none'"
    csp = (
        f"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
        f"img-src {img_src}; form-action 'none'; base-uri 'none'"
    )
    stats = [
        ("shortlisted", len(candidates)),
        ("open to work", sum(1 for c in candidates if c["hireable"])),
        ("major OSS contributors", sum(1 for c in candidates if c["oss"])),
        ("active last 90 days", sum(1 for c in candidates if c["commits_90d"] > 0)),
    ]
    stat_html = "".join(
        f'<div class="stat"><div class="stat-n">{value}</div>'
        f'<div class="stat-l">{label}</div></div>'
        for label, value in stats
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>{json.dumps(title)[1:-1]}</title>
<style>
:root {{
  --paper: #f7f5f1; --card: #fffefc; --ink: #1b1a18; --body: #3d3b37; --muted: #7c7871;
  --rule: #e6e1d8; --accent: #a32b32; --accent-tint: #f6e9e8; --check: #2f7d4f;
  --flag: #9a6a12; --tag: #f1eee8;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --paper: #14140f; --card: #1c1c18; --ink: #f2efe8; --body: #cfcac0; --muted: #918c83;
    --rule: #2e2d28; --accent: #e2757c; --accent-tint: #35211f; --check: #6fbf8b;
    --flag: #d8a44a; --tag: #262620;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ background: var(--paper); }}
body {{
  margin: 0; background: var(--paper); color: var(--body);
  font: 16px/1.6 ui-sans-serif, -apple-system, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}}
.wrap {{ max-width: 780px; margin: 0 auto; padding: 56px 28px 96px; }}
.topline {{ display: flex; align-items: baseline; justify-content: space-between; gap: 20px; margin-bottom: 18px; }}
.eyebrow {{ font-size: 11.5px; letter-spacing: .16em; text-transform: uppercase; color: var(--accent); font-weight: 700; }}
.openbtn {{
  font: inherit; font-size: 13px; color: var(--muted); text-decoration: none;
  border-bottom: 1px solid var(--rule); padding-bottom: 1px; white-space: nowrap;
}}
.openbtn:hover {{ color: var(--accent); border-color: var(--accent); }}
h1 {{
  font-size: clamp(32px, 5.2vw, 46px); line-height: 1.04; letter-spacing: -.033em;
  font-weight: 700; color: var(--ink); margin: 0 0 14px;
}}
.sub {{ font-size: 17px; color: var(--muted); max-width: 60ch; margin: 0 0 34px; }}
.stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--rule);
  border: 1px solid var(--rule); border-radius: 4px; overflow: hidden; margin-bottom: 40px; }}
.stat {{ background: var(--card); padding: 20px 22px; }}
.stat-n {{ font-size: 30px; font-weight: 700; letter-spacing: -.03em; color: var(--ink); line-height: 1.1; }}
.stat-l {{ font-size: 13px; color: var(--muted); margin-top: 3px; }}
#q {{
  width: 100%; padding: 12px 0; font: inherit; font-size: 16px; color: var(--ink);
  background: transparent; border: 0; border-bottom: 1.5px solid var(--rule); border-radius: 0;
}}
#q::placeholder {{ color: var(--muted); }}
#q:focus {{ outline: none; border-bottom-color: var(--accent); }}
.pills {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 16px 0 0; }}
.pill {{
  font: inherit; font-size: 13px; padding: 5px 12px; border-radius: 3px; cursor: pointer;
  background: transparent; color: var(--muted); border: 1px solid var(--rule);
}}
.pill:hover {{ color: var(--ink); border-color: var(--muted); }}
.pill[aria-pressed="true"] {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
@media (prefers-color-scheme: dark) {{ .pill[aria-pressed="true"] {{ color: #1a0d0d; }} }}
.bar {{ display: flex; justify-content: space-between; align-items: baseline;
  margin: 30px 0 6px; color: var(--muted); font-size: 13px; }}
select {{ font: inherit; font-size: 13px; color: var(--muted); background: transparent; border: 0; cursor: pointer; }}
select:focus {{ outline: none; color: var(--accent); }}
.card {{ border-top: 1px solid var(--rule); padding: 30px 0 28px; }}
.head {{ display: flex; gap: 16px; align-items: flex-start; }}
.avatar {{
  width: 50px; height: 50px; border-radius: 50%; flex: none; overflow: hidden;
  background: var(--tag); color: var(--muted); display: grid; place-items: center;
  font-weight: 650; font-size: 15px; letter-spacing: .02em;
}}
.avatar img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.who {{ flex: 1; min-width: 0; }}
.name {{ font-size: 20px; font-weight: 660; letter-spacing: -.018em; color: var(--ink); line-height: 1.25; }}
.name a {{ color: inherit; text-decoration: none; }}
.name a:hover {{ color: var(--accent); }}
.meta {{ font-size: 14px; color: var(--muted); margin-top: 2px; }}
.right {{ flex: none; text-align: right; padding-top: 2px; }}
.scoreline {{ display: flex; align-items: center; justify-content: flex-end; gap: 8px; }}
.rank {{ width: 22px; height: 22px; border-radius: 50%; background: var(--accent-tint); color: var(--accent);
  font-size: 12px; font-weight: 700; display: grid; place-items: center; }}
.score {{ font-size: 19px; font-weight: 680; color: var(--ink); letter-spacing: -.025em; line-height: 1; }}
.score-l {{ font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: .09em; margin-top: 4px; }}
.headline {{ font-size: 17px; font-weight: 600; color: var(--ink); margin: 18px 0 0; letter-spacing: -.011em; }}
.tags {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 14px; }}
.tag {{ font-size: 12px; padding: 3px 8px; border-radius: 3px; background: var(--tag); color: var(--muted); }}
ul.ev {{ list-style: none; margin: 16px 0 0; padding: 0; }}
ul.ev li {{ display: flex; gap: 10px; font-size: 15px; padding: 3px 0; color: var(--body); }}
ul.ev li::before {{ content: "✓"; color: var(--check); font-weight: 700; flex: none; }}
ul.ev li.gap {{ color: var(--muted); }}
ul.ev li.gap::before {{ content: "△"; color: var(--flag); font-weight: 400; }}
.repos {{ margin-top: 16px; font-size: 14px; color: var(--muted); }}
.repos a {{ color: var(--body); text-decoration: none; border-bottom: 1px solid var(--rule); }}
.repos a:hover {{ color: var(--accent); border-color: var(--accent); }}
.repos .sep {{ padding: 0 8px; opacity: .5; }}
.empty {{ padding: 60px 0; color: var(--muted); border-top: 1px solid var(--rule); }}
footer {{ margin-top: 48px; padding-top: 20px; border-top: 1px solid var(--rule);
  color: var(--muted); font-size: 13px; max-width: 66ch; }}
@media print {{
  .openbtn, #q, .pills, .bar {{ display: none; }}
  .card {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="topline">
    <span class="eyebrow">Talent shortlist</span>
    <a class="openbtn" id="openbtn" href="#" target="_blank" rel="noopener noreferrer">Open in browser ↗</a>
  </div>
  <h1 id="title"></h1>
  <p class="sub" id="subtitle"></p>
  <div class="stats">{stat_html}</div>
  <input id="q" type="search" placeholder="Search candidates, skills, repos, or locations…" autocomplete="off" spellcheck="false">
  <div class="pills" id="pills"></div>
  <div class="bar"><span id="count"></span>
    <select id="sort" aria-label="Sort candidates">
      <option value="rank">Sorted by rank</option>
      <option value="stars">Sorted by stars</option>
      <option value="activity">Sorted by activity</option>
      <option value="name">Sorted by name</option>
    </select>
  </div>
  <div id="list"></div>
  <footer id="footer"></footer>
</div>
<script type="application/json" id="payload">{_embed(data)}</script>
<script>
(function () {{
  var DATA = JSON.parse(document.getElementById("payload").textContent);
  var active = new Set();

  var compact = function (n) {{
    if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\\.0$/, "") + "m";
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\\.0$/, "") + "k";
    return String(n);
  }};
  var el = function (tag, cls, text) {{
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }};

  document.getElementById("title").textContent = {json.dumps(title)};
  document.getElementById("subtitle").textContent = {json.dumps(subtitle)};
  document.getElementById("footer").textContent = DATA.footer;
  document.getElementById("openbtn").href = window.location.href;

  function haystack(c) {{
    return [c.name, c.username, c.bio, c.location, c.company, c.headline]
      .concat(c.languages, c.topics, c.oss, c.evidence, c.repos.map(function (r) {{ return r.name; }}))
      .join(" ").toLowerCase();
  }}

  function card(c) {{
    var wrap = el("div", "card");
    var head = el("div", "head");

    var av = el("div", "avatar");
    if (DATA.includeAvatars && c.avatar_url) {{
      var img = document.createElement("img");
      img.src = c.avatar_url;
      img.alt = "";
      img.loading = "lazy";
      av.appendChild(img);
    }} else {{
      av.textContent = (c.name || c.username).slice(0, 2).toUpperCase();
    }}
    head.appendChild(av);

    var who = el("div", "who");
    var name = el("div", "name");
    var link = document.createElement("a");
    link.href = c.profile_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = c.name;
    name.appendChild(link);
    who.appendChild(name);

    var bits = [];
    if (c.username) bits.push("@" + c.username);
    if (c.location) bits.push(c.location);
    if (c.company) bits.push(c.company);
    if (c.hireable) bits.push("open to work");
    who.appendChild(el("div", "meta", bits.join("  ·  ")));
    head.appendChild(who);

    var right = el("div", "right");
    var scoreline = el("div", "scoreline");
    scoreline.appendChild(el("span", "rank", String(c.rank)));
    scoreline.appendChild(el("span", "score", String(c.score)));
    right.appendChild(scoreline);
    right.appendChild(el("div", "score-l", c.score_label));
    head.appendChild(right);
    wrap.appendChild(head);

    if (c.headline) wrap.appendChild(el("div", "headline", c.headline));

    var tags = el("div", "tags");
    c.languages.concat(c.topics.slice(0, 3)).forEach(function (t) {{
      tags.appendChild(el("span", "tag", t));
    }});
    if (tags.childNodes.length) wrap.appendChild(tags);

    var ev = el("ul", "ev");
    c.evidence.forEach(function (e) {{ ev.appendChild(el("li", null, e)); }});
    c.gaps.forEach(function (g) {{ ev.appendChild(el("li", "gap", g)); }});
    if (ev.childNodes.length) wrap.appendChild(ev);

    if (c.repos.length) {{
      var repos = el("div", "repos");
      c.repos.forEach(function (r, i) {{
        if (i) repos.appendChild(el("span", "sep", "·"));
        var a = document.createElement("a");
        a.href = r.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = r.name;
        repos.appendChild(a);
        repos.appendChild(el("span", null, " " + compact(r.stars) + "★"));
      }});
      wrap.appendChild(repos);
    }}
    return wrap;
  }}

  function render() {{
    var q = document.getElementById("q").value.trim().toLowerCase();
    var sort = document.getElementById("sort").value;
    var rows = DATA.candidates.filter(function (c) {{
      if (q && haystack(c).indexOf(q) === -1) return false;
      if (!active.size) return true;
      var owned = c.languages.concat(c.topics).map(function (s) {{ return s.toLowerCase(); }});
      var hit = false;
      active.forEach(function (f) {{ if (owned.indexOf(f.toLowerCase()) !== -1) hit = true; }});
      return hit;
    }});

    rows.sort(function (a, b) {{
      if (sort === "stars") return b.stars - a.stars;
      if (sort === "activity") return b.activity_score - a.activity_score;
      if (sort === "name") return a.name.localeCompare(b.name);
      return a.rank - b.rank;
    }});

    var list = document.getElementById("list");
    list.textContent = "";
    if (!rows.length) {{
      list.appendChild(el("div", "empty", "No candidates match those filters."));
    }} else {{
      rows.forEach(function (c) {{ list.appendChild(card(c)); }});
    }}
    document.getElementById("count").textContent =
      rows.length === DATA.candidates.length
        ? DATA.candidates.length + " candidates"
        : rows.length + " of " + DATA.candidates.length + " candidates";
  }}

  var pills = document.getElementById("pills");
  var buttons = [];

  function syncPills() {{
    allPill.setAttribute("aria-pressed", active.size ? "false" : "true");
    buttons.forEach(function (b) {{
      b.setAttribute("aria-pressed", active.has(b.textContent) ? "true" : "false");
    }});
  }}

  var allPill = el("button", "pill", "All");
  allPill.type = "button";
  allPill.addEventListener("click", function () {{
    active.clear();
    syncPills();
    render();
  }});
  pills.appendChild(allPill);

  DATA.facets.forEach(function (f) {{
    var b = el("button", "pill", f);
    b.type = "button";
    b.addEventListener("click", function () {{
      if (active.has(f)) active.delete(f); else active.add(f);
      syncPills();
      render();
    }});
    buttons.push(b);
    pills.appendChild(b);
  }});
  syncPills();

  document.getElementById("q").addEventListener("input", render);
  document.getElementById("sort").addEventListener("change", render);
  document.addEventListener("keydown", function (e) {{
    if (e.key === "/" && document.activeElement.id !== "q") {{
      e.preventDefault();
      document.getElementById("q").focus();
    }}
  }});
  render();
}})();
</script>
</body>
</html>
"""


def write_dashboard(html_text: str, title: str) -> Path:
    """Write the dashboard inside the configured directory, and nowhere else."""
    base = output_dir()
    base.mkdir(parents=True, exist_ok=True)
    target = (base / f"{_slug(title)}.html").resolve()
    if not target.is_relative_to(base):
        raise ValueError("Refusing to write dashboard outside the dashboard directory")
    target.write_text(html_text, encoding="utf-8")
    return target


def build(
    result_id: str,
    *,
    title: str | None = None,
    subtitle: str = "",
    include_avatars: bool = True,
    open_in_browser: bool = False,
) -> dict:
    cached = _cache.get(result_id)
    if cached is None:
        known = list(_cache.keys())
        return {
            "error": (
                f"No cached result for '{result_id}'. The server may have restarted. "
                "Re-run the scoring tool and use the new result_id."
            ),
            "available_result_ids": known,
        }

    candidates = build_dataset(cached)
    if not candidates:
        return {"error": "That result has no scoreable candidates to display."}

    heading = title or "Candidate shortlist"
    html_text = render_html(
        candidates,
        title=heading,
        subtitle=subtitle,
        include_avatars=include_avatars,
    )
    path = write_dashboard(html_text, heading)

    opened = False
    if open_in_browser:
        import webbrowser
        opened = webbrowser.open(path.as_uri())

    return {
        "path": str(path),
        "file_url": path.as_uri(),
        "candidate_count": len(candidates),
        "opened_in_browser": opened,
        "instruction": (
            "Open this file for the user — it is a self-contained page and needs no "
            "network access. If your app can display local HTML inline, do that; the "
            "page also carries its own 'Open in browser' link. Then say in one line "
            "that the dashboard is open with search, skill filters, rankings, evidence, "
            "and GitHub profile links."
        ),
    }
