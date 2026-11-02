import { z } from "zod";

const idSchema = z.string().regex(/^[A-Za-z][A-Za-z0-9_-]{0,47}$/);
const labelSchema = z.string().trim().min(1).max(120);
const probabilitySchema = z.number().finite().min(0).max(1);

export const segmentSchema = z.object({
  segment_id: idSchema,
  gene_id: idSchema,
  start: z.number().int().min(0),
  end: z.number().int().positive(),
}).strict();

export const constructSchema = z.object({
  length_nt: z.number().int().min(1).max(5000),
  phase_origin_nt: z.number().int().min(0).max(20).default(0),
  segments: z.array(segmentSchema).min(1).max(32),
}).strict().superRefine((construct, ctx) => {
  let cursor = 0;
  const ids = new Set<string>();
  construct.segments.forEach((segment, index) => {
    if (ids.has(segment.segment_id)) ctx.addIssue({ code: "custom", path: ["segments", index, "segment_id"], message: "segment_id debe ser único" });
    ids.add(segment.segment_id);
    if (segment.start !== cursor || segment.end <= segment.start || segment.end > construct.length_nt) {
      ctx.addIssue({ code: "custom", path: ["segments", index], message: "segments debe ser una partición ordenada y contigua" });
    }
    cursor = segment.end;
  });
  if (cursor !== construct.length_nt) ctx.addIssue({ code: "custom", path: ["segments"], message: "segments debe cubrir length_nt completo" });
});

export const epsilonSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("constant"), schema_version: z.literal(1), epsilon: probabilitySchema }).strict(),
  z.object({ type: z.literal("linear"), schema_version: z.literal(1), epsilon_start: probabilitySchema, epsilon_end: probabilitySchema }).strict(),
  z.object({ type: z.literal("quadratic"), schema_version: z.literal(1), epsilon_start: probabilitySchema, epsilon_end: probabilitySchema, curvature: z.number().finite().min(-1).max(1).default(0.5) }).strict(),
  z.object({ type: z.literal("exponential"), schema_version: z.literal(1), epsilon_start: probabilitySchema, epsilon_end: probabilitySchema, rate: z.number().finite().min(-20).max(20) }).strict(),
  z.object({ type: z.literal("custom"), schema_version: z.literal(1), expression: z.string().min(1).max(256), parameters: z.record(z.string(), z.number().finite()).refine((parameters) => Object.keys(parameters).length <= 16, "Hasta 16 parámetros") }).strict(),
  z.object({
    type: z.literal("piecewise"), schema_version: z.literal(1),
    breakpoints: z.array(z.number().int().positive().max(5000)).max(16),
    values: z.array(probabilitySchema),
  }).strict().superRefine((policy, ctx) => {
    if (policy.values.length !== policy.breakpoints.length + 1) ctx.addIssue({ code: "custom", path: ["values"], message: "values debe tener un elemento más que breakpoints" });
    let previous = 0;
    policy.breakpoints.forEach((point, index) => {
      if (point <= previous) ctx.addIssue({ code: "custom", path: ["breakpoints", index], message: "breakpoints deben ser crecientes" });
      previous = point;
    });
  }),
]);

const common = {
  web_schema_version: z.literal(1),
  construct: constructSchema,
  p22: probabilitySchema,
  f_left: probabilitySchema,
};

export const previewRequestSchema = z.object({
  ...common,
  seed: z.number().int().min(0).max(4_294_967_295),
  epsilon: epsilonSchema,
}).strict();

const scenarioSchema = z.object({
  id: idSchema, label: labelSchema,
  seed: z.number().int().min(0).max(4_294_967_295),
  epsilon: epsilonSchema,
}).strict();

export const jobRequestSchema = z.object({
  web_schema_version: z.literal(1), label: labelSchema,
  construct: constructSchema,
  n_molecules: z.number().int().min(1).max(100_000),
  f_left: probabilitySchema, p22: probabilitySchema,
  scenarios: z.array(scenarioSchema).min(1).max(4),
  baseline_id: idSchema, alpha_family: z.literal(0.05), compute_exact: z.boolean(),
}).strict().superRefine((job, ctx) => {
  const ids = new Set<string>();
  const seeds = new Set<number>();
  job.scenarios.forEach((scenario, index) => {
    if (ids.has(scenario.id)) ctx.addIssue({ code: "custom", path: ["scenarios", index, "id"], message: "scenario IDs deben ser únicos" });
    if (seeds.has(scenario.seed)) ctx.addIssue({ code: "custom", path: ["scenarios", index, "seed"], message: "cada escenario requiere una semilla distinta" });
    ids.add(scenario.id); seeds.add(scenario.seed);
  });
  const baseline = job.scenarios.find((scenario) => scenario.id === job.baseline_id);
  if (!baseline) ctx.addIssue({ code: "custom", path: ["baseline_id"], message: "baseline_id debe identificar un escenario" });
  if (job.scenarios.length > 1 && baseline?.epsilon.type !== "constant") ctx.addIssue({ code: "custom", path: ["baseline_id"], message: "la referencia de comparación debe ser constante" });
  const work = job.scenarios.length * job.n_molecules * Math.max(1, Math.floor(job.construct.length_nt / 21)) * job.construct.segments.length;
  if (work > 30_000_000) ctx.addIssue({ code: "custom", path: ["n_molecules"], message: "el trabajo estimado supera el presupuesto" });
  if (job.compute_exact && (job.construct.length_nt > 1000 || job.construct.segments.length > 16)) ctx.addIssue({ code: "custom", path: ["compute_exact"], message: "DP requiere length_nt <= 1000 y hasta 16 segmentos" });
});
