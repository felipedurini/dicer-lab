"""Eventos visuales derivados únicamente de Product y TerminalRemainder reales."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
from typing import Literal

import numpy as np

from src.dicer_sim.analysis import classify_product
from src.dicer_sim.domain import Construct, MoleculeResult, RunConfig
from src.dicer_sim.models import CutModel


def _engine_provenance() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    source_paths = (
        "src/dicer_sim/domain.py",
        "src/dicer_sim/models.py",
        "src/dicer_sim/simulation.py",
        "src/dicer_sim/analysis.py",
        "src/dicer_sim/exact.py",
        "src/dicer_sim/experiments.py",
        "src/fase.py",
    )
    hashes = {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in source_paths
    }
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "rng": "numpy.random.Generator(PCG64)",
        "terminal_rule": "stop_on_overshoot_v1",
        "engine_sha256": hashes,
    }


def trajectory_payload(
    construct: Construct,
    model: CutModel,
    config: RunConfig,
    result: MoleculeResult,
    *,
    source_kind: Literal["preview", "population_first"] = "preview",
    sequence_rna: str | None = None,
) -> dict[str, object]:
    """Serializa una trayectoria sin simular, reordenar o añadir cortes."""
    if not isinstance(construct, Construct):
        raise TypeError("construct debe ser Construct")
    if not isinstance(config, RunConfig):
        raise TypeError("config debe ser RunConfig")
    if not isinstance(result, MoleculeResult):
        raise TypeError("result debe ser MoleculeResult")
    if source_kind not in {"preview", "population_first"}:
        raise ValueError("source_kind desconocido")

    segments = {segment.segment_id: segment for segment in construct.segments}
    events: list[dict[str, object]] = []
    for product in result.products:
        annotation = classify_product(product, construct, result.direction)
        remaining = product.remaining_before
        probabilities = model.probabilities(remaining, construct.length_nt)
        genes = tuple(dict.fromkeys(
            segments[segment_id].gene_id for segment_id in annotation.touching_segment_ids
        ))
        events.append({
            "kind": "cut",
            "cut_index": product.cut_index,
            "start": product.start,
            "end": product.end,
            "length_nt": product.length_nt,
            "remaining_before": product.remaining_before,
            "remaining_after": remaining - product.length_nt,
            "epsilon_before": model.epsilon_value(remaining, construct.length_nt),
            "probabilities_before": {
                "21": probabilities[0], "22": probabilities[1], "24": probabilities[2],
            },
            "contained_gene_id": genes[0] if len(genes) == 1 else None,
            "touching_gene_ids": list(genes),
            "annotation": {
                "relative_phase_before": annotation.relative_phase_before,
                "relative_phase_after": annotation.relative_phase_after,
                "global_phase_before": annotation.global_phase_before,
                "aligned21_local": annotation.aligned21_local,
                "aligned21_global": annotation.aligned21_global,
                "contained_segment_id": annotation.contained_segment_id,
                "touching_segment_ids": list(annotation.touching_segment_ids),
                "crossed_segment_boundaries": list(annotation.crossed_segment_boundaries),
                "crossed_gene_boundaries": list(annotation.crossed_gene_boundaries),
                "overlap_nt_by_segment": [
                    {"segment_id": segment_id, "nt": overlap}
                    for segment_id, overlap in annotation.overlap_nt_by_segment
                ],
            },
        })

    terminal = result.remainder
    last_length = result.products[-1].remaining_before - result.products[-1].length_nt if result.products else construct.length_nt
    if result.direction == "left":
        terminal_before = last_length
    else:
        terminal_before = last_length
    probabilities = None
    epsilon_before = None
    if terminal.reason == "proposal_exceeds_remaining":
        proposed_probabilities = model.probabilities(terminal.length_nt, construct.length_nt)
        probabilities = {
            "21": proposed_probabilities[0],
            "22": proposed_probabilities[1],
            "24": proposed_probabilities[2],
        }
        epsilon_before = model.epsilon_value(terminal.length_nt, construct.length_nt)
        terminal_before = terminal.length_nt
    events.append({
        "kind": "terminal",
        "start": terminal.start,
        "end": terminal.end,
        "length_nt": terminal.length_nt,
        "reason": terminal.reason,
        "proposed_length": terminal.proposed_length,
        "remaining_before": terminal_before,
        "epsilon_before": epsilon_before,
        "probabilities_before": probabilities,
    })

    config_dto = {
        "construct": {
            "length_nt": construct.length_nt,
            "phase_origin_nt": construct.phase_origin_nt,
            "segments": [asdict(segment) for segment in construct.segments],
        },
        "model": model.describe(),
        # A trajectory is reproducible with a single-molecule stream. Population
        # size is provenance about its source, not an input to this path.
        "run_config": {
            "n_molecules": 1,
            "seed": config.seed,
            "f_left": config.f_left,
        },
    }
    scientific_provenance = _engine_provenance()
    hash_input = {
        "web_schema_version": 1,
        "config": config_dto,
        "direction": result.direction,
        "events": events,
        "scientific_provenance": scientific_provenance,
    }
    canonical = json.dumps(hash_input, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload = {
        "web_schema_version": 1,
        "source": {
            "kind": source_kind,
            "molecule_index": 1,
            "population_size": config.n_molecules,
        },
        "config": config_dto,
        "direction": result.direction,
        "events": events,
        "remainder": {
            "start": terminal.start,
            "end": terminal.end,
            "length_nt": terminal.length_nt,
            "reason": terminal.reason,
            "proposed_length": terminal.proposed_length,
        },
        "scientific_provenance": scientific_provenance,
        "trajectory_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    if sequence_rna is not None:
        from .design.sequence_projection import annotate_trajectory
        from .design.schemas import DesignTarget
        DesignTarget(gene_id="sequence", sequence_rna=sequence_rna)
        payload = annotate_trajectory(payload, sequence_rna)
        payload["sequence_source"] = {"kind": "design_candidate", "sha256": hashlib.sha256(sequence_rna.encode()).hexdigest()}
        payload["trajectory_hash"] = hashlib.sha256((canonical + payload["sequence_source"]["sha256"]).encode()).hexdigest()
    return payload
