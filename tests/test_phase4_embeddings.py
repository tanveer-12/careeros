"""
tests/test_phase4_embeddings.py

Verification tests for Phase 4.
Run after embed_jobs() and embed_resume() to confirm everything works.

Usage:
    # Test job embedding only
    python tests/test_phase4_embeddings.py

    # Test job + resume embedding
    python tests/test_phase4_embeddings.py <resume_id>
"""

import asyncio
import logging
import sys
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


# ─────────────────────────────────────────────
# Test 1 — Model loads without error
# ─────────────────────────────────────────────

def test_model_loads():
    print("\n=== Test 1: Model loads ===")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vec = model.encode("Senior Mechanical Engineer at Boeing", normalize_embeddings=True)
    assert vec.shape == (384,), f"Expected 384 dims, got {vec.shape}"
    print(f"✓ Model loaded — vector shape: {vec.shape}")


# ─────────────────────────────────────────────
# Test 2 — Embed all unembedded jobs
# Expected: "N jobs embedded across M batches"
# ─────────────────────────────────────────────

async def test_embed_jobs():
    print("\n=== Test 2: embed_jobs() ===")
    from core.embeddings.job_embedder import JobEmbedder
    await JobEmbedder().embed_jobs()
    print("✓ embed_jobs() completed without exception")


# ─────────────────────────────────────────────
# Test 3 — Embed a single resume
# ─────────────────────────────────────────────

async def test_embed_resume(resume_id: str):
    print(f"\n=== Test 3: embed_resume({resume_id}) ===")
    from core.embeddings.resume_embedder import ResumeEmbedder
    ok = await ResumeEmbedder().embed_resume(resume_id)
    assert ok, "embed_resume() returned False — check logs above"
    print(f"✓ Resume {resume_id} embedded")


# ─────────────────────────────────────────────
# Test 4 — Idempotency: calling twice produces no duplicates
# ─────────────────────────────────────────────

async def test_idempotency(resume_id: str):
    print(f"\n=== Test 4: idempotency for resume {resume_id} ===")
    from core.embeddings.resume_embedder import ResumeEmbedder
    e = ResumeEmbedder()
    r1 = await e.embed_resume(resume_id)
    r2 = await e.embed_resume(resume_id)  # should skip with a log message
    assert r1 and r2, "Both calls must return True"
    print("✓ Second call was a no-op (idempotent)")


# ─────────────────────────────────────────────
# Test 5 — Same-domain similarity > cross-domain similarity
# (sanity check that the vector space makes sense)
# ─────────────────────────────────────────────

def test_cosine_sanity():
    """
    Quick in-memory cosine similarity check — no DB needed.
    Two mechanical engineering job titles should be closer to each other
    than either is to an investment banking title.
    """
    print("\n=== Test 5: cosine similarity sanity ===")
    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [
        "Senior Mechanical Engineer at Boeing in Seattle",       # [0] mech eng
        "Mechanical Design Engineer at SpaceX in Hawthorne",    # [1] mech eng
        "Investment Banking Analyst at Goldman Sachs in NYC",   # [2] finance
    ]
    vecs = model.encode(texts, normalize_embeddings=True)

    sim_same  = float(np.dot(vecs[0], vecs[1]))  # mech vs mech
    sim_cross = float(np.dot(vecs[0], vecs[2]))  # mech vs finance

    print(f"  mech vs mech:    cosine = {sim_same:.3f}  (expect > 0.55)")
    print(f"  mech vs finance: cosine = {sim_cross:.3f}  (expect < 0.50)")

    assert sim_same  > 0.55, f"Same-domain similarity too low: {sim_same:.3f}"
    assert sim_cross < 0.50, f"Cross-domain similarity too high: {sim_cross:.3f}"
    assert sim_same  > sim_cross, "Same-domain must score higher than cross-domain"
    print("✓ Vector space is semantically coherent")


# ─────────────────────────────────────────────
# SQL checks to run in pgAdmin after the tests
# ─────────────────────────────────────────────

SQL_CHECKS = """
-- How many jobs have embeddings?
SELECT COUNT(*) FROM job_embeddings;

-- Spot check: title + domain + vector present
SELECT j.title, j.domain, cardinality(je.embedding) AS dims
FROM jobs j
JOIN job_embeddings je ON je.job_id = j.id
LIMIT 5;

-- Cross-domain similarity (should be LOW, < 0.5)
SELECT j1.title, j2.title,
       1 - (je1.embedding <=> je2.embedding) AS similarity
FROM job_embeddings je1
JOIN job_embeddings je2 ON je1.job_id != je2.job_id
JOIN jobs j1 ON j1.id = je1.job_id
JOIN jobs j2 ON j2.id = je2.job_id
WHERE j1.domain = 'mechanical engineering'
  AND j2.domain = 'investment banking'
LIMIT 5;

-- Same-domain similarity (should be HIGH, > 0.7)
SELECT j1.title, j2.title,
       1 - (je1.embedding <=> je2.embedding) AS similarity
FROM job_embeddings je1
JOIN job_embeddings je2 ON je1.job_id != je2.job_id
JOIN jobs j1 ON j1.id = je1.job_id
JOIN jobs j2 ON j2.id = je2.job_id
WHERE j1.domain = 'mechanical engineering'
  AND j2.domain = 'mechanical engineering'
LIMIT 5;
"""

async def main():
    test_model_loads()
    test_cosine_sanity()
    await test_embed_jobs()
    if len(sys.argv) > 1:
        rid = sys.argv[1]
        await test_embed_resume(rid)
        await test_idempotency(rid)

if __name__ == "__main__":
    asyncio.run(main())
# if __name__ == "__main__":
#     # Test 1 and 5 are synchronous — run immediately
#     test_model_loads()
#     test_cosine_sanity()

#     # Test 2: embed all jobs
#     asyncio.run(test_embed_jobs())

#     # Tests 3 & 4: need a real resume_id
#     if len(sys.argv) > 1:
#         rid = sys.argv[1]
#         asyncio.run(test_embed_resume(rid))
#         asyncio.run(test_idempotency(rid))
#     else:
#         print("\n(Skipping resume tests — pass a resume_id as argument)")
#         print("  python tests/test_phase4_embeddings.py <resume_id>")

#     print("\n✓ All tests passed.")
#     print("\nRun these SQL checks in pgAdmin to verify DB state:")
#     print(SQL_CHECKS)
