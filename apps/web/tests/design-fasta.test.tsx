// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DesignPage from "../app/design/page";
import { parseMultiFasta } from "../app/design/fasta";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.localStorage.removeItem("dicer-lab-active-design-job"); });

const longDna = "ACGT".repeat(23);

describe("parser multi-FASTA de objetivos", () => {
  it("reconoce tres accesiones, descripciones largas, secuencias multilínea y normaliza T", () => {
    const parsed = parseMultiFasta(
      `>PZ371507.1 ecdysis triggering hormone transcript, voucher CeBio_01_1; descripcion extendida\n${longDna.slice(0, 40)}\n${longDna.slice(40)}\n` +
      `>PZ371508.1 bursicon alpha mRNA from Dalbulus maidis, voucher CeBio_01_2\n${longDna}\n` +
      `>GITV01008430.1 transcript region with a deliberately long descriptive header\n${longDna}`,
    );

    expect(parsed.error).toBeNull();
    expect(parsed.targets).toHaveLength(3);
    expect(parsed.targets.map(({ gene_id }) => gene_id)).toEqual(["PZ371507.1", "PZ371508.1", "GITV01008430.1"]);
    expect(parsed.targets[0].description).toContain("voucher CeBio_01_1; descripcion extendida");
    expect(parsed.targets[0].sequence_rna).toBe(longDna.replaceAll("T", "U"));
  });

  it("devuelve errores comprensibles para encabezados, cantidad, IDs y bases inválidas", () => {
    expect(parseMultiFasta("ACGTACGT").error).toMatch(/antes del primer encabezado/i);
    expect(parseMultiFasta(`>same desc\n${longDna}\n>same other\n${longDna}`).error).toMatch(/ID repetido/i);
    expect(parseMultiFasta(`>g1\n${longDna}`).error).toMatch(/entre 2 y 8/i);
    expect(parseMultiFasta(Array.from({ length: 9 }, (_, index) => `>g${index}\n${longDna}`).join("\n")).error).toMatch(/entre 2 y 8/i);
    expect(parseMultiFasta(`>g1\n${longDna}\n>g2\n${"ACGN".repeat(23)}`).error).toMatch(/carácter inválido/i);
    expect(parseMultiFasta(`>g1\n${longDna}\n>\n${longDna}`).error).toMatch(/encabezado/i);
  });
});

describe("formulario de diseño multi-FASTA", () => {
  it("preselects the complete Apis mellifera transcriptome and allows deselection", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input).endsWith("/design/references")) return new Response(JSON.stringify({ items: [{
        id: "apis_mellifera_amel_hav3_1_ar104", organism: "Apis mellifera", version: "GCF_003254395.2; Annotation Release 104",
        length_nt: 98_645_700, record_count: 27_887, scope: "complete_transcriptome",
        completeness: "complete_annotated_refseq_transcript_set", assembly_accession: "GCF_003254395.2", annotation_release: 104,
      }], catalog_status: "ready" }));
      return new Response("{}", { status: 404 });
    });
    render(<DesignPage />);
    const reference = await screen.findByRole("checkbox", { name: /Apis mellifera - transcriptoma completo/ }) as HTMLInputElement;
    expect(reference.checked).toBe(true);
    expect(screen.getByText(/Assembly GCF_003254395.2/)).toBeTruthy();
    expect(screen.getByText(/Annotation Release 104/)).toBeTruthy();
    fireEvent.click(reference);
    expect(reference.checked).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/design/references", { cache: "no-store" });
  });

  it("busca un accession NCBI e importa su secuencia conservando ID y descripción", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/design/references")) return new Response(JSON.stringify({ items: [], catalog_status: "ready" }));
      if (url.includes("/ncbi/search?accession=PZ371507.1")) return new Response(JSON.stringify({ items: [{
        accession: "PZ371507.1", organism: "Dalbulus maidis", description: "eth mRNA", length_nt: 615,
        molecule_type: "mRNA", source_uri: "https://www.ncbi.nlm.nih.gov/nuccore/PZ371507.1",
      }] }));
      if (url.endsWith("/ncbi/sequences") && init?.method === "POST") return new Response(JSON.stringify({ items: [{
        accession: "PZ371507.1", description: "eth mRNA from Dalbulus maidis", sequence_rna: "ACGU".repeat(21),
      }] }));
      return new Response("{}", { status: 404 });
    });
    render(<DesignPage />);
    fireEvent.change(screen.getByLabelText("Accession"), { target: { value: "PZ371507.1" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    expect(await screen.findByText(/Dalbulus maidis · eth mRNA · 615 nt/)).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Importar como genes objetivo/i }));
    await waitFor(() => expect((screen.getByRole("textbox", { name: /multi-FASTA/i }) as HTMLTextAreaElement).value).toContain(">PZ371507.1 eth mRNA from Dalbulus maidis"));
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/ncbi/sequences"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ accessions: ["PZ371507.1"] });
  });

  it("registra secuencias importadas como referencias parciales y las selecciona para off-target", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/design/references")) return new Response(JSON.stringify({ items: [], catalog_status: "missing" }));
      if (url.includes("/ncbi/search?accession=GITV01008430.1")) return new Response(JSON.stringify({ items: [{
        accession: "GITV01008430.1", organism: "Dalbulus maidis", description: "TSA transcript", length_nt: 1503,
        molecule_type: "RNA", source_uri: "https://www.ncbi.nlm.nih.gov/nuccore/GITV01008430.1",
      }] }));
      if (url.endsWith("/ncbi/references") && init?.method === "POST") return new Response(JSON.stringify({ items: [{
        id: "ncbi_GITV01008430.1", organism: "Dalbulus maidis", version: "GITV01008430.1", length_nt: 1503, scope: "partial_reference",
      }] }));
      return new Response("{}", { status: 404 });
    });
    render(<DesignPage />);
    fireEvent.change(screen.getByLabelText("Accession"), { target: { value: "GITV01008430.1" } });
    fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
    await screen.findByText(/TSA transcript · 1503 nt/);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Agregar como referencias off-target/i }));
    expect(await screen.findByText(/secuencia individual o parcial/i)).toBeTruthy();
    expect((screen.getByRole("checkbox", { name: /ncbi_GITV01008430.1/ }) as HTMLInputElement).checked).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/ncbi/references", expect.objectContaining({ method: "POST" }));
  });

  it("resume tres genes, calcula la quimera y envía los objetivos normalizados al backend", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/design/references")) return new Response(JSON.stringify({ items: [], catalog_status: "ready" }));
      if (url.endsWith("/design/jobs") && init?.method === "POST") return new Response(JSON.stringify({ id: "123", state: "queued", kind: "dsrna_design", progress: { stage: "queued", completed: 0, total: 4 } }), { status: 202 });
      if (url.endsWith("/jobs/123")) return new Response(JSON.stringify({ id: "123", state: "running", progress: { stage: "discover", completed: 0, total: 4 } }));
      return new Response("{}", { status: 404 });
    });
    render(<DesignPage />);
    const fasta = `>PZ371507.1 eth transcript\n${longDna}\n>PZ371508.1 bursicon transcript\n${longDna}\n>GITV01008430.1 genomic contig transcript\n${longDna}`;
    fireEvent.change(screen.getByRole("textbox", { name: /multi-FASTA/i }), { target: { value: fasta } });
    expect(screen.getByText(/3 genes reconocidos/i)).toBeTruthy();
    expect(screen.getByText(/126 nt por hebra/i)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Longitud de cada bloque/i), { target: { value: "90" } });
    expect(screen.getByText(/270 pb/i)).toBeTruthy();
    expect(screen.getByText(/No hace falta recortar/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Diseñar candidatos/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/design/jobs", expect.objectContaining({ method: "POST" })));
    expect(window.localStorage.getItem("dicer-lab-active-design-job")).toBe("123");
    const init = fetchMock.mock.calls.find(([url, options]) => String(url).endsWith("/design/jobs") && options?.method === "POST")?.[1];
    const body = JSON.parse(String(init?.body));
    expect(body.targets.map((target: { gene_id: string; sequence_rna: string }) => target.gene_id)).toEqual([
      "PZ371507.1", "PZ371508.1", "GITV01008430.1",
    ]);
    expect(body.targets[0].sequence_rna).toBe(longDna.replaceAll("T", "U"));
    expect(body.targets[0]).not.toHaveProperty("description");
  });

  it("muestra estado y etapas reales, y conserva el control para cancelar el trabajo en cola", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/design/references")) return new Response(JSON.stringify({ items: [], catalog_status: "ready" }));
      if (url.endsWith("/design/jobs")) return new Response(JSON.stringify({ id: "queued-job", state: "queued", created_at: "2026-10-29T10:00:00Z", progress: { stage: "queued", operation: "Esperando que el worker tome el trabajo" } }), { status: 202 });
      if (url.endsWith("/jobs/queued-job/cancel") && init?.method === "POST") return new Response(JSON.stringify({ id: "queued-job", state: "cancelled" }), { status: 202 });
      return new Response("{}", { status: 404 });
    });
    render(<DesignPage />);
    fireEvent.change(screen.getByRole("textbox", { name: /multi-FASTA/i }), {
      target: { value: `>g1\n${longDna}\n>g2\n${longDna}` },
    });
    fireEvent.click(screen.getByRole("button", { name: /Diseñar candidatos/i }));
    expect(await screen.findByText(/Duración total:/)).toBeTruthy();
    expect(screen.queryByText(/etapas completadas/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Cancelar trabajo/ }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/jobs/queued-job/cancel", expect.objectContaining({ method: "POST" })));
  });

  it("muestra progreso y ETA de ViennaRNA a partir de candidatos procesados", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/design/references")) return new Response(JSON.stringify({ items: [], catalog_status: "ready" }));
      if (url.endsWith("/jobs/folding-job")) return new Response(JSON.stringify({
        id: "folding-job", state: "running", created_at: "2026-10-29T10:00:00Z",
        progress: { stage: "folding", operation: "Plegando candidatos con ViennaRNA", completed_candidates: 37,
          total_candidates: 83, fold_samples: 37, estimated_remaining_seconds: 46.8 },
      }));
      return new Response("{}", { status: 404 });
    });
    window.localStorage.setItem("dicer-lab-active-design-job", "folding-job");
    render(<DesignPage />);
    expect(await screen.findByText(/Plegamiento con ViennaRNA [-—] 37 de 83 candidatos evaluados \(44,6 %\)\./)).toBeTruthy();
    expect(screen.getByText("Tiempo restante estimado: 00:00:46")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Candidatos evaluados con ViennaRNA" })).toBeTruthy();
  });

  it("recupera estado y resultado del trabajo guardado después de volver a abrir la página", async () => {
    window.localStorage.removeItem("dicer-lab-active-design-job");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/design/references")) return new Response(JSON.stringify({ items: [], catalog_status: "ready" }));
      if (url.endsWith("/jobs/saved-job")) return new Response(JSON.stringify({ id: "saved-job", state: "succeeded", created_at: "2026-10-29T10:00:00Z", finished_at: "2026-10-29T10:01:10Z", result_available: true, progress: { stage: "complete" } }));
      if (url.endsWith("/jobs/saved-job/results")) return new Response(JSON.stringify({ candidates: [], warnings: [] }));
      return new Response("{}", { status: 404 });
    });
    window.localStorage.setItem("dicer-lab-active-design-job", "saved-job");
    render(<DesignPage />);
    expect(await screen.findByRole("heading", { name: "Candidatos evaluados (0)" })).toBeTruthy();
    expect(screen.getByText("00:01:10").closest("p")?.textContent).toBe("Duración total: 00:01:10");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/jobs/saved-job", { cache: "no-store" });
  });
});
