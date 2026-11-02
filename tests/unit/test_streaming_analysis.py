"""Agregación de una pasada y combinación de lotes sin retener trayectorias."""

import unittest

from src.dicer_sim.analysis import merge_summaries, summarize
from src.dicer_sim.domain import Construct, RunConfig, Segment
from src.dicer_sim.experiments import summarize_population
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel
from src.dicer_sim.simulation import iter_population


def construct():
    return Construct(64, (Segment("whole", "gene", 0, 64),))


class OnePass:
    def __init__(self, values):
        self.values = values
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("results fue recorrido más de una vez")
        yield from self.values


class StreamingAnalysisTests(unittest.TestCase):
    def test_streaming_matches_explicit_small_population(self):
        model = EpsilonCutModel(ConstantEpsilon(0.15), p22=0.4)
        config = RunConfig(25, seed=882, f_left=0.3)
        source = OnePass(iter_population(construct(), model, config))
        streaming = summarize(source, construct())
        orchestrated = summarize_population(construct(), model, config)
        explicit = summarize(list(iter_population(construct(), model, config)), construct())
        self.assertEqual(source.iterations, 1)
        self.assertEqual(streaming, explicit)
        self.assertEqual(orchestrated, explicit)

    def test_one_pass_iterable_is_supported(self):
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        results = list(iter_population(construct(), model, RunConfig(5, seed=9)))
        source = OnePass(results)
        summary = summarize(source, construct())
        self.assertEqual(source.iterations, 1)
        self.assertEqual(summary.n_molecules, 5)

    def test_merging_counts_preserves_denominators(self):
        model = EpsilonCutModel(ConstantEpsilon(0.12), p22=0.5)
        config = RunConfig(30, seed=45, f_left=0.4)
        results = list(iter_population(construct(), model, config))
        whole = summarize(results, construct())
        pieces = (summarize(results[:11], construct()), summarize(results[11:], construct()))
        self.assertEqual(merge_summaries(pieces), whole)
        self.assertEqual(merge_summaries((whole,)).n_molecules, whole.n_molecules)

    def test_direction_subgroups_preserve_global_product_counts(self):
        model = EpsilonCutModel(ConstantEpsilon(0.1))
        config = RunConfig(100, seed=2026, f_left=0.5)
        summary = summarize_population(construct(), model, config)
        directions = {item.direction: item for item in summary.direction_summaries}
        self.assertEqual(set(directions), {"left", "right"})
        self.assertEqual(sum(item.n_molecules for item in directions.values()), 100)
        self.assertEqual(sum(item.n_products for item in directions.values()), summary.n_products)
        for length, count in summary.length_counts:
            self.assertEqual(
                sum(dict(item.length_counts)[length] for item in directions.values()),
                count,
            )


if __name__ == "__main__":
    unittest.main()
