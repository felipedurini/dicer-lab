"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { parseMultiFasta } from "./fasta";

type Job = {
  id: string;
  state: string;
  kind?: string;
  created_at?: string;
  updated_at?: string;
  finished_at?: string | null;
  progress?: {
    stage?: string;
    operation?: string;
    completed_candidates?: number;
    total_candidates?: number;
    estimated_remaining_seconds?: number | null;
  };
  error?: { message: string };
};
type Candidate = {
  candidate_id: string;
  rank: number;
  sequence_rna: string;
  length_nt: number;
  metrics: Record<string, number>;
  blocks: Array<{ gene_id: string; start: number; end: number }>;
};
type Result = { candidates: Candidate[]; warnings: string[] };
type Reference = { id: string; organism: string; version: string; length_nt: number; record_count?: number; scope?: string; completeness?: string; assembly_accession?: string; annotation_release?: number };
type NcbiRecord = { accession: string; organism: string; description: string; length_nt: number; molecule_type: string; source_uri: string };
type ReferenceStatus = "loading" | "missing" | "ready" | "unauthorized" | "error";
type ReferenceResponse = { items?: Reference[]; catalog_status?: "missing" | "ready"; error?: { message?: string }; detail?: { message?: string } };

const DESIGN_JOB_STORAGE_KEY = "dicer-lab-active-design-job";

const stageLabels: Record<string, string> = {
  queued: "En cola",
  starting: "Preparando el trabajo",
  discover: "Descubriendo ventanas de 21 nt",
  thermodynamics: "Calculando perfiles termodinámicos",
  assemble: "Buscando bloques por gen",
  candidate_generation: "Construyendo combinaciones candidatas",
  screen: "Revisando coincidencias off-target",
  folding: "Plegamiento con ViennaRNA",
  ranking: "Ordenando candidatos",
  complete: "Completado",
};
const terminalStates = new Set(["succeeded", "failed", "cancelled", "deleted"]);

function formatDuration(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function elapsedSeconds(job: Job, now: number): number | null {
  if (!job.created_at) return null;
  const start = Date.parse(job.created_at);
  const end = terminalStates.has(job.state) && job.finished_at
    ? Date.parse(job.finished_at)
    : terminalStates.has(job.state) && job.updated_at ? Date.parse(job.updated_at) : now;
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, (end - start) / 1000) : null;
}

function formatEstimate(seconds: number): string {
  return formatDuration(seconds);
}
const stateLabels: Record<string, string> = {
  queued: "En cola",
  running: "En curso",
  cancel_requested: "Cancelación solicitada",
  succeeded: "Completado",
  failed: "Fallido",
  cancelled: "Cancelado",
};

export default function DesignPage() {
  const [fastaText, setFastaText] = useState("");
  const parsed = useMemo(() => parseMultiFasta(fastaText), [fastaText]);
  const [length, setLength] = useState(42);
  const [references, setReferences] = useState<Reference[]>([]);
  const [referenceIds, setReferenceIds] = useState<string[]>([]);
  const [referenceStatus, setReferenceStatus] = useState<ReferenceStatus>("loading");
  const [referenceError, setReferenceError] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [clockNow, setClockNow] = useState(0);
  const [ncbiOrganism, setNcbiOrganism] = useState("");
  const [ncbiQuery, setNcbiQuery] = useState("");
  const [ncbiAccession, setNcbiAccession] = useState("");
  const [ncbiItems, setNcbiItems] = useState<NcbiRecord[]>([]);
  const [ncbiSelected, setNcbiSelected] = useState<string[]>([]);
  const [ncbiBusy, setNcbiBusy] = useState(false);
  const [ncbiMessage, setNcbiMessage] = useState("");

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const response = await fetch("/api/v1/design/references", { cache: "no-store" });
        const data = await response.json() as ReferenceResponse;
        if (!active) return;
        if (!response.ok) {
          setReferenceStatus(response.status === 401 ? "unauthorized" : "error");
          setReferenceError(data.error?.message ?? data.detail?.message ?? `HTTP ${response.status}`);
          return;
        }
        setReferences(data.items ?? []);
        const beeTranscriptome = (data.items ?? []).find((item: Reference) => item.id === "apis_mellifera_amel_hav3_1_ar104");
        if (beeTranscriptome) setReferenceIds((ids) => ids.length ? ids : [beeTranscriptome.id]);
        setReferenceStatus(data.catalog_status === "missing" ? "missing" : "ready");
      } catch {
        if (active) {
          setReferenceStatus("error");
          setReferenceError("No se pudo conectar con el servicio de diseño.");
        }
      }
    })();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    const savedJobId = window.localStorage.getItem(DESIGN_JOB_STORAGE_KEY);
    if (!savedJobId) return () => { active = false; };
    void (async () => {
      try {
        const response = await fetch(`/api/v1/jobs/${savedJobId}`, { cache: "no-store" });
        if (!response.ok) {
          if (response.status === 404) window.localStorage.removeItem(DESIGN_JOB_STORAGE_KEY);
          else if (active) setMessage("No se pudo recuperar el estado del último diseño. Revisá tu sesión y volvé a intentarlo.");
          return;
        }
        const savedJob = await response.json() as Job & { result_available?: boolean };
        if (!active) return;
        setJob(savedJob);
        if (savedJob.state === "succeeded" && savedJob.result_available) {
          const resultResponse = await fetch(`/api/v1/jobs/${savedJobId}/results`, { cache: "no-store" });
          if (resultResponse.ok && active) setResult(await resultResponse.json() as Result);
        }
        if (["failed", "cancelled"].includes(savedJob.state)) setMessage(savedJob.error?.message ?? stateLabels[savedJob.state]);
      } catch {
        if (active) setMessage("No se pudo recuperar el estado del último diseño; el trabajo del servidor no se cancela al cerrar la pestaña.");
      }
    })();
    return () => { active = false; };
  }, []);

  const jobId = job?.id;
  const jobState = job?.state;
  useEffect(() => {
    if (!jobId || terminalStates.has(jobState ?? "")) return;
    const updateClock = () => setClockNow(Date.now());
    const firstUpdate = setTimeout(updateClock, 0);
    const timer = setInterval(updateClock, 1000);
    return () => { clearTimeout(firstUpdate); clearInterval(timer); };
  }, [jobId, jobState]);
  useEffect(() => {
    if (!jobId || !["queued", "running", "cancel_requested"].includes(jobState ?? "")) return;
    let active = true;
    const timer = setInterval(async () => {
      try {
        const response = await fetch(`/api/v1/jobs/${jobId}`, { cache: "no-store" });
        const updated = await response.json() as Job;
        if (!active) return;
        setJob(updated);
        if (updated.state === "succeeded") {
          const resultResponse = await fetch(`/api/v1/jobs/${jobId}/results`, { cache: "no-store" });
          if (resultResponse.ok) setResult(await resultResponse.json() as Result);
        }
        if (["failed", "cancelled"].includes(updated.state)) setMessage(updated.error?.message ?? updated.state);
      } catch {
        if (active) setMessage("No se pudo actualizar el trabajo");
      }
    }, 1200);
    return () => { active = false; clearInterval(timer); };
  }, [jobId, jobState]);

  const maxBlockLength = parsed.targets.length ? Math.floor(1000 / parsed.targets.length) : 1000;
  const blockFitsSequences = parsed.targets.every((target) => target.sequence_rna.length >= length);
  const blockLengthValid = Number.isInteger(length) && length >= 21 && length <= maxBlockLength && blockFitsSequences;
  const requestedConstructLength = parsed.targets.length * length;
  const hasValidTargets = parsed.error === null && parsed.targets.length >= 2 && parsed.targets.length <= 8;

  async function submit() {
    if (!hasValidTargets || !blockLengthValid) return;
    setBusy(true);
    setMessage("");
    setResult(null);
    try {
      const body = {
        design_schema_version: 1,
        label: "Diseño dsRNA",
        targets: parsed.targets.map(({ gene_id, sequence_rna }) => ({ gene_id, sequence_rna })),
        blocks: parsed.targets.map(({ gene_id }) => ({ gene_id, length_nt: length })),
        reference_ids: referenceIds,
        seed: Math.floor(Math.random() * 2147483647),
        lambda: 1,
        thermo_profile: "lucid_end3_v1",
        iterations: 100,
      };
      const response = await fetch("/api/v1/design/jobs", {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error?.message ?? data.detail?.message ?? "No se pudo enviar el diseño");
      setJob(data as Job);
      if (typeof data.id === "string") window.localStorage.setItem(DESIGN_JOB_STORAGE_KEY, data.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Error de red");
    } finally {
      setBusy(false);
    }
  }

  async function searchNcbi(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNcbiBusy(true);
    setNcbiMessage("");
    setNcbiItems([]);
    setNcbiSelected([]);
    try {
      const params = new URLSearchParams(ncbiAccession.trim()
        ? { accession: ncbiAccession.trim() }
        : { organism: ncbiOrganism.trim(), query: ncbiQuery.trim() });
      const response = await fetch(`/api/v1/ncbi/search?${params.toString()}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail?.message ?? data.error?.message ?? `NCBI respondió HTTP ${response.status}`);
      setNcbiItems(data.items ?? []);
      if (!data.items?.length) setNcbiMessage("NCBI no encontró registros para esa búsqueda.");
    } catch (error) {
      setNcbiMessage(error instanceof Error ? error.message : "No se pudo consultar NCBI.");
    } finally {
      setNcbiBusy(false);
    }
  }

  function appendImported(records: Array<{ accession: string; description: string; sequence_rna: string }>) {
    const existingRecords: Array<{ id: string; sequence: string }> = [];
    let id = "";
    let chunks: string[] = [];
    for (const line of fastaText.split(/\r?\n/)) {
      if (line.startsWith(">")) {
        if (id) existingRecords.push({ id: id.toLowerCase(), sequence: chunks.join("").toUpperCase().replaceAll("T", "U") });
        id = line.slice(1).trim().split(/\s+/, 1)[0] ?? "";
        chunks = [];
      } else if (id) chunks.push(line.trim());
    }
    if (id) existingRecords.push({ id: id.toLowerCase(), sequence: chunks.join("").toUpperCase().replaceAll("T", "U") });
    const existingIds = new Set(existingRecords.map((record) => record.id));
    const existingSequences = new Set(existingRecords.map((record) => record.sequence).filter(Boolean));
    const currentCount = existingRecords.length;
    const added: typeof records = [];
    for (const record of records) {
      const id = record.accession.toLowerCase();
      const sequence = record.sequence_rna.toUpperCase().replaceAll("T", "U");
      if (existingIds.has(id) || existingSequences.has(sequence)) continue;
      existingIds.add(id);
      existingSequences.add(sequence);
      added.push(record);
    }
    if (!added.length) {
      setNcbiMessage("Las secuencias seleccionadas ya están en el multi-FASTA.");
      return;
    }
    if (currentCount + added.length > 8) {
      setNcbiMessage(`El límite es 8 genes objetivo; ahora hay ${currentCount} y seleccionaste ${added.length} nuevos.`);
      return;
    }
    const fasta = added.map((record) => `>${record.accession} ${record.description}\n${record.sequence_rna.match(/.{1,80}/g)?.join("\n") ?? record.sequence_rna}`).join("\n");
    setFastaText((current) => `${current.trimEnd()}${current.trim() ? "\n" : ""}${fasta}\n`);
    setNcbiMessage(`Se agregaron ${added.length} secuencias al multi-FASTA. Podés editarlas o combinarlas con entradas manuales.`);
  }

  async function importNcbiTargets() {
    const selected = ncbiItems.filter((record) => ncbiSelected.includes(record.accession));
    if (!selected.length) return;
    setNcbiBusy(true);
    try {
      const response = await fetch("/api/v1/ncbi/sequences", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ accessions: selected.map((item) => item.accession) }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail?.message ?? "No se pudieron importar las secuencias objetivo.");
      appendImported(data.items);
    } catch (error) {
      setNcbiMessage(error instanceof Error ? error.message : "No se pudieron importar las secuencias.");
    } finally {
      setNcbiBusy(false);
    }
  }

  async function importNcbiReferences() {
    const selected = ncbiItems.filter((record) => ncbiSelected.includes(record.accession));
    if (!selected.length) return;
    const nextSelection = [...new Set([...referenceIds, ...selected.map((record) => `ncbi_${record.accession}`)])];
    if (nextSelection.length > 8) {
      setNcbiMessage("El screening permite seleccionar hasta 8 referencias por diseño. Quitá alguna referencia antes de agregar más.");
      return;
    }
    setNcbiBusy(true);
    try {
      const response = await fetch("/api/v1/ncbi/references", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ accessions: selected.map((item) => item.accession) }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail?.message ?? "No se pudieron registrar las referencias.");
      const imported = data.items as Array<Reference & { scope?: string }>;
      setReferences((current) => [...current.filter((item) => !imported.some((row) => row.id === item.id)), ...imported]);
      setReferenceIds((current) => [...new Set([...current, ...imported.map((item) => item.id)])]);
      setReferenceStatus("ready");
      setNcbiMessage(`Se incorporaron ${imported.length} referencias locales parciales al screening off-target. No son genomas ni transcriptomas completos.`);
    } catch (error) {
      setNcbiMessage(error instanceof Error ? error.message : "No se pudieron registrar las referencias.");
    } finally {
      setNcbiBusy(false);
    }
  }

  async function cancelJob() {
    if (!jobId) return;
    setBusy(true);
    try {
      const response = await fetch(`/api/v1/jobs/${jobId}/cancel`, { method: "POST" });
      const data = await response.json() as Job;
      if (!response.ok) throw Error((data as Job & { message?: string }).message ?? "No se pudo cancelar el trabajo");
      setJob(data);
      setMessage("Se solicitó cancelar el trabajo; el worker finalizará el proceso científico.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo cancelar el trabajo");
    } finally {
      setBusy(false);
    }
  }

  async function simulate(candidate: Candidate) {
    if (!job) return;
    setBusy(true);
    try {
      const request = {
        label: `Dicer · candidato ${candidate.rank}`,
        n_molecules: 1000,
        f_left: 0.5,
        p22: 0.5,
        scenarios: [{ id: "baseline", label: "Constante", seed: 101,
          epsilon: { type: "constant", schema_version: 1, epsilon: 0.1 } }],
        baseline_id: "baseline",
        alpha_family: 0.05,
        compute_exact: false,
      };
      const response = await fetch(`/api/v1/design/jobs/${job.id}/candidates/${candidate.candidate_id}/simulate`, {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": crypto.randomUUID() },
        body: JSON.stringify(request),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error?.message ?? data.detail?.message ?? "No se pudo iniciar la simulación");
      setMessage(`Simulación Dicer en cola: ${data.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Error de red");
    } finally {
      setBusy(false);
    }
  }

  return <main className="subpage">
    <Link href="/lab">← Volver al laboratorio</Link>
    <section className="subpage-card">
      <span className="eyebrow">DISEÑO COMPUTACIONAL · HIPÓTESIS</span>
      <h1>Diseño de dsRNA</h1>
      <p>Encontrá bloques candidatos, revisá su ranking exploratorio y enviá una secuencia al simulador de Dicer. No es una predicción de eficacia experimental.</p>
      <div className="design-form">
        <fieldset><legend>Buscar secuencias en NCBI</legend>
          <form onSubmit={(event) => void searchNcbi(event)}>
            <label htmlFor="ncbi-organism">Organismo
              <input id="ncbi-organism" value={ncbiOrganism} onChange={(event) => setNcbiOrganism(event.target.value)} placeholder="Dalbulus maidis" disabled={Boolean(ncbiAccession.trim())} />
            </label>
            <label htmlFor="ncbi-gene">Nombre o término del gen
              <input id="ncbi-gene" value={ncbiQuery} onChange={(event) => setNcbiQuery(event.target.value)} placeholder="eth" disabled={Boolean(ncbiAccession.trim())} />
            </label>
            <small>O buscá directamente por accession.version</small>
            <label htmlFor="ncbi-accession">Accession
              <input id="ncbi-accession" value={ncbiAccession} onChange={(event) => setNcbiAccession(event.target.value)} placeholder="PZ371507.1" />
            </label>
            <button type="submit" className="secondary-button" disabled={ncbiBusy || (!ncbiAccession.trim() && (!ncbiOrganism.trim() || !ncbiQuery.trim()))}>
              {ncbiBusy ? "Consultando NCBI…" : "Buscar"}
            </button>
          </form>
          {ncbiMessage && <p role="status">{ncbiMessage}</p>}
          {ncbiItems.length > 0 && <>
            <div aria-label="Resultados NCBI">
              {ncbiItems.map((record) => <label key={record.accession}>
                <input type="checkbox" checked={ncbiSelected.includes(record.accession)}
                  onChange={(event) => setNcbiSelected((items) => event.target.checked
                    ? [...items, record.accession]
                    : items.filter((item) => item !== record.accession))} />
                <b>{record.accession}</b> · {record.organism} · {record.description} · {record.length_nt} nt · {record.molecule_type}
              </label>)}
            </div>
            <button type="button" className="secondary-button" disabled={ncbiBusy || !ncbiSelected.length} onClick={() => void importNcbiTargets()}>
              Importar como genes objetivo
            </button>
            <button type="button" className="secondary-button" disabled={ncbiBusy || !ncbiSelected.length} onClick={() => void importNcbiReferences()}>
              Agregar como referencias off-target
            </button>
          </>}
          <small>Las secuencias de referencia se conservan localmente en el catálogo del backend y el screening exacto se ejecuta allí. Los registros importados son secuencias parciales, no genomas ni transcriptomas completos.</small>
          <small>La búsqueda usa NCBI E-utilities. Verificá la procedencia y los avisos del registro antes de reutilizar una secuencia (<a href="https://www.ncbi.nlm.nih.gov/About/disclaimer.html" target="_blank" rel="noreferrer">aviso de NCBI</a>).</small>
        </fieldset>
        <label htmlFor="target-fasta">Genes objetivo en multi-FASTA</label>
        <textarea id="target-fasta" aria-label="Genes objetivo en multi-FASTA" rows={14} spellCheck={false}
          placeholder={">PZ371507.1 descripción opcional del gen\nACGT...\n>segundo_gen otra descripción\nACGU..."}
          value={fastaText} onChange={(event) => setFastaText(event.target.value)} />
        <small>Pegá de 2 a 8 registros juntos. Cada uno empieza con &gt;, seguido del ID y una descripción opcional. Se admiten secuencias multilínea con A, C, G, T o U.</small>
        {parsed.error && <p role="alert">{parsed.error}</p>}
        {!fastaText.trim() && <p role="status">Pegá todas las secuencias en esta única área de texto.</p>}
        {hasValidTargets && <section aria-label="Resumen de genes reconocidos" className="design-target-summary">
          <b>{parsed.targets.length} genes reconocidos</b>
          {parsed.targets.map((target) => <small key={target.gene_id}>
            {target.gene_id}{target.description ? ` · ${target.description}` : ""} · {target.sequence_rna.length} nt
          </small>)}
        </section>}

        <label htmlFor="block-length">Longitud de cada bloque (nt)
          <input id="block-length" type="number" min={21} max={maxBlockLength} value={length}
            onChange={(event) => setLength(Number(event.target.value))} />
        </label>
        <small>Es la cantidad de nucleótidos que se seleccionará de cada gen para construir el dsRNA quimérico. No hace falta recortar manualmente las secuencias originales: el programa busca las regiones candidatas.</small>
        {hasValidTargets && <p role="status">{parsed.targets.length} genes × {length} nt por bloque = {requestedConstructLength} nt por hebra ({requestedConstructLength} pb de dsRNA).</p>}
        {parsed.targets.length > 0 && !blockLengthValid && <p role="alert">Con {parsed.targets.length} genes, cada bloque debe medir al menos 21 nt, no superar {maxBlockLength} nt y caber dentro de cada secuencia objetivo.</p>}

        <fieldset><legend>Referencias para screening off-target exacto (21 nt)</legend>
          {referenceStatus === "loading" && <small>Consultando el catálogo de referencias del backend…</small>}
          {referenceStatus === "missing" && <small>El backend respondió, pero no tiene `DATA_DIR/references/catalog.json`. Para screening off-target real, el responsable debe preparar e instalar referencias versionadas y con licencia en el servicio.</small>}
          {referenceStatus === "unauthorized" && <small role="alert">La sesión no permite consultar las referencias. Volvé a iniciar sesión y reintentá.</small>}
          {referenceStatus === "error" && <small role="alert">No se pudo cargar el catálogo desde el backend: {referenceError}</small>}
          {referenceStatus === "ready" && references.length === 0 && <small>El catálogo está disponible, pero no contiene referencias registradas.</small>}
          {referenceStatus === "ready" && references.length > 0 && <small>{referenceIds.length} referencias seleccionadas de {references.length}. Marca o desmarca para agregar o quitar referencias de este analisis.</small>}
          {referenceStatus === "ready" && references.map((reference) => <label key={reference.id}>
            <input type="checkbox" checked={referenceIds.includes(reference.id)}
              onChange={(event) => setReferenceIds((ids) => event.target.checked
                ? [...ids, reference.id]
                : ids.filter((id) => id !== reference.id))} />
            {reference.scope === "complete_transcriptome"
              ? `${reference.organism} - transcriptoma completo`
              : reference.scope === "partial_reference"
                ? `${reference.organism} - secuencia individual o parcial`
                : `${reference.organism} - ${reference.id}`}
            {` | ${reference.id} | ${reference.version} | ${reference.length_nt.toLocaleString("es-AR")} nt`}
            {reference.record_count ? ` | ${reference.record_count.toLocaleString("es-AR")} registros` : ""}
            {reference.assembly_accession ? ` | Assembly ${reference.assembly_accession}` : ""}
            {reference.annotation_release ? ` | Annotation Release ${reference.annotation_release}` : ""}
            {reference.completeness === "complete_annotated_refseq_transcript_set" ? " | conjunto anotado RefSeq" : ""}
          </label>)}
        </fieldset>
        {(referenceStatus === "missing" || (referenceStatus === "ready" && referenceIds.length === 0)) &&
          <small role="status">Este diseño continuará sin screening off-target si no seleccionás referencias.</small>}
        <button className="primary-button" disabled={busy || !hasValidTargets || !blockLengthValid} onClick={() => void submit()}>
          {busy ? "Procesando…" : "Diseñar candidatos"}
        </button>
      </div>
      {job && <div className="info-box" role="status">
        {stateLabels[job.state] ?? job.state} · {stageLabels[job.progress?.stage ?? ""] ?? job.progress?.stage ?? "En cola"}
        {job.progress?.operation && <p>{job.progress.operation}</p>}
        {job.progress?.stage === "folding" && Number.isInteger(job.progress.total_candidates) && job.progress.total_candidates! > 0 && (() => {
          const completed = job.progress?.completed_candidates ?? 0;
          const total = job.progress?.total_candidates ?? 0;
          const percent = 100 * completed / total;
          return <div aria-label="Progreso de plegamiento con ViennaRNA">
            <p><b>Plegamiento con ViennaRNA - {completed} de {total} candidatos evaluados ({percent.toLocaleString("es-AR", { maximumFractionDigits: 1 })} %).</b></p>
            <progress aria-label="Candidatos evaluados con ViennaRNA" value={completed} max={total} />
            {job.progress?.estimated_remaining_seconds != null && <p>Tiempo restante estimado: {formatEstimate(job.progress.estimated_remaining_seconds)}</p>}
          </div>;
        })()}
        {elapsedSeconds(job, clockNow) !== null && <p>Duración total: <time>{formatDuration(elapsedSeconds(job, clockNow)!)}</time></p>}
        {job.state === "failed" ? ` · ${job.error?.message ?? "falló"}` : ""}
        {["queued", "running", "cancel_requested"].includes(job.state) && <button type="button" className="text-link" disabled={busy || job.state === "cancel_requested"} onClick={() => void cancelJob()}>Cancelar trabajo</button>}
      </div>}
      {message && <div className="info-box" role="status">{message}</div>}
      {result && <>
        <h2>Candidatos evaluados ({result.candidates.length})</h2>
        <p>Ranking Pareto: cobertura y estabilidad exploratoria se maximizan; brecha de energía dimérica se minimiza.</p>
        {result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        {result.candidates.map((candidate) => <article className="run-row" key={candidate.candidate_id}>
          <b>#{candidate.rank} · {candidate.length_nt} nt</b><code>{candidate.sequence_rna}</code>
          <p>Cobertura mínima {candidate.metrics.minimum_gene_coverage.toFixed(3)} · ventanas h {candidate.metrics.high_stability_window_fraction.toFixed(3)} · P {candidate.metrics.dimer_gap_per_nt.toFixed(3)} kcal/mol/nt</p>
          <button className="secondary-button" disabled={busy} onClick={() => void simulate(candidate)}>Simular con Dicer</button>
        </article>)}
        <div className="export-row">{["design-manifest.json", "kmers.jsonl", "candidates.fasta", "ranking.csv"].map((name) =>
          <a key={name} href={`/api/v1/jobs/${job!.id}/exports/${name}`}>{name}</a>)}</div>
      </>}
    </section>
  </main>;
}
