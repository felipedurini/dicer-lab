"""Proyección sin cambios del motor: toda métrica conserva numerador y base."""

from __future__ import annotations

from typing import Any

from src.dicer_sim.analysis import CountSummary, DirectionSummary
from src.dicer_sim.domain import Construct
from src.dicer_sim.exact import ExpectedSummary


def _row(
    key: str,
    scope: str,
    scope_id: str | None,
    numerator: int | float,
    denominator: int | float,
    basis: str,
    unit: str = "fraction",
    source_kind: str = "monte_carlo",
) -> dict[str, Any]:
    value = numerator / denominator if denominator else None
    return {
        "key": key,
        "scope": scope,
        "scope_id": scope_id,
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "basis": basis,
        "unit": unit,
        "source_kind": source_kind,
    }


def _add_product_rows(
    rows: list[dict[str, Any]],
    *,
    scope: str,
    scope_id: str | None,
    products: int,
    lengths: dict[int, int],
    relative_before: int,
    relative_after: int,
    global_before: int,
    aligned_local: int,
    aligned_global: int,
    contained_segment: int,
    segment_crossing: int,
    gene_crossing: int,
    source_kind: str = "monte_carlo",
) -> None:
    for length in (21, 22, 24):
        rows.append(_row(f"length_{length}", scope, scope_id, lengths[length], products,
                         "pooled_products", source_kind=source_kind))
    for key, numerator in (
        ("relative_phase_before", relative_before),
        ("relative_phase_after", relative_after),
        ("global_phase_before", global_before),
        ("aligned21_local", aligned_local),
        ("aligned21_global", aligned_global),
        ("contained_segment", contained_segment),
        ("segment_crossing", segment_crossing),
        ("gene_crossing", gene_crossing),
        ("contained_gene", products - gene_crossing),
    ):
        rows.append(_row(key, scope, scope_id, numerator, products, "pooled_products",
                         source_kind=source_kind))


def _observed_rows(summary: CountSummary) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _add_product_rows(
        rows,
        scope="global",
        scope_id=None,
        products=summary.n_products,
        lengths=dict(summary.length_counts),
        relative_before=summary.relative_phase_before_count,
        relative_after=summary.relative_phase_after_count,
        global_before=summary.global_phase_before_count,
        aligned_local=summary.aligned21_local_count,
        aligned_global=summary.aligned21_global_count,
        contained_segment=summary.contained_count,
        segment_crossing=summary.crossing_count,
        gene_crossing=summary.gene_crossing_count,
    )
    rows.append(_row("products_per_molecule", "global", None, summary.n_products,
                     summary.n_molecules, "molecules", "products_per_molecule"))
    rows.append(_row("molecules_without_products", "global", None,
                     summary.n_molecules_without_products, summary.n_molecules, "molecules"))
    remainder_total = sum(length * count for length, count in summary.terminal_length_items)
    rows.append(_row("mean_remainder_nt", "global", None, remainder_total,
                     summary.n_molecules, "molecules", "nt_per_molecule"))
    for length, count in summary.terminal_length_items:
        rows.append(_row("terminal_length", "terminal", str(length), count,
                         summary.n_molecules, "molecules"))
    for reason, count in summary.terminal_reason_items:
        rows.append(_row("terminal_reason", "terminal_reason", reason, count,
                         summary.n_molecules, "molecules"))

    for item in summary.segment_counts:
        scope_id = item.segment_id
        rows.append(_row("segment_interior", "segment", scope_id,
                         item.contained_count, summary.n_products, "pooled_products"))
        rows.append(_row("segment_touching", "segment", scope_id,
                         item.touching_count, summary.n_products, "pooled_products"))
        rows.append(_row("segment_crossing_touching", "segment", scope_id,
                         item.crossing_touching_count, item.touching_count, "touching_products"))
        rows.append(_row("segment_coverage", "segment", scope_id, item.overlap_nt,
                         summary.n_molecules * (item.end - item.start),
                         "nucleotide_mass"))

    for gene in summary.gene_counts:
        interior = gene.touching_count - gene.gene_crossing_touching_count
        rows.append(_row("gene_interior", "gene", gene.gene_id, interior,
                         summary.n_products, "pooled_products"))
        rows.append(_row("gene_interior_given_touch", "gene", gene.gene_id, interior,
                         gene.touching_count, "touching_products"))
        rows.append(_row("gene_touching", "gene", gene.gene_id, gene.touching_count,
                         summary.n_products, "pooled_products"))
        rows.append(_row("gene_segment_interior", "gene", gene.gene_id,
                         gene.contained_count, summary.n_products, "pooled_products"))
        rows.append(_row("gene_crossing_touching", "gene", gene.gene_id,
                         gene.gene_crossing_touching_count, gene.touching_count,
                         "touching_products"))
        rows.append(_row("gene_crossing_products", "gene", gene.gene_id,
                         gene.gene_crossing_touching_count, summary.n_products,
                         "pooled_products"))
        rows.append(_row("gene_coverage", "gene", gene.gene_id, gene.overlap_nt,
                         summary.n_molecules * gene.gene_length_nt, "nucleotide_mass"))
        for segment in summary.segment_counts:
            if segment.gene_id == gene.gene_id:
                rows.append(_row(
                    "gene_segment_interior_detail", "segment", segment.segment_id,
                    segment.contained_count, summary.n_products, "pooled_products",
                ))

    for direction in summary.direction_summaries:
        _append_direction_rows(rows, direction)
    for ordinal in summary.ordinal_counts:
        scope_id = str(ordinal.cut_index)
        rows.append(_row("ordinal_reached", "ordinal", scope_id, ordinal.n_reached,
                         summary.n_molecules, "molecules"))
        for key, numerator in (
            ("ordinal_relative_phase_before_joint", ordinal.relative_phase_before_count),
            ("ordinal_relative_phase_after_joint", ordinal.relative_phase_after_count),
            ("ordinal_aligned21_local_joint", ordinal.aligned21_local_count),
        ):
            rows.append(_row(key, "ordinal", scope_id, numerator,
                             summary.n_molecules, "molecules"))
        for key, numerator in (
            ("ordinal_relative_phase_before_given_reached", ordinal.relative_phase_before_count),
            ("ordinal_relative_phase_after_given_reached", ordinal.relative_phase_after_count),
            ("ordinal_aligned21_local_given_reached", ordinal.aligned21_local_count),
        ):
            rows.append(_row(key, "ordinal", scope_id, numerator,
                             ordinal.n_reached, "reached_molecules"))
    for unit in summary.physical_unit_counts:
        rows.append(_row("physical_unit_recovery", "physical_unit",
                         f"{unit.start}:{unit.end}", unit.recovered_molecule_count,
                         unit.n_molecules, "molecules"))
    return rows


def _append_direction_rows(rows: list[dict[str, Any]], direction: DirectionSummary) -> None:
    _add_product_rows(
        rows,
        scope="direction",
        scope_id=direction.direction,
        products=direction.n_products,
        lengths=dict(direction.length_counts),
        relative_before=direction.relative_phase_before_count,
        relative_after=direction.relative_phase_after_count,
        global_before=direction.global_phase_before_count,
        aligned_local=direction.aligned21_local_count,
        aligned_global=direction.aligned21_global_count,
        contained_segment=direction.contained_count,
        segment_crossing=direction.crossing_count,
        gene_crossing=direction.gene_crossing_count,
    )
    rows.append(_row("products_per_molecule", "direction", direction.direction,
                     direction.n_products, direction.n_molecules,
                     "molecules", "products_per_molecule"))


def _expected_rows(construct: Construct, expected: ExpectedSummary) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metrics = expected.expected_metrics
    products = expected.expected_products
    counts = expected.expected_length_counts
    _add_product_rows(
        rows,
        scope="global",
        scope_id=None,
        products=products,
        lengths=counts,
        relative_before=metrics.get("relative_phase_before_count", 0.0),
        relative_after=metrics.get("relative_phase_after_count", 0.0),
        global_before=metrics.get("global_phase_before_count", 0.0),
        aligned_local=metrics.get("aligned21_local_count", 0.0),
        aligned_global=metrics.get("aligned21_global_count", 0.0),
        contained_segment=metrics.get("contained_count", 0.0),
        segment_crossing=metrics.get("crossing_count", 0.0),
        gene_crossing=metrics.get("gene_crossing_count", 0.0),
        source_kind="exact_expectation",
    )
    rows.append(_row("products_per_molecule", "global", None, products, 1.0,
                     "molecules", "products_per_molecule", "exact_expectation"))
    for segment in construct.segments:
        prefix = f"segment:{segment.segment_id}:"
        interior = metrics.get(prefix + "contained_count", 0.0)
        touching = metrics.get(prefix + "touching_count", 0.0)
        crossing = metrics.get(prefix + "crossing_touching_count", 0.0)
        overlap = metrics.get(prefix + "overlap_nt", 0.0)
        rows.append(_row("segment_interior", "segment", segment.segment_id,
                         interior, products, "pooled_products", source_kind="exact_expectation"))
        rows.append(_row("segment_touching", "segment", segment.segment_id,
                         touching, products, "pooled_products", source_kind="exact_expectation"))
        rows.append(_row("segment_crossing_touching", "segment", segment.segment_id,
                         crossing, touching, "touching_products", source_kind="exact_expectation"))
        rows.append(_row("segment_coverage", "segment", segment.segment_id, overlap,
                         segment.end - segment.start, "nucleotide_mass",
                         source_kind="exact_expectation"))
    for gene_id in dict.fromkeys(segment.gene_id for segment in construct.segments):
        segments = tuple(segment for segment in construct.segments if segment.gene_id == gene_id)
        prefix = f"gene:{gene_id}:"
        touching = metrics.get(prefix + "touching_count", 0.0)
        crossing = metrics.get(prefix + "gene_crossing_touching_count", 0.0)
        interior = touching - crossing
        overlap = metrics.get(prefix + "overlap_nt", 0.0)
        rows.append(_row("gene_interior", "gene", gene_id, interior, products,
                         "pooled_products", source_kind="exact_expectation"))
        rows.append(_row("gene_interior_given_touch", "gene", gene_id, interior,
                         touching, "touching_products", source_kind="exact_expectation"))
        rows.append(_row("gene_touching", "gene", gene_id, touching, products,
                         "pooled_products", source_kind="exact_expectation"))
        segment_interior = sum(
            metrics.get(f"segment:{segment.segment_id}:contained_count", 0.0)
            for segment in segments
        )
        rows.append(_row("gene_segment_interior", "gene", gene_id, segment_interior,
                         products, "pooled_products", source_kind="exact_expectation"))
        rows.append(_row("gene_crossing_touching", "gene", gene_id, crossing,
                         touching, "touching_products", source_kind="exact_expectation"))
        rows.append(_row("gene_crossing_products", "gene", gene_id, crossing,
                         products, "pooled_products", source_kind="exact_expectation"))
        gene_length = sum(segment.end - segment.start for segment in segments)
        rows.append(_row("gene_coverage", "gene", gene_id, overlap, gene_length,
                         "nucleotide_mass", source_kind="exact_expectation"))
        for segment in segments:
            rows.append(_row(
                "gene_segment_interior_detail", "segment", segment.segment_id,
                metrics.get(f"segment:{segment.segment_id}:contained_count", 0.0),
                products, "pooled_products", source_kind="exact_expectation",
            ))
    for length, probability in expected.terminal_probabilities.items():
        rows.append(_row("terminal_length", "terminal", str(length), probability,
                         1.0, "molecules", source_kind="exact_expectation"))
    for reason, probability in expected.terminal_reason_probabilities.items():
        rows.append(_row("terminal_reason", "terminal_reason", reason, probability,
                         1.0, "molecules", source_kind="exact_expectation"))
    for direction, directional in expected.direction_summaries:
        _append_expected_direction_rows(rows, direction, directional)
    return rows


def _append_expected_direction_rows(
    rows: list[dict[str, Any]], direction: str, summary: ExpectedSummary
) -> None:
    metrics = summary.expected_metrics
    _add_product_rows(
        rows,
        scope="direction",
        scope_id=direction,
        products=summary.expected_products,
        lengths=summary.expected_length_counts,
        relative_before=metrics.get("relative_phase_before_count", 0.0),
        relative_after=metrics.get("relative_phase_after_count", 0.0),
        global_before=metrics.get("global_phase_before_count", 0.0),
        aligned_local=metrics.get("aligned21_local_count", 0.0),
        aligned_global=metrics.get("aligned21_global_count", 0.0),
        contained_segment=metrics.get("contained_count", 0.0),
        segment_crossing=metrics.get("crossing_count", 0.0),
        gene_crossing=metrics.get("gene_crossing_count", 0.0),
        source_kind="exact_expectation",
    )
    rows.append(_row("products_per_molecule", "direction", direction,
                     summary.expected_products, 1.0, "molecules",
                     "products_per_molecule", "exact_expectation"))


def metric_rows(
    summary: CountSummary, *, exact: ExpectedSummary | None = None,
    construct: Construct | None = None,
) -> tuple[dict[str, Any], ...]:
    """Proyecta filas observadas y, si se da, filas DP en un mismo contrato."""
    if not isinstance(summary, CountSummary):
        raise TypeError("summary debe ser CountSummary")
    rows = _observed_rows(summary)
    if exact is not None:
        if not isinstance(exact, ExpectedSummary) or not isinstance(construct, Construct):
            raise TypeError("exact requiere ExpectedSummary y construct")
        rows.extend(_expected_rows(construct, exact))
    return tuple(rows)
