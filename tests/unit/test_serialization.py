import json
import unittest

from src.dicer_sim.domain import Construct, RunConfig, Segment
from src.dicer_sim.experiments import (
    deserialize_manifest, model_from_description, result_manifest, run_scenario,
    serialize_manifest,
)
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel, PiecewiseEpsilon, CustomEpsilon, LinearEpsilon, QuadraticEpsilon, ExponentialEpsilon


class SerializationTests(unittest.TestCase):
    def setUp(self):
        self.construct = Construct(42, (Segment("s", "g", 0, 42),), 3)
        self.model = EpsilonCutModel(PiecewiseEpsilon((30,), (0.1, 0.4)), 0.3)
        self.result = run_scenario(self.construct, self.model, RunConfig(12, 44, 0.25))

    def test_manifest_roundtrip(self):
        loaded = deserialize_manifest(serialize_manifest(result_manifest(self.result)))
        self.assertEqual(loaded["construct"]["length_nt"], 42)
        self.assertEqual(loaded["config"]["seed"], 44)
        self.assertEqual(loaded["summary"], result_manifest(self.result)["summary"])

    def test_manifest_contains_all_parameters_and_hashes(self):
        manifest = result_manifest(self.result)
        self.assertEqual(manifest["model"]["p22"], 0.3)
        self.assertEqual(manifest["config"]["f_left"], 0.25)
        self.assertEqual(manifest["support_nt"], [21, 22, 24])
        self.assertIn("source_hashes", manifest["provenance"])
        self.assertIn("spawn_keys", manifest["rng"])

    def test_builtin_policy_roundtrip_preserves_probabilities(self):
        rebuilt = model_from_description(self.model.describe())
        for length in (21, 30, 31, 42):
            self.assertEqual(rebuilt.probabilities(length), self.model.probabilities(length))
        constant = model_from_description(EpsilonCutModel(ConstantEpsilon(0.2)).describe())
        self.assertEqual(constant.probabilities(21), (0.8, 0.1, 0.1))

    def test_none_serializes_as_null_and_nonfinite_is_rejected(self):
        encoded = serialize_manifest({"estimate": None})
        self.assertIn('"estimate": null', encoded)
        with self.assertRaises(ValueError):
            serialize_manifest({"invalid": float("nan")})

    def test_new_epsilon_descriptions_roundtrip(self):
        policies = [LinearEpsilon(.1, .4), QuadraticEpsilon(.1, .4),
                    ExponentialEpsilon(.1, .4, 2), CustomEpsilon("α + β*sqrt(1-L/N)", {"α": .1, "β": .2})]
        for policy in policies:
            with self.subTest(policy=policy):
                model = EpsilonCutModel(policy, .3)
                loaded = model_from_description(model.describe())
                for remaining in (21, 30, 42):
                    self.assertEqual(loaded.probabilities(remaining, 42), model.probabilities(remaining, 42))

    def test_unknown_schema_version_rejected(self):
        with self.assertRaises(ValueError):
            deserialize_manifest('{"schema_version": 77}')


if __name__ == "__main__":
    unittest.main()
