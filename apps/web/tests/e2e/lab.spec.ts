import { expect, test } from "@playwright/test";

test("muestra el preset sin metricas inventadas y reproduce solo el preview recibido", async ({ page }) => {
  const browserConsole: string[] = [];
  page.on("console", (message) => browserConsole.push(message.text()));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/trajectories", async (route) => {
    const request = route.request().postDataJSON();
    expect(request.construct).toMatchObject({ length_nt: 315, segments: [{ start: 0, end: 105 }, { start: 105, end: 210 }, { start: 210, end: 315 }] });
    await route.fulfill({ json: {
      web_schema_version: 1,
      direction: "left",
      source: { kind: "preview", molecule_index: 1, population_size: 1 },
      config: { construct: { length_nt: 315 }, model: {}, run_config: { n_molecules: 1, seed: 101, f_left: 0.5 } },
      events: [
        { kind: "cut", cut_index: 1, start: 0, end: 21, length_nt: 21, annotation: { crossed_gene_boundaries: [], crossed_segment_boundaries: [], touching_segment_ids: ["seg_a"], relative_phase_before: 0, global_phase_before: 0, aligned21_global: true } },
        { kind: "terminal", start: 21, end: 315, length_nt: 0, reason: "exhausted" },
      ],
      remainder: { start: 21, end: 21, length_nt: 0, reason: "exhausted" },
      scientific_provenance: { python: "fixture", numpy: "fixture", rng: "numpy.random.Generator(PCG64)", terminal_rule: "stop_on_overshoot_v1", engine_sha256: {} },
      trajectory_hash: "a".repeat(64),
    } });
  });

  await page.route("**/api/v1/epsilon-profile", async (route) => route.fulfill({ json: {
    length_nt: 315, points: [{ length_nt: 21, epsilon: 0.1 }, { length_nt: 315, epsilon: 0.1 }],
  } }));
  const response = await page.goto("/lab");
  expect(response?.headers()["content-security-policy"]).toContain("'unsafe-eval'");
  const accountButton = page.getByRole("button", { name: "Cuenta local" });
  await accountButton.click();
  await expect(page.getByRole("region", { name: "Opciones de cuenta" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("region", { name: "Opciones de cuenta" })).toHaveCount(0);
  await expect(page.getByText("315", { exact: true })).toBeVisible();
  await expect(page.getByText("Sin resultados todavía")).toBeVisible();
  await expect(page.getByText("Productos de 21 nt")).toHaveCount(0);
  await expect(page.getByRole("img", { name: "Gráfico de epsilon según longitud restante" })).toBeVisible();
  await page.getByRole("button", { name: "Generar trayectoria" }).click();
  await expect(page.getByText(/Reproducible/)).toBeVisible();
  await page.getByRole("button", { name: "Paso siguiente" }).click();
  await expect(page.getByText("Producto 1 · 21 nt")).toBeVisible();
  await expect(page.getByRole("img", { name: /Molécula dsRNA/ })).toBeVisible();
  await page.getByRole("button", { name: "Agregar segmento" }).click();
  await expect(page.getByText(/4 segmentos/)).toBeVisible();
  await page.getByRole("textbox", { name: "Gene ID segmento 4" }).fill("gene_a");
  await expect(page.getByRole("textbox", { name: "Gene ID segmento 4" })).toHaveValue("gene_a");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(browserConsole.join("\n")).not.toContain("eval() is not supported in this environment");
});

test("configura cuatro escenarios unicos y los entrega como una comparacion comun", async ({ page }) => {
  await page.route("**/api/v1/epsilon-profile", async (route) => route.fulfill({ json: {
    length_nt: 315, points: [{ length_nt: 21, epsilon: 0.2 }, { length_nt: 315, epsilon: 0.1 }],
  } }));
  await page.goto("/compare");
  await page.getByRole("button", { name: "Agregar escenario" }).click();
  await page.getByRole("button", { name: "Agregar escenario" }).click();
  await expect(page.getByRole("article", { name: /Escenario/ })).toHaveCount(4);
  await expect(page.getByRole("button", { name: "Agregar escenario" })).toBeDisabled();
  await page.getByRole("combobox", { name: "Modelo de epsilon" }).nth(1).selectOption("custom");

  await page.route("**/api/v1/jobs", async (route) => {
    if (route.request().method() !== "POST") return route.fulfill({ status: 404 });
    const request = route.request().postDataJSON();
    expect(request.scenarios).toHaveLength(4);
    expect(new Set(request.scenarios.map((item: { seed: number }) => item.seed)).size).toBe(4);
    expect(request.scenarios[0].epsilon.type).toBe("constant");
    expect(request.scenarios.some((item: { epsilon: { type: string } }) => item.epsilon.type === "custom")).toBe(true);
    expect(request.construct.length_nt).toBe(315);
    await route.fulfill({ json: { id: "00000000-0000-4000-8000-000000000001", state: "queued", progress: { stage: "queued", completed_molecules: 0, total_molecules: 20000 } } });
  });
  await page.getByRole("button", { name: "Ejecutar comparacion" }).click();
  await expect(page.getByText(/QUEUED/)).toBeVisible();
});
