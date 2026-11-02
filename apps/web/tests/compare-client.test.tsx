// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import CompareClient from "../app/compare-client";

afterEach(cleanup);

describe("editor de comparacion", () => {
  it("describe qué hacen los controles de comparación al pasar el cursor", () => {
    render(<CompareClient />);
    expect(screen.getAllByRole("textbox", { name: "Nombre" })[0].getAttribute("title")).toMatch(/identificar este escenario/);
    expect(screen.getByRole("button", { name: "Agregar escenario" }).getAttribute("title")).toMatch(/candidato nuevo/);
    expect(screen.getByRole("button", { name: "Ejecutar comparacion" }).getAttribute("title")).toMatch(/diferencias/);
  });

  it("permite editar entre uno y cuatro escenarios y conserva una referencia constante", () => {
    render(<CompareClient />);
    expect(screen.getByText("Epsilon constante", { selector: "strong" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Agregar escenario" }));
    fireEvent.click(screen.getByRole("button", { name: "Agregar escenario" }));
    expect(screen.getAllByRole("article", { name: /Escenario/ })).toHaveLength(4);
    expect(screen.getByRole("button", { name: "Agregar escenario" })).toHaveProperty("disabled", true);
  });
});
