import json
import unittest

from pydantic import ValidationError

from services.simulator_api.schemas import JobRequest, validate_job_request


def request_dict():
    return {
        "web_schema_version": 1,
        "label": "Synthetic 315",
        "construct": {
            "length_nt": 315,
            "phase_origin_nt": 0,
            "segments": [
                {"segment_id": "a", "gene_id": "gene_a", "start": 0, "end": 105},
                {"segment_id": "b", "gene_id": "gene_b", "start": 105, "end": 210},
                {"segment_id": "c", "gene_id": "gene_c", "start": 210, "end": 315},
            ],
        },
        "n_molecules": 5000,
        "f_left": 0.5,
        "p22": 0.5,
        "scenarios": [
            {
                "id": "baseline",
                "label": "Constante",
                "seed": 101,
                "epsilon": {"type": "constant", "schema_version": 1, "epsilon": 0.1},
            },
            {
                "id": "variable",
                "label": "Aumenta al acortar",
                "seed": 202,
                "epsilon": {
                    "type": "piecewise",
                    "schema_version": 1,
                    "breakpoints": [106, 211],
                    "values": [0.2, 0.1, 0.05],
                },
            },
        ],
        "baseline_id": "baseline",
        "alpha_family": 0.05,
        "compute_exact": True,
    }


class JobSchemaTests(unittest.TestCase):
    def test_custom_policy_is_supported_and_rejects_unsafe_or_invalid_domain(self):
        from services.simulator_api.schemas import PreviewRequest
        data = request_dict()
        data["scenarios"] = data["scenarios"][:1]
        data["epsilon"] = {"type": "custom", "schema_version": 1,
                            "expression": "0.05 + α * sqrt(1 - L/N)", "parameters": {"α": 0.15}}
        preview = PreviewRequest.model_validate({
            "web_schema_version": 1, "construct": data["construct"], "p22": .5,
            "f_left": .5, "seed": 101, "epsilon": data["epsilon"]})
        model = preview.to_model()
        self.assertAlmostEqual(model.epsilon.value(315, 315), .05)
        data["scenarios"][0]["epsilon"] = {"type": "custom", "schema_version": 1,
            "expression": "__import__('os')", "parameters": {}}
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)
        data["scenarios"][0]["epsilon"] = {"type": "custom", "schema_version": 1,
            "expression": "α + L/N", "parameters": {"α": .5}}
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)

    def test_all_predefined_policy_inputs(self):
        from services.simulator_api.schemas import PreviewRequest
        base = {"web_schema_version": 1, "construct": request_dict()["construct"],
                "p22": .5, "f_left": .5, "seed": 101}
        configs = [
            {"type": "linear", "schema_version": 1, "epsilon_start": .1, "epsilon_end": .4},
            {"type": "quadratic", "schema_version": 1, "epsilon_start": .1, "epsilon_end": .4},
            {"type": "exponential", "schema_version": 1, "epsilon_start": .1, "epsilon_end": .4, "rate": 2},
        ]
        for config in configs:
            with self.subTest(config=config):
                request = PreviewRequest.model_validate({**base, "epsilon": config})
                self.assertTrue(0 <= request.to_model().probabilities(150, 315)[0] <= 1)

    def test_each_policy_can_be_a_comparison_candidate_against_constant_baseline(self):
        candidates = [
            {"type": "piecewise", "schema_version": 1, "breakpoints": [100], "values": [.1, .2]},
            {"type": "linear", "schema_version": 1, "epsilon_start": .1, "epsilon_end": .3},
            {"type": "quadratic", "schema_version": 1, "epsilon_start": .1, "epsilon_end": .3, "curvature": .5},
            {"type": "exponential", "schema_version": 1, "epsilon_start": .1, "epsilon_end": .3, "rate": 2},
            {"type": "custom", "schema_version": 1, "expression": "α + β*(1-L/N)", "parameters": {"α": .1, "β": .2}},
        ]
        for candidate in candidates:
            data = request_dict()
            data["scenarios"] = data["scenarios"][:1] + [{"id": "candidate", "label": "Variable", "seed": 202, "epsilon": candidate}]
            with self.subTest(type=candidate["type"]):
                self.assertEqual(JobRequest.model_validate(data).scenario_count, 2)
    def test_documented_request_is_valid_and_preserves_same_gene_ids(self):
        data = request_dict()
        data["construct"]["segments"][1]["gene_id"] = "gene_a"
        request = JobRequest.model_validate(data)
        self.assertEqual(request.construct_config.length_nt, 315)
        self.assertEqual(request.construct_config.segments[0].gene_id, "gene_a")
        self.assertEqual(request.scenarios[1].epsilon.values, [0.2, 0.1, 0.05])

    def test_construct_partition_and_ids_are_strict(self):
        for mutate in (
            lambda d: d["construct"]["segments"][1].update(start=106),
            lambda d: d["construct"]["segments"][1].update(end=105),
            lambda d: d["construct"]["segments"][0].update(segment_id="bad id"),
            lambda d: d["construct"]["segments"][0].update(start=True),
            lambda d: d["construct"].update(length_nt=5001),
            lambda d: d["construct"].update(phase_origin_nt=21),
        ):
            data = request_dict()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(ValidationError):
                JobRequest.model_validate(data)

    def test_unknown_fields_nonfinite_and_boolean_probabilities_are_rejected(self):
        data = request_dict()
        data["owner_id"] = "attacker"
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)
        for value in (True, float("nan"), float("inf"), -0.01, 1.01):
            data = request_dict()
            data["p22"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                JobRequest.model_validate(data)

    def test_scenarios_require_unique_ids_seeds_and_constant_baseline(self):
        for mutate in (
            lambda d: d["scenarios"][1].update(id="baseline"),
            lambda d: d["scenarios"][1].update(seed=101),
            lambda d: d.update(baseline_id="missing"),
            lambda d: d["scenarios"][0].update(
                epsilon={
                    "type": "piecewise", "schema_version": 1,
                    "breakpoints": [10], "values": [0.1, 0.2],
                }
            ),
        ):
            data = request_dict()
            mutate(data)
            with self.subTest(data=data), self.assertRaises(ValidationError):
                JobRequest.model_validate(data)

    def test_piecewise_boundaries_values_breakpoints_and_work_budget(self):
        data = request_dict()
        data["scenarios"][1]["epsilon"]["values"] = [0.1, 0.2]
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)
        data = request_dict()
        data["scenarios"][1]["epsilon"]["breakpoints"] = [211, 106]
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)
        data = request_dict()
        data["n_molecules"] = 100000
        data["construct"]["segments"] = [
            {"segment_id": f"s{i}", "gene_id": f"g{i}", "start": i, "end": i+1}
            for i in range(315)
        ]
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)

    def test_dp_limit_is_explicit_and_job_has_between_one_and_four_scenarios(self):
        data = request_dict()
        data["construct"]["length_nt"] = 2000
        data["construct"]["segments"] = [
            {"segment_id": "all", "gene_id": "g", "start": 0, "end": 2000}
        ]
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)
        data = request_dict()
        data["scenarios"] = []
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)
        data = request_dict()
        data["scenarios"] = data["scenarios"] * 3
        with self.assertRaises(ValidationError):
            JobRequest.model_validate(data)

    def test_json_validation_rejects_coercion(self):
        data = request_dict()
        data["n_molecules"] = "5000"
        with self.assertRaises(ValidationError):
            JobRequest.model_validate_json(json.dumps(data))

    def test_work_estimate_is_reproducible_and_shared_limit_is_enforced(self):
        request = JobRequest.model_validate(request_dict())
        validated = validate_job_request(request)
        self.assertEqual(validated.estimated_work, 450000)
        self.assertEqual(validated.baseline.id, "baseline")
        self.assertEqual(validated.scenario_count, 2)


if __name__ == "__main__":
    unittest.main()
