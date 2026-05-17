# Agent 3 — Strategy & Execution Agent

**Layer:** Decision (Layer 3)  
**File:** `decision_layer/strategy_execution_agent.py`

---

## Responsibility

Owns the decision layer. Reads final rankings from Agent 2 and converts them into specific, executable outputs: a prioritized job target list, tailored resume variants, a weekly action plan, and a structured export dataset.

This agent does not re-rank, re-embed, or call the scraper. It reads from `rankings` and writes to `execution_plans`. All LLM calls in this agent are generative — resume writing and plan generation — not analytical.

---

## Input

```python
resume:    Resume          # ORM object with skills[], raw_text, current_title
db:        AsyncSession    # active database session
```

Rankings are read from the `rankings` table filtered by `resume.id`. The agent expects at least one ranking row to exist. If none exist, it raises immediately — it does not trigger Agent 2.

---

## Output

**`execution_plans` table — one row per analysis run:**

```
id · resume_id · created_at · plan (JSON)
```

The `plan` JSON object has this fixed schema:

```json
{
  "weekly_actions": [
    {
      "priority": 1,
      "category": "apply | resume | skill | network",
      "action": "string — specific instruction",
      "time_estimate": "string — e.g. '45 min'"
    }
  ],
  "top_jobs": [
    {
      "job_id": "uuid",
      "title": "string",
      "company": "string",
      "url": "string",
      "cluster": "string — cluster label",
      "fit_reason": "string — 1–2 sentences"
    }
  ],
  "resume_variants": {
    "<cluster_label>": {
      "tailored_summary": "string — rewritten professional summary",
      "skills_to_emphasize": ["string"],
      "bullet_suggestions": ["string — specific rewrite instructions"],
      "full_text": "string — complete resume text with modifications applied"
    }
  },
  "skill_development": [
    {
      "skill": "string",
      "priority": "high | medium | low",
      "resource": "string — specific course, project, or resource suggestion"
    }
  ]
}
```

Also writes to the filesystem under `settings.output_dir`:
```
career_report.json
career_report.xlsx
resume_<cluster_label>.txt   (one per strong/adjacent cluster)
```

---

## Logic

### Step 1 — Load and filter rankings

Query `rankings` for the given `resume_id`, ordered by `cosine_similarity` descending.

Filter to the top `MAX_CLUSTERS_IN_PLAN` clusters (default: 3) that are not `fit_category == "weak"`. If fewer than 2 non-weak clusters exist, include the top weak clusters with an explicit caveat added to their reasoning.

### Step 2 — Select top jobs per cluster

For each selected cluster:

1. Query `job_cluster_memberships` for member job IDs
2. Sort by `distance_to_centroid` ascending (nearest to centroid = most representative)
3. Select the top `TOP_JOBS_PER_CLUSTER` (default: 3) jobs
4. Generate a 1–2 sentence `fit_reason` per job via LLM, grounded in the resume's skills and the job's domain

The LLM prompt for `fit_reason` receives: job title, company, top 5 skills from the job description, and the top 3 matching skills from the resume. Temperature: 0.3.

### Step 3 — Generate resume variants

For each selected cluster, generate one resume variant. The variant does NOT rewrite the entire resume. It produces:

1. **`tailored_summary`** — a rewritten professional summary (3–5 sentences) that leads with domain alignment, references the cluster's top skills that match the resume, and omits domain-irrelevant experience
2. **`skills_to_emphasize`** — intersection of `ranking.skill_matches` and the cluster's `top_skills`, ordered by cluster prevalence
3. **`bullet_suggestions`** — 2–4 specific rewrite instructions for existing resume bullets (e.g. "Reframe your Airflow work to lead with scheduling and pipeline reliability rather than implementation detail")
4. **`full_text`** — base `resume.raw_text` with the `tailored_summary` substituted for the original summary section

The LLM prompt for variant generation receives: full resume text, cluster label, cluster top skills, resume skill matches and gaps. Model: `gpt-4o-mini`. Temperature: 0.5. The prompt explicitly instructs the model not to fabricate skills or experience.

### Step 4 — Build weekly action list

Actions are generated deterministically from the plan data — not by LLM. The ordering logic:

1. **Apply** actions first — one per top job, ordered by `cosine_similarity` of their cluster
2. **Resume** actions — one per variant (update summary, emphasize listed skills)
3. **Skill** actions — one per top skill gap, prioritized: `high` if gap appears in >60% of cluster jobs, `medium` if >30%, `low` otherwise
4. **Network** actions — one generic action per selected cluster (e.g. "Join the dbt Slack and post in #show-and-tell")

Each action includes a `time_estimate` derived from action type: apply (30 min), resume edit (45 min), skill (2–4 hrs), network (30 min).

### Step 5 — Persist and export

1. Write `ExecutionPlan` row to `execution_plans` table
2. Call export system to write `career_report.json`, `career_report.xlsx`, and one `.txt` file per resume variant

If the DB write succeeds but the filesystem write fails, the exception is surfaced — the plan is already persisted and can be re-exported without re-running the agent.

---

## Failure Cases

| Failure | Behavior |
|---|---|
| No rankings exist for resume | Raise `ValueError`: "Run career mapping before generating a plan" |
| All rankings are `fit_category == "weak"` | Include top 2 weak clusters; prepend explicit caveat to each variant and all weekly actions |
| No jobs exist in a winning cluster | Skip job selection for that cluster; log warning; select replacement jobs from the adjacent cluster with next-highest similarity |
| LLM `fit_reason` generation fails for a job | Set `fit_reason` to the cluster's `reasoning` field as a fallback; continue |
| LLM resume variant generation fails for a cluster | Store variant with `tailored_summary = None` and `full_text = resume.raw_text`; mark variant as `ungenerated` in the JSON |
| Output directory is not writable | Raise `OSError` with the full path; plan is already in DB and can be re-exported once permissions are fixed |
| Excel export fails | Log error, skip `.xlsx` write, continue — JSON and `.txt` files still written |
| DB commit fails | SQLAlchemy rolls back; no `ExecutionPlan` row written; filesystem writes are NOT rolled back (idempotent — re-run will overwrite) |