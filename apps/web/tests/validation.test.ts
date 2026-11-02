import { describe, expect, it } from "vitest";
import { jobRequestSchema, previewRequestSchema } from "../lib/validation";

const construct = { length_nt: 315, phase_origin_nt: 0, segments: [
  { segment_id: "seg_a", gene_id: "gene_a", start: 0, end: 105 },
  { segment_id: "seg_b", gene_id: "gene_b", start: 105, end: 210 },
  { segment_id: "seg_c", gene_id: "gene_c", start: 210, end: 315 },
] };
const constant = { type: "constant" as const, schema_version: 1 as const, epsilon: 0.1 };
const piecewise = { type: "piecewise" as const, schema_version: 1 as const, breakpoints: [106, 211], values: [0.2, 0.1, 0.05] };

describe("HTTP v1 browser validation", () => {
  it("accepts matching synthetic preview and comparison requests", () => {
    expect(previewRequestSchema.safeParse({ web_schema_version: 1, construct, p22: 0.5, f_left: 0.5, seed: 101, epsilon: piecewise }).success).toBe(true);
    expect(jobRequestSchema.safeParse({ web_schema_version: 1, label: "synthetic", construct, n_molecules: 5000, f_left: 0.5, p22: 0.5, scenarios: [
      { id: "baseline", label: "constant", seed: 101, epsilon: constant }, { id: "variable", label: "piecewise", seed: 202, epsilon: piecewise },
    ], baseline_id: "baseline", alpha_family: 0.05, compute_exact: false }).success).toBe(true);
  });

  it("accepts built-in curves and custom expressions as simulation inputs", () => {
    const formulas = [
      { type: "linear", schema_version: 1, epsilon_start: 0.1, epsilon_end: 0.4 },
      { type: "quadratic", schema_version: 1, epsilon_start: 0.1, epsilon_end: 0.4 },
      { type: "exponential", schema_version: 1, epsilon_start: 0.1, epsilon_end: 0.4, rate: 2 },
      { type: "custom", schema_version: 1, expression: "α + β*sqrt(1-L/N)", parameters: { α: 0.05, β: 0.15 } },
    ];
    for (const epsilon of formulas) {
      expect(previewRequestSchema.safeParse({ web_schema_version: 1, construct, p22: 0.5, f_left: 0.5, seed: 101, epsilon }).success).toBe(true);
    }
  });

  it("rejects gaps, repeated seeds, nonconstant baselines, and over-budget DP", () => {
    expect(previewRequestSchema.safeParse({ web_schema_version: 1, construct: { ...construct, segments: [construct.segments[0], { ...construct.segments[1], start: 106 }, construct.segments[2]] }, p22: 0.5, f_left: 0.5, seed: 1, epsilon: constant }).success).toBe(false);
    const pair = [{ id: "base", label: "base", seed: 1, epsilon: constant }, { id: "candidate", label: "candidate", seed: 1, epsilon: piecewise }];
    expect(jobRequestSchema.safeParse({ web_schema_version: 1, label: "x", construct, n_molecules: 5, f_left: 0.5, p22: 0.5, scenarios: pair, baseline_id: "base", alpha_family: 0.05, compute_exact: false }).success).toBe(false);
    expect(jobRequestSchema.safeParse({ web_schema_version: 1, label: "x", construct, n_molecules: 5, f_left: 0.5, p22: 0.5, scenarios: [{ id: "base", label: "base", seed: 1, epsilon: constant }], baseline_id: "base", alpha_family: 0.05, compute_exact: true }).success).toBe(true);
    expect(jobRequestSchema.safeParse({ web_schema_version: 1, label: "x", construct: { ...construct, length_nt: 1001, segments: [{ segment_id: "seg_a", gene_id: "gene_a", start: 0, end: 1001 }] }, n_molecules: 5, f_left: 0.5, p22: 0.5, scenarios: [{ id: "base", label: "base", seed: 1, epsilon: constant }], baseline_id: "base", alpha_family: 0.05, compute_exact: true }).success).toBe(false);
  });
});
