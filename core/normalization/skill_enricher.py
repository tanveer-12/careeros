"""Shared skill-enrichment layer for job normalizers.

Accepts title, description, categories, domain, and seniority; returns
extracted, normalized, inferred, and final skill lists with confidence.

Design principles
-----------------
* One canonical name per skill; aliases resolve at extraction time.
* Tools and hard competencies are extracted from text first.
* Soft skills are also extracted but placed last in skills_final so they
  never push out hard skills; they do not influence confidence scoring.
* Inference is layered: domain baseline → role-type overlay → seniority
  overlay. Skills already extracted are never duplicated in inferred.
* Pattern matching uses (?<!\\w)...(?!\\w) pseudo-word-boundaries so
  skill names with non-word chars (C++, C#, .NET, gRPC) are handled
  correctly without false-positive contamination.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SKILL_ENRICHER_VERSION = "v2"

# =============================================================================
# ALIAS TABLE
# Format: canonical_name -> [alias, ...]
# • Aliases are plain Python strings; re.escape() is applied when compiling.
# • Longer aliases are compiled before shorter ones so a multi-word phrase
#   takes priority over any shorter alias that is a prefix of it.
# • Keep each canonical name unique; the same tool/competency must not appear
#   under two different canonical names.
# =============================================================================

_SKILL_ALIASES: dict[str, list[str]] = {

    # =========================================================================
    # PROGRAMMING LANGUAGES
    # =========================================================================
    "Python":           ["python"],
    "JavaScript":       ["javascript", "js", "ecmascript"],
    "TypeScript":       ["typescript"],
    "Go":               ["golang"],
    "Rust":             ["rust"],
    "Java":             ["java"],
    "C++":              ["c++", "cpp"],
    "C#":               ["c#", "csharp"],
    ".NET":             [".net core", ".net framework", "dotnet"],
    "Ruby":             ["ruby"],
    "PHP":              ["php"],
    "Swift":            ["swift"],
    "Kotlin":           ["kotlin"],
    "Scala":            ["scala"],
    "SQL":              ["sql", "pl/sql", "t-sql"],
    "Bash":             ["bash", "shell scripting", "shell script"],
    "R":                ["r programming", "r language", "rstudio"],
    "MATLAB":           ["matlab"],
    "Julia":            ["julia"],
    "Elixir":           ["elixir"],
    "Erlang":           ["erlang"],
    "Clojure":          ["clojure"],
    "Haskell":          ["haskell"],

    # =========================================================================
    # FRONTEND
    # =========================================================================
    "React":                ["react.js", "reactjs", "react"],
    "Next.js":              ["next.js", "nextjs"],
    "Vue.js":               ["vue.js", "vuejs", "vue"],
    "Angular":              ["angular"],
    "Svelte":               ["svelte"],
    "Remix":                ["remix"],
    "React Native":         ["react native"],
    "Tailwind CSS":         ["tailwindcss", "tailwind css", "tailwind"],
    "HTML":                 ["html5", "html"],
    "CSS":                  ["css3", "css"],
    "Redux":                ["redux"],
    "Zustand":              ["zustand"],
    "Webpack":              ["webpack"],
    "Vite":                 ["vite"],
    "Accessibility":        ["accessibility", "a11y", "wcag", "aria"],
    "Responsive Design":    ["responsive design", "responsive web design"],
    "Component Libraries":  ["design system", "component library", "storybook",
                             "ui library", "ui components"],

    # =========================================================================
    # BACKEND FRAMEWORKS
    # =========================================================================
    "Node.js":          ["node.js", "nodejs"],
    "Express.js":       ["express.js", "expressjs", "express"],
    "FastAPI":          ["fastapi"],
    "Django":           ["django"],
    "Flask":            ["flask"],
    "Spring Boot":      ["spring boot"],
    "Spring":           ["spring framework"],
    "Laravel":          ["laravel"],
    "Ruby on Rails":    ["ruby on rails", "rails"],
    "ASP.NET Core":     ["asp.net core"],
    "NestJS":           ["nest.js", "nestjs"],

    # =========================================================================
    # APIS, INTEGRATION & ARCHITECTURE
    # =========================================================================
    "REST APIs":            ["rest api", "restful", "rest apis",
                             "restful api", "restful apis"],
    "GraphQL":              ["graphql"],
    "gRPC":                 ["grpc"],
    "WebSockets":           ["websockets", "websocket"],
    "Authentication":       ["oauth2", "oauth", "jwt", "saml", "sso",
                             "authentication", "authorization"],
    "Microservices":        ["microservices", "microservice architecture",
                             "service-oriented architecture", "soa"],
    "Distributed Systems":  ["distributed systems", "distributed computing"],

    # =========================================================================
    # CLOUD PLATFORMS
    # =========================================================================
    "AWS":          ["amazon web services", "aws"],
    "Azure":        ["microsoft azure", "azure"],
    "GCP":          ["google cloud platform", "google cloud", "gcp"],
    "Cloudflare":   ["cloudflare"],
    "Serverless":   ["serverless", "aws lambda", "cloud functions",
                     "lambda functions", "faas"],

    # =========================================================================
    # DEVOPS / INFRASTRUCTURE / SRE
    # =========================================================================
    "Kubernetes":               ["kubernetes", "k8s"],
    "Docker":                   ["docker", "containerization", "containers"],
    "Terraform":                ["terraform"],
    "Ansible":                  ["ansible"],
    "CI/CD":                    ["ci/cd", "cicd", "continuous integration",
                                  "continuous deployment", "continuous delivery"],
    "GitHub Actions":           ["github actions"],
    "Jenkins":                  ["jenkins"],
    "Linux":                    ["linux", "unix"],
    "Helm":                     ["helm"],
    "Prometheus":               ["prometheus"],
    "Grafana":                  ["grafana"],
    "Observability":            ["observability", "distributed tracing",
                                  "opentelemetry", "jaeger"],
    "Infrastructure as Code":   ["infrastructure as code", "iac"],
    "SRE":                      ["site reliability engineering", "sre",
                                  "reliability engineering"],

    # =========================================================================
    # DATABASES
    # =========================================================================
    "PostgreSQL":   ["postgresql", "postgres"],
    "MySQL":        ["mysql"],
    "MongoDB":      ["mongodb"],
    "Redis":        ["redis"],
    "Elasticsearch": ["elasticsearch"],
    "DynamoDB":     ["dynamodb"],
    "SQLite":       ["sqlite"],
    "Snowflake":    ["snowflake"],
    "BigQuery":     ["bigquery"],
    "Cassandra":    ["cassandra"],
    "ClickHouse":   ["clickhouse"],
    "SQL Server":   ["sql server", "mssql", "microsoft sql server"],
    "Oracle DB":    ["oracle database", "oracle db"],

    # =========================================================================
    # DATA / ANALYTICS / BI
    # =========================================================================
    "Apache Spark":         ["pyspark", "apache spark", "spark"],
    "Apache Kafka":         ["apache kafka", "kafka"],
    "Airflow":              ["apache airflow", "airflow"],
    "dbt":                  ["dbt", "data build tool"],
    "Tableau":              ["tableau"],
    "Power BI":             ["power bi", "powerbi"],
    "Looker":               ["looker"],
    "pandas":               ["pandas"],
    "NumPy":                ["numpy"],
    "Data Modeling":        ["data modeling", "data modelling", "schema design",
                             "dimensional modeling", "star schema"],
    "Analytics Engineering": ["analytics engineering"],
    "Data Warehousing":     ["data warehouse", "data warehousing",
                             "warehouse design"],
    "BI Reporting":         ["bi reporting", "business intelligence reporting",
                             "dashboard reporting", "data visualization",
                             "data dashboards"],
    "ETL / ELT":            ["etl", "elt", "extract transform load",
                             "data pipeline", "data pipelines", "data ingestion"],
    "Data Analysis":        ["data analysis", "data analytics",
                             "quantitative analysis"],

    # =========================================================================
    # ML / AI
    # =========================================================================
    "TensorFlow":           ["tensorflow"],
    "PyTorch":              ["pytorch"],
    "scikit-learn":         ["scikit-learn", "sklearn"],
    "Hugging Face":         ["hugging face", "huggingface"],
    "LangChain":            ["langchain"],
    "MLflow":               ["mlflow"],
    "Machine Learning":     ["machine learning", "ml model", "ml models",
                             "ml pipeline", "ml pipelines"],
    "Deep Learning":        ["deep learning", "neural network", "neural networks",
                             "convolutional", "cnn", "rnn", "lstm",
                             "transformers"],
    "LLMs":                 ["large language model", "large language models",
                             "llms", "llm", "generative ai", "genai"],
    "Prompt Engineering":   ["prompt engineering"],
    "RAG":                  ["rag", "retrieval augmented generation",
                             "retrieval-augmented"],
    "Embeddings":           ["embeddings", "vector embeddings", "word embeddings"],
    "MLOps":                ["mlops", "ml ops", "model deployment",
                             "model serving", "model monitoring"],
    "Model Evaluation":     ["model evaluation", "model validation",
                             "evaluation metrics"],
    "Feature Engineering":  ["feature engineering"],
    "A/B Testing":          ["a/b testing", "a/b test", "experimentation",
                             "hypothesis testing", "statistical testing"],
    "Vector Databases":     ["vector database", "vector databases", "vector store",
                             "pinecone", "weaviate", "chroma", "qdrant"],
    "Statistical Analysis": ["statistical analysis", "regression analysis",
                             "statistical modeling"],
    "NLP":                  ["natural language processing", "nlp",
                             "text classification", "named entity recognition",
                             "sentiment analysis"],

    # =========================================================================
    # MARKETING
    # =========================================================================
    "HubSpot":              ["hubspot"],
    "Marketo":              ["marketo"],
    "Google Analytics":     ["google analytics", "ga4", "google tag manager"],
    "SEO":                  ["seo", "search engine optimization",
                             "on-page seo", "technical seo", "link building"],
    "SEM":                  ["sem", "search engine marketing", "paid search",
                             "google ads", "google adwords", "ppc"],
    "Content Strategy":     ["content strategy", "content planning",
                             "editorial strategy", "editorial calendar"],
    "Copywriting":          ["copywriting", "copy writing", "ad copy",
                             "marketing copy"],
    "Performance Marketing": ["performance marketing",
                              "performance advertising"],
    "Paid Social":          ["paid social", "facebook ads", "instagram ads",
                             "linkedin ads", "social media advertising"],
    "Email Marketing":      ["email marketing", "email campaigns",
                             "drip campaigns", "email automation"],
    "Lifecycle Marketing":  ["lifecycle marketing", "retention marketing",
                             "customer lifecycle"],
    "Growth Marketing":     ["growth marketing", "growth hacking"],
    "Marketing Automation": ["marketing automation"],
    "Demand Generation":    ["demand generation", "demand gen"],

    # =========================================================================
    # FINANCE
    # =========================================================================
    "Excel":                ["microsoft excel", "excel"],
    "QuickBooks":           ["quickbooks"],
    "SAP":                  ["sap"],
    "Financial Modeling":   ["financial modeling", "financial modelling",
                             "financial model", "financial models"],
    "Forecasting":          ["forecasting", "financial forecasting",
                             "revenue forecasting", "demand forecasting"],
    "FP&A":                 ["fp&a", "financial planning and analysis",
                             "financial planning"],
    "Budgeting":            ["budgeting", "budget management", "budget planning"],
    "Pricing":              ["pricing strategy", "pricing analysis",
                             "price modeling"],
    "Accounting":           ["accounting", "bookkeeping", "general ledger",
                             "accounts payable", "accounts receivable",
                             "gaap", "ifrs"],
    "Audit":                ["internal audit", "external audit",
                             "auditing", "audit"],
    "Risk Management":      ["risk management", "risk assessment",
                             "risk analysis", "credit risk", "market risk"],
    "Valuation":            ["valuation", "financial valuation", "dcf", "lbo",
                             "discounted cash flow"],
    "Financial Reporting":  ["financial reporting", "management reporting",
                             "financial statements"],

    # =========================================================================
    # DESIGN / CREATIVE
    # =========================================================================
    "Figma":            ["figma"],
    "Sketch":           ["sketch"],
    "Adobe XD":         ["adobe xd"],
    "Illustrator":      ["adobe illustrator", "illustrator"],
    "Photoshop":        ["adobe photoshop", "photoshop"],
    "After Effects":    ["after effects", "adobe after effects"],
    "InDesign":         ["indesign", "adobe indesign"],
    "Canva":            ["canva"],
    "UI Design":        ["ui design", "user interface design", "interface design"],
    "UX Design":        ["ux design", "user experience design"],
    "UX Research":      ["ux research", "user research", "usability testing",
                         "usability studies"],
    "Visual Design":    ["visual design", "graphic design"],
    "Prototyping":      ["prototyping", "wireframing", "wireframes",
                         "mockups", "high-fidelity mockups"],
    "Motion Design":    ["motion design", "motion graphics", "animation"],
    "Design Systems":   ["design systems"],
    "Brand Design":     ["brand design", "branding", "brand identity",
                         "brand guidelines"],

    # =========================================================================
    # WRITING / CONTENT
    # =========================================================================
    "Technical Writing":    ["technical writing", "technical documentation",
                             "api documentation", "developer docs"],
    "Editing":              ["editing", "copy editing", "proofreading"],
    "Storytelling":         ["storytelling", "narrative writing"],
    "Grant Writing":        ["grant writing", "grant proposals"],

    # =========================================================================
    # SALES / CRM / ACCOUNT MANAGEMENT
    # =========================================================================
    "Salesforce":           ["salesforce", "sfdc"],
    "Account Management":   ["account management"],
    "Customer Success":     ["customer success"],
    "Business Development": ["business development", "biz dev"],
    "Sales Strategy":       ["sales strategy", "go-to-market", "gtm strategy"],
    "Pipeline Management":  ["pipeline management", "sales pipeline",
                             "opportunity management"],
    "CRM":                  ["crm", "customer relationship management"],
    "Negotiation":          ["negotiation", "contract negotiation"],

    # =========================================================================
    # OPERATIONS / PROJECT & PROGRAM MANAGEMENT
    # =========================================================================
    "Jira":                 ["jira"],
    "Asana":                ["asana"],
    "Confluence":           ["confluence"],
    "Project Management":   ["project management", "pmp", "prince2"],
    "Program Management":   ["program management"],
    "Agile":                ["agile", "agile methodology", "agile development"],
    "Scrum":                ["scrum"],
    "Kanban":               ["kanban"],
    "Process Improvement":  ["process improvement", "process optimization",
                             "lean", "six sigma", "kaizen"],
    "Scheduling":           ["resource scheduling", "capacity planning",
                             "scheduling"],
    "Stakeholder Management": ["stakeholder management",
                               "stakeholder engagement",
                               "cross-functional collaboration"],

    # =========================================================================
    # HR / PEOPLE
    # =========================================================================
    "Recruiting":               ["recruiting", "talent acquisition",
                                  "talent sourcing", "headhunting"],
    "People Operations":        ["people operations", "people ops"],
    "Performance Management":   ["performance management",
                                  "performance reviews", "360 feedback"],
    "Compensation & Benefits":  ["compensation", "benefits administration",
                                  "total rewards"],
    "Training & Development":   ["learning and development", "l&d",
                                  "training programs", "training"],
    "HRIS":                     ["workday", "bamboohr", "successfactors",
                                  "adp", "hris"],
    "Employee Relations":       ["employee relations", "employee engagement"],

    # =========================================================================
    # MANAGEMENT / LEADERSHIP
    # =========================================================================
    "Team Leadership":      ["team leadership", "leading teams", "leadership"],
    "People Management":    ["people management", "managing people",
                             "managing teams", "line management"],
    "Mentoring":            ["mentoring", "coaching", "mentorship"],
    "Hiring":               ["hiring", "building teams"],
    "Strategic Thinking":   ["strategic thinking", "strategy development",
                             "business strategy"],
    "Change Management":    ["change management", "organizational change"],
    "P&L Management":       ["profit and loss", "budget ownership",
                             "revenue responsibility"],

    # =========================================================================
    # SOFT SKILLS
    # These are extracted from text but sorted to the end of skills_final and
    # excluded from hard-skill confidence scoring.
    # =========================================================================
    "Communication":        ["communication skills", "written communication",
                             "verbal communication", "strong communication",
                             "excellent communication", "interpersonal skills"],
    "Presentation Skills":  ["presentation skills", "presentations",
                             "public speaking"],
    "Problem Solving":      ["problem solving", "problem-solving",
                             "troubleshooting", "critical thinking"],
    "Analytical Thinking":  ["analytical thinking", "analytical skills",
                             "data-driven", "analytical mindset"],
    "Teamwork":             ["teamwork", "collaboration", "team player",
                             "collaborative"],
    "Adaptability":         ["adaptability", "fast-paced environment",
                             "comfortable with ambiguity", "flexibility"],
    "Time Management":      ["time management", "prioritization",
                             "multitasking"],
}

# =============================================================================
# SOFT SKILL REGISTRY
# Used to deprioritize soft skills in skills_final and exclude them from
# confidence scoring.
# =============================================================================

_SOFT_SKILLS: frozenset[str] = frozenset({
    "Communication",
    "Presentation Skills",
    "Problem Solving",
    "Analytical Thinking",
    "Teamwork",
    "Adaptability",
    "Time Management",
})

# =============================================================================
# COMPILE PATTERNS AT IMPORT TIME
# Longer aliases compiled first so multi-word phrases take priority over any
# shorter alias that happens to be a substring of them.
# =============================================================================

_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str]] = []

_all_pairs: list[tuple[str, str]] = []
for _canonical, _aliases in _SKILL_ALIASES.items():
    for _alias in _aliases:
        _all_pairs.append((_alias, _canonical))

_all_pairs.sort(key=lambda x: len(x[0]), reverse=True)

for _alias, _canonical in _all_pairs:
    _COMPILED_PATTERNS.append((
        re.compile(r"(?<!\w)" + re.escape(_alias) + r"(?!\w)", re.IGNORECASE),
        _canonical,
    ))

del _all_pairs, _alias, _canonical, _aliases  # clean up module namespace


# =============================================================================
# DOMAIN BASELINE INFERENCE
# Skills inferred when domain is known but not found in text.
# =============================================================================

_DOMAIN_SKILLS: dict[str, list[str]] = {
    "software engineering": [
        "Git", "Linux", "REST APIs", "CI/CD", "SQL",
    ],
    "data & ai": [
        "Python", "SQL", "Git", "Data Analysis",
    ],
    "product": [
        "Agile", "Scrum", "Jira", "Stakeholder Management",
    ],
    "design": [
        "Figma", "UI Design", "UX Design", "Prototyping",
    ],
    "marketing": [
        "Google Analytics", "SEO", "Content Strategy",
    ],
    "finance": [
        "Excel", "Financial Modeling", "SQL",
    ],
    "sales": [
        "Salesforce", "CRM", "Pipeline Management", "Negotiation",
    ],
    "hr": [
        "Excel", "Recruiting", "Stakeholder Management",
    ],
    "operations": [
        "Excel", "Jira", "Project Management", "Process Improvement",
    ],
    "support": [
        "Communication", "Stakeholder Management",
    ],
    "legal": [
        "Research", "Analytical Thinking",
    ],
    "creative": [
        "Copywriting", "Editing", "Content Strategy",
    ],
    "other": [],
}

# =============================================================================
# ROLE-TYPE OVERLAY
# Additional skills inferred when a specific role type is detected from title.
# =============================================================================

_ROLE_TYPE_SKILLS: dict[str, list[str]] = {
    "intern": [
        "Communication", "Teamwork", "Adaptability",
    ],
    "analyst": [
        "Excel", "SQL", "Data Analysis", "Analytical Thinking",
        "Financial Reporting",
    ],
    "coordinator": [
        "Scheduling", "Project Management", "Communication",
        "Stakeholder Management", "Time Management",
    ],
    "associate": [
        "Communication", "Analytical Thinking", "Teamwork",
    ],
    "consultant": [
        "Stakeholder Management", "Analytical Thinking",
        "Presentation Skills", "Problem Solving",
    ],
    "researcher": [
        "Analytical Thinking", "Problem Solving",
    ],
    "writer": [
        "Copywriting", "Editing", "Content Strategy", "Storytelling",
    ],
    "designer": [
        "Figma", "UI Design", "UX Design", "Prototyping",
    ],
    "manager": [
        "Team Leadership", "People Management", "Stakeholder Management",
        "Performance Management", "Hiring",
    ],
    "director": [
        "Team Leadership", "People Management", "Stakeholder Management",
        "Strategic Thinking", "P&L Management", "Change Management",
    ],
}

# =============================================================================
# SENIORITY OVERLAY
# Applied on top of domain and role-type inference.
# =============================================================================

_SENIORITY_OVERLAY: dict[str, list[str]] = {
    "intern":     ["Communication", "Teamwork", "Adaptability"],
    "entry":      ["Communication", "Teamwork", "Analytical Thinking"],
    "mid":        [],
    "senior":     ["Mentoring", "Stakeholder Management"],
    "staff":      ["Mentoring", "Stakeholder Management", "Strategic Thinking"],
    "principal":  ["Mentoring", "Stakeholder Management", "Strategic Thinking"],
    "executive":  [
        "Team Leadership", "People Management", "Stakeholder Management",
        "Strategic Thinking", "P&L Management",
    ],
}


# =============================================================================
# RESULT DATACLASS
# =============================================================================

@dataclass
class SkillEnrichment:
    extracted:      list[str] = field(default_factory=list)
    normalized:     list[str] = field(default_factory=list)
    inferred:       list[str] = field(default_factory=list)
    final:          list[str] = field(default_factory=list)
    confidence:     float = 0.0
    source_version: str = SKILL_ENRICHER_VERSION


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _detect_role_type(title: str | None) -> str | None:
    """Classify the role category from the job title for inference layering."""
    if not title:
        return None
    lower = title.lower()
    # Director / exec level checked first — most specific
    if any(kw in lower for kw in ["director", "vp of", "vice president", "chief "]):
        return "director"
    if "manager" in lower or "head of" in lower:
        return "manager"
    if "coordinator" in lower:
        return "coordinator"
    if "analyst" in lower:
        return "analyst"
    if "associate" in lower:
        return "associate"
    if "consultant" in lower or "advisor" in lower:
        return "consultant"
    if "researcher" in lower:
        return "researcher"
    if any(kw in lower for kw in ["writer", "copywriter", "editor", "journalist"]):
        return "writer"
    if "designer" in lower:
        return "designer"
    if "intern" in lower:
        return "intern"
    return None


def _extract_skills_from_text(text: str) -> list[str]:
    """Return canonical skill names found in *text*, ordered by first occurrence.

    Each canonical name is returned at most once; the longer-alias-first
    compilation order means a more-specific phrase (e.g. "Spring Boot") is
    matched and its shorter prefix ("Spring") is skipped.
    """
    found: dict[str, int] = {}  # canonical -> position of first match
    for pattern, canonical in _COMPILED_PATTERNS:
        if canonical in found:
            continue  # already claimed by a longer alias
        m = pattern.search(text)
        if m:
            found[canonical] = m.start()
    return [c for c, _ in sorted(found.items(), key=lambda kv: kv[1])]


def _compute_confidence(n_hard: int, n_soft: int, n_inferred: int) -> float:
    """Confidence based on hard-skill extraction only; soft skills are excluded."""
    if n_hard >= 6:
        return 0.90
    if n_hard >= 4:
        return 0.80
    if n_hard >= 2:
        return 0.65
    if n_hard == 1:
        return 0.55
    if n_soft > 0:
        return 0.40  # soft mentions exist but no hard skills found in text
    if n_inferred > 0:
        return 0.30  # domain/role inference only
    return 0.0


# =============================================================================
# PUBLIC API
# =============================================================================

def enrich_skills(
    title: str | None,
    description: str | None,
    categories: list[str],
    domain: str | None,
    seniority: str | None = None,
) -> SkillEnrichment:
    """Extract, normalize, and infer skills for a job posting.

    Parameters
    ----------
    title:       Job title (plain text).
    description: Job description (HTML-stripped plain text).
    categories:  Category / tag strings from the source API.
    domain:      Normalised domain string (e.g. ``"software engineering"``).
    seniority:   Normalised seniority level (e.g. ``"senior"``, ``"intern"``).
    """
    # Build search corpus: title first (highest signal), then categories, then body
    parts: list[str] = []
    if title:
        parts.append(title)
    if categories:
        parts.extend(c for c in categories if c)
    if description:
        parts.append(description)
    corpus = " ".join(parts)

    # ── Extraction ───────────────────────────────────────────────────────────
    extracted = _extract_skills_from_text(corpus)
    normalized = extracted[:]  # canonical names are already normalised on extraction

    # Split extracted into hard vs. soft buckets
    extracted_hard = [s for s in extracted if s not in _SOFT_SKILLS]
    extracted_soft = [s for s in extracted if s in _SOFT_SKILLS]
    extracted_set = set(extracted)

    # ── Inference (domain → role-type → seniority) ───────────────────────────
    inferred_set: set[str] = set()

    # Layer 1: domain baseline
    domain_key = (domain or "other").lower()
    for skill in _DOMAIN_SKILLS.get(domain_key, []):
        if skill not in extracted_set:
            inferred_set.add(skill)

    # Layer 2: role-type overlay
    role_type = _detect_role_type(title)
    if role_type:
        for skill in _ROLE_TYPE_SKILLS.get(role_type, []):
            if skill not in extracted_set:
                inferred_set.add(skill)

    # Layer 3: seniority overlay
    seniority_key = (seniority or "").lower()
    for skill in _SENIORITY_OVERLAY.get(seniority_key, []):
        if skill not in extracted_set:
            inferred_set.add(skill)

    # Preserve a stable order for inferred (domain order first, then role, then seniority)
    inferred_ordered: list[str] = []
    seen_inferred: set[str] = set()
    for pool in [
        _DOMAIN_SKILLS.get(domain_key, []),
        _ROLE_TYPE_SKILLS.get(role_type, []) if role_type else [],
        _SENIORITY_OVERLAY.get(seniority_key, []),
    ]:
        for skill in pool:
            if skill in inferred_set and skill not in seen_inferred:
                inferred_ordered.append(skill)
                seen_inferred.add(skill)

    # ── Assemble skills_final ─────────────────────────────────────────────────
    # Hard skills first (extracted hard + inferred hard), then soft skills last.
    # Soft skills that are inferred (e.g. "Communication" from seniority overlay)
    # are kept in skills_inferred for transparency but placed in the soft bucket
    # in skills_final so they never displace hard skills.
    # Cap: 20 hard slots + 5 soft slots = 25 total
    inferred_hard = [s for s in inferred_ordered if s not in _SOFT_SKILLS]
    inferred_soft = [s for s in inferred_ordered if s in _SOFT_SKILLS]
    hard_final = (extracted_hard + inferred_hard)[:20]
    soft_final = (extracted_soft + inferred_soft)[:5]
    final = hard_final + soft_final

    confidence = _compute_confidence(len(extracted_hard), len(extracted_soft),
                                     len(inferred_ordered))

    return SkillEnrichment(
        extracted=extracted,
        normalized=normalized,
        inferred=inferred_ordered,
        final=final,
        confidence=confidence,
        source_version=SKILL_ENRICHER_VERSION,
    )
