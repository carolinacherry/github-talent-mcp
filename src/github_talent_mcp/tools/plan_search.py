from __future__ import annotations

import json
import re

# Role family -> (detection keywords, targeted follow-up questions).
ROLE_FAMILIES: dict[str, dict[str, tuple[str, ...]]] = {
    "security/IAM": {
        "keywords": (
            "security", "iam", "appsec", "authn", "authz", "authentication",
            "authorization", "infosec", "identity", "oauth", "oidc", "saml",
            "cryptography", "zero trust",
        ),
        "questions": (
            "Security focus — IAM/identity, application security, cloud security, or cryptography?",
            "Any compliance or clearance requirements (SOC 2, FedRAMP, security clearance)?",
        ),
    },
    "ML/AI": {
        "keywords": (
            "machine learning", "ml ", " ai ", "llm", "nlp", "deep learning",
            "pytorch", "tensorflow", "jax", "inference", "training", "data scien",
        ),
        "questions": (
            "ML focus — research, training infrastructure, or inference/serving?",
            "Required frameworks (PyTorch, JAX, TensorFlow)? Do publications/benchmarks matter?",
        ),
    },
    "frontend": {
        "keywords": (
            "frontend", "front-end", "react", "vue", "svelte", "angular",
            "ui engineer", "web developer",
        ),
        "questions": (
            "Primary framework (React, Vue, Svelte, Angular)?",
            "How important are design-systems and accessibility (a11y) depth?",
        ),
    },
    "infra/platform": {
        "keywords": (
            "infrastructure", "devops", "platform", "sre", "site reliability",
            "kubernetes", "k8s", "terraform", "cloud", "aws", "gcp", "azure",
        ),
        "questions": (
            "Which clouds (AWS, GCP, Azure)?",
            "Required tooling — Kubernetes, Terraform/IaC, specific CI/CD?",
        ),
    },
    "data": {
        "keywords": (
            "data engineer", "data platform", "etl", "spark", "dbt", "warehouse",
            "snowflake", "streaming", "kafka", "analytics engineer",
        ),
        "questions": (
            "Batch or streaming focus?",
            "Stack — Spark, dbt, Snowflake/BigQuery, Kafka?",
        ),
    },
    "mobile": {
        "keywords": ("mobile", "ios", "android", "swift", "kotlin", "react native", "flutter"),
        "questions": (
            "Platform — iOS, Android, or cross-platform?",
            "Languages/frameworks — Swift, Kotlin, React Native, Flutter?",
        ),
    },
}

UNIVERSAL_QUESTIONS: tuple[str, ...] = (
    "Seniority/level — IC vs people-manager, and target band (senior/staff/principal/director)?",
    "What are the 2-4 must-have skills or technologies (vs nice-to-haves)?",
    "Location or remote policy, plus timezone and work-authorization/visa constraints?",
    "Any hard dealbreakers (e.g. minimum years, prior management required, specific domain)?",
)

JD_QUESTION = (
    "Paste the full job description, or share a public link to the posting and "
    "paste what it shows — I may not be able to open links myself."
)

_KNOWN_LANGUAGES = (
    "python", "javascript", "typescript", "go", "golang", "rust", "java",
    "kotlin", "swift", "scala", "ruby", "c++", "c#", "php", "elixir", "clojure",
)
_SENIORITY_TERMS = (
    "intern", "junior", "mid-level", "senior", "staff", "principal",
    "distinguished", "lead", "manager", "director", "vp", "head of",
)
_LOCATION_TERMS = ("remote", "hybrid", "onsite", "on-site")
_URL_RE = re.compile(r"https?://\S+")


async def plan_search(request: str, job_description: str | None = None) -> str:
    """Parse a sourcing request and return follow-up questions to ask first.

    Pure analysis — makes no GitHub API calls. Returns parsed criteria, what is
    still missing, and targeted role-aware questions the assistant should ask the
    user before running a real search.
    """
    text = f"{request} {job_description or ''}".lower()

    detected_roles = [
        family for family, spec in ROLE_FAMILIES.items()
        if any(kw in text for kw in spec["keywords"])
    ]
    languages = [lang for lang in _KNOWN_LANGUAGES if lang in text]
    seniority = [term for term in _SENIORITY_TERMS if term in text]
    location_signal = [term for term in _LOCATION_TERMS if term in text]
    has_jd = bool(job_description and job_description.strip())
    jd_link_in_request = bool(_URL_RE.search(request))

    questions: list[str] = []
    if not has_jd:
        questions.append(JD_QUESTION)
    for family in detected_roles:
        questions.extend(ROLE_FAMILIES[family]["questions"])
    if not seniority:
        questions.append(UNIVERSAL_QUESTIONS[0])
    if not languages:
        questions.append(UNIVERSAL_QUESTIONS[1])
    if not location_signal:
        questions.append(UNIVERSAL_QUESTIONS[2])
    questions.append(UNIVERSAL_QUESTIONS[3])  # dealbreakers — always worth asking

    missing = []
    if not has_jd:
        missing.append("job_description")
    if not seniority:
        missing.append("seniority")
    if not languages:
        missing.append("must_have_skills")
    if not location_signal:
        missing.append("location_or_remote")

    if detected_roles:
        strategy = (
            "Source from contributors to a few well-known repos in the "
            f"{', '.join(detected_roles)} space (get_repo_contributors), then "
            "rank/score the pool. This is more reproducible than open-ended search. "
            "Confirm the target repos with the user if unsure."
        )
    else:
        strategy = (
            "Use search_developers with concrete language + location filters, or "
            "get_repo_contributors on repos the user names. Avoid broad, low-signal "
            "searches."
        )

    result = {
        "parsed": {
            "detected_roles": detected_roles,
            "languages": languages,
            "seniority_terms": seniority,
            "location_signal": location_signal,
            "has_job_description": has_jd,
            "job_description_link_in_request": jd_link_in_request,
        },
        "missing": missing,
        "follow_up_questions": questions,
        "suggested_strategy": strategy,
        "ready_to_search": len(missing) == 0,
        "instruction": (
            "Ask the user the follow_up_questions above (especially the job "
            "description) and wait for answers BEFORE calling search_developers, "
            "rank_candidates, or score_against_jd. Do not guess missing criteria."
        ),
    }
    return json.dumps(result, indent=2)
