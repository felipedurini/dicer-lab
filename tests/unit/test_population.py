"""Configuración y streams reproducibles de una población de moléculas."""

import unittest

import numpy as np

from src.dicer_sim.domain import Construct, RunConfig, Segment
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel
from src.dicer_sim.simulation import iter_population


def construct(length):
    return Construct(length, (Segment("whole", "gene", 0, length),))


class PopulationTests(unittest.TestCase):
    def test_same_seed_and_config_reproduce_results(self):
        model = EpsilonCutModel(ConstantEpsilon(0.2), p22=0.35)
        config = RunConfig(n_molecules=12, seed=441, f_left=0.4)
        first = list(iter_population(construct(100), model, config))
        second = list(iter_population(construct(100), model, config))
        self.assertEqual(first, second)

    def test_direction_endpoints(self):
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        left = list(iter_population(construct(20), model, RunConfig(8, 10, 1.0)))
        right = list(iter_population(construct(20), model, RunConfig(8, 10, 0.0)))
        self.assertEqual({result.direction for result in left}, {"left"})
        self.assertEqual({result.direction for result in right}, {"right"})

    def test_one_direction_draw_per_molecule(self):
        seed, n, fraction_left = 731, 40, 0.37
        direction_seed, _cut_seed = np.random.SeedSequence(seed).spawn(2)
        expected_rng = np.random.Generator(np.random.PCG64(direction_seed))
        expected = [
            "left" if expected_rng.random() < fraction_left else "right"
            for _ in range(n)
        ]
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        actual = [
            result.direction
            for result in iter_population(
                construct(20), model, RunConfig(n, seed, fraction_left)
            )
        ]
        self.assertEqual(actual, expected)

    def test_direction_stream_is_separate_from_cut_stream(self):
        config = RunConfig(n_molecules=100, seed=2026, f_left=0.5)
        model = EpsilonCutModel(ConstantEpsilon(0.1))
        short_directions = [
            result.direction for result in iter_population(construct(20), model, config)
        ]
        long_directions = [
            result.direction for result in iter_population(construct(160), model, config)
        ]
        self.assertEqual(short_directions, long_directions)

    def test_invalid_run_config(self):
        for n in (0, -1):
            with self.subTest(n=n), self.assertRaises(ValueError):
                RunConfig(n, 1)
        for n in (True, 1.0):
            with self.subTest(n=n), self.assertRaises(TypeError):
                RunConfig(n, 1)
        for seed in (-1,):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                RunConfig(1, seed)
        for seed in (True, 1.0):
            with self.subTest(seed=seed), self.assertRaises(TypeError):
                RunConfig(1, seed)
        for f_left in (-0.1, 1.1, float("nan"), float("inf"), True):
            with self.subTest(f_left=f_left), self.assertRaises((TypeError, ValueError)):
                RunConfig(1, 1, f_left)

    def test_population_yields_exact_requested_count(self):
        results = iter_population(
            construct(20),
            EpsilonCutModel(ConstantEpsilon(0.0)),
            RunConfig(n_molecules=7, seed=5),
        )
        self.assertEqual(len(list(results)), 7)


if __name__ == "__main__":
    unittest.main()
