"""
core/clustering/reducer.py

UMAP dimensionality reduction for job embeddings.

Rules:
- 5-dim output is used as HDBSCAN input (tighter cluster packing, more stable).
- 2-dim output is used for visualization only (stored in job_cluster_memberships).
- The 384-dim vectors in job_embeddings remain the canonical representation for
  cosine retrieval. UMAP coordinates are ephemeral and tied to a specific run.
- min_dist=0.0 packs clusters tightly — this is intentional for HDBSCAN.
  Do not increase it without re-tuning HDBSCAN min_cluster_size.
"""
import logging
import numpy as np
from umap import UMAP

logger = logging.getLogger("lumia.clustering.reducer")


def reduce(matrix: np.ndarray, n_components: int = 5) -> np.ndarray:
    """
    Reduce a (n_jobs, 384) L2-normalized embedding matrix to (n_jobs, n_components).

    Args:
        matrix:       float32 array, shape (n_jobs, 384), L2-normalized
        n_components: 5 for HDBSCAN clustering input, 2 for 2-D visualization

    Returns:
        float32 array, shape (n_jobs, n_components)
    """
    logger.info("UMAP: %d jobs → %d dims", matrix.shape[0], n_components)
    reducer = UMAP(
        n_components = n_components,
        n_neighbors  = 15,
        min_dist     = 0.0,       # 0.0 packs clusters tightly; best for HDBSCAN
        metric       = "cosine",
        random_state = 42,
        low_memory   = False,
    )
    out = reducer.fit_transform(matrix).astype(np.float32)
    logger.info("UMAP complete — output shape: %s", out.shape)
    return out
