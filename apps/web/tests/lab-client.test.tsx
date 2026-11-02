// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import LabClient from "../app/lab-client";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("laboratorio local", () => {
  it("incluye acceso al diseño de dsRNA en la navegación principal", () => {
    render(<LabClient />);
    expect(screen.getByRole("link", { name: "Diseño de dsRNA" }).getAttribute("href")).toBe("/design");
  });

  it("abre el menu del boton de cuenta", () => {
    render(<LabClient />);
    const account = screen.getByRole("button", { name: "Cuenta local" });
    expect(account.getAttribute("title")).toMatch(/opciones de cuenta/);
    fireEvent.click(account);
    expect(screen.getByRole("region", { name: "Opciones de cuenta" })).toBeTruthy();
    expect(screen.getByText("Entorno local de desarrollo")).toBeTruthy();
  });

  it("explica al pasar el cursor para qué sirven los controles principales", () => {
    render(<LabClient />);
    expect(screen.getByRole("slider", { name: /izquierda/ }).getAttribute("title")).toMatch(/extremo izquierdo.*derecha/);
    expect(screen.getByRole("button", { name: "Generar trayectoria" }).getAttribute("title")).toMatch(/una molécula/);
    expect(screen.getByRole("button", { name: /Ejecutar población/ }).getAttribute("title")).toMatch(/estadísticas/);
    expect(screen.getByText("Desde la izquierda").closest("label")?.getAttribute("title") ?? "").toMatch(/extremo izquierdo.*derecha/);
    expect(screen.getByRole("button", { name: "Eliminar segmento 1" }).getAttribute("title")).toMatch(/quitar este segmento/i);
  });

  it("permite anadir segmentos y reutilizar el mismo gene_id", () => {
    render(<LabClient />);
    fireEvent.click(screen.getByRole("button", { name: "Agregar segmento" }));
    const gene = screen.getByRole("textbox", { name: "Gene ID segmento 4" });
    fireEvent.change(gene, { target: { value: "gene_a" } });
    expect(gene).toHaveProperty("value", "gene_a");
    expect(screen.getByText(/4 segmentos/)).toBeTruthy();
  });

  it("inserta símbolos matemáticos en la posición del cursor del editor", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ points: [] }) }));
    render(<LabClient />);
    fireEvent.change(screen.getByRole("combobox", { name: "Modelo de epsilon" }), { target: { value: "custom" } });
    const editor = screen.getByRole("textbox", { name: "Expresión de epsilon" }) as HTMLTextAreaElement;
    fireEvent.change(editor, { target: { value: "L + N", selectionStart: 2, selectionEnd: 2 } });
    editor.setSelectionRange(2, 2);
    fireEvent.select(editor);
    fireEvent.click(screen.getByRole("button", { name: "Insertar α" }));
    await waitFor(() => expect(editor).toHaveProperty("value", "L α+ N"));
  });

  it("starts without invented metrics and renders only events returned by the Python preview", async () => {
    const response = {
      web_schema_version: 1,
      source: { kind: "preview", molecule_index: 1, population_size: 1 },
      config: { construct: { length_nt: 315 }, model: {}, run_config: { n_molecules: 1, seed: 101, f_left: 0.5 } },
      direction: "left",
      events: [{ kind: "cut", cut_index: 1, start: 0, end: 21, length_nt: 21, remaining_before: 315, remaining_after: 294, epsilon_before: 0.1, probabilities_before: { "21": 0.9, "22": 0.05, "24": 0.05 }, contained_gene_id: "gene_a", touching_gene_ids: ["gene_a"], annotation: { relative_phase_before: 0, relative_phase_after: 0, global_phase_before: 0, aligned21_local: true, aligned21_global: true, contained_segment_id: "seg_a", touching_segment_ids: ["seg_a"], crossed_segment_boundaries: [], crossed_gene_boundaries: [], overlap_nt_by_segment: [] } }, { kind: "terminal", start: 21, end: 315, length_nt: 294, reason: "shorter_than_min", proposed_length: null, remaining_before: 294, epsilon_before: null, probabilities_before: null }],
      remainder: { start: 21, end: 315, length_nt: 294, reason: "shorter_than_min", proposed_length: null },
      scientific_provenance: { python: "3.13", numpy: "2.4.0", rng: "numpy.random.Generator(PCG64)", terminal_rule: "stop_on_overshoot_v1", engine_sha256: {} },
      trajectory_hash: "a".repeat(64),
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => response });
    vi.stubGlobal("fetch", fetchMock);
    render(<LabClient />);

    expect(screen.getByText("Sin resultados todavía")).toBeTruthy();
    expect(screen.queryByText("Productos de 21 nt")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Generar trayectoria" }));

    await waitFor(() => expect(screen.getByText(/Reproducible/)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Paso siguiente" }));
    expect(screen.getByText("Producto 1 · 21 nt")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/trajectories", expect.objectContaining({ method: "POST" }));
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.construct).toMatchObject({ length_nt: 315, segments: [{ start: 0, end: 105 }, { start: 105, end: 210 }, { start: 210, end: 315 }] });
    expect(body.p22).toBe(0.5);
  });
});
