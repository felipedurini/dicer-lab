"""Oráculo de programación dinámica para conteos esperados finitos."""

from dataclasses import dataclass
import math
from numbers import Real

from .analysis import classify_product
from .domain import Construct, Product
from .models import CutModel, EpsilonCutModel, validate_probabilities


@dataclass(frozen=True)
class ExpectedSummary:
    """Expectativas por molécula y distribución de su remanente terminal."""

    expected_products: float
    expected_length_items: tuple[tuple[int, float], ...]
    terminal_probability_items: tuple[tuple[int, float], ...]
    terminal_reason_probability_items: tuple[tuple[str, float], ...]
    expected_remainder_nt: float
    expected_metric_items: tuple[tuple[str, float], ...] = ()
    direction_summaries: tuple[tuple[str, "ExpectedSummary"], ...] = ()

    @property
    def expected_metrics(self) -> dict[str, float]:
        return dict(self.expected_metric_items)

    @property
    def expected_length_counts(self) -> dict[int, float]:
        return dict(self.expected_length_items)

    @property
    def length_counts(self) -> tuple[tuple[int, float], ...]:
        return self.expected_length_items

    @property
    def terminal_probabilities(self) -> dict[int, float]:
        return dict(self.terminal_probability_items)

    @property
    def terminal_reason_probabilities(self) -> dict[str, float]:
        return dict(self.terminal_reason_probability_items)

    @property
    def expected_proportion21(self) -> float | None:
        return (
            self.expected_length_counts[21] / self.expected_products
            if self.expected_products
            else None
        )


def _one_direction(construct: Construct, model: CutModel, direction: str) -> ExpectedSummary:
    length_nt = construct.length_nt
    visits = [0.0] * (length_nt + 1)
    visits[length_nt] = 1.0
    expected_lengths = {21: 0.0, 22: 0.0, 24: 0.0}
    terminal = {length: 0.0 for length in range(24)}
    reasons = {"exhausted": 0.0, "shorter_than_min": 0.0, "proposal_exceeds_remaining": 0.0}
    metrics: dict[str, float] = {}

    def reward(key: str, value: float = 1.0) -> None:
        metrics[key] = metrics.get(key, 0.0) + value

    for remaining in range(length_nt, -1, -1):
        mass = visits[remaining]
        if mass == 0.0:
            continue
        if remaining == 0:
            terminal[0] += mass
            reasons["exhausted"] += mass
            continue
        if remaining < 21:
            terminal[remaining] += mass
            reasons["shorter_than_min"] += mass
            continue

        probabilities = (model.probabilities(remaining, length_nt) if isinstance(model, EpsilonCutModel)
                         else model.probabilities(remaining))
        q21, q22, q24 = validate_probabilities(probabilities)
        for cut_length, probability in ((21, q21), (22, q22), (24, q24)):
            branch_mass = mass * probability
            if not branch_mass:
                continue
            if cut_length > remaining:
                terminal[remaining] += branch_mass
                reasons["proposal_exceeds_remaining"] += branch_mass
            else:
                expected_lengths[cut_length] += branch_mass
                visits[remaining - cut_length] += branch_mass
                consumed = length_nt - remaining
                if direction == "left":
                    start, end = consumed, consumed + cut_length
                else:
                    end, start = remaining, remaining - cut_length
                product = Product(
                    cut_index=1, start=start, end=end, remaining_before=remaining
                )
                annotation = classify_product(product, construct, direction)
                for key, occurred in (
                    ("relative_phase_before_count", annotation.relative_phase_before == 0),
                    ("relative_phase_after_count", annotation.relative_phase_after == 0),
                    ("global_phase_before_count", annotation.global_phase_before == 0),
                    ("aligned21_local_count", annotation.aligned21_local),
                    ("aligned21_global_count", annotation.aligned21_global),
                    ("contained_count", annotation.contained_segment_id is not None),
                    ("crossing_count", bool(annotation.crossed_boundaries)),
                    ("gene_crossing_count", bool(annotation.crossed_gene_boundaries)),
                ):
                    if occurred:
                        reward(key, branch_mass)
                for segment in construct.segments:
                    overlap = dict(annotation.overlap_nt_by_segment).get(segment.segment_id, 0)
                    prefix = f"segment:{segment.segment_id}:"
                    if annotation.contained_segment_id == segment.segment_id:
                        reward(prefix + "contained_count", branch_mass)
                    if segment.segment_id in annotation.touching_segment_ids:
                        reward(prefix + "touching_count", branch_mass)
                    if any(start < boundary < end for boundary in (segment.start, segment.end)
                           if boundary not in (0, length_nt)):
                        reward(prefix + "crossing_touching_count", branch_mass)
                    if overlap:
                        reward(prefix + "overlap_nt", branch_mass * overlap)
                for gene_id in dict.fromkeys(s.gene_id for s in construct.segments):
                    segments = tuple(s for s in construct.segments if s.gene_id == gene_id)
                    touched = any(s.segment_id in annotation.touching_segment_ids for s in segments)
                    crossed = any(
                        start < boundary < end
                        for s in segments for boundary in (s.start, s.end)
                        if boundary not in (0, length_nt)
                    )
                    crossed_gene_junction = any(
                        left.end in annotation.crossed_gene_boundaries
                        and gene_id in (left.gene_id, right.gene_id)
                        for left, right in zip(construct.segments, construct.segments[1:])
                    )
                    contained = any(annotation.contained_segment_id == s.segment_id for s in segments)
                    overlap = sum(dict(annotation.overlap_nt_by_segment).get(s.segment_id, 0)
                                  for s in segments)
                    prefix = f"gene:{gene_id}:"
                    if contained:
                        reward(prefix + "contained_count", branch_mass)
                    if touched:
                        reward(prefix + "touching_count", branch_mass)
                    if crossed:
                        reward(prefix + "crossing_touching_count", branch_mass)
                    if crossed_gene_junction:
                        reward(prefix + "gene_crossing_touching_count", branch_mass)
                    if overlap:
                        reward(prefix + "overlap_nt", branch_mass * overlap)
                for offset in range(construct.phase_origin_nt, length_nt - 20, 21):
                    if offset + 21 <= length_nt and (start, end) == (offset, offset + 21):
                        reward(f"physical:{offset}:{offset + 21}:recovered_count", branch_mass)

    expected_products = sum(expected_lengths.values())
    expected_remainder = sum(length * probability for length, probability in terminal.items())
    return ExpectedSummary(
        expected_products=expected_products,
        expected_length_items=tuple((length, expected_lengths[length]) for length in (21, 22, 24)),
        terminal_probability_items=tuple(terminal.items()),
        terminal_reason_probability_items=tuple(reasons.items()),
        expected_remainder_nt=expected_remainder,
        expected_metric_items=tuple(metrics.items()),
    )


def expected_summary(
    construct: Construct,
    model: CutModel,
    f_left: float = 1.0,
) -> ExpectedSummary:
    """Calcula expectativas exactas por DP y mezcla ponderada de direcciones."""
    if not isinstance(construct, Construct):
        raise TypeError("construct debe ser Construct")
    if isinstance(f_left, bool) or not isinstance(f_left, Real):
        raise TypeError("f_left debe ser un número real")
    f_left = float(f_left)
    if not math.isfinite(f_left) or not 0.0 <= f_left <= 1.0:
        raise ValueError("f_left debe ser finito y estar entre 0 y 1")

    left = _one_direction(construct, model, "left")
    right = _one_direction(construct, model, "right")
    f_right = 1.0 - f_left
    expected_lengths = {
        length: f_left * left.expected_length_counts[length]
        + f_right * right.expected_length_counts[length]
        for length in (21, 22, 24)
    }
    terminal = {
        length: f_left * left.terminal_probabilities[length]
        + f_right * right.terminal_probabilities[length]
        for length in range(24)
    }
    reasons = {
        reason: f_left * left.terminal_reason_probabilities[reason]
        + f_right * right.terminal_reason_probabilities[reason]
        for reason in left.terminal_reason_probabilities
    }
    metric_keys = set(left.expected_metrics) | set(right.expected_metrics)
    metrics = {
        key: f_left * left.expected_metrics.get(key, 0.0)
        + f_right * right.expected_metrics.get(key, 0.0)
        for key in sorted(metric_keys)
    }
    combined = ExpectedSummary(
        expected_products=f_left * left.expected_products + f_right * right.expected_products,
        expected_length_items=tuple((length, expected_lengths[length]) for length in (21, 22, 24)),
        terminal_probability_items=tuple(terminal.items()),
        terminal_reason_probability_items=tuple(reasons.items()),
        expected_remainder_nt=(f_left * left.expected_remainder_nt
                               + f_right * right.expected_remainder_nt),
        expected_metric_items=tuple(metrics.items()),
        direction_summaries=(("left", left), ("right", right)),
    )
    return combined
