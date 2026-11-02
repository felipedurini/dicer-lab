"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowDownRight, Download, FileJson2, LoaderCircle } from "lucide-react";

type Metric = { key: string; scope: string; scope_id: string | null; numerator: number; denominator: number; value: number | null; basis: string; unit: string; source_kind: string };
type Scenario = { id: string; label: string; model: Record<string, unknown>; config: Record<string, unknown>; summary: { n_products: number; n_molecules: number }; metrics: Metric[]; manifest: Record<string, unknown> };
type Run = { web_schema_version: number; label: string; n_molecules: number; baseline_id: string; construct: { length_nt: number; segments: { segment_id: string; gene_id: string; start: number; end: number }[] }; scenarios: Scenario[]; comparisons: Record<string, unknown> };
type Job = { id: string; label: string; state: string; progress: { stage: string; completed_molecules: number; total_molecules: number }; error: { message: string } | null; result_available: boolean };

export default function RunDetailPage() {
  return <Suspense fallback={<main className="subpage"><div className="subpage-card">Cargando corrida…</div></main>}><RunDetailContent /></Suspense>;
}

function RunDetailContent() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<Run | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    let terminal = false;
    async function load() {
      if (terminal) return;
      try {
        const response = await fetch(`/api/v1/jobs/${id}`, { cache: "no-store" });
        if (!response.ok) throw new Error(response.status === 404 ? "No existe una corrida con ese identificador." : "No se pudo consultar la corrida.");
        const current = await response.json() as Job;
        if (!active) return;
        setJob(current);
        if (["failed", "cancelled", "deleted"].includes(current.state)) terminal = true;
        if (current.result_available) {
          const resultResponse = await fetch(`/api/v1/jobs/${id}/results`, { cache: "no-store" });
          if (!resultResponse.ok) throw new Error("El resultado ya no está disponible.");
          const data = await resultResponse.json() as Run;
          if (active) { setResult(data); terminal = true; }
        }
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Error de red"); }
    }
    void load();
    const timer = window.setInterval(() => { void load(); }, 1500);
    return () => { active = false; window.clearInterval(timer); };
  }, [id]);

  return <main className="subpage"><Link href="/runs" title="Regresar a la lista de corridas guardadas">← Historial de resultados</Link><div className="subpage-card run-detail">
    <p className="eyebrow">RESULTADO CONGELADO · {id.slice(0,8)}</p>
    <h1>{job?.label ?? "Corrida"}</h1>
    {error && <div className="info-box" role="alert">{error}</div>}
    {!error && !job && <div className="info-box"><LoaderCircle size={16}/> Cargando estado del trabajo…</div>}
    {job && !result && !error && <div className="detail-progress"><b>{job.state === "succeeded" ? "Preparando resultados" : job.state === "failed" ? "La corrida falló" : job.state === "cancelled" ? "Corrida cancelada" : "Corrida en curso"}</b><span>{job.progress.stage} · {job.progress.completed_molecules} / {job.progress.total_molecules} moléculas</span>{job.error && <p>{job.error.message}</p>}</div>}
    {result && <>
      <div className="frozen-config" title="Resumen de la configuracion guardada en esta corrida"><span title="Longitud total del constructo en nucleotidos">Constructo <b>{result.construct.length_nt} nt</b></span><span title="Cantidad de tramos contiguos del constructo">Segmentos <b>{result.construct.segments.length}</b></span><span>Moléculas <b>{result.n_molecules}</b></span><span title="Cantidad de politicas epsilon evaluadas">Escenarios <b>{result.scenarios.length}</b></span></div>
      <div className="export-row"><span>Archivos de esta corrida</span><a title="Descargar la configuración, los parámetros y las semillas en JSON" href={`/api/v1/jobs/${id}/exports/configuration.json`}><Download size={12}/> Configuración</a><a title="Descargar resultados y métricas completas en JSON" href={`/api/v1/jobs/${id}/exports/results.json`}><FileJson2 size={12}/> JSON</a><a title="Descargar las métricas tabulares en CSV" href={`/api/v1/jobs/${id}/exports/metrics.csv`}><Download size={12}/> Métricas CSV</a></div>
      {result.scenarios.map((scenario) => <section className="detail-scenario" key={scenario.id}><div className="scenario-heading"><div><span className="eyebrow">ESCENARIO {scenario.id}</span><h2>{scenario.label}</h2></div><a title="Descargar los parámetros y la procedencia científica de este escenario" href={`/api/v1/jobs/${id}/exports/manifest-${scenario.id}.json`}>Manifiesto <ArrowDownRight size={13}/></a></div><div className="table-wrap"><table><thead><tr><th>Métrica</th><th>Ámbito</th><th>Numerador</th><th>Denominador</th><th>Valor</th><th>Base</th></tr></thead><tbody>{scenario.metrics.map((metric, index) => <tr key={`${metric.key}-${metric.scope}-${metric.scope_id}-${metric.source_kind}-${index}`} title={`Métrica ${metric.key}: valor basado en ${metric.numerator} de ${metric.denominator} observaciones`}><td>{metric.key}</td><td>{metric.scope_id ? `${metric.scope}:${metric.scope_id}` : metric.scope}</td><td>{metric.numerator}</td><td>{metric.denominator}</td><td>{metric.value == null ? "No definido" : metric.unit === "fraction" ? `${(metric.value*100).toFixed(2)}%` : metric.value.toFixed(3)}</td><td>{metric.source_kind === "exact_expectation" ? "DP exacta" : metric.basis}</td></tr>)}</tbody></table></div></section>)}
    </>}
  </div></main>;
}
