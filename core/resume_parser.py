"""Lightweight DOCX resume parser — no LLM, no perfect section parsing.

Produces raw_text, skills (keyword match), experience_years (year-range heuristic),
and current_or_last_role (regex on first 600 chars).
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path


SKILLS = [
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl", "Elixir",
    "Haskell", "Clojure",
    # Frontend
    "React", "Vue.js", "Angular", "Next.js", "Svelte", "HTML", "CSS",
    "Tailwind CSS", "Redux", "GraphQL", "REST",
    # Backend
    "Node.js", "FastAPI", "Django", "Flask", "Spring Boot", "Express.js",
    "Rails", ".NET", "Laravel", "ASP.NET", "gRPC",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "DynamoDB", "SQLite", "Snowflake", "BigQuery", "Redshift", "Databricks",
    "Pinecone", "Weaviate", "ChromaDB",
    # Cloud & DevOps
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Ansible",
    "CI/CD", "GitHub Actions", "Jenkins", "Helm", "Linux", "Git", "Pulumi",
    "Cloudflare", "Nginx", "Prometheus", "Grafana",
    # Data Engineering
    "Spark", "Airflow", "Kafka", "dbt", "Hadoop", "Flink", "RabbitMQ",
    "Celery", "Hive", "Presto", "Trino", "Fivetran", "Stitch",
    # ML & AI
    "TensorFlow", "PyTorch", "scikit-learn", "Keras", "Hugging Face",
    "LangChain", "XGBoost", "LightGBM", "pandas", "NumPy", "CUDA", "JAX",
    "MLflow", "OpenAI", "LLM", "NLP", "Computer Vision", "RAG",
    "Reinforcement Learning", "Feature Engineering", "Model Deployment",
    "Weights & Biases", "SageMaker", "Vertex AI",
    # Analytics & BI
    "SQL", "Tableau", "Power BI", "Looker", "Excel", "Google Analytics",
    "Mixpanel", "Amplitude", "Segment", "dbt",
    # Design
    "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator", "InDesign",
    "After Effects", "Premiere Pro", "Canva",
    # Product & Collaboration
    "Agile", "Scrum", "Jira", "Confluence", "Notion", "Asana", "Linear",
    # Marketing & Sales
    "Salesforce", "HubSpot", "Marketo", "SEO", "SEM", "Google Ads",
    "Meta Ads", "Copywriting", "Content Marketing", "Email Marketing",
    # Finance & Legal
    "Financial Modeling", "Valuation", "Bloomberg", "QuickBooks", "SAP",
    # HR & People
    "Workday", "BambooHR", "Greenhouse", "Lever",
]

_YEAR_RANGE = re.compile(
    r'\b(20\d{2})\s*[-–—]\s*(20\d{2}|present|current|now)\b',
    re.IGNORECASE,
)

_TITLE_PATTERN = re.compile(
    r'\b('
    # Engineering
    r'software engineer|senior engineer|staff engineer|principal engineer|'
    r'frontend developer|backend developer|full[\s\-]?stack developer|'
    r'devops engineer|platform engineer|site reliability engineer|sre|'
    r'mobile developer|ios developer|android developer|'
    r'security engineer|cloud engineer|infrastructure engineer|'
    # Data & ML
    r'data scientist|ml engineer|machine learning engineer|ai engineer|'
    r'data engineer|analytics engineer|data analyst|business analyst|'
    r'research scientist|applied scientist|'
    # Product & Design
    r'product manager|product designer|ux designer|ui designer|'
    r'ux researcher|design lead|'
    # Leadership
    r'engineering manager|tech lead|team lead|cto|vp of engineering|'
    r'director of engineering|head of engineering|'
    # Other
    r'solutions architect|cloud architect|data architect|'
    r'marketing manager|growth manager|sales manager|account executive|'
    r'customer success manager|operations manager|finance manager'
    r')\b',
    re.IGNORECASE,
)


@dataclass
class ParsedResume:
    raw_text: str
    skills: list[str] = field(default_factory=list)
    experience_years: float = 0.0
    current_or_last_role: str | None = None


def parse_resume(file_path: str | Path) -> ParsedResume:
    """Parse a DOCX file into structured resume data."""
    from docx import Document  # deferred import

    doc = Document(str(file_path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    raw_text = _normalize_text("\n".join(paragraphs))

    return ParsedResume(
        raw_text=raw_text,
        skills=_extract_skills(raw_text),
        experience_years=_estimate_experience(raw_text),
        current_or_last_role=_detect_role(raw_text),
    )


def _normalize_text(text: str) -> str:
    text = text.replace('\x00', '').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _extract_skills(text: str) -> list[str]:
    lower = text.lower()
    return [s for s in SKILLS if s.lower() in lower]


def _estimate_experience(text: str) -> float:
    current_year = datetime.datetime.now().year
    total = 0.0
    for start_str, end_str in _YEAR_RANGE.findall(text):
        start = int(start_str)
        end = current_year if end_str.lower() in ('present', 'current', 'now') else int(end_str)
        duration = end - start
        if 0 < duration <= 20:
            total += duration
    return min(total, 40.0)


def _detect_role(text: str) -> str | None:
    m = _TITLE_PATTERN.search(text[:600])
    return m.group(0).title() if m else None
