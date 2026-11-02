"""Deterministic orchestration from input FASTA through screened chimeras."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import random
import time
from typing import Any

from .dsrnamax import DsRNAMaxAdapter, DsRNAMaxError
from .references import ReferenceCatalog, ReferenceError
from .schemas import DesignRequest
from .thermo import energy_profile, window_weight
from .folding import fold_candidate
from .ranking import pareto_rank


class DesignPipelineError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DesignPipeline:
    dsrnamax: DsRNAMaxAdapter
    references: ReferenceCatalog

    def run(self, request: DesignRequest, *, work_dir: Path | str,
            cancel_check=None, progress=None) -> dict[str, Any]:
        if not isinstance(request, DesignRequest):
            raise TypeError("request must be a validated DesignRequest")
        root = Path(work_dir)
        root.mkdir(parents=True, exist_ok=False)
        try:
            selected_references = self.references.resolve(request.reference_ids)
            target_fasta = root / "targets.fa"
            target_fasta.write_text("".join(
                f">{item.gene_id}\n{item.sequence_dna}\n" for item in request.targets
            ), encoding="ascii")
            # Pass persistent source files directly to dsRNAmax. This avoids
            # copying an entire transcriptome into both Python and a temporary FASTA.
            reference_fastas = [reference.path for reference in selected_references]

            _report(progress, "discover", "Buscando ventanas de 21 nt en objetivos y referencias")
            discovery = self.dsrnamax.discover(target_fasta, reference_fastas)
            _report(progress, "thermodynamics", "Calculando perfiles termodinámicos de las ventanas elegibles")
            _write_json(root / "discovery.json", discovery)
            if not discovery.get("kmers"):
                raise DesignPipelineError("no_feasible_candidate", "all target 21-mers were filtered or absent")

            profiles: dict[str, dict[str, Any]] = {}
            eligible_records: list[dict[str, Any]] = []
            weights: dict[str, int] = {}
            eligible_kmers_by_gene: dict[str, set[str]] = {item.gene_id: set() for item in request.targets}
            for raw_record in discovery["kmers"]:
                _check_work(cancel_check)
                sequence = raw_record["sequence_rna"]
                profile = energy_profile(sequence)
                weight = window_weight(profile["delta"], lambda_value=request.lambda_value)
                profiles[sequence] = profile
                weights[sequence] = weight
                for occurrence in raw_record["occurrences"]:
                    eligible_kmers_by_gene[occurrence["gene_id"]].add(sequence)
                eligible_records.append({**raw_record, "thermodynamics": profile,
                                         "stability_indicator": int(profile["delta"] >= 1.0),
                                         "weight": weight})
            _write_json(root / "eligible-kmers.json", {
                "schema_version": 1, "k": 21, "genes": discovery["genes"], "kmers": eligible_records,
            })
            _write_json(root / "filtered-kmers.json", {
                "schema_version": 1, "kmers": discovery.get("filtered_kmers", []),
                "reference_windows_skipped": discovery.get("reference_windows_skipped", 0),
            })

            block_lengths = {item.gene_id: item.length_nt for item in request.blocks}
            block_request = {
                "schema_version": 1,
                "targets": [{"gene_id": item.gene_id, "sequence_dna": item.sequence_dna}
                            for item in request.targets],
                "block_lengths": [{"gene_id": item.gene_id, "length_nt": item.length_nt}
                                  for item in request.blocks],
                "weights": weights,
                "max_blocks_per_gene": 5,
            }
            _report(progress, "assemble", "Construyendo bloques candidatos por gen")
            assembly = self.dsrnamax.build_blocks(root, block_request)
            _report(progress, "candidate_generation", "Combinando bloques y eliminando duplicados")
            _write_json(root / "blocks.json", assembly)
            per_gene = assembly["blocks"]
            sizes = [len(gene["blocks"]) for gene in per_gene]
            total_combinations = 1
            for size in sizes:
                total_combinations *= size
            selected_indices = _sample_combination_indices(total_combinations, request.iterations, request.seed)
            candidates: list[dict[str, Any]] = []
            seen_sequences: dict[str, str] = {}
            duplicates: list[dict[str, str]] = []
            with (root / "candidate-window-profiles.jsonl").open("w", encoding="utf-8", newline="\n") as profile_handle:
                for index in selected_indices:
                    _check_work(cancel_check)
                    selection = _unrank_combination(index, per_gene)
                    sequence_parts: list[str] = []
                    block_rows: list[dict[str, Any]] = []
                    cursor = 0
                    for gene_id, block in zip((gene["gene_id"] for gene in per_gene), selection, strict=True):
                        sequence = block["sequence_rna"]
                        sequence_parts.append(sequence)
                        block_rows.append({
                            "gene_id": gene_id,
                            "start": cursor,
                            "end": cursor + len(sequence),
                            "target_start": block["start"],
                            "target_end": block["end"],
                            "sequence_rna": sequence,
                            "kmer_sequences": block["kmer_sequences"],
                            "assembly_score": block["score"],
                        })
                        cursor += len(sequence)
                    sequence_rna = "".join(sequence_parts)
                    candidate_id = _candidate_id(sequence_rna, block_rows)
                    if sequence_rna in seen_sequences:
                        duplicates.append({"candidate_id": candidate_id, "duplicate_of": seen_sequences[sequence_rna]})
                        continue
                    seen_sequences[sequence_rna] = candidate_id
                    candidate, profiles_by_position = _candidate_metrics(
                        candidate_id, sequence_rna, block_rows, request, profiles,
                        eligible_kmers_by_gene, block_lengths,
                    )
                    candidates.append(candidate)
                    for item in profiles_by_position:
                        profile_handle.write(json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")

            if not candidates:
                raise DesignPipelineError("no_feasible_candidate", "no unique candidate combination was generated")

            rejected: list[dict[str, Any]] = []
            screening: dict[str, Any] = {"schema_version": 1, "hits": [], "reference_windows_skipped": 0}
            screening_candidate_count = 0
            if reference_fastas:
                _report(progress, "screen", "Comparando ventanas candidatas con las referencias seleccionadas")
                screening_candidate_count = len(candidates)
                screening = self.dsrnamax.screen(root, [
                    {"id": item["candidate_id"], "sequence_dna": item["sequence_rna"].replace("U", "T")}
                    for item in candidates
                ], reference_fastas)
                _write_json(root / "screening.json", screening)
                blocked = {item["candidate_id"] for item in screening["hits"]}
                for candidate in candidates:
                    if candidate["candidate_id"] in blocked:
                        hits = [item for item in screening["hits"] if item["candidate_id"] == candidate["candidate_id"]]
                        rejected.append({"candidate_id": candidate["candidate_id"], "reason": "off_target_exact_21mer",
                                         "hits": hits})
                candidates = [item for item in candidates if item["candidate_id"] not in blocked]
            else:
                _write_json(root / "screening.json", screening)

            if not candidates:
                raise DesignPipelineError("no_feasible_candidate", "all generated candidates matched selected off-target references")
            _check_work(cancel_check)
            evaluated_candidate_count = len(candidates)
            folded_count = 0
            fold_seconds = 0.0
            _report(progress, "folding", "Plegando candidatos con ViennaRNA",
                    completed_candidates=0, total_candidates=evaluated_candidate_count,
                    fold_samples=0, estimated_remaining_seconds=None)
            for candidate in candidates:
                _check_work(cancel_check)
                fold_started = time.perf_counter()
                try:
                    folding = fold_candidate(candidate["sequence_rna"])
                except ValueError as exc:
                    raise DesignPipelineError("folding_failed", str(exc)) from exc
                fold_seconds += time.perf_counter() - fold_started
                _check_work(cancel_check)
                candidate["folding"] = folding
                candidate["metrics"]["dimer_gap_per_nt"] = folding["dimer"]["gap_per_nt"]
                folded_count += 1
                remaining = (fold_seconds / folded_count * (evaluated_candidate_count - folded_count)
                             if folded_count >= 3 else None)
                _report(progress, "folding", "Plegando candidatos con ViennaRNA",
                        completed_candidates=folded_count, total_candidates=evaluated_candidate_count,
                        fold_samples=folded_count, fold_elapsed_seconds=fold_seconds,
                        estimated_remaining_seconds=remaining)
            _report(progress, "ranking", "Ordenando candidatos por frentes de Pareto")
            candidates = pareto_rank(candidates)[:20]
            _report(progress, "complete", "Diseño completado")
            warnings = [] if selected_references else ["off_target_screen_not_run: no reference IDs were selected"]
            result = {
                "design_schema_version": 1,
                "job_kind": "dsrna_design",
                "request": request.model_dump(mode="json", by_alias=True),
                "genes": [item.gene_id for item in request.targets],
                "seed": request.seed,
                "iterations_requested": request.iterations,
                "combinations_available": total_combinations,
                "combinations_evaluated": len(selected_indices),
                "eligible_kmer_count": len(eligible_records),
                "filtered_kmer_count": len(discovery.get("filtered_kmers", [])),
                "reference_windows_skipped": discovery.get("reference_windows_skipped", 0),
                "references": [item.public_metadata() for item in selected_references],
                "thermo_profile": "lucid_end3_v1",
                "folding_profile": "vienna_turner2004_v1",
                "dsrnamax": {
                    "version": "1.1.15",
                    "source_commit": "674b5b513248ea551dcc9217f1059d593f827766",
                    "protocol_schema_version": 1,
                },
                "python_version": platform.python_version(),
                "candidate_count": len(candidates),
                "unique_candidate_count": evaluated_candidate_count,
                "duplicate_candidate_count": len(duplicates),
                "duplicates": duplicates,
                "rejected_candidate_count": len(rejected),
                "reference_windows_skipped_candidate_screen": screening.get("reference_windows_skipped", 0),
                "reference_windows_skipped_total": discovery.get("reference_windows_skipped", 0) + screening.get("reference_windows_skipped", 0),
                "off_target_screen": {
                    "performed": bool(reference_fastas),
                    "status": "completed" if reference_fastas else "not_run_no_references_selected",
                    "method": "exact_21nt_forward_or_reverse_complement" if reference_fastas else None,
                    "reference_ids": [item.id for item in selected_references],
                    "candidate_count": screening_candidate_count,
                    "candidate_hit_count": len({item["candidate_id"] for item in screening.get("hits", [])}),
                    "window_hit_count": len(screening.get("hits", [])),
                    "reference_windows_skipped": screening.get("reference_windows_skipped", 0),
                },
                "candidates": candidates,
                "rejected_candidates": rejected,
                "warnings": warnings,
            }
            _write_json(root / "result.json", result)
            return result
        except ReferenceError as exc:
            raise DesignPipelineError("reference_invalid", str(exc)) from exc
        except DsRNAMaxError as exc:
            raise DesignPipelineError(exc.code, str(exc)) from exc


def _sample_combination_indices(total: int, requested: int, seed: int) -> list[int]:
    if total < 1:
        raise DesignPipelineError("no_feasible_candidate", "one or more genes have no feasible block")
    count = min(total, requested, 100)
    if count == total:
        return list(range(total))
    if count == 1:
        return [0]
    sampled = random.Random(seed).sample(range(1, total), count - 1)
    return [0, *sorted(sampled)]


def _unrank_combination(index: int, genes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    digits: list[int] = []
    remainder = index
    for gene in reversed(genes):
        radix = len(gene["blocks"])
        if radix == 0:
            raise DesignPipelineError("no_feasible_candidate", f"gene {gene['gene_id']} has no feasible block")
        digits.append(remainder % radix)
        remainder //= radix
    if remainder:
        raise ValueError("combination index exceeds block product")
    return [gene["blocks"][digit] for gene, digit in zip(genes, reversed(digits), strict=True)]


def _candidate_id(sequence: str, blocks: list[dict[str, Any]]) -> str:
    canonical = json.dumps({"sequence_rna": sequence, "blocks": blocks}, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _candidate_metrics(candidate_id: str, sequence: str, blocks: list[dict[str, Any]],
                       request: DesignRequest, target_profiles: dict[str, dict[str, Any]],
                       eligible_kmers_by_gene: dict[str, set[str]],
                       block_lengths: dict[str, int]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if len(sequence) > 1000:
        raise DesignPipelineError("construct_too_long", "assembled candidate exceeds 1,000 nt")
    windows = [sequence[start:start + 21] for start in range(len(sequence) - 20)]
    profiles_by_position: list[dict[str, Any]] = []
    high_stability = 0
    for start, window in enumerate(windows):
        profile = target_profiles.get(window) or energy_profile(window)
        stable = int(profile["delta"] >= 1.0)
        high_stability += stable
        profiles_by_position.append({
            "candidate_id": candidate_id, "start": start, "end": start + 21,
            "sequence_rna": window, "profile_id": profile["profile_id"],
            "duplex_dg": profile["duplex_dg"], "sense_end_dg": profile["sense_end_dg"],
            "antisense_end_dg": profile["antisense_end_dg"], "delta": profile["delta"],
            "weight": window_weight(profile["delta"], lambda_value=request.lambda_value),
        })
    block_by_gene = {item["gene_id"]: item for item in blocks}
    coverage: dict[str, float] = {}
    for target in request.targets:
        block = block_by_gene.get(target.gene_id)
        if block is None:
            raise DesignPipelineError("invalid_candidate_blocks", f"candidate has no block for {target.gene_id}")
        block_sequence = block["sequence_rna"]
        denominator = len(block_sequence) - 20
        if denominator <= 0:
            raise DesignPipelineError("invalid_block_length", "coverage denominator must be positive")
        if len(block_sequence) != block_lengths[target.gene_id]:
            raise DesignPipelineError("invalid_candidate_blocks", f"candidate block length differs for {target.gene_id}")
        block_windows = (block_sequence[start:start + 21] for start in range(denominator))
        matching_windows = sum(window in eligible_kmers_by_gene[target.gene_id] for window in block_windows)
        coverage[target.gene_id] = matching_windows / denominator
    profile_lines = profiles_by_position
    metrics = {
        "coverage_by_gene": coverage,
        "minimum_gene_coverage": min(coverage.values()),
        "high_stability_window_fraction": high_stability / len(windows) if windows else None,
        "window_count": len(windows),
        "dimer_gap_per_nt": None,
    }
    return {
        "candidate_id": candidate_id,
        "sequence_rna": sequence,
        "sequence_dna": sequence.replace("U", "T"),
        "length_nt": len(sequence),
        "blocks": blocks,
        "metrics": metrics,
    }, profile_lines


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _report(progress, stage: str, operation: str, **details) -> None:
    if progress:
        progress({"stage": stage, "operation": operation, **details})


def _check_work(cancel_check) -> None:
    if cancel_check is not None and cancel_check():
        raise DesignPipelineError("job_cancelled", "design job cancellation requested")
