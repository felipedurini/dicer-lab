// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DesignPage from "../app/design/page";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("entrada FASTA y referencias del diseño", () => {
  it("presenta una sola entrada multi-FASTA en vez de campos separados por gen", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ items: [], catalog_status: "missing" })));
    render(<DesignPage />);
    expect(screen.getByRole("textbox", { name: "Genes objetivo en multi-FASTA" })).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: /Secuencia objetivo/ })).toBeNull();
    fireEvent.change(screen.getByRole("textbox", { name: "Genes objetivo en multi-FASTA" }), {
      target: { value: `>g1\n${"A".repeat(42)}\n>g2\n${"C".repeat(42)}` },
    });
    expect(screen.getByText(/2 genes reconocidos/)).toBeTruthy();
    expect(await screen.findByText(/DATA_DIR\/references\/catalog.json/)).toBeTruthy();
  });

  it("distingue catalogo ausente de una respuesta de backend no autorizada", async () => {
    const response = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ items: [], catalog_status: "missing" })));
    const { unmount } = render(<DesignPage />);
    expect(await screen.findByText(/DATA_DIR\/references\/catalog.json/)).toBeTruthy();
    unmount();
    response.mockResolvedValue(new Response(JSON.stringify({ error: { message: "sesion vencida" } }), { status: 401 }));
    render(<DesignPage />);
    expect(await screen.findByText(/sesión no permite consultar las referencias/)).toBeTruthy();
    expect(screen.queryByText(/catalogo esta disponible/i)).toBeNull();
  });
});
