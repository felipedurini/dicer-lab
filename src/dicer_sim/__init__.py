"""Núcleo del simulador de procesamiento de dsRNA."""

from .analysis import classify_product, summarize
from .domain import Construct, Product, RunConfig, Segment
from .exact import ExpectedSummary, expected_summary
from .experiments import (
    RunResult,
    compare_scenarios,
    result_manifest,
    run_scenario,
    save_result,
    summarize_population,
)
from .models import ConstantEpsilon, EpsilonCutModel, PiecewiseEpsilon, LinearEpsilon, QuadraticEpsilon, ExponentialEpsilon, CustomEpsilon
from .simulation import iter_population, simulate_molecule

__all__ = [
    "Construct", "Segment", "Product", "RunConfig", "ConstantEpsilon",
    "PiecewiseEpsilon", "LinearEpsilon", "QuadraticEpsilon", "ExponentialEpsilon",
    "CustomEpsilon", "EpsilonCutModel", "simulate_molecule",
    "iter_population", "classify_product", "summarize", "summarize_population",
    "ExpectedSummary", "expected_summary", "RunResult", "run_scenario",
    "compare_scenarios", "result_manifest", "save_result",
]
