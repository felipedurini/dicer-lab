"""Orquestación ligera de poblaciones y resúmenes en streaming."""

from dataclasses import dataclass
from dataclasses import asdict
import hashlib
import json
import math
import platform
from pathlib import Path
import subprocess

import numpy as np

from .analysis import CountSummary, summarize
from .domain import Construct, RunConfig
from .models import ConstantEpsilon, CutModel, EpsilonCutModel, PiecewiseEpsilon, LinearEpsilon, QuadraticEpsilon, ExponentialEpsilon, CustomEpsilon
from .simulation import iter_population


@dataclass(frozen=True)
class RunResult:
    """Resumen de una corrida con su configuración suficiente para interpretarla."""

    construct: Construct
    model_description: dict[str, object]
    config: RunConfig
    summary: CountSummary
    metadata: dict[str, object]


def run_scenario(construct: Construct, model: CutModel, config: RunConfig) -> RunResult:
    """Ejecuta un escenario y conserva configuración y versiones del entorno."""
    summary = summarize_population(construct, model, config)
    return RunResult(
        construct=construct,
        model_description=model.describe(),
        config=config,
        summary=summary,
        metadata={"python": platform.python_version(), "numpy": np.__version__,
                  "bit_generator": "PCG64", "seed": config.seed},
    )



def summarize_population(
    construct: Construct,
    model: CutModel,
    config: RunConfig,
) -> CountSummary:
    """Simula y resume una población sin conservar la lista de moléculas."""
    return summarize(iter_population(construct, model, config), construct)


def ratio_interval_from_bounded_counts(
    numerator_mean: float,
    denominator_mean: float,
    delta: float,
    *,
    estimate: bool = False,
):
    """Cociente e intervalo conservador desde medias normalizadas en [0,1]."""
    values = (numerator_mean, denominator_mean, delta)
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("medias y delta deben ser finitos")
    if not 0 <= numerator_mean <= 1 or not 0 <= denominator_mean <= 1:
        raise ValueError("las medias deben estar en [0,1]")
    if not 0 <= delta <= 1:
        raise ValueError("delta debe estar en [0,1]")
    if estimate:
        return numerator_mean / denominator_mean if denominator_mean else None
    lower_denominator = max(0.0, denominator_mean - delta)
    upper_denominator = min(1.0, denominator_mean + delta)
    if lower_denominator == 0.0:
        return (0.0, 1.0)
    lower_numerator = max(0.0, numerator_mean - delta)
    upper_numerator = min(1.0, numerator_mean + delta)
    return (
        max(0.0, lower_numerator / upper_denominator),
        min(1.0, upper_numerator / lower_denominator),
    )


def difference_interval(candidate_interval, baseline_interval):
    """Resta dos intervalos como candidate menos baseline."""
    candidate_low, candidate_high = candidate_interval
    baseline_low, baseline_high = baseline_interval
    if candidate_low > candidate_high or baseline_low > baseline_high:
        raise ValueError("cada intervalo debe estar ordenado")
    return (candidate_low - baseline_high, candidate_high - baseline_low)


def compare_scenarios(
    baseline: RunResult,
    candidate: RunResult,
    *,
    alpha: float = 0.05,
) -> dict[str, object]:
    """Compara proporción 21 agrupada con cotas conservadoras por molécula."""
    if not isinstance(baseline, RunResult) or not isinstance(candidate, RunResult):
        raise TypeError("baseline y candidate deben ser RunResult")
    if baseline.construct != candidate.construct:
        raise ValueError("los escenarios deben usar el mismo constructo y retícula")
    if baseline.config.f_left != candidate.config.f_left:
        raise ValueError("los escenarios deben usar la misma mezcla de direcciones")
    for result in (baseline, candidate):
        if isinstance(result.model_description.get("p22"), bool):
            raise ValueError("p22 inválido")
    if baseline.model_description.get("p22") != candidate.model_description.get("p22"):
        raise ValueError("los escenarios deben usar el mismo p22")
    if baseline.config.seed == candidate.config.seed:
        raise ValueError("las semillas de ambos escenarios deben ser distintas")
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha debe estar entre 0 y 1")

    def components(result):
        summary = result.summary
        bound = result.construct.length_nt // 21
        if bound == 0:
            return None, None, None
        scale = result.config.n_molecules * bound
        a = dict(summary.length_counts)[21] / scale
        t = summary.n_products / scale
        estimate = dict(summary.length_counts)[21] / summary.n_products if summary.n_products else None
        return a, t, estimate

    base_a, base_t, base_estimate = components(baseline)
    candidate_a, candidate_t, candidate_estimate = components(candidate)
    if base_a is None or candidate_a is None:
        return {"proportion21": {"baseline": None, "candidate": None,
                                 "delta": None, "delta_interval": (0.0, 0.0),
                                 "interval_method": "exact: zero product capacity"}}
    delta = None if base_estimate is None or candidate_estimate is None else candidate_estimate - base_estimate
    exact_degenerate = all(
        result.model_description.get("epsilon", {}).get("type") == "constant"
        and result.model_description.get("epsilon", {}).get("epsilon") == 0.0
        for result in (baseline, candidate)
    )
    if exact_degenerate:
        base_interval = (base_estimate, base_estimate) if base_estimate is not None else (0.0, 1.0)
        candidate_interval = (candidate_estimate, candidate_estimate) if candidate_estimate is not None else (0.0, 1.0)
    else:
        # Four bounded means (numerator and denominator for two scenarios).
        confidence_delta = max(
            math.sqrt(math.log(2 * 4 / alpha) / (2 * result.config.n_molecules))
            for result in (baseline, candidate)
        )
        base_interval = ratio_interval_from_bounded_counts(base_a, base_t, confidence_delta)
        candidate_interval = ratio_interval_from_bounded_counts(candidate_a, candidate_t, confidence_delta)
    return {
        "proportion21": {
            "baseline": base_estimate,
            "baseline_numerator": dict(baseline.summary.length_counts)[21],
            "baseline_denominator": baseline.summary.n_products,
            "candidate": candidate_estimate,
            "candidate_numerator": dict(candidate.summary.length_counts)[21],
            "candidate_denominator": candidate.summary.n_products,
            "delta": delta,
            "delta_interval": difference_interval(candidate_interval, base_interval),
            "interval_method": "exact degenerate" if exact_degenerate else "Hoeffding union bound, ratio of bounded means",
            "alpha": alpha,
            "n_baseline": baseline.config.n_molecules,
            "n_candidate": candidate.config.n_molecules,
        }
    }


def model_from_description(description: dict[str, object]) -> EpsilonCutModel:
    """Reconstruye solamente las políticas incorporadas; nunca evalúa código."""
    if not isinstance(description, dict) or description.get("type") != "epsilon_cut_model":
        raise ValueError("descripción de modelo desconocida")
    if description.get("schema_version") != 1 or description.get("support_nt") != [21, 22, 24]:
        raise ValueError("esquema o soporte de modelo desconocido")
    epsilon = description.get("epsilon")
    if not isinstance(epsilon, dict) or epsilon.get("schema_version") != 1:
        raise ValueError("descripción epsilon desconocida")
    if epsilon.get("type") == "constant":
        policy = ConstantEpsilon(epsilon["epsilon"])
    elif epsilon.get("type") == "piecewise":
        policy = PiecewiseEpsilon(tuple(epsilon["breakpoints"]), tuple(epsilon["values"]))
    elif epsilon.get("type") == "linear":
        policy = LinearEpsilon(epsilon["epsilon_start"], epsilon["epsilon_end"])
    elif epsilon.get("type") == "quadratic":
        policy = QuadraticEpsilon(epsilon["epsilon_start"], epsilon["epsilon_end"], epsilon.get("curvature", 0.5))
    elif epsilon.get("type") == "exponential":
        policy = ExponentialEpsilon(epsilon["epsilon_start"], epsilon["epsilon_end"], epsilon["rate"])
    elif epsilon.get("type") == "custom":
        policy = CustomEpsilon(epsilon["expression"], epsilon["parameters"])
    else:
        raise ValueError("política epsilon no incorporada")
    return EpsilonCutModel(policy, description["p22"])


def result_manifest(result: RunResult) -> dict[str, object]:
    """Forma un manifiesto JSON versionado con parámetros, resultados y procedencia."""
    if not isinstance(result, RunResult):
        raise TypeError("result debe ser RunResult")
    root = Path(__file__).resolve().parents[2]
    module_paths = ("domain.py", "models.py", "simulation.py", "analysis.py", "exact.py", "experiments.py")
    source_hashes = {
        name: hashlib.sha256((root / "src" / "dicer_sim" / name).read_bytes()).hexdigest()
        for name in module_paths
    }
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    manifest = {
        "schema_version": 1,
        "construct": {
            "length_nt": result.construct.length_nt,
            "phase_origin_nt": result.construct.phase_origin_nt,
            "segments": [asdict(segment) for segment in result.construct.segments],
        },
        "model": result.model_description,
        "config": asdict(result.config),
        "support_nt": [21, 22, 24],
        "terminal_rule": "stop_on_overshoot_v1",
        "rng": {
            "name": "numpy.random.Generator(PCG64)",
            "seed": result.config.seed,
            "spawn_keys": [[0], [1]],
            "streams": ["direction", "cuts"],
        },
        "metadata": result.metadata,
        "summary": asdict(result.summary),
        "metric_definitions": {
            "proportion21": "number of emitted 21 nt products / all emitted products",
            "coverage_fraction": "overlap nt / (molecules * target length nt)",
            "recovery_fraction": "exact physical 21 nt interval count / molecules",
        },
        "provenance": {
            "git_revision": revision,
            "source_hashes": source_hashes if revision is None else {},
        },
    }
    # Return only JSON-native values so in-memory and parsed manifests compare equally.
    return json.loads(serialize_manifest(manifest))


def serialize_manifest(manifest: dict[str, object]) -> str:
    """Codifica JSON estricto, rechazando NaN e infinitos."""
    return json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False)


def deserialize_manifest(serialized: str) -> dict[str, object]:
    """Decodifica el esquema admitido y rechaza constantes JSON no estándar."""
    def reject_constant(value):
        raise ValueError(f"constante JSON no finita: {value}")
    data = json.loads(serialized, parse_constant=reject_constant)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("schema_version desconocida")
    return data


def save_result(result: RunResult, path) -> None:
    """Guarda un manifiesto reproducible en UTF-8."""
    Path(path).write_text(serialize_manifest(result_manifest(result)), encoding="utf-8")
