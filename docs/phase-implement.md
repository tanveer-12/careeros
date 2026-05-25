Phase 1: DB + Schema + Local Imports
Goal:
Get lumia_dev clean, schema.sql running, and ingestion able to read Remotive → jobs in.

Tasks
In pgAdmin:

Drop lumia_dev (if you want a clean reset).

Recreate lumia_dev (same name, UTF8, your user).

Run database/migration/schema.sql once on lumia_dev → wait for no errors.

Verify in pgAdmin:

public schema → Tables → all tables (jobs, job_embeddings, clustering_runs, role_clusters, job_cluster_memberships, user_resumes, resume_embeddings, rankings, two_week_plans, two_week_plan_steps).

Data Types → job_source, employment_type, etc., are present.

In database/models/:

Confirm jobs.py uses column source: Mapped[enums.JobSource].

Confirm two_week_plans.py uses week_plan_status enum.

In pyproject.toml:

Confirm sqlalchemy[asyncio], asyncpg, pgvector are installed.

If schema.sql is correct, no code changes needed here.

## Phase 2: Core Ingestion Flow (jobs → embeddings → clustering → rankings)
Goal:
From Remotive → jobs → job_embeddings → clustering_runs + role_clusters + job_cluster_memberships → test UserResume → rankings.

Tasks
In core/collectors/api_scrapers/remotive.py:

URL endpoint for HTTP Request
GET https://remotive.com/api/remote-jobs

Optional Querystring Parameters
Following optional querystring parameters can be used to filter job listings.

Parameter	Description	Example
category	Retrieve jobs only for this category. Category name or category slug must be provided here. Existing categories are available at this endoint.	https://remotive.com/api/remote-jobs?category=software-dev
company_name	Filter by company name. Case insensitive, partial match ('ilike') will be used here to filter job listings based on provided company name.	https://remotive.com/api/remote-jobs?company_name=remotive
search	Search job listing title and description. Case insensitive, partial match ('ilike') will be used here to filter job listings.	https://remotive.com/api/remote-jobs?search=front%20end
limit	Limit the number of job listing results (default: all). An integer must be provided.	https://remotive.com/api/remote-jobs?limit=5
Response
For example, the following request:

curl 'https://remotive.com/api/remote-jobs?limit=1'

Would return a JSON response with the following format:

{
    "0-legal-notice": "Remotive API Legal Notice",
    "job-count": 1, # Number or jobs matching the query == length of 'jobs'list
    "jobs": # The list of all jobs retrieved.
    [
        # Then for each job, you get:
        {
            # Unique Remotive ID
            "id": 123, 
            # Job listing detail url
            "url": "https://remotive.com/remote-jobs/product/lead-developer-123", 
            # Job title
            "title": "Lead Developer", 
            # Name of the company which is hiring
            "company_name": "Remotive", 
            # URL to the company logo
            "company_logo": "https://remotive.com/job/123/logo", 
             # See https: # https://remotive.com/api/remote-jobs/categories for existing categories
            "category": "Software Development",
            # full_time/contract/part_time/freelance/internship here.It 's optional and often not filled.
            "job_type": "full_time", 
            # Publication date and time on remotive.com
            "publication_date": "2020-02-15T10:23:26",
            # Geographical restriction for the remote candidate, if any.
            "candidate_required_location": "Worldwide", 
            # salary description, usually a yearly salary range, in USD. Optional.
            "salary": "$40,000 - $50,000", 
            # HTML full description of the job listing
            "description": "The full HTML job description here", 
        },
    ]
}

Confirm RemotiveScraper.fetch_jobs_page(...) and get_fresh_jobs(...) talk to https://remotive.com/api/remote-jobs and return jobs list.

Confirm hours_fresh is set to 24.

In core/workflows/pipeline.py:

Implement run_ingest_pipeline():

Uses RemotiveScraper → raw_jobs.

For each raw_job, call Job.from_remotive(raw_job) → insert into DB.

Call run_ingest_pipeline() from cli.commands.ingest.ingest() → CLI lumia ingest.

In database/models/jobs.py:

Implement Job.from_remotive(raw: dict) -> Job:

Map raw["id"] → external_id.

Map raw["title"] → title.

Map raw["company_name"] → company.

Map raw["candidate_required_location"] → location.

Map raw["job_type"] → employment_type.

Map raw["description"] → description.

Map raw["salary"] → salary_min / salary_max (if you want).

Map raw["category"] → domain.

Map raw["publication_date"] → posted_at (as datetime).

In core/embeddings/job_embedder.py:

Confirm job_embedder.JobEmbedder uses sentence‑transformers + BAAI/bge‑small‑en.

Implement embed_job(job: Job) -> job_embeddings:

Input text = job.title + " " + job.description + " " + join(job.skills).

Compute bge‑small‑en embedding → store in job_embeddings with model = "bge-small-en".

Mark job.status = "embedded" (optional, can be skipped).

In core/clustering/kmeans.py:

Implement KMeansClustering:

Query all job_embeddings for latest model.

Run K‑Means (e.g., k=10).

For each cluster: write role_clusters with centroid = cluster.center.tolist().

For each job → job_cluster_memberships (distance to centroid).

In core/ranking/career_mapper.py:

Implement CareerMapper:

Take UserResume → compute resume_embedder.resume_to_job_similarity(resume: UserResume, clusters: List[RoleCluster]) -> List[Ranking].

Implement resume_embedding generation (same bge‑small‑en).

Implement Ranking creation (cosine‑similarity, fit_category, skill_gaps, skill_matches).

At the end of this phase:

lumia ingest → lumia analyze → lumia status gives you rankings and 2‑week plan for a test UserResume.

Phase 3: FastAPI Endpoints (backend‑only, no UI yet)
Goal:
Expose jobs, clusters, and two_week_plan as JSON APIs, without any frontend running.

Files to change / create
api/: create if not existing.

api/main.py: FastAPI app + routers.

api/routers/jobs.py.

api/routers/clusters.py.

api/routers/plan.py.

Tasks
In api/main.py:

Create app = FastAPI().

Mount jobs, clusters, plan routers.

Add CORS middleware (allow localhost:5173).

In api/routers/jobs.py:

Implement GET /jobs:

Query jobs table → return List[Job] (DTO format).

Implement GET /jobs/count → count.

In api/routers/clusters.py:

Implement GET /clusters:

Return List[RoleCluster].

Implement GET /clusters/best-for-resume/{resume_id}:

Query rankings → filter by resume_id, order by cosine_similarity → return top N clusters.

In api/routers/plan.py:

Implement GET /plan/{resume_id}/{cluster_id}:

Query two_week_plan + two_week_plan_steps → return JSON tree.

Implement POST /plan (optional, if you want web to trigger plan generation).

After this phase:

You can test:

curl http://localhost:8000/api/clusters

curl http://localhost:8000/api/plan/abc123/xyz789

and see JSON. No UI needed yet.

Phase 4: Web‑app Setup (Vite + React + Tailwind + Framer‑Motion + your palette)
Goal:
No‑code‑yet web‑app skeleton with:

Nice layout

Animation for logo + sections

Color palette applied

Routes defined

Proxy to FastAPI

Files to create / change
web/vite.config.ts.

web/tailwind.config.ts.

web/index.css.

web/src/App.tsx.

web/src/pages/LandingPage.tsx.

web/src/pages/UploadPage.tsx.

web/src/pages/PlanPage.tsx.

Tasks
In web/:

npm create vite@latest . --template react-ts

npm install -D tailwindcss postcss autoprefixer

npx tailwindcss init -p

npm install framer-motion

In web/tailwind.config.ts:

Define background, text, contrast, accent, accentSecondary from your palette.

Set font-family for display and body.

In web/index.css:

Include @tailwind base; @tailwind components; @tailwind utilities;

Set body to background: #fffaf1, color: #3a0303.

In web/vite.config.ts:

Add proxy to http://localhost:8000 for /api.

In web/src/App.tsx:

Define BrowserRouter + routes:

/ → LandingPage

/upload → UploadPage

/plan/:resumeId/:clusterId → PlanPage

In web/src/pages/LandingPage.tsx:

Implement hero section:

Animated Lumia logo text (Framer‑Motion motion + animate + whileHover).

“Upload your resume” headline.

CTA button to /upload.

Use bg-background, text colors from Tailwind.

In web/src/pages/UploadPage.tsx:

Implement “Upload your resume” form:

File input.

Upload button → POST to /api/jobs (or /api/upload-resume).

Show loading bar / simulation.

On success, navigate('/plan/...') to a fake or real plan.

In web/src/pages/PlanPage.tsx:

Implement useEffect to fetch /api/plan/{resumeId}/{clusterId}.

Display plan.weeks as accordions / sections.

Use motion.div for slide‑in animation per week.

At the end of this phase:

You have a fully animated, modern web‑app that:

Uploads resume → backend → backend → plan generation.

Shows 2‑week plan with motion.

Phase 5: Hugging Face embedding + LLM‑only‑on‑demand
Goal:
No‑code‑yet understanding of where HF fits in.

Files to touch / concepts
core/embeddings/job_embedder.py.

core/embeddings/resume_embedder.py.

core/llm/client.py.

core/ranking/career_mapper.py (optional for on‑demand text explanations).

Tasks
In core/embeddings/...:

Use sentence‑transformers with BAAI/bge‑small‑en (no HF‑API key needed if you run locally).

Every time job or resume is created → generate embedding → store in DB.

In core/llm/client.py:

Keep LLM_ENABLED → optional.

When LLM_ENABLED=True, connect to:

HF Inference API (with key), or

Local HF model (via text‑generation‑inference / llama.cpp / llm-engine).

Only call for:

generate_ai_explanation(ranking) (optional “AI‑style explanation”).

generate_plan_step_explanation(step) (if you want).

In core/ranking/career_mapper.py:

For rankings:

Show template‑based summary (no LLM).

When user wants “AI‑style explanation” → call llm_client → get reasoning text.

This keeps everything domain‑agnostic and LLM‑only‑on‑demand, which matches your design constraints.