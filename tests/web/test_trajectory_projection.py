import unittest

from src.dicer_sim.domain import Construct, RunConfig, Segment
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel
from src.dicer_sim.simulation import iter_population
from services.simulator_api.trajectory import trajectory_payload


def construct(length=30):
    return Construct(length, (
        Segment("a", "gene_a", 0, 10),
        Segment("b", "gene_b", 10, 20),
        Segment("c", "gene_c", 20, length),
    ))


class TrajectoryProjectionTests(unittest.TestCase):
    def result(self, construct_, model, config):
        return next(iter_population(construct_, model, config))

    def test_cut_events_are_real_products_in_generation_order(self):
        molecule = construct()
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        config = RunConfig(1, seed=101, f_left=1.0)
        result = self.result(molecule, model, config)
        payload = trajectory_payload(molecule, model, config, result)
        self.assertEqual(payload["source"]["kind"], "preview")
        self.assertEqual(payload["events"][0]["kind"], "cut")
        cut = payload["events"][0]
        product = result.products[0]
        self.assertEqual((cut["cut_index"], cut["start"], cut["end"]),
                         (product.cut_index, product.start, product.end))
        self.assertEqual(cut["remaining_before"], product.remaining_before)
        self.assertEqual(cut["length_nt"], product.length_nt)
        self.assertEqual(cut["annotation"]["crossed_segment_boundaries"], [10, 20])
        self.assertEqual(cut["annotation"]["crossed_gene_boundaries"], [10, 20])
        self.assertEqual(payload["events"][-1]["kind"], "terminal")
        self.assertEqual(payload["events"][-1]["length_nt"], result.remainder.length_nt)
        self.assertEqual(payload["events"][-1]["reason"], "shorter_than_min")

    def test_same_gene_segment_boundary_is_not_promoted_to_gene_junction(self):
        molecule = Construct(30, (
            Segment("a1", "gene_a", 0, 10),
            Segment("a2", "gene_a", 10, 30),
        ))
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        config = RunConfig(1, seed=101, f_left=1.0)
        payload = trajectory_payload(molecule, model, config,
                                     self.result(molecule, model, config))
        annotation = payload["events"][0]["annotation"]
        self.assertEqual(annotation["crossed_segment_boundaries"], [10])
        self.assertEqual(annotation["crossed_gene_boundaries"], [])
        self.assertEqual(payload["events"][0]["contained_gene_id"], "gene_a")

    def test_right_direction_keeps_decreasing_global_coordinates(self):
        molecule = Construct(64, (Segment("whole", "gene", 0, 64),))
        model = EpsilonCutModel(ConstantEpsilon(0.0))
        config = RunConfig(1, seed=101, f_left=0.0)
        result = self.result(molecule, model, config)
        payload = trajectory_payload(molecule, model, config, result)
        observed = [(event["start"], event["end"])
                    for event in payload["events"] if event["kind"] == "cut"]
        self.assertEqual(observed, [(product.start, product.end) for product in result.products])
        self.assertEqual(observed, [(43, 64), (22, 43), (1, 22)])

    def test_overshoot_is_a_terminal_proposal_and_never_a_product_event(self):
        molecule = Construct(22, (Segment("whole", "gene", 0, 22),))
        model = EpsilonCutModel(ConstantEpsilon(1.0), p22=0.0)
        config = RunConfig(1, seed=15, f_left=1.0)
        result = self.result(molecule, model, config)
        payload = trajectory_payload(molecule, model, config, result)
        self.assertEqual(result.products, ())
        self.assertEqual([event["kind"] for event in payload["events"]], ["terminal"])
        self.assertEqual(payload["events"][0]["reason"], "proposal_exceeds_remaining")
        self.assertEqual(payload["events"][0]["proposed_length"], 24)
        self.assertEqual(payload["events"][0]["probabilities_before"], {
            "21": 0.0, "22": 0.0, "24": 1.0,
        })

    def test_same_seed_replays_same_scientific_hash_and_events(self):
        molecule = construct()
        model = EpsilonCutModel(ConstantEpsilon(0.2))
        config = RunConfig(1, seed=776, f_left=0.5)
        left = trajectory_payload(molecule, model, config,
                                  self.result(molecule, model, config))
        right = trajectory_payload(molecule, model, config,
                                   self.result(molecule, model, config))
        self.assertEqual(left["trajectory_hash"], right["trajectory_hash"])
        self.assertEqual(left["events"], right["events"])
        self.assertEqual(left["config"]["run_config"]["seed"], 776)


if __name__ == "__main__":
    unittest.main()
