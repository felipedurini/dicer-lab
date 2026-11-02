"""Spawned, single-consumer worker; all scientific operations call src.dicer_sim."""
from __future__ import annotations

from dataclasses import asdict
import json
import logging
import platform
from pathlib import Path
import time

from .storage import JobStore

logger = logging.getLogger("dicer.web.worker")
ENGINE_VERSION = "web-adapter-v1"


class JobCancelled(Exception):
    """Cooperative cancellation reached between summarized molecules."""


class JobTimedOut(Exception):
    """The scientific work exceeded the documented per-attempt budget."""


def execute_request(request_data: dict, store: JobStore, job_id: str) -> dict:
    """Run scenarios serially and persist exact engine summaries without RNG changes."""
    from src.dicer_sim.domain import RunConfig
    from src.dicer_sim.models import EpsilonCutModel
    from src.dicer_sim.experiments import RunResult, compare_scenarios, result_manifest
    from src.dicer_sim.analysis import summarize
    from src.dicer_sim.exact import expected_summary
    from .metrics import metric_rows
    from .trajectory import trajectory_payload
    from src.dicer_sim.simulation import iter_population
    from .schemas import JobRequest, epsilon_policy
    import numpy as np

    request_data = dict(request_data)
    sequence_source = request_data.pop("_sequence_source", None)
    request = JobRequest.model_validate(request_data)
    construct = request.construct_config.to_domain()
    results = {}
    payloads = []
    first_id = request.scenarios[0].id
    total = len(request.scenarios) * request.n_molecules
    deadline = time.monotonic() + 900
    for index, scenario in enumerate(request.scenarios):
        if store.is_cancel_requested(job_id):
            store.mark_cancelled(job_id)
            return {"cancelled": True}
        policy = epsilon_policy(scenario.epsilon)
        model = EpsilonCutModel(policy, request.p22)
        config = RunConfig(request.n_molecules, scenario.seed, request.f_left)
        first_molecule = None
        completed_in_scenario = 0
        emitted_intervals: dict[tuple[int, int], int] = {}

        def observed_population():
            nonlocal first_molecule, completed_in_scenario
            for molecule in iter_population(construct, model, config):
                if first_molecule is None:
                    first_molecule = molecule
                for product in molecule.products:
                    key = (product.start, product.end)
                    emitted_intervals[key] = emitted_intervals.get(key, 0) + 1
                yield molecule
                completed_in_scenario += 1
                if completed_in_scenario % 250 == 0 or completed_in_scenario == request.n_molecules:
                    if store.is_cancel_requested(job_id):
                        raise JobCancelled
                    if time.monotonic() >= deadline:
                        raise JobTimedOut
                    store.set_progress(job_id, index * request.n_molecules + completed_in_scenario,
                                        total, "monte_carlo", scenario.id, index, len(request.scenarios))

        summary = summarize(observed_population(), construct)
        run_result = RunResult(construct, model.describe(), config, summary,
            {"python": platform.python_version(), "numpy": np.__version__,
             "bit_generator": "PCG64", "seed": config.seed})
        results[scenario.id] = run_result
        observed = metric_rows(run_result.summary)
        if time.monotonic() >= deadline:
            raise JobTimedOut
        exact = expected_summary(construct, model, request.f_left) if request.compute_exact else None
        if time.monotonic() >= deadline:
            raise JobTimedOut
        rows = metric_rows(run_result.summary, exact=exact, construct=construct) if exact else observed
        manifest = result_manifest(run_result)
        item = {
            "id": scenario.id, "label": scenario.label,
            "model": model.describe(), "config": asdict(config),
            "summary": asdict(run_result.summary), "metrics": rows,
            "manifest": manifest,
        }
        if sequence_source:
            from .design.sequence_projection import project_interval
            item["sequence_catalog"] = [
                {"start": start, "end": end, "length_nt": end-start, "count": count,
                 "sequence": project_interval(sequence_source["sequence_rna"], start, end)}
                for (start, end), count in sorted(emitted_intervals.items())
                if end-start in {21, 22, 24}
            ]
        payloads.append(item)
        store.set_progress(job_id, (index + 1) * request.n_molecules, total,
                           "exact" if exact else "monte_carlo", scenario.id, index + 1,
                           len(request.scenarios))
        if scenario.id == first_id:
            item["first_trajectory"] = trajectory_payload(construct, model,
                RunConfig(1, scenario.seed, request.f_left), first_molecule, source_kind="population_first",
                sequence_rna=sequence_source.get("sequence_rna") if sequence_source else None)
    baseline = results[request.baseline_id]
    comparisons = {
        item.id: compare_scenarios(baseline, results[item.id], alpha=request.alpha_family / max(1, len(results) - 1))
        for item in request.scenarios if item.id != request.baseline_id
    }
    return {"web_schema_version": 1, "label": request.label,
            "construct": request.construct_config.model_dump(mode="json"),
            "n_molecules": request.n_molecules, "baseline_id": request.baseline_id,
            "scenarios": payloads, "comparisons": comparisons,
            "sequence_source": ({key: value for key, value in sequence_source.items() if key != "sequence_rna"}
                                if sequence_source else None)}


def worker_loop(data_dir: str, stop_event=None) -> None:
    """Poll SQLite in a spawned process; never start a process during module import."""
    store = JobStore(Path(data_dir) / "jobs.sqlite3")
    store.initialize()
    store.recover_running(ENGINE_VERSION)
    try:
        while stop_event is None or not stop_event.is_set():
            job = store.claim_next(ENGINE_VERSION)
            if job is None:
                time.sleep(0.25)
                continue
            try:
                if job.kind == "dsrna_design":
                    from .design.executor import execute_design
                    output = execute_design(job.request, data_dir, job.id, job.attempts, store, stop_event)
                    result = output["result"]
                    store.register_artifacts(job.id, output["artifacts"])
                else:
                    result = execute_request(job.request, store, job.id)
                current = store.get_owned(job.owner_id, job.id)
                if result.get("cancelled") or current and current.state == "cancel_requested":
                    store.mark_cancelled(job.id)
                elif current and current.state == "running":
                    store.finish(job.id, result)
            except JobCancelled:
                store.mark_cancelled(job.id)
            except JobTimedOut:
                current = store.get_owned(job.owner_id, job.id)
                if current and current.state == "cancel_requested":
                    store.mark_cancelled(job.id)
                else:
                    store.fail(job.id, "simulation_timeout", "La simulación superó el límite de 900 segundos")
            except Exception as exc:
                logger.exception("Scientific job failed job=%s", job.id)
                try:
                    current = store.get_owned(job.owner_id, job.id)
                    if stop_event is not None and stop_event.is_set():
                        # Leave the row running for recover_running() in the replacement worker.
                        pass
                    elif current and current.state == "cancel_requested":
                        store.mark_cancelled(job.id)
                    else:
                        code = getattr(exc, "code", "simulation_failed")
                        message = str(exc)[:500] if code != "simulation_failed" else "El trabajo científico no pudo completarse"
                        store.fail(job.id, code, message)
                except ValueError:
                    pass
    finally:
        store.close()
