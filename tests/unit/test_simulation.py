"""Trayectoria secuencial desde el extremo izquierdo."""

import unittest

from src.dicer_sim.domain import Construct, Segment, RunConfig
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel, PiecewiseEpsilon, CustomEpsilon
from src.dicer_sim.simulation import simulate_molecule, iter_population


class ScriptedRandom:
    def __init__(self, values=()):
        self.values = iter(values)
        self.calls = 0

    def random(self):
        self.calls += 1
        return next(self.values)


class RecordingModel:
    def __init__(self, probabilities):
        self.kernel = probabilities
        self.calls = []

    def probabilities(self, remaining_nt):
        self.calls.append(remaining_nt)
        return self.kernel


class LengthSensitiveModel:
    def __init__(self):
        self.calls = []

    def probabilities(self, remaining_nt):
        self.calls.append(remaining_nt)
        if remaining_nt == 70:
            return (0.0, 1.0, 0.0)
        if remaining_nt == 48:
            return (0.0, 0.0, 1.0)
        if remaining_nt == 24:
            return (1.0, 0.0, 0.0)
        return (1.0, 0.0, 0.0)


def construct(length):
    return Construct(length, (Segment("whole", "target", 0, length),))


class SimulationTests(unittest.TestCase):
    def test_custom_length_model_uses_initial_length_and_repeats_with_seed(self):
        construct = Construct(105, (Segment("s", "g", 0, 105),))
        model = EpsilonCutModel(CustomEpsilon("0.1 + 0.2*(1-L/N)", {}), p22=0.4)
        config = RunConfig(25, 991, 1.0)
        first = list(iter_population(construct, model, config))
        second = list(iter_population(construct, model, config))
        self.assertEqual(first, second)
    def test_zero_epsilon_length64(self):
        rng = ScriptedRandom((0.1, 0.2, 0.3))
        result = simulate_molecule(
            construct(64), EpsilonCutModel(ConstantEpsilon(0.0)), "left", rng
        )
        self.assertEqual([(p.start, p.end) for p in result.products],
                         [(0, 21), (21, 42), (42, 63)])
        self.assertEqual(result.remainder.start, 63)
        self.assertEqual(result.remainder.end, 64)
        self.assertEqual(result.remainder.reason, "shorter_than_min")
        self.assertEqual(rng.calls, 3)

    def test_short_substrate_uses_no_model_or_rng(self):
        model = RecordingModel((1.0, 0.0, 0.0))
        rng = ScriptedRandom()
        result = simulate_molecule(construct(20), model, "left", rng)
        self.assertEqual(result.products, ())
        self.assertEqual((result.remainder.start, result.remainder.end), (0, 20))
        self.assertEqual(result.remainder.reason, "shorter_than_min")
        self.assertEqual(model.calls, [])
        self.assertEqual(rng.calls, 0)

    def test_exact_exhaustion(self):
        result = simulate_molecule(
            construct(21), EpsilonCutModel(ConstantEpsilon(0.0)), "left", ScriptedRandom((0.9,))
        )
        self.assertEqual([(p.start, p.end) for p in result.products], [(0, 21)])
        self.assertEqual(result.remainder.reason, "exhausted")
        self.assertEqual(result.remainder.length_nt, 0)

    def test_overshoot_does_not_resample(self):
        rng = ScriptedRandom((0.5, 0.2))
        result = simulate_molecule(
            construct(21), EpsilonCutModel(ConstantEpsilon(1.0), p22=0.0), "left", rng
        )
        self.assertEqual(result.products, ())
        self.assertEqual(result.remainder.length_nt, 21)
        self.assertEqual(result.remainder.reason, "proposal_exceeds_remaining")
        self.assertEqual(result.remainder.proposed_length, 24)
        self.assertEqual(rng.calls, 1)

    def test_terminal_edge_lengths_conserve_substrate(self):
        cases = (
            (22, (0.7,), (22,)),
            (23, (0.7,), (22,)),
            (24, (0.8,), (24,)),
        )
        for length, uniforms, expected_product_lengths in cases:
            with self.subTest(length=length):
                result = simulate_molecule(
                    construct(length),
                    EpsilonCutModel(ConstantEpsilon(0.5), p22=0.5),
                    "left",
                    ScriptedRandom(uniforms),
                )
                self.assertEqual([p.length_nt for p in result.products], list(expected_product_lengths))
                self.assertEqual(
                    sum(p.length_nt for p in result.products) + result.remainder.length_nt,
                    length,
                )

    def test_epsilon_one_p22_endpoints(self):
        result_22 = simulate_molecule(
            construct(44), EpsilonCutModel(ConstantEpsilon(1.0), p22=1.0),
            "left", ScriptedRandom((0.0, 0.99)),
        )
        result_24 = simulate_molecule(
            construct(48), EpsilonCutModel(ConstantEpsilon(1.0), p22=0.0),
            "left", ScriptedRandom((0.0, 0.99)),
        )
        self.assertEqual([p.length_nt for p in result_22.products], [22, 22])
        self.assertEqual([p.length_nt for p in result_24.products], [24, 24])

    def test_direction_argument_is_validated(self):
        with self.assertRaises(ValueError):
            simulate_molecule(
                construct(21), EpsilonCutModel(ConstantEpsilon(0.0)), "both", ScriptedRandom()
            )

    def test_model_is_queried_at_actual_remaining_lengths(self):
        model = LengthSensitiveModel()
        result = simulate_molecule(construct(70), model, "left", ScriptedRandom((0.2, 0.4, 0.8)))
        self.assertEqual(model.calls, [70, 48, 24])
        self.assertEqual([p.length_nt for p in result.products], [22, 24, 21])
        self.assertEqual(result.remainder.length_nt, 3)
        self.assertEqual(result.remainder.reason, "shorter_than_min")

    def test_equal_cut_index_can_have_different_remaining_lengths(self):
        model = RecordingModel((0.5, 0.0, 0.5))
        simulate_molecule(construct(70), model, "left", ScriptedRandom((0.1, 0.1, 0.1)))
        self.assertEqual(model.calls[:2], [70, 49])
        model.calls.clear()
        simulate_molecule(construct(70), model, "left", ScriptedRandom((0.8, 0.1, 0.1)))
        self.assertEqual(model.calls[:2], [70, 46])

    def test_piecewise_epsilon_switches_at_remaining_length_threshold(self):
        model = EpsilonCutModel(PiecewiseEpsilon((50,), (1.0, 0.0)), p22=1.0)
        rng = ScriptedRandom((0.2, 0.7, 0.9))
        result = simulate_molecule(construct(70), model, "left", rng)
        self.assertEqual([p.length_nt for p in result.products[:2]], [21, 22])
        self.assertEqual(result.products[1].remaining_before, 49)

    def test_right_length64_zero_epsilon(self):
        result = simulate_molecule(
            construct(64), EpsilonCutModel(ConstantEpsilon(0.0)), "right",
            ScriptedRandom((0.1, 0.2, 0.3)),
        )
        self.assertEqual([(p.start, p.end) for p in result.products],
                         [(43, 64), (22, 43), (1, 22)])
        self.assertEqual((result.remainder.start, result.remainder.end), (0, 1))
        self.assertEqual(result.direction, "right")

    def test_right_products_mirror_the_left_products(self):
        left = simulate_molecule(construct(70), LengthSensitiveModel(), "left",
                                 ScriptedRandom((0.2, 0.4, 0.8)))
        right = simulate_molecule(construct(70), LengthSensitiveModel(), "right",
                                  ScriptedRandom((0.2, 0.4, 0.8)))
        mirrored_left = [(70 - p.end, 70 - p.start) for p in left.products]
        self.assertEqual([(p.start, p.end) for p in right.products], mirrored_left)
        self.assertEqual((right.remainder.start, right.remainder.end),
                         (70 - left.remainder.end, 70 - left.remainder.start))
        self.assertEqual(right.direction, "right")

    def test_mirrored_terminal_overshoot(self):
        class StopAtRemainder:
            def probabilities(self, remaining_nt):
                return (1.0, 0.0, 0.0) if remaining_nt == 43 else (0.0, 0.0, 1.0)

        left = simulate_molecule(construct(43), StopAtRemainder(), "left",
                                 ScriptedRandom((0.0, 0.0)))
        right = simulate_molecule(construct(43), StopAtRemainder(), "right",
                                  ScriptedRandom((0.0, 0.0)))
        self.assertEqual([(p.start, p.end) for p in left.products], [(0, 21)])
        self.assertEqual([(p.start, p.end) for p in right.products], [(22, 43)])
        self.assertEqual((left.remainder.start, left.remainder.end), (21, 43))
        self.assertEqual((right.remainder.start, right.remainder.end), (0, 22))
        self.assertEqual(left.remainder.proposed_length, right.remainder.proposed_length)


if __name__ == "__main__":
    unittest.main()
