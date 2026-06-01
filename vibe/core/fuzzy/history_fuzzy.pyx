# distutils: language = c
# cython: language_level=3, binding=True, boundscheck=False, wraparound=False, cdivision=True, initializedcheck=False, infer_types=True

"""
Fuzzy match module for history search - Cython implementation.

Greedy subsequence matching with kind-hoisted dispatch for direct
PyUnicode_DATA access (zero-copy, no encoding dispatch).
Single-pass O(n) per candidate.

Score formula: max(0, 100 - penalty * 100 / candidate_length)
where penalty is the number of non-matching characters between matched query chars.
"""

from cpython.mem cimport PyMem_Malloc, PyMem_Free
from libc.stdint cimport uint8_t, uint16_t, uint32_t

cdef extern from "Python.h":
    Py_ssize_t PyUnicode_GET_LENGTH(object)
    void* PyUnicode_DATA(object)
    int PyUnicode_KIND(object)
    int PyUnicode_READY(object)


cdef inline uint32_t case_fold(uint32_t c) noexcept:
    """Case-fold ASCII uppercase to lowercase."""
    if c >= 65 and c <= 90:  # 'A'-'Z'
        return c + 32
    return c


# -- Greedy match + penalty + fill positions, per kind pair --

cdef inline int greedy_11(const uint8_t *q, int q_len,
                          const uint8_t *c, int c_len,
                          int *out_pos) noexcept:
    cdef int qi = 0, pos_i = 0, ci
    for ci in range(c_len):
        if qi < q_len and case_fold(q[qi]) == case_fold(c[ci]):
            out_pos[pos_i] = ci
            pos_i += 1
            qi += 1
    if qi < q_len:
        return -1
    cdef int penalty = 0
    for i in range(1, pos_i):
        penalty += out_pos[i] - out_pos[i - 1] - 1
    return penalty


cdef inline int greedy_22(const uint16_t *q, int q_len,
                          const uint16_t *c, int c_len,
                          int *out_pos) noexcept:
    cdef int qi = 0, pos_i = 0, ci
    for ci in range(c_len):
        if qi < q_len and case_fold(q[qi]) == case_fold(c[ci]):
            out_pos[pos_i] = ci
            pos_i += 1
            qi += 1
    if qi < q_len:
        return -1
    cdef int penalty = 0
    for i in range(1, pos_i):
        penalty += out_pos[i] - out_pos[i - 1] - 1
    return penalty


cdef inline int greedy_44(const uint32_t *q, int q_len,
                          const uint32_t *c, int c_len,
                          int *out_pos) noexcept:
    cdef int qi = 0, pos_i = 0, ci
    for ci in range(c_len):
        if qi < q_len and case_fold(q[qi]) == case_fold(c[ci]):
            out_pos[pos_i] = ci
            pos_i += 1
            qi += 1
    if qi < q_len:
        return -1
    cdef int penalty = 0
    for i in range(1, pos_i):
        penalty += out_pos[i] - out_pos[i - 1] - 1
    return penalty


# -- Mixed kind wrappers: 4-byte query with 1/2-byte candidate --

cdef inline int greedy_41(const uint32_t *q, int q_len,
                          const uint8_t *c, int c_len,
                          int *out_pos) noexcept:
    cdef int qi = 0, pos_i = 0, ci
    for ci in range(c_len):
        if qi < q_len and case_fold(q[qi]) == case_fold(c[ci]):
            out_pos[pos_i] = ci
            pos_i += 1
            qi += 1
    if qi < q_len:
        return -1
    cdef int penalty = 0
    for i in range(1, pos_i):
        penalty += out_pos[i] - out_pos[i - 1] - 1
    return penalty


cdef inline int greedy_42(const uint32_t *q, int q_len,
                          const uint16_t *c, int c_len,
                          int *out_pos) noexcept:
    cdef int qi = 0, pos_i = 0, ci
    for ci in range(c_len):
        if qi < q_len and case_fold(q[qi]) == case_fold(c[ci]):
            out_pos[pos_i] = ci
            pos_i += 1
            qi += 1
    if qi < q_len:
        return -1
    cdef int penalty = 0
    for i in range(1, pos_i):
        penalty += out_pos[i] - out_pos[i - 1] - 1
    return penalty


def fuzzy_match(str query, str candidate) -> tuple[float, list[int] | None]:
    """Fuzzy match query against candidate.

    Args:
        query: Search query (case-insensitive).
        candidate: Text to search in.

    Returns:
        tuple: (score: float, indices: list[int] or None)
    """
    cdef:
        int q_kind
        void *q_raw = NULL
        Py_ssize_t q_len
        int c_kind
        void *c_raw = NULL
        Py_ssize_t c_len
        int penalty
        int pos_count
        float score
        int *positions = NULL
        uint32_t *q_promoted = NULL
        int j

    if PyUnicode_READY(query) < 0:
        return (0.0, None)

    q_kind = PyUnicode_KIND(query)
    q_raw = PyUnicode_DATA(query)
    q_len = PyUnicode_GET_LENGTH(query)

    if q_len == 0:
        return (100.0, None)

    if PyUnicode_READY(candidate) < 0:
        return (0.0, None)

    c_kind = PyUnicode_KIND(candidate)
    c_raw = PyUnicode_DATA(candidate)
    c_len = PyUnicode_GET_LENGTH(candidate)

    if q_len > c_len:
        return (0.0, None)

    # Allocate positions buffer (q_len positions needed for matched indices)
    positions = <int*>PyMem_Malloc(sizeof(int) * q_len)
    if positions is NULL:
        return (0.0, None)

    # Initialize positions to -1 to avoid reading uninitialized memory
    for j in range(<int>q_len):
        positions[j] = -1

    # Kind-hoisted dispatch — single greedy pass
    if q_kind == 1 and c_kind == 1:
        penalty = greedy_11(<const uint8_t*>q_raw, <int>q_len,
                            <const uint8_t*>c_raw, <int>c_len, positions)
    elif q_kind == 2 and c_kind == 2:
        penalty = greedy_22(<const uint16_t*>q_raw, <int>q_len,
                            <const uint16_t*>c_raw, <int>c_len, positions)
    elif q_kind == 4 and c_kind == 4:
        penalty = greedy_44(<const uint32_t*>q_raw, <int>q_len,
                            <const uint32_t*>c_raw, <int>c_len, positions)
    else:
        # Mixed kinds: promote query to 4-byte
        q_promoted = <uint32_t*>PyMem_Malloc(sizeof(uint32_t) * q_len)
        if q_promoted is NULL:
            PyMem_Free(positions)
            return (0.0, None)
        if q_kind == 1:
            for j in range(q_len):
                q_promoted[j] = (<const uint8_t*>q_raw)[j]
        elif q_kind == 2:
            for j in range(q_len):
                q_promoted[j] = (<const uint16_t*>q_raw)[j]
        else:
            for j in range(q_len):
                q_promoted[j] = (<const uint32_t*>q_raw)[j]

        if c_kind == 1:
            penalty = greedy_41(q_promoted, <int>q_len,
                                <const uint8_t*>c_raw, <int>c_len, positions)
        elif c_kind == 2:
            penalty = greedy_42(q_promoted, <int>q_len,
                                <const uint16_t*>c_raw, <int>c_len, positions)
        else:
            penalty = greedy_44(q_promoted, <int>q_len,
                                <const uint32_t*>c_raw, <int>c_len, positions)
        PyMem_Free(q_promoted)

    if penalty < 0:
        PyMem_Free(positions)
        return (0.0, None)

    # positions[] already filled by greedy(); count matched
    pos_count = 0
    while pos_count < <int>q_len and positions[pos_count] >= 0:
        pos_count += 1

    # Build Python list from C array
    idx_list = []
    for j in range(pos_count):
        idx_list.append(positions[j])
    PyMem_Free(positions)

    # Calculate score
    score = 100.0 - <float>penalty * 100.0 / <float>c_len
    if score < 0.0:
        score = 0.0

    return (score, idx_list)


def fuzzy_match_batch(str query, list candidates) -> list:
    """Fuzzy match query against all candidates at once.

    Args:
        query: Search query (case-insensitive).
        candidates: List of text strings to search in.

    Returns:
        list: List of (score: float, indices: list[int] or None) tuples.
    """
    cdef:
        int q_kind
        void *q_raw = NULL
        Py_ssize_t q_len
        int c_kind
        void *c_raw = NULL
        Py_ssize_t c_len
        int penalty
        int pos_count
        float score
        list result = []
        str c_str
        int *c_positions = NULL
        uint32_t *q_promoted = NULL
        int j
        int k

    if PyUnicode_READY(query) < 0:
        return []

    q_kind = PyUnicode_KIND(query)
    q_raw = PyUnicode_DATA(query)
    q_len = PyUnicode_GET_LENGTH(query)

    if q_len == 0:
        for _ in candidates:
            result.append((100.0, None))
        return result

    # Promote query to 4-byte once if needed (handles mixed kinds correctly)
    if q_kind != 4:
        q_promoted = <uint32_t*>PyMem_Malloc(sizeof(uint32_t) * q_len)
        if q_promoted is NULL:
            return []
        if q_kind == 1:
            for j in range(q_len):
                q_promoted[j] = (<const uint8_t*>q_raw)[j]
        else:  # q_kind == 2
            for j in range(q_len):
                q_promoted[j] = (<const uint16_t*>q_raw)[j]
        q_raw = <void*>q_promoted
        q_kind = 4

    for c_str in candidates:
        if PyUnicode_READY(c_str) < 0:
            result.append((0.0, None))
            continue

        c_kind = PyUnicode_KIND(c_str)
        c_raw = PyUnicode_DATA(c_str)
        c_len = PyUnicode_GET_LENGTH(c_str)

        if q_len > c_len:
            result.append((0.0, None))
            continue

        # Allocate positions buffer for this candidate
        c_positions = <int*>PyMem_Malloc(sizeof(int) * q_len)
        if c_positions is NULL:
            result.append((0.0, None))
            continue

        # Initialize positions to -1
        for k in range(<int>q_len):
            c_positions[k] = -1

        # Kind-hoisted dispatch — single greedy pass
        if c_kind == 1:
            penalty = greedy_41(<const uint32_t*>q_raw, <int>q_len,
                                <const uint8_t*>c_raw, <int>c_len, c_positions)
        elif c_kind == 2:
            penalty = greedy_42(<const uint32_t*>q_raw, <int>q_len,
                                <const uint16_t*>c_raw, <int>c_len, c_positions)
        else:  # c_kind == 4
            penalty = greedy_44(<const uint32_t*>q_raw, <int>q_len,
                                <const uint32_t*>c_raw, <int>c_len, c_positions)

        if penalty < 0:
            PyMem_Free(c_positions)
            result.append((0.0, None))
            continue

        # positions[] already filled by greedy(); count matched
        pos_count = 0
        while pos_count < <int>q_len and c_positions[pos_count] >= 0:
            pos_count += 1

        # Build Python list from C array using Python API
        idx_list = []
        for j in range(pos_count):
            idx_list.append(c_positions[j])
        PyMem_Free(c_positions)

        # Calculate score
        score = 100.0 - <float>penalty * 100.0 / <float>c_len
        if score < 0.0:
            score = 0.0

        result.append((score, idx_list))

    if q_promoted:
        PyMem_Free(q_promoted)
    return result
