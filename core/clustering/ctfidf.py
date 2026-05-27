"""
core/clustering/ctfidf.py

BERTopic-style class-based TF-IDF (c-TF-IDF) for archetype keyword extraction.

Standard TF-IDF finds terms frequent in one document vs. all others.
c-TF-IDF treats each cluster as a single "class document" and finds terms
that are both frequent within a cluster AND distinctive across clusters.

Algorithm:
  1. Merge all job embedding texts in a cluster into one cluster document.
  2. Compute TF within each cluster document, normalized by cluster word count.
  3. Compute IDF across cluster documents (not individual jobs):
         idf(t) = log(1 + n_clusters / df(t))
     where df(t) = number of clusters containing term t.
  4. c-TF-IDF score = TF_normalized * IDF.
  5. Top-k terms per cluster are the most distinctive terms for that archetype.

This is functionally equivalent to BERTopic's c-TF-IDF without the BERTopic dep.
"""
import logging
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS

logger = logging.getLogger("lumia.clustering.ctfidf")


def extract_keywords(
    cluster_texts: dict[int, str],
    top_n: int = 15,
    extra_stop_words: set[str] | None = None,
) -> dict[int, list[str]]:
    """
    Extract the most distinctive keywords per cluster using c-TF-IDF.

    Args:
        cluster_texts: {cluster_label: concatenated text of all jobs in that cluster}
        top_n:         number of top keywords to return per cluster

    Returns:
        {cluster_label: [keyword, ...]} ordered by c-TF-IDF score descending
    """
    if not cluster_texts:
        return {}

    cluster_ids = sorted(cluster_texts.keys())
    docs        = [cluster_texts[ci] for ci in cluster_ids]

    stop_words = list(ENGLISH_STOP_WORDS | (extra_stop_words or set()))
    vectorizer = CountVectorizer(
        stop_words    = stop_words,
        ngram_range   = (1, 2),       # unigrams + bigrams: "data engineer", "machine learning"
        min_df        = 1,
        max_features  = 15_000,
        # keep tokens like "c++", ".net", "k8s", "devops"
        token_pattern = r"(?u)\b[a-zA-Z][a-zA-Z0-9+#\-\.]{1,}\b",
    )

    # Raw term frequency matrix: shape (n_clusters, vocab_size)
    tf_matrix = vectorizer.fit_transform(docs).toarray().astype(np.float64)

    # Normalize TF by total words in each cluster so large clusters don't dominate
    words_per_cluster = tf_matrix.sum(axis=1, keepdims=True)
    tf_norm           = tf_matrix / (words_per_cluster + 1e-9)

    # IDF computed across cluster documents — NOT individual job documents
    n_clusters = len(docs)
    df         = (tf_matrix > 0).sum(axis=0)            # (vocab_size,)
    idf        = np.log(1.0 + n_clusters / (df + 1.0))  # +1 smoothing

    ctfidf_matrix = tf_norm * idf  # (n_clusters, vocab_size)

    vocab  = vectorizer.get_feature_names_out()
    result = {}

    for i, ci in enumerate(cluster_ids):
        top_idx    = np.argsort(ctfidf_matrix[i])[::-1][:top_n]
        keywords   = [vocab[j] for j in top_idx]
        result[ci] = keywords
        logger.debug("Cluster %d c-TF-IDF top-5: %s", ci, keywords[:5])

    return result
