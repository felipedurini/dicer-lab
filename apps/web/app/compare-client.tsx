"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft, GitCompareArrows, Plus, Trash2 } from "lucide-react";
import { jobRequestSchema } from "@/lib/validation";
import EpsilonEditor, { type EpsilonConfig } from "./epsilon-editor";

type Scenario = { id: string; label: string; seed: number; epsilon: EpsilonConfig };
type Metric = { key: string; numerator: number; denominator: number; value: number | null; unit: string };
type RunJob = { id: string; state: string; progress: { completed_molecules?: number; total_molecules?: number; stage?: string }; result?: { scenarios: { id: string; label: string; metrics: Metric[] }[]; comparisons: Record<string, { proportion21: { delta: number | null; delta_interval: number[] } }> } };
const construct = { length_nt: 315, phase_origin_nt: 0, segments: [
  { segment_id: "seg_1", gene_id: "gene_a", start: 0, end: 105 },
  { segment_id: "seg_2", gene_id: "gene_b", start: 105, end: 210 },
  { segment_id: "seg_3", gene_id: "gene_c", start: 210, end: 315 },
] };
const initial: Scenario[] = [
  { id: "baseline", label: "Epsilon constante", seed: 101, epsilon: { type: "constant", schema_version: 1, epsilon: 0.1 } },
  { id: "candidate_1", label: "Epsilon por tramos A", seed: 202, epsilon: { type: "piecewise", schema_version: 1, breakpoints: [106, 211], values: [0.2, 0.1, 0.05] } },
];

export default function CompareClient() {
  const [scenarios, setScenarios] = useState(initial);
  const [count, setCount] = useState(5000);
  const [job, setJob] = useState<RunJob | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!job || !["queued", "running", "cancel_requested"].includes(job.state)) return;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`/api/v1/jobs/${job.id}`, { cache: "no-store" });
        if (!response.ok) return;
        const fresh = await response.json() as RunJob;
        if (fresh.state === "succeeded" && !fresh.result) {
          const resultResponse = await fetch(`/api/v1/jobs/${job.id}/results`, { cache: "no-store" });
          if (resultResponse.ok) fresh.result = await resultResponse.json() as NonNullable<RunJob["result"]>;
        }
        setJob(fresh);
      } catch { /* transient local connection loss; retry next tick */ }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  function updateScenario(index: number, patch: Partial<Scenario>) {
    setScenarios((items) => items.map((item, i) => i === index ? { ...item, ...patch } : item));
  }

  function addScenario() {
    if (scenarios.length >= 4) return;
    const number = scenarios.length;
    setScenarios((items) => [...items, { id: `candidate_${number}`, label: `Escenario ${String.fromCharCode(65 + number)}`, seed: 101 + number * 101, epsilon: { type: "linear", schema_version: 1, epsilon_start: 0.1, epsilon_end: 0.3 } }]);
  }

  async function submit() {
    setBusy(true); setError(""); setJob(null);
    try {
      const request = {
        web_schema_version: 1 as const, label: "Comparacion sintetica", construct,
        n_molecules: count, f_left: 0.5, p22: 0.5,
        scenarios: scenarios.map((scenario) => ({
          id: scenario.id, label: scenario.label, seed: scenario.seed,
          epsilon: scenario.epsilon,
        })),
        baseline_id: "baseline", alpha_family: 0.05 as const,
        compute_exact: construct.length_nt <= 1000 && construct.segments.length <= 16,
      };
      const parsed = jobRequestSchema.safeParse(request);
      if (!parsed.success) throw new Error(parsed.error.issues[0]?.message ?? "Configuracion invalida");
      const response = await fetch("/api/v1/jobs", { method: "POST", headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() }, body: JSON.stringify(parsed.data) });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message ?? "No se pudo iniciar la comparacion");
      setJob(body as RunJob);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Error de conexion con el simulador"); }
    finally { setBusy(false); }
  }

  return <main className="subpage"><Link href="/lab" title="Regresar al laboratorio de simulación"><ArrowLeft size={14}/> Volver al laboratorio</Link><div className="subpage-card compare-editor">
    <span className="sub-icon"><GitCompareArrows/></span><p className="eyebrow">ANALISIS COMPARATIVO</p><h1>Comparar escenarios</h1>
    <p>Constructo sintetico comun de 315 nt, tres segmentos de 105 nt, p22 y mezcla de direcciones iguales. Cada escenario usa una semilla distinta.</p>
    <div className="comparison-scenarios">{scenarios.map((scenario, index) => <article className="comparison-scenario" title="Configuraci?n de epsilon, semilla y nombre para una corrida del constructo com?n" aria-label={`Escenario ${index + 1}`} key={scenario.id}>
      <div className="comparison-scenario-head"><strong>{index === 0 ? "Epsilon constante" : `Escenario ${index + 1}`}</strong>{index === 0 ? <span title="El escenario constante se usa como referencia para calcular las diferencias">REFERENCIA</span> : <button type="button" title="Quitar este escenario de la comparación" aria-label={`Eliminar escenario ${index + 1}`} onClick={() => setScenarios((items) => items.filter((_, i) => i !== index))}><Trash2 size={13}/></button>}</div>
      <label title="Etiqueta para distinguir este escenario en tablas y gr?ficos">Nombre <input title="Nombre descriptivo para identificar este escenario en los resultados" value={scenario.label} maxLength={120} onChange={(event) => updateScenario(index, { label: event.target.value })}/></label>
      <label title="Semilla del generador pseudoaleatorio; permite reproducir este escenario">Semilla <input title="Semilla que hace reproducible la simulación de este escenario" type="number" min={0} max={4294967295} value={scenario.seed} onChange={(event) => updateScenario(index, { seed: Number(event.target.value) })}/></label>
      <EpsilonEditor lengthNt={construct.length_nt} value={scenario.epsilon} lockModel={index === 0} onChange={(epsilon) => updateScenario(index, { epsilon })}/>
    </article>)}</div>
    <button type="button" className="text-link" title="Añadir un candidato nuevo; el límite total es de cuatro escenarios" onClick={addScenario} disabled={scenarios.length >= 4}><Plus size={14}/> Agregar escenario</button>
    <label className="comparison-count" title="N?mero de moleculas simuladas por cada pol?tica epsilon">Moleculas por escenario <input title="Cantidad de moléculas simuladas independientemente para cada escenario" type="number" min={1} max={100000} value={count} onChange={(event) => setCount(Number(event.target.value))}/></label>
    <button type="button" className="primary-link" title="Ejecutar todos los escenarios y calcular sus diferencias respecto de la referencia" onClick={() => void submit()} disabled={busy}>{busy ? "Enviando..." : "Ejecutar comparacion"} <Activity size={15}/></button>
    {error && <div className="info-box" role="alert">{error}</div>}
    {job && <section className="comparison-result" title="Estado y metricas calculadas para cada escenario"><p className="eyebrow" title="Progreso de moleculas procesadas respecto del total solicitado">{job.state.toUpperCase()} · {job.progress.completed_molecules ?? 0} / {job.progress.total_molecules ?? count} moleculas</p><h2>Resultado</h2>{job.result?.scenarios.map((scenario) => <div key={scenario.id}><h3>{scenario.label}</h3><p>{scenario.metrics.filter((metric) => metric.key === "length_21" || metric.key === "gene_crossing").map((metric) => `${metric.key}: ${metric.value == null ? "no definido" : `${(metric.value * 100).toFixed(2)}%`} (${metric.numerator}/${metric.denominator})`).join(" · ")}</p></div>)}{Object.entries(job.result?.comparisons ?? {}).map(([candidate, comparison]) => <p key={candidate}>Candidato menos referencia, 21 nt: {comparison.proportion21.delta == null ? "no definido" : `${(comparison.proportion21.delta * 100).toFixed(2)} puntos porcentuales`}; IC [{comparison.proportion21.delta_interval.map((value) => (value * 100).toFixed(2)).join(", ")}]</p>)}<Link title="Abrir el detalle, las tablas y las exportaciones de esta corrida" href={`/runs/${job.id}`}>Abrir resultado completo</Link></section>}
    <div className="info-box" title="Los intervalos cuantifican incertidumbre del modelo Monte Carlo; no son evidencia experimental">La comparacion estima diferencias de 21 nt e intervalos del modelo. No presupone que epsilon variable aumente o reduzca esa proporcion; las secuencias son sinteticas y no representan evidencia experimental.</div>
  </div></main>;
}
