"""Fuzzy match module for history search.

Cython-accelerated subsequence matching with gap penalty.
Case-insensitive. Supports multi-byte characters (Japanese, emoji, etc.).

Score formula: max(0, 100 - penalty * 100 / candidate_length)
where penalty is the number of non-matching characters between matched query chars.
"""

from __future__ import annotations

try:
    from vibe.core.fuzzy.history_fuzzy import fuzzy_match, fuzzy_match_batch
except ImportError:
    # Fallback to pure Python if Cython extension not available
    def fuzzy_match(query: str, candidate: str) -> tuple[float, list[int] | None]:
        """Pure Python fallback for fuzzy matching."""
        q_lower = query.lower()
        c_lower = candidate.lower()
        q_len = len(q_lower)
        c_len = len(c_lower)

        if q_len == 0:
            return (100.0, None)
        if q_len > c_len:
            return (0.0, None)

        q_chars = [ord(c) for c in q_lower]
        c_chars = [ord(c) for c in c_lower]

        best_start = -1
        best_penalty = c_len + 1

        for start in range(c_len - q_len + 1):
            q_idx = 0
            c_idx = start
            penalty = 0

            while q_idx < q_len and c_idx < c_len:
                if q_chars[q_idx] == c_chars[c_idx]:
                    q_idx += 1
                else:
                    penalty += 1
                c_idx += 1

            if q_idx == q_len and penalty < best_penalty:
                best_penalty = penalty
                best_start = start

        if best_start < 0:
            return (0.0, None)

        q_idx = 0
        c_idx = best_start
        indices: list[int] = []

        while q_idx < q_len and c_idx < c_len:
            if q_chars[q_idx] == c_chars[c_idx]:
                indices.append(c_idx)
                q_idx += 1
            c_idx += 1

        score = 100.0 - best_penalty * 100.0 / c_len
        score = max(score, 0.0)

        return (score, indices)

    def fuzzy_match_batch(
        query: str, candidates: list[str]
    ) -> list[tuple[float, list[int] | None]]:
        """Batch version of fuzzy_match."""
        return [fuzzy_match(query, c) for c in candidates]


__all__ = ["fuzzy_match", "fuzzy_match_batch"]
