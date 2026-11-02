"""Probabilidades del núcleo para longitud de corte fija."""

import json
import math
import unittest

from src.dicer_sim.models import (
    ConstantEpsilon,
    EpsilonCutModel,
    PiecewiseEpsilon,
    LinearEpsilon, QuadraticEpsilon, ExponentialEpsilon, CustomEpsilon,
    validate_probabilities,
)


class ModelTests(unittest.TestCase):
    def test_preexisting_one_argument_epsilon_policy_remains_compatible(self):
        class LegacyPolicy:
            def value(self, remaining_nt):
                return 0.25
            def describe(self):
                return {"type": "legacy"}
        self.assertEqual(EpsilonCutModel(LegacyPolicy()).probabilities(100, 200), (.75, .125, .125))

    def test_length_dependent_models_use_current_and_initial_length(self):
        self.assertAlmostEqual(LinearEpsilon(0.1, 0.5).value(50, 100), 0.3)
        self.assertAlmostEqual(QuadraticEpsilon(0.1, 0.5).value(50, 100), 0.35)
        self.assertAlmostEqual(ExponentialEpsilon(0.1, 0.5, 2).value(50, 100), 0.1 + 0.4 * (math.e - 1) / (math.exp(2) - 1))

    def test_custom_expression_is_safe_and_uses_unicode_parameters_and_initial_length(self):
        policy = CustomEpsilon("α + β * sqrt(1 - L/N)", {"α": 0.05, "β": 0.15})
        self.assertAlmostEqual(policy.value(75, 100), 0.125)
        self.assertEqual(policy.describe()["expression"], "α + β * sqrt(1 - L/N)")

    def test_custom_expression_rejects_code_and_invalid_math_without_clipping(self):
        for expression in ("__import__('os')", "L.__class__", "1/0", "sqrt(-1)", "2", "exp(10000)"):
            with self.subTest(expression=expression):
                with self.assertRaises((ValueError, TypeError)):
                    policy = CustomEpsilon(expression, {})
                    policy.value(50, 100)

    def test_custom_parameters_must_match_safe_identifiers_and_be_finite(self):
        for parameters in ({"L": 0.2}, {"x; import os": 0.1}, {"α": math.nan}):
            with self.subTest(parameters=parameters), self.assertRaises((ValueError, TypeError)):
                CustomEpsilon("α", parameters)

    def test_models_reject_values_outside_probability_domain(self):
        with self.assertRaises(ValueError):
            LinearEpsilon(-0.1, 0.5)
        with self.assertRaises(ValueError):
            EpsilonCutModel(CustomEpsilon("α + L/N", {"α": 0.5})).probabilities(100, 100)

    def test_model_probabilities_receive_initial_construct_length(self):
        model = EpsilonCutModel(LinearEpsilon(0.0, 1.0))
        self.assertEqual(model.probabilities(50, 100), (0.5, 0.25, 0.25))
        with self.assertRaises(ValueError):
            EpsilonCutModel(ConstantEpsilon(0.2)).probabilities(51, 50)
    def test_constant_epsilon_distribution(self):
        model = EpsilonCutModel(ConstantEpsilon(0.2), p22=0.5)
        self.assertEqual(model.probabilities(100), (0.8, 0.1, 0.1))

    def test_epsilon_zero(self):
        model = EpsilonCutModel(ConstantEpsilon(0.0), p22=0.37)
        self.assertEqual(model.probabilities(21), (1.0, 0.0, 0.0))

    def test_epsilon_one_with_p22_endpoints(self):
        all_24 = EpsilonCutModel(ConstantEpsilon(1.0), p22=0.0)
        all_22 = EpsilonCutModel(ConstantEpsilon(1.0), p22=1.0)
        self.assertEqual(all_24.probabilities(24), (0.0, 0.0, 1.0))
        self.assertEqual(all_22.probabilities(24), (0.0, 1.0, 0.0))

    def test_invalid_epsilon_or_p22_rejected(self):
        for value in (-0.1, 1.1, math.nan, math.inf, -math.inf, True, "0.5"):
            with self.subTest(epsilon=value), self.assertRaises((TypeError, ValueError)):
                ConstantEpsilon(value)
            with self.subTest(p22=value), self.assertRaises((TypeError, ValueError)):
                EpsilonCutModel(ConstantEpsilon(0.2), p22=value)

    def test_invalid_kernel_probabilities_rejected(self):
        invalid = (
            (0.5, 0.5),
            (0.5, 0.25, 0.2),
            (-0.1, 0.5, 0.6),
            (math.nan, 0.0, 1.0),
            (math.inf, 0.0, 0.0),
            (True, 0.0, 0.0),
            "not-a-kernel",
        )
        for probabilities in invalid:
            with self.subTest(probabilities=probabilities), self.assertRaises(
                (TypeError, ValueError)
            ):
                validate_probabilities(probabilities)

    def test_epsilon_and_model_descriptions_are_json_serializable(self):
        policy = ConstantEpsilon(0.2)
        model = EpsilonCutModel(policy, p22=0.35)
        self.assertEqual(policy.value(40), policy.value(40))
        self.assertEqual(model.probabilities(40), model.probabilities(40))
        self.assertIn("epsilon", policy.describe())
        description = model.describe()
        self.assertEqual(description["epsilon"]["epsilon"], 0.2)
        self.assertEqual(description["p22"], 0.35)
        json.dumps(description, allow_nan=False)

    def test_epsilon_requires_a_positive_integer_length(self):
        policy = ConstantEpsilon(0.1)
        for length in (0, -1, 1.5, True):
            with self.subTest(length=length), self.assertRaises((TypeError, ValueError)):
                policy.value(length)

    def test_piecewise_threshold_boundary(self):
        policy = PiecewiseEpsilon((50,), (0.8, 0.1))
        self.assertEqual(policy.value(49), 0.8)
        self.assertEqual(policy.value(50), 0.1)
        self.assertEqual(policy.value(51), 0.1)

    def test_piecewise_covers_the_positive_length_domain(self):
        policy = PiecewiseEpsilon((30, 60), (0.9, 0.4, 0.2))
        self.assertEqual([policy.value(length) for length in (1, 29, 30, 59, 60, 100)],
                         [0.9, 0.9, 0.4, 0.4, 0.2, 0.2])
        constant = PiecewiseEpsilon((), (0.3,))
        self.assertEqual(constant.value(1), constant.value(100))

    def test_unsorted_duplicate_or_nonpositive_thresholds_are_rejected(self):
        for breakpoints in ((50, 20), (30, 30), (0,), (-1,), (True,), (30.5,)):
            with self.subTest(breakpoints=breakpoints), self.assertRaises(
                (TypeError, ValueError)
            ):
                PiecewiseEpsilon(breakpoints, (0.2,) * (len(breakpoints) + 1))

    def test_piecewise_value_count_and_probabilities_are_validated(self):
        with self.assertRaises(ValueError):
            PiecewiseEpsilon((50,), (0.2,))
        for values in ((-0.1, 0.5), (0.2, 1.1), (math.nan, 0.5), (0.1, math.inf)):
            with self.subTest(values=values), self.assertRaises((TypeError, ValueError)):
                PiecewiseEpsilon((50,), values)

    def test_equal_piecewise_values_make_a_constant_policy(self):
        policy = PiecewiseEpsilon((21, 100), (0.25, 0.25, 0.25))
        self.assertEqual([policy.value(length) for length in (1, 21, 100, 200)],
                         [0.25, 0.25, 0.25, 0.25])
        description = policy.describe()
        self.assertEqual(description["breakpoints"], [21, 100])
        json.dumps(description, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
