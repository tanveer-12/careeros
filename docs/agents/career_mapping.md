# Agent 2 — Career Mapping Agent

**Layer:** Intelligence (Layer 2)  
**File:** `docs/agents/career_mapping_agent.py`

---

## Responsibility

Owns the comparison between one resume and the job market clusters. Produces ranked career directions with similarity scores, skill gap analysis, and LLM-generated reasoning.

This agent reads from `role_clusters` (written by Agent 1) and writes to `rankings`. It does not select specific jobs, generate plans, or produce output files — those are Agent 3's responsibility.

---

## Input

```python
resume: Resume          # ORM object, already stored in PostgreSQL
db:     AsyncSession    # active database session
top_k:  int = 5        # how many clusters to generate LLM reasoning for
```

The `Resume` object must already have a corresponding row in `resume_embeddings`. If it does not, this agent raises immediately — it does not attempt to create the embedding.

---

## Output

**`rankings` table — one row per cluster:**
```
id · resume_id · cluster_id
cosine_similarity   float   # 0.0 – 1.0; higher = better fit
rank                int     # 1 = highest similarity
fit_category        str     # "strong" | "adjacent" | "weak"
skill_matches       list    # skills present in both resume and cluster
skill_gaps          list    # top cluster skills absent from resume (max 10)
reasoning           str     # LLM text; null for clusters outside top_k
created_at          datetime
```

Also returns `list[ClusterRanking]` to the caller — a dataclass wrapping the above fields plus the `RoleCluster` object for direct access without a second DB query.

---

## Logic

### Step 1 — Load embeddings

Load the resume's `vector(1536)` from `resume_embeddings`. Load all cluster centroids from `role_clusters`. Both are L2-normalized in memory before any computation.

### Step 2 — Cosine similarity

For each cluster:

```
similarity = dot( L2(resume_vec), L2(centroid_vec) )
```

After L2 normalization, the dot product is equivalent to cosine similarity. This avoids an explicit division and is numerically stable.

Results are sorted descending by similarity. Ranks are assigned 1-through-N after sorting.

### Step 3 — Fit categorization

| Threshold | Category | Interpretation |
|---|---|---|
| `similarity >= 0.75` | `strong` | High match; apply now |
| `similarity >= 0.60` | `adjacent` | Meaningful overlap; worth pursuing with minor gaps |
| `similarity < 0.60` | `weak` | Significant gap; long-term target only |

Thresholds are calibrated for `text-embedding-3-small` on job description + resume text. Adjust after observing the actual similarity distribution in your corpus — the right values depend on how diverse your job set is.

### Step 4 — Skill gap analysis

For each cluster, compute the union of skills across member jobs (capped at 50 sampled jobs for performance). Skills appearing in at least 20% of sampled jobs are treated as "cluster skills."

```
skill_matches = cluster_skills ∩ resume_skills
skill_gaps    = cluster_skills - resume_skills   (top 10 by prevalence)
```

`top_skills` is cached on the `RoleCluster` object within the session to avoid repeated queries when processing multiple resumes.

### Step 5 — LLM reasoning (top K only)

LLM reasoning is generated only for the top `top_k` clusters (default: 5). Reasoning for weak-fit clusters is rarely acted on, so this is a deliberate cost/quality tradeoff.

The prompt provides:
- Resume: current title, skills preview, structured summary
- Cluster: label and fit score
- Evidence: skill matches and top gaps

The model (`gpt-4o-mini`) is instructed to produce 3–4 sentences that are specific, honest, and actionable. Temperature is set to 0.4 — low enough for consistency, high enough to avoid formulaic phrasing.

### Step 6 — Persist

All rankings (with or without reasoning) are written to the `rankings` table in a single transaction. The caller receives the full `list[ClusterRanking]` regardless of DB write success — the exception propagates if the commit fails.

---

## Failure Cases

| Failure | Behavior |
|---|---|
| Resume has no embedding in DB | Raise `ValueError` immediately with message: "Run embedding before analysis" |
| No clusters exist in DB | Raise `ValueError` with message: "Run market intelligence pipeline first" |
| LLM reasoning call fails for one cluster | Set `ranking.reasoning = None`; ranking is valid and persisted without it |
| All LLM reasoning calls fail | All rankings stored with `reasoning = None`; no exception raised to caller |
| Cluster has no member jobs (empty cluster) | Skill gap analysis returns empty lists; similarity computation is unaffected |
| DB commit fails | SQLAlchemy rolls back; caller receives exception; no partial rankings written |
| Cosine similarity produces NaN (zero-norm vector) | Guard with `1e-8` denominator in normalization; NaN is replaced with 0.0 and logged |