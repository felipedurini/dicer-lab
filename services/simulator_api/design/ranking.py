"""Deterministic non-dominated sorting for three exploratory design objectives."""
from __future__ import annotations

import math


def pareto_rank(candidates: list[dict]) -> list[dict]:
    rows = []
    for candidate in candidates:
        metrics = candidate["metrics"]
        values = (float(metrics["minimum_gene_coverage"]),
                  float(metrics["high_stability_window_fraction"]),
                  float(metrics["dimer_gap_per_nt"]))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("candidate objective must be finite")
        rows.append((candidate, values))
    remaining = set(range(len(rows)))
    front = 0
    ranked = []
    while remaining:
        current = []
        for i in remaining:
            a = rows[i][1]
            dominated = any(j != i and _dominates(rows[j][1], a) for j in remaining)
            if not dominated:
                current.append(i)
        current.sort(key=lambda i: (-rows[i][1][0], -rows[i][1][1], rows[i][1][2], rows[i][0]["candidate_id"]))
        for rank_in_front, index in enumerate(current, 1):
            ranked.append({**rows[index][0], "pareto_front": front, "rank": len(ranked) + 1,
                           "rank_in_front": rank_in_front})
        remaining.difference_update(current)
        front += 1
    return ranked


def _dominates(a, b):
    no_worse = a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2]
    strictly = a[0] > b[0] or a[1] > b[1] or a[2] < b[2]
    return no_worse and strictly
