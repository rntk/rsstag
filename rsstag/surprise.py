"""Bayesian Surprise computation for posts.

Based on Itti & Baldi (2009) "Bayesian surprise attracts human attention".
Surprise is the KL divergence between posterior and prior Dirichlet distributions.
"""

from typing import List, Dict, Tuple
import numpy as np
from scipy.special import digamma, gammaln
from collections import Counter, defaultdict


def _dirichlet_kl(alpha_posterior: np.ndarray, alpha_prior: np.ndarray) -> float:
    """KL divergence KL(Dir(alpha_posterior) || Dir(alpha_prior)).

    Closed-form solution using digamma and log-gamma functions.
    """
    sum_post = alpha_posterior.sum()
    sum_prior = alpha_prior.sum()

    kl = (
        gammaln(sum_post)
        - gammaln(sum_prior)
        - np.sum(gammaln(alpha_posterior) - gammaln(alpha_prior))
        + np.sum(
            (alpha_posterior - alpha_prior) * (digamma(alpha_posterior) - digamma(sum_post))
        )
    )
    return float(max(kl, 0.0))


class BayesianSurprise:
    """Compute Bayesian Surprise for a sequence of documents.

    Documents are processed in order. Each document updates the Dirichlet
    prior via Bayesian update, and the surprise is the KL divergence between
    prior and posterior for that document.

    Vocabulary is built incrementally: new words encountered in each document
    are added to the vocabulary and the Dirichlet prior is extended.

    Args:
        zeta: Forgetting factor (0 < zeta < 1). Prevents the prior from
              becoming too rigid over time. 0.7 recommended from Itti & Baldi.
        max_features: Maximum vocabulary size. Once reached, new words are ignored.
    """

    def __init__(self, zeta: float = 0.7, max_features: int = 5000):
        self.zeta = zeta
        self.max_features = max_features

    def compute(self, texts: List[str]) -> List[float]:
        """Return surprise score per document (same order as input texts).

        Vocabulary grows incrementally as new words appear.

        Args:
            texts: List of preprocessed (lemmatized, space-separated) document strings.

        Returns:
            List of surprise scores (floats), one per document.
        """
        if not texts:
            return []

        vocab: dict = {}  # word -> index
        alpha = np.ones(0, dtype=np.float64)
        scores = []

        for text in texts:
            words = text.split()
            if not words:
                scores.append(0.0)
                continue

            # Count words in this document
            local_counts: dict = {}
            for w in words:
                local_counts[w] = local_counts.get(w, 0) + 1

            # Register new words into vocabulary
            for w in local_counts:
                if w not in vocab and len(vocab) < self.max_features:
                    vocab[w] = len(vocab)
                    # Extend prior with uniform concentration = 1
                    alpha = np.append(alpha, 1.0)

            # Build count vector
            word_counts = np.zeros(len(vocab), dtype=np.float64)
            for w, c in local_counts.items():
                if w in vocab:
                    word_counts[vocab[w]] = c

            # Bayesian update: posterior = zeta * prior + word_counts
            alpha_posterior = self.zeta * alpha + word_counts

            surprise = _dirichlet_kl(alpha_posterior, alpha)
            scores.append(surprise)

            # Posterior becomes new prior
            alpha = alpha_posterior

        return scores


class TagBayesianSurprise:
    """Compute Bayesian Surprise at the tag level.

    Instead of operating on word distributions within documents, this operates
    on tag co-occurrence distributions. For each tag, we track a Dirichlet
    distribution over all other tags that co-occur with it. As new posts
    arrive chronologically, we update each tag's prior and measure surprise.

    A tag's surprise score reflects how much its co-occurrence pattern has
    shifted over the document stream — tags whose neighbors change unexpectedly
    score higher.

    Args:
        zeta: Forgetting factor (0 < zeta < 1).
    """

    def __init__(self, zeta: float = 0.7):
        self.zeta = zeta

    def compute(self, posts: List[List[str]]) -> Dict[str, float]:
        """Compute per-tag surprise scores from a chronological list of posts.

        Args:
            posts: List of tag-lists, one per post, in chronological order.
                   Each inner list contains the stemmed tags for that post.

        Returns:
            Dict mapping tag -> cumulative surprise score.
        """
        if not posts:
            return {}

        # Global tag vocabulary (incremental)
        tag_vocab: dict = {}  # tag -> index

        # Per-tag Dirichlet prior over co-occurring tags
        tag_alphas: dict = {}  # tag -> np.ndarray

        # Per-tag cumulative surprise
        tag_surprise: dict = defaultdict(float)  # tag -> total surprise
        tag_post_count: dict = defaultdict(int)  # tag -> number of posts seen

        for post_tags in posts:
            if len(post_tags) < 2:
                continue

            unique_tags = list(set(post_tags))

            # Register new tags
            for t in unique_tags:
                if t not in tag_vocab:
                    tag_vocab[t] = len(tag_vocab)
                    # Extend all existing priors
                    for existing_tag, alpha in tag_alphas.items():
                        tag_alphas[existing_tag] = np.append(alpha, 1.0)

            vocab_size = len(tag_vocab)

            for t in unique_tags:
                # Ensure this tag has a prior
                if t not in tag_alphas:
                    tag_alphas[t] = np.ones(vocab_size, dtype=np.float64)
                elif len(tag_alphas[t]) < vocab_size:
                    # Extend if vocab grew
                    diff = vocab_size - len(tag_alphas[t])
                    tag_alphas[t] = np.append(tag_alphas[t], np.ones(diff, dtype=np.float64))

                # Build co-occurrence counts for this tag in this post
                co_counts = np.zeros(vocab_size, dtype=np.float64)
                for other in unique_tags:
                    if other != t:
                        co_counts[tag_vocab[other]] = 1.0

                alpha = tag_alphas[t]
                alpha_posterior = self.zeta * alpha + co_counts

                surprise = _dirichlet_kl(alpha_posterior, alpha)
                tag_surprise[t] += surprise
                tag_post_count[t] += 1

                tag_alphas[t] = alpha_posterior

        # Return average surprise per tag
        result = {}
        for t in tag_surprise:
            if tag_post_count[t] > 0:
                result[t] = tag_surprise[t] / tag_post_count[t]
        return result


class LeaveOneOutSurprise:
    """Compute tag surprise using a leave-one-out approach.

    For each post, computes how surprising its tag co-occurrences are compared
    to the background formed by all other posts. This is order-independent and
    finds tags that are genuinely unusual in the corpus.
    """

    def __init__(self, smoothing: float = 1.0) -> None:
        self.smoothing: float = smoothing

    def _post_surprise(
        self,
        neighbors: np.ndarray,
        background_log_sum: float,
        background_total: int,
        vocabulary_size: int,
    ) -> float:
        """Sum the dense formula analytically, visiting only this post's neighbors."""
        smoothing: float = self.smoothing
        neighbor_count: int = len(neighbors)
        post_total: float = neighbor_count + smoothing * vocabulary_size
        background_denominator: float = background_total + smoothing * vocabulary_size
        original_logs: np.ndarray = np.log1p(neighbors / smoothing)
        remaining_logs: np.ndarray = np.log1p((neighbors - 1.0) / smoothing)
        # All unobserved coordinates share the smoothing value. Their log terms
        # cancel, leaving the row's log sum and corrections for this post only.
        numerator: float = float(
            neighbor_count * (1.0 + smoothing) * np.log1p(1.0 / smoothing)
            - smoothing * background_log_sum
            + smoothing * original_logs.sum()
            - (1.0 + smoothing) * remaining_logs.sum()
        )
        kl: float = float(
            np.log(background_denominator / post_total) + numerator / post_total
        )
        return max(kl, 0.0)

    def compute(self, posts: List[List[str]], post_idx: int = -1) -> Dict[str, float]:
        """Return leave-one-out scores without allocating a vocabulary-square matrix.

        post_idx selects a post after filtering out posts with fewer than two
        unique tags. Negative or out-of-range indices score all filtered posts.
        Memory grows with input tag occurrences and a single tag's neighbors.
        """
        post_sets: List[List[str]] = []
        tag_posts: Dict[str, List[int]] = defaultdict(list)
        for tags in posts:
            unique_tags: List[str] = list(dict.fromkeys(tags))
            if len(unique_tags) < 2:
                continue
            index: int = len(post_sets)
            post_sets.append(unique_tags)
            for tag in unique_tags:
                tag_posts[tag].append(index)
        if not post_sets:
            return {}

        selected_post: bool = 0 <= post_idx < len(post_sets)
        target_tags: List[str] = post_sets[post_idx] if selected_post else list(tag_posts)
        vocabulary_size: int = len(tag_posts)
        result: Dict[str, float] = {}
        for tag in target_tags:
            indices: List[int] = tag_posts[tag]
            if len(indices) < 2:
                continue
            # Keep just one co-occurrence row, and skip tags without a background.
            counts: Counter[str] = Counter()
            for index in indices:
                counts.update(post_sets[index])
            del counts[tag]
            row_counts: np.ndarray = np.fromiter(counts.values(), dtype=np.float64)
            background_log_sum: float = float(
                np.log1p(row_counts / self.smoothing).sum()
            )
            score_indices: List[int] = [post_idx] if selected_post else indices
            total_surprise: float = 0.0
            for index in score_indices:
                neighbors: np.ndarray = np.fromiter(
                    (counts[other] for other in post_sets[index] if other != tag),
                    dtype=np.float64,
                )
                total_surprise += self._post_surprise(
                    neighbors, background_log_sum, len(indices) - 1, vocabulary_size
                )
            result[tag] = total_surprise / len(score_indices)
        return result
