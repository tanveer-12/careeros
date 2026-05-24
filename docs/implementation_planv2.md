# Lumia: Career‑clarity OS – Implementation Plan v2

**Goal:** Build a local‑first career‑intelligence system that maps user resumes against job‑market archetypes, then **generates prioritized learning paths** and micro‑action plans to unlock those roles, without relying on paid OpenAI API keys.  

**Data focus:**  
- Remote‑focused sources only (Remotive, plus optional future APIs). [web:3][web:6]  
- Embeddings via Hugging Face / local models (e.g., `Supabase/bge‑small‑en`). [web:53][web:59]  


---

## 1. Product vision

- **What Lumia is:**  
  - A personal career‑clarity OS that helps users answer:  
    - “Which kinds of roles fit me best?”  
    - “What should I learn to get there?”  
    - “What should I write on my resume and LinkedIn each week?”  

- **Scope boundaries:**  
  - Focus on **learning‑path‑driven growth**, not just job‑ranking.  
  - Use **Remotive** as the primary job‑data source; Greenhouse / Lever / Ashby are removed entirely. [web:3][web:6]  
  - Replace paid‑API embeddings with **Hugging Face / local models** (e.g., `Supabase/bge‑small‑en` via TEI). [web:53][web:59]  


---

## 2. High‑level architecture

Organize the system into four logical layers:

### Layer 1: Job‑data ingestion (Remotive‑only in MVP)

- Ingest job postings from:
  - **Remotive** (remote‑focused, structured fields) — the **only** source in MVP. [web:3][web:6]  
- Normalize each job into:
  - Title, company, location(s), remote/hybrid/onsite, experience level, skills/tags.  
- Store in PostgreSQL for later use.  

### Layer 2: Embedding & clustering

- Use a **local Hugging Face embedding model** (e.g., `Supabase/bge‑small‑en`) to generate embeddings for each job text. [web:53][web:59]  
- Store embeddings in PostgreSQL using `pgvector`. [web:54]  
- Run clustering (K‑means or HDBSCAN) on job embeddings to discover natural role archetypes. [web:5][web:29]  
- For each cluster:
  - Assign a human‑readable archetype label (e.g., “ML Platform Engineering”, “Analytics Engineer”).  
  - Extract a list of key skills and responsibilities from the cluster’s jobs.  

### Layer 3: Resume‑to‑market mapping

- Support user resumes in:
  - Plain‑text or PDF.  
  - Store parsed sections: skills, experience, projects, education. [web:12]  
- Embed the resume using the **same HF model** as the jobs, then:
  - Compute a weighted embedding (prioritizing skills and experience).  
- Compute cosine similarity between the resume embedding and each archetype centroid. [web:7][web:29]  
- Rank archetypes by relevance and compute:
  - Skill‑match score (skills in resume vs archetype).  
  - **Skill‑gap list (skills in archetype but not in resume)** — this is the **core learning‑input**.  

### Layer 4: Learning‑path‑driven execution plan

- For a given user:
  - Inputs:
    - Resume.  
    - Selected archetype(s) and target constraints.  
  - Outputs:
    - **A 3–12‑week learning path** per key skill gap, e.g.:
      - “Learn dbt basics → 4 weeks”  
      - “Build 1 end‑to‑end ML pipeline project → 6 weeks”  
      - “Add 2 CI/CD examples to your resume → 1 week”  
    - For each week:
      - **Concrete micro‑actions**:
        - “Rewrite project X to emphasize MLOps / CI‑CD / data‑governance.”  
        - “Add Y to your resume bullets.”  
        - “Draft a LinkedIn post about X trend to signal your alignment.”  
      - **Resources** (optional, but valuable):
        - Links to free courses, docs, tutorials aligned with the skill gap (e.g., “Free SQL course on Khan Academy”, “dbt docs” etc.). [web:24]  
    - **One‑click reminders**:
      - “After you finish this week, you can update your LinkedIn to reflect X.”  
      - “Update this resume section once you complete Y.”  

---

## 3. MVP‑phase roadmap (learning‑path‑first)

### Phase 1: Data layer & ingestion (no ATS)

(Keep same as your current Phase 1, but explicitly state:)

- **No Greenhouse / Lever / Ashby scrapers.**  
- **Only Remotive‑based ingestion.**  

---

### Phase 2: Vector embeddings & clustering

(Keep same as before, but keep in mind this is feeding the **learning‑path engine**, not just job‑ranking.)

---

### Phase 3: Resume‑to‑market mapping + skill‑gaps

- **Emphasize:**
  - The **skill‑gap list** is the **primary input** into the learning‑path generator.  
  - For each archetype, the system outputs:
    - “You need to learn: A, B, C.”  
    - “You already have: X, Y.”  

---

### Phase 4: Learning‑path‑engine design

- **Define a “learning‑path” schema:**
  - Fields:
    - `skill_gap`  
    - `recommended_resource_links` (URLs, optional)  
    - `estimated_weeks`  
    - `weekly_actions` (array of micro‑tasks)  
- **Implement a path‑generator function:**
  - For each skill gap:
    - Decide level: “intro”, “intermediate”, “project‑level”.  
    - Generate:
      - Recommended resources (free‑tier where possible).  
      - Micro‑actions (e.g., “Build Z”, “Rewrite Q”).  
- **Store learning‑paths** in the DB (e.g., `learning_paths`, `learning_path_steps`).  

### Phase 5: Weekly execution plan (2‑week learning‑focused)

- Implement a “2‑week plan” generator that:
  - Takes:
    - User’s resume.  
    - Skill‑gap list.  
    - Current archetype(s).  
  - Outputs:
    - A **2‑week plan**:
      - **Week 1:**
        - 1–2 learning tasks (e.g., “Start course X”, “Read docs for Y”, “Build Z”).  
        - 1–2 writing / LinkedIn tasks:
          - “Rewrite resume bullet for project A to emphasize B.”  
          - “Draft a LinkedIn post about starting X.”  
      - **Week 2:**
        - 1–2 learning tasks (e.g., “Finish module 1 of X”, “Build 1 mini‑project”).  
        - 1–2 writing / LinkedIn tasks:
          - “Add completed X to your resume bullets.”  
          - “Draft a follow‑up LinkedIn post about what you learned.”  
        - Optional:
          - 0–1 “apply”‑type tasks:
            - “Apply to 2–3 roles that match archetype X.”  
  - The **2‑week plan is the default and only option in MVP**.  
  - Long‑term plans (4–8–12 weeks) will be added in future stages.

- Expose:
  - A simple API / UI view that shows:
    - “2‑week learning‑and‑writing plan: learning + writing + optional apply.”  
  - Clear labels:
    - “This is a 2‑week starter plan. Extended plans will come later.”

### Phase 6: Light‑themed web‑app prototype (learning‑journey UI)

- Implement a minimal UI where the user:
  - Uploads a resume.  
  - Views:
    - Top archetypes.  
    - Skill‑gap list.  
    - Full learning path (timeline).  
    - Weekly plan.  
- Use:
  - **Light‑themed, soothing design** with **clear sections** for:
    - “Your archetypes”  
    - “Skill gaps → Learning path”  
    - “This week’s plan (learn + write + LinkedIn)”  
- Add:
  - Simple “mark as done” for weekly tasks.  
  - Optional “Add LinkedIn‑post‑draft” suggestions.  

---

## 4. Non‑functional considerations

- **Focus on “learning as the core metric”:**
  - User progress is tracked by:
    - Weeks completed.  
    - Skill‑gap resolution (e.g., “You’ve closed 4 of 7 gaps”).  
- **Keep job‑data secondary;**
  - The “apply”‑side of the plan is **optional**, not the core value.  

---

## 5. Git / branch strategy

- Keep `main` as the “source of truth”.  
- Use `refactor/v2-dev` to:
  - Remove ATS scrapers.  
  - Add `learning_paths` / `learning_path_steps` tables.  
  - Build the **learning‑path‑engine** and **LinkedIn‑suggestion logic**.  
- When stable, merge back to `main`.  