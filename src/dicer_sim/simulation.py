"""Rutinas de simulación secuencial de cortes."""

import math
from numbers import Real
from typing import Protocol

import numpy as np

from .domain import Construct, MoleculeResult, Product, TerminalRemainder
from .domain import RunConfig
from .models import CutModel, EpsilonCutModel, validate_probabilities


class UniformSource(Protocol):
    """Fuente inyectable de uniformes en el intervalo semiabierto `[0, 1)`."""

    def random(self) -> float: ...


def sample_cut_length(model: CutModel, remaining_nt: int, rng: UniformSource, initial_nt: int | None = None) -> int:
    """Propone un único corte 21/22/24 por CDF inversa."""
    if isinstance(remaining_nt, bool) or not isinstance(remaining_nt, int):
        raise TypeError("remaining_nt debe ser un entero")
    if remaining_nt <= 0:
        raise ValueError("remaining_nt debe ser positivo")
    if not callable(getattr(model, "probabilities", None)):
        raise TypeError("model debe implementar probabilities(remaining_nt)")
    if not callable(getattr(rng, "random", None)):
        raise TypeError("rng debe implementar random()")

    probabilities = (model.probabilities(remaining_nt, initial_nt) if isinstance(model, EpsilonCutModel)
                     else model.probabilities(remaining_nt))
    q21, q22, _q24 = validate_probabilities(probabilities)
    uniform = rng.random()
    if isinstance(uniform, bool) or not isinstance(uniform, Real):
        raise TypeError("rng.random() debe devolver un número real")
    uniform = float(uniform)
    if not math.isfinite(uniform) or not 0.0 <= uniform < 1.0:
        raise ValueError("rng.random() debe devolver un valor en [0, 1)")

    if uniform < q21:
        return 21
    if uniform < q21 + q22:
        return 22
    return 24


def simulate_molecule(
    construct: Construct,
    model: CutModel,
    direction: str,
    rng: UniformSource,
) -> MoleculeResult:
    """Procesa una molécula desde un extremo hasta una condición terminal."""
    if not isinstance(construct, Construct):
        raise TypeError("construct debe ser Construct")
    if direction not in ("left", "right"):
        raise ValueError("direction debe ser 'left' o 'right'")

    products: list[Product] = []
    consumed = 0
    length_nt = construct.length_nt
    while True:
        remaining = length_nt - consumed
        if remaining == 0:
            terminal_start = length_nt if direction == "left" else 0
            terminal = TerminalRemainder(
                terminal_start, terminal_start, reason="exhausted"
            )
            break
        if remaining < 21:
            terminal_start, terminal_end = (
                (consumed, length_nt) if direction == "left" else (0, remaining)
            )
            terminal = TerminalRemainder(
                terminal_start, terminal_end, reason="shorter_than_min"
            )
            break

        proposed = sample_cut_length(model, remaining, rng, length_nt)
        if proposed > remaining:
            terminal_start, terminal_end = (
                (consumed, length_nt) if direction == "left" else (0, remaining)
            )
            terminal = TerminalRemainder(
                terminal_start,
                terminal_end,
                reason="proposal_exceeds_remaining",
                proposed_length=proposed,
            )
            break

        product_start, product_end = (
            (consumed, consumed + proposed)
            if direction == "left"
            else (remaining - proposed, remaining)
        )
        products.append(
            Product(
                cut_index=len(products) + 1,
                start=product_start,
                end=product_end,
                remaining_before=remaining,
            )
        )
        consumed += proposed

    return MoleculeResult(direction=direction, products=tuple(products), remainder=terminal)


def iter_population(
    construct: Construct,
    model: CutModel,
    config: RunConfig,
):
    """Genera moléculas serialmente con streams separados para dirección y cortes."""
    if not isinstance(config, RunConfig):
        raise TypeError("config debe ser RunConfig")
    if not isinstance(construct, Construct):
        raise TypeError("construct debe ser Construct")

    direction_seed, cut_seed = np.random.SeedSequence(config.seed).spawn(2)
    direction_rng = np.random.Generator(np.random.PCG64(direction_seed))
    cut_rng = np.random.Generator(np.random.PCG64(cut_seed))
    for _ in range(config.n_molecules):
        direction = "left" if direction_rng.random() < config.f_left else "right"
        yield simulate_molecule(construct, model, direction, cut_rng)
