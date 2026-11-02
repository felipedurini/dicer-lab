"use client";

import { useEffect, useMemo, useReducer, useState } from "react";
import Link from "next/link";
import { Activity, ArrowDownRight, ArrowLeft, ArrowRight, Beaker, Check, ChevronDown, CircleHelp, Clock3, Dna, Download, FlaskConical, History, Pause, Play, Plus, RotateCcw, Settings2, Sparkles, Square, Waves } from "lucide-react";
import type { ReactNode } from "react";
import { initialPlayback, playbackReducer } from "@/lib/playback";
import { jobRequestSchema, previewRequestSchema } from "@/lib/validation";
import AccountMenu from "./account-menu";
import EpsilonEditor, { type EpsilonConfig } from "./epsilon-editor";

type Cut = { kind: "cut"; start: number; end: number; length_nt: number; cut_index: number; annotation: { crossed_segment_boundaries: number[]; crossed_gene_boundaries: number[]; touching_segment_ids: string[]; relative_phase_before: number; global_phase_before: number; aligned21_global: boolean } };
type Terminal = { kind: "terminal"; start: number; end: number; length_nt: number; reason: string };
type Trajectory = { direction: "left" | "right"; events: (Cut | Terminal)[]; trajectory_hash: string; remainder: { start: number; end: number; length_nt: number; reason: string } };
type Job = { id: string; state: string; progress: { completed?: number; total?: number; stage?: string }; result?: { scenarios: { id: string; label: string; metrics: { key: string; scope: string; scope_id: string | null; numerator: number; denominator: number; value: number | null; source_kind: string }[] }[]; comparisons: Record<string, { proportion21: { delta: number | null; delta_interval: number[] } }> } };

const colors = ["#56b4e9", "#e69f00", "#009e73", "#cc79a7", "#f0e442", "#d55e00", "#b8c0ff", "#b8c4d1"];
export default function LabClient() {
  const [lengths, setLengths] = useState([105, 105, 105]);
  const [geneIds, setGeneIds] = useState(["gene_a", "gene_b", "gene_c"]);
  const segments = useMemo(() => {
    return lengths.map((length, i) => ({ segment_id: `seg_${i + 1}`, gene_id: geneIds[i], start: lengths.slice(0, i).reduce((sum, value) => sum + value, 0), end: lengths.slice(0, i + 1).reduce((sum, value) => sum + value, 0) }));
  }, [lengths, geneIds]);
  const [epsilonConfig, setEpsilonConfig] = useState<EpsilonConfig>({ type: "constant", schema_version: 1, epsilon: 0.1 });
  const [fLeft, setFLeft] = useState(0.5);
  const [seed, setSeed] = useState(101);
  const [count, setCount] = useState(5000);
  const [trajectory, setTrajectory] = useState<Trajectory | null>(null);
  const [playback, dispatchPlayback] = useReducer(playbackReducer, initialPlayback);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const total = lengths.reduce((a, b) => a + b, 0);
  const epsilonInput = epsilonConfig;
  const cuts = trajectory?.events.filter((event): event is Cut => event.kind === "cut") ?? [];
  const cursor = playback.index;
  const playing = playback.playing;
  const setCursor = (index: number) => dispatchPlayback({ type: "seek", index, eventCount: cuts.length });
  const shown = cuts.slice(0, cursor);

  useEffect(() => {
    if (!playing || !trajectory) return;
    const timer = window.setInterval(() => dispatchPlayback({ type: "next", eventCount: cuts.length }), 720 / playback.speed);
    return () => window.clearInterval(timer);
  }, [playing, trajectory, cuts.length, playback.speed]);

  useEffect(() => {
    if (!job || !["queued", "running", "cancel_requested"].includes(job.state)) return;
    const timer = window.setInterval(async () => {
      try { const response = await fetch(`/api/v1/jobs/${job.id}`, { cache: "no-store" }); if (response.ok) { const fresh = await response.json() as Job; if (fresh.state === "succeeded" && !fresh.result) { const resultResponse = await fetch(`/api/v1/jobs/${job.id}/results`, { cache: "no-store" }); if (resultResponse.ok) fresh.result = await resultResponse.json() as NonNullable<Job["result"]>; } setJob(fresh); } }
      catch { /* polling resumes on the next interval */ }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  async function createTrajectory() {
    setBusy(true); setError(""); setTrajectory(null); dispatchPlayback({ type: "replace", eventCount: cuts.length }); setJob(null);
    try {
      const request = { web_schema_version: 1, construct: { length_nt: total, phase_origin_nt: 0, segments }, p22: 0.5, f_left: fLeft, seed, epsilon: epsilonInput };
      const validation = previewRequestSchema.safeParse(request);
      if (!validation.success) throw new Error(validation.error.issues[0]?.message ?? "Configuración inválida");
      const response = await fetch("/api/v1/trajectories", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({
        ...validation.data,
      }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message ?? "No se pudo generar la trayectoria");
      setTrajectory(body as Trajectory);
    } catch (exception) { setError(exception instanceof Error ? exception.message : "Error de conexión con el simulador"); }
    finally { setBusy(false); }
  }

  async function runPopulation() {
    setBusy(true); setError("");
    try {
      const request = {
        web_schema_version: 1 as const, label: "Exploración sintética", construct: { length_nt: total, phase_origin_nt: 0, segments }, n_molecules: count, f_left: fLeft, p22: 0.5,
        scenarios: [
          { id: "baseline", label: "Epsilon constante", seed, epsilon: epsilonConfig.type === "constant" ? epsilonConfig : { type: "constant" as const, schema_version: 1 as const, epsilon: 0.1 } },
          ...(epsilonConfig.type !== "constant" ? [{ id: "variable", label: "Epsilon variable", seed: (seed + 1) % 4_294_967_296, epsilon: epsilonInput }] : []),
        ], baseline_id: "baseline", alpha_family: 0.05 as const, compute_exact: total <= 1000 && segments.length <= 16,
      };
      const validation = jobRequestSchema.safeParse(request);
      if (!validation.success) throw new Error(validation.error.issues[0]?.message ?? "Configuración inválida");
      const response = await fetch("/api/v1/jobs", { method: "POST", headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() }, body: JSON.stringify({
        ...validation.data,
      }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message ?? "No se pudo iniciar la corrida");
      setJob(body as Job);
    } catch (exception) { setError(exception instanceof Error ? exception.message : "Error de conexión con el simulador"); }
    finally { setBusy(false); }
  }

  async function cancelJob() {
    if (!job) return;
    await fetch(`/api/v1/jobs/${job.id}/cancel`, { method: "POST" });
  }

  function updateLength(index: number, value: number) {
    setLengths((items) => items.map((item, i) => i === index ? Math.max(1, Math.min(5000 - items.reduce((s, n, j) => j === index ? s : s + n, 0), value || 1)) : item));
    setTrajectory(null); setJob(null);
  }

  function addSegment() {
    if (lengths.length >= 32 || total >= 5000) return;
    setLengths((items) => [...items, Math.min(105, 5000 - total)]);
    setGeneIds((items) => [...items, `gene_${items.length + 1}`]);
    setTrajectory(null); setJob(null);
  }

  function removeSegment(index: number) {
    if (lengths.length <= 1) return;
    setLengths((items) => items.filter((_, i) => i !== index));
    setGeneIds((items) => items.filter((_, i) => i !== index));
    setTrajectory(null); setJob(null);
  }

  const palette = new Map<string, string>();
  segments.forEach((segment) => { if (!palette.has(segment.gene_id)) palette.set(segment.gene_id, colors[palette.size % colors.length]); });
  const currentEvent = shown.at(-1);
  const cursorX = trajectory ? currentEvent ? (trajectory.direction === "left" ? currentEvent.end : currentEvent.start) : (trajectory.direction === "left" ? 0 : total) : 0;
  const n21 = job?.result?.scenarios[0]?.metrics.find((metric) => metric.key === "length_21" && metric.scope === "global");
  const n22 = job?.result?.scenarios[0]?.metrics.find((metric) => metric.key === "length_22" && metric.scope === "global");
  const n24 = job?.result?.scenarios[0]?.metrics.find((metric) => metric.key === "length_24" && metric.scope === "global");
  const crossing = job?.result?.scenarios[0]?.metrics.find((metric) => metric.key === "gene_crossing" && metric.scope === "global");
  const products = job?.result?.scenarios[0]?.metrics.find((metric) => metric.key === "length_21" && metric.scope === "global")?.denominator;
  const delta21 = job?.result?.comparisons.variable?.proportion21.delta;
  const lengthRows = [{ length: 21, metric: n21, color: "#67e8f9" }, { length: 22, metric: n22, color: "#e6ae56" }, { length: 24, metric: n24, color: "#c48fc0" }];

  return <main className="lab-shell">
    <header className="topbar">
      <a className="brand" href="/lab" title="Ir al laboratorio de simulación"><span className="brand-mark"><Dna size={20}/></span><span><b>Dicer Lab</b><small>Procesamiento de dsRNA</small></span></a>
      <nav aria-label="Navegación principal"><a className="active" href="/lab" title="Configurar y ejecutar una simulación individual"><FlaskConical size={15}/>Laboratorio</a><Link href="/design" title="Diseñar secuencias candidatas de dsRNA"><Dna size={15}/>Diseño de dsRNA</Link><a href="/compare" title="Comparar hasta cuatro políticas epsilon sobre el mismo constructo"><Waves size={15}/>Comparar</a><Link href="/runs" title="Consultar corridas guardadas y exportar sus resultados"><History size={15}/>Resultados</Link><a href="/help" title="Consultar definiciones, convenciones y límites científicos"><CircleHelp size={15}/>Ayuda</a></nav>
      <AccountMenu />
    </header>
    <div className="page-heading"><div><div className="eyebrow"><span className="live-dot"/> ESPACIO DE TRABAJO · LOCAL</div><h1>Laboratorio <span>de procesamiento</span></h1><p>Explorá cómo la longitud restante modula los productos del modelo.</p></div><button className="quiet-button" title="Restablecer constructo, epsilon, probabilidades y semilla al preset inicial" onClick={() => { setLengths([105,105,105]); setGeneIds(["gene_a","gene_b","gene_c"]); setEpsilonConfig({ type: "constant", schema_version: 1, epsilon: .1 }); setFLeft(.5); setSeed(101); setTrajectory(null); setJob(null); }}><RotateCcw size={15}/> Restaurar preset</button></div>
    <div className="workspace">
      <aside className="editor-column">
        <section className="panel editor-panel">
          <div className="panel-title"><div className="icon-tile cyan"><Settings2 size={17}/></div><div><h2>Configuración</h2><p>Definí la molécula y el proceso</p></div><button className="dots" title="Indicador de opciones adicionales; todavía no tiene acciones disponibles" aria-label="Más opciones">···</button></div>
          <div className="field-label"><span>Constructo sintético</span><span className="tag">PRESET</span></div>
          <div className="total-card" title="Longitud total del constructo; cada bloque coloreado representa un segmento"><div><span>Longitud total - {segments.length} segmentos</span><strong>{total}<small> nt</small></strong></div><div className="mini-construct">{segments.map((s, i) => <i key={s.segment_id} style={{ width: `${(lengths[i] / Math.max(total,1))*100}%`, background: palette.get(s.gene_id) }} />)}</div></div>
          <div className="segment-list">{segments.map((segment, i) => <div className="segment-row" key={segment.segment_id}><i className="gene-swatch" style={{ background: palette.get(segment.gene_id) }}/><div className="segment-name" title={`Tramo contiguo del constructo; coordenadas semiabiertas ${segment.start} a ${segment.end}`}><b>Segmento {i + 1}</b><small>[{segment.start}, {segment.end})</small></div><label className="number-input" title="Longitud del segmento en nucleotidos"><input title="Cambiar cuántos nucleótidos ocupa este segmento" aria-label={`Longitud segmento ${i + 1}`} type="number" min={1} max={5000} value={lengths[i]} onChange={(e) => updateLength(i, Number(e.target.value))}/><span>nt</span></label><label className="number-input" title="Identificador de gen; repetirlo agrupa segmentos en el mismo gen"><input title="Asignar un identificador de gen; repetirlo agrupa segmentos en un mismo gen" aria-label={`Gene ID segmento ${i + 1}`} type="text" value={geneIds[i]} onChange={(e) => { setGeneIds((items) => items.map((gene, index) => index === i ? e.target.value : gene)); setTrajectory(null); setJob(null); }}/></label><button type="button" title="Quitar este segmento del constructo" aria-label={`Eliminar segmento ${i + 1}`} onClick={() => removeSegment(i)} disabled={segments.length <= 1}>Quitar</button></div>)}</div>
          <button type="button" className="text-link" title="Añadir otro tramo contiguo al constructo" onClick={addSegment} disabled={segments.length >= 32 || total >= 5000}><Plus size={13}/> Agregar segmento</button>
          <div className="section-divider"/><div className="field-label"><span>Política de epsilon</span></div>
          <EpsilonEditor lengthNt={total} value={epsilonConfig} onChange={setEpsilonConfig}/>
          <div className="section-divider"/><div className="two-fields"><label title="Fraccion de moleculas que inicia desde el extremo izquierdo; las restantes comienzan desde la derecha"><span>Desde la izquierda <b>{fLeft.toFixed(2)}</b></span><input title="Fraccion de moleculas que inicia desde el extremo izquierdo; las restantes comienzan desde la derecha" aria-label="Proporcion desde la izquierda" className="slider" type="range" min={0} max={1} step={0.01} value={fLeft} onChange={(e) => setFLeft(Number(e.target.value))}/></label></div>
          <div className="two-fields last"><label title="Valor inicial del generador pseudoaleatorio; repetirlo y la configuracion reproduce la corrida"><span>Semilla <button className="text-link" type="button" title="Generar una semilla aleatoria nueva para cambiar la secuencia reproducible" onClick={() => setSeed(Math.floor(Math.random()*4_294_967_296))}>Nueva</button></span><input title="Semilla que permite repetir la misma corrida con igual configuración" className="plain-input mono" type="number" min={0} max={4294967295} value={seed} onChange={(e) => setSeed(Math.max(0,Math.min(4_294_967_295,Number(e.target.value))))}/></label><label title="Numero de moleculas independientes simuladas en la poblacion"><span>Moléculas</span><input title="Cantidad de moléculas independientes simuladas en la población" className="plain-input mono" type="number" min={1} max={100000} value={count} onChange={(e) => setCount(Math.max(1,Math.min(100000,Number(e.target.value))))}/></label></div>
          <button className="primary-button" title="Simular una molécula y mostrar sus cortes en orden, con la semilla actual" onClick={createTrajectory} disabled={busy || total < 21}><Sparkles size={16}/>{busy ? "Procesando…" : "Generar trayectoria"}<ArrowRight size={15}/></button>
          <button className="secondary-button" title="Simular la cantidad de moléculas indicada y calcular estadísticas agregadas" onClick={runPopulation} disabled={busy || total < 21}><Activity size={16}/>Ejecutar población <span>↗</span></button>
          <p className="tiny-note"><Clock3 size={12}/> Las corridas se procesan en segundo plano.</p>
        </section>
        <section className="note-panel"><span className="note-icon"><Beaker size={15}/></span><p><b>Exploración científica</b><br/>El modelo describe supuestos matemáticos; no representa evidencia experimental.</p></section>
      </aside>

      <section className="results-column">
        <section className="panel trajectory-panel">
          <div className="result-header"><div><div className="eyebrow">VISTA MOLECULAR <span className="separator">/</span> {total} NT</div><h2>Trayectoria individual <span className="seed-pill">semilla {seed}</span></h2><p>Procesamiento de un dsRNA sintético de izquierda a derecha o viceversa.</p></div><button className="outline-button" title="Copiar el hash que identifica esta trayectoria reproducible" disabled={!trajectory} onClick={() => trajectory && navigator.clipboard.writeText(trajectory.trajectory_hash)}><Download size={14}/> Hash</button></div>
          <div className="gene-legend">{segments.map((s) => <span key={s.segment_id} title={`Segmento ${s.segment_id}, perteneciente al gen ${s.gene_id}; longitud ${s.end-s.start} nt`}><i style={{ background: palette.get(s.gene_id) }}/>{s.gene_id}<small>{s.end-s.start} nt</small></span>)}</div>
          <div className="molecule-stage">
            <div className="axis" title="Coordenadas en nucleotidos a lo largo del constructo"><span>0</span><span>{Math.round(total/4)}</span><span>{Math.round(total/2)}</span><span>{Math.round(total*3/4)}</span><span>{total}</span></div>
            <svg className="molecule-svg" viewBox={`0 0 ${Math.max(total,1)} 120`} role="img" aria-label={`Molécula dsRNA de ${total} nucleótidos con ${shown.length} cortes reproducidos`} preserveAspectRatio="none">
              <title>Vista espacial de segmentos y cortes emitidos hasta el evento seleccionado</title>
              <defs><pattern id="dots" width="7" height="7" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".7" fill="#8da1bb" opacity=".42"/></pattern></defs>
              <rect x="0" y="25" width={total} height="54" rx="8" fill="#0c1727" stroke="#263950"/>
              {segments.map((s) => <g key={s.segment_id}><rect x={s.start} y="25" width={s.end-s.start} height="54" fill={palette.get(s.gene_id)} opacity=".13"/><line x1={s.start} x2={s.start} y1="20" y2="84" stroke="#dce8f8" strokeOpacity=".42" strokeDasharray="2 3"/>{s.start > 0 && <text x={s.start+2} y="96" fill="#a8b8cc" fontSize="4.3">{s.gene_id.replace("gene_", "Gen ")}</text>}</g>)}
              <line x1="0" x2={total} y1="43" y2="43" stroke="#8fa4bf" strokeWidth="1.5" opacity=".65"/><line x1="0" x2={total} y1="61" y2="61" stroke="#8fa4bf" strokeWidth="1.5" opacity=".65"/>
              <rect x="0" y="25" width={total} height="54" rx="8" fill="url(#dots)"/>
              {shown.map((cut) => <g key={`${cut.start}-${cut.end}`}>{segments.map((segment) => { const start = Math.max(cut.start, segment.start); const end = Math.min(cut.end, segment.end); return end > start ? <rect key={segment.segment_id} x={start} y="29" width={end-start} height="46" fill={palette.get(segment.gene_id)} opacity=".88"/> : null; })}<line x1={cut.end} x2={cut.end} y1="18" y2="86" stroke="#fff" strokeOpacity=".7" strokeWidth=".55"/></g>)}
              {trajectory && <g><line x1={cursorX} x2={cursorX} y1="12" y2="88" stroke="#67e8f9" strokeWidth="2"/><path d={`M${cursorX} 8 L${cursorX-3} 13 L${cursorX+3} 13Z`} fill="#67e8f9"/></g>}
            </svg>
            {!trajectory && <div className="empty-overlay"><div className="empty-orbit"><Dna size={28}/></div><b>Tu molécula está lista</b><span>Generá una trayectoria real para visualizar<br/>cada producto en orden de emisión.</span></div>}
          </div>
          <div className="playback"><button title="Volver al inicio de la animación, antes del primer corte" aria-label="Inicio" onClick={() => dispatchPlayback({ type: "reset", eventCount: cuts.length })}><Square size={13} fill="currentColor"/></button><button title={playing ? "Pausar la reproducción de cortes" : "Reproducir la trayectoria automáticamente"} className="play-button" aria-label={playing ? "Pausar" : "Reproducir"} disabled={!trajectory || !cuts.length} onClick={() => dispatchPlayback({ type: "toggle", eventCount: cuts.length })}>{playing ? <Pause size={16} fill="currentColor"/> : <Play size={16} fill="currentColor"/>}</button><button title="Mostrar el corte anterior" aria-label="Paso anterior" onClick={() => dispatchPlayback({ type: "previous", eventCount: cuts.length })}><ArrowLeft size={14}/></button><button title="Mostrar el corte siguiente" aria-label="Paso siguiente" onClick={() => dispatchPlayback({ type: "next", eventCount: cuts.length })}><ArrowRight size={14}/></button><span className="event-count" title="Posicion del evento actual dentro de la trayectoria">Evento <b>{cursor}</b> de {cuts.length || "—"}</span><input title="Desplazar el cursor para inspeccionar un evento de corte" aria-label="Posición de reproducción" type="range" min={0} max={Math.max(cuts.length,1)} value={cursor} disabled={!trajectory} onChange={(e) => setCursor(Number(e.target.value))}/><label className="speed" aria-label="Velocidad de reproducción"><select title="Ajustar la velocidad de reproducción de la trayectoria" value={playback.speed} onChange={(e) => dispatchPlayback({ type: "speed", speed: Number(e.target.value) as 0.25 | 0.5 | 1 | 2 | 4 })}><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1">1×</option><option value="2">2×</option><option value="4">4×</option></select><ChevronDown size={12}/></label></div>
          <div className="event-detail" title="Detalle del evento seleccionado: coordenadas, longitud, junturas atravesadas y fase"><span className="event-icon"><Waves size={14}/></span>{currentEvent ? <><b>Producto {currentEvent.cut_index} · {currentEvent.length_nt} nt</b><span>[{currentEvent.start}, {currentEvent.end})</span>{currentEvent.annotation.crossed_gene_boundaries.length > 0 ? <em className="crossing">Cruza juntura entre genes</em> : currentEvent.annotation.crossed_segment_boundaries.length > 0 ? <em>Cruza segmento · mismo gen</em> : <em>Dentro de un segmento</em>}<em>Fase {currentEvent.annotation.relative_phase_before} / global {currentEvent.annotation.global_phase_before}{currentEvent.annotation.aligned21_global ? " · alineado 21" : ""}</em></> : <><b>{trajectory ? `Trayectoria ${trajectory.direction === "left" ? "izquierda" : "derecha"} completada` : "Esperando trayectoria"}</b><span>{trajectory ? `Remanente ${trajectory.remainder.length_nt} nt · ${trajectory.remainder.reason}` : "Los eventos aparecerán aquí en su orden real."}</span></>}</div>
          {trajectory && <div className="trace-line"><Check size={13}/> Reproducible <span>·</span><code>{trajectory.trajectory_hash.slice(0,24)}…</code></div>}
        </section>

        <section className="panel population-panel">
          <div className="result-header compact"><div><div className="eyebrow">SIMULACIÓN DE POBLACIÓN <span className="separator">/</span> MONTE CARLO</div><h2>Resumen de resultados</h2><p>{job ? `Corrida ${job.id.slice(0,8)} · semilla ${seed}` : "Las estadísticas aparecerán al completar la población."}</p></div>{job && <span className={`status-badge ${job.state}`}><i/>{job.state === "succeeded" ? "Completado" : job.state === "failed" ? "Falló" : job.state === "cancelled" ? "Cancelado" : job.state === "queued" ? "En cola" : "En proceso"}</span>}</div>
          {job && ["queued", "running", "cancel_requested"].includes(job.state) && <div className="progress-wrap"><div className="progress-label"><span>{job.progress.stage ?? "En cola"}</span><span>{job.progress.completed ?? 0} / {job.progress.total ?? count}</span></div><div className="progress-track"><i style={{ width: `${Math.min(100,100*(job.progress.completed ?? 0)/(job.progress.total || count))}%` }}/></div><button className="text-link" title="Solicitar la cancelación de la corrida en curso" onClick={cancelJob}>Cancelar corrida</button></div>}
          {job?.result ? <><div className="metric-grid"><Metric title="Productos de 21 nt" description="Fracción de productos simulados que mide exactamente 21 nt" value={n21?.value == null ? "—" : `${(n21.value*100).toFixed(1)}%`} sub={`${n21?.numerator ?? 0} de ${n21?.denominator ?? 0} productos`} icon={<Waves size={16}/>} /><Metric title="Cruce entre genes" description="Fracción de productos que atraviesa una frontera entre genes distintos" value={crossing?.value == null ? "—" : `${(crossing.value*100).toFixed(1)}%`} sub="De todos los productos emitidos" icon={<ArrowDownRight size={16}/>} /><Metric title="Δ proporción 21 nt" description="Cambio frente a la referencia constante; positivo indica mayor proporción de productos de 21 nt" value={delta21 == null ? "—" : `${delta21 > 0 ? "+" : ""}${(delta21*100).toFixed(1)} pp`} sub={delta21 == null ? "Una política en esta corrida" : "Por tramos − constante"} icon={<Activity size={16}/>} /></div><div className="distribution" title="Proporción de productos observados de 21, 22 y 24 nucleótidos"><div className="distribution-head"><b>Distribución de longitudes</b><span>Productos emitidos · N = {products ?? 0}</span></div><div className="distribution-bar">{lengthRows.map(({metric,color},i) => <i key={i} style={{ width: `${metric?.value == null ? 0 : metric.value*100}%`, background: color }}/>)}</div><div className="distribution-legend" title="Cada color representa la cantidad de productos de esa longitud">{lengthRows.map(({length,metric,color}) => <span key={length}><i style={{background:color}}/>{length} nt <b>{metric?.numerator ?? 0}</b></span>)}</div></div><div className="export-row"><span>Datos del modelo, con numeradores y denominadores</span><a title="Descargar la tabla de métricas en formato CSV" href={`/api/v1/jobs/${job.id}/exports/metrics.csv`}>CSV</a><a title="Descargar los resultados completos en formato JSON" href={`/api/v1/jobs/${job.id}/exports/results.json`}>JSON</a><a title="Descargar la configuración completa usada en esta corrida" href={`/api/v1/jobs/${job.id}/exports/configuration.json`}>Configuración</a></div><div className="result-foot"><span>Resumen agregado de {products ?? 0} productos. Los productos de una molécula no son réplicas independientes.</span><Link className="text-link" title="Abrir la lista de corridas guardadas" href="/runs">Ver historial <ArrowRight size={13}/></Link></div></> : <div className="empty-results"><div className="empty-chart"><span/><span/><span/><span/><span/><span/><span/></div><div><b>Sin resultados todavía</b><span>Ejecutá una población para calcular métricas agregadas.</span></div><button className="small-run" title="Iniciar una simulación de población con la configuración actual" onClick={runPopulation} disabled={busy}><Plus size={14}/> Nueva corrida</button></div>}
        </section>
        <div className="scientific-note" title="Las salidas dependen de los supuestos del modelo y no son datos experimentales"><span>i</span> Simulación bajo supuestos del modelo. No es evidencia experimental ni predicción de eficacia.</div>
        {error && <div className="error-banner" role="alert">{error}<button title="Cerrar este mensaje de error" onClick={() => setError("")}>Cerrar</button></div>}
      </section>
    </div>
    <footer className="footer"><span>© Dicer Lab <i/> Laboratorio de simulación reproducible</span><span><span className="live-dot"/> Motor científico Python · v1.0</span></footer>
  </main>;
}

function Metric({ title, description, value, sub, icon }: { title: string; description: string; value: string; sub: string; icon: ReactNode }) {
  return <article className="metric-card" title={description}><div className="metric-title"><span>{icon}</span>{title}</div><strong>{value}</strong><small>{sub}</small></article>;
}
