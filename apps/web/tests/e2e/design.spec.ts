import { expect, test } from "@playwright/test";

test("diseña, muestra ranking y envía un candidato al simulador", async ({ page }) => {
  const id = "123e4567-e89b-42d3-a456-426614174000";
  const candidate = { candidate_id: "a".repeat(64), rank: 1, sequence_rna: "AUGC".repeat(11), length_nt: 42,
    metrics: { minimum_gene_coverage: 1, high_stability_window_fraction: .4, dimer_gap_per_nt: .2 },
    blocks: [{gene_id:"gene_a",start:0,end:21},{gene_id:"gene_b",start:21,end:42}] };
  await page.route("**/api/v1/design/references", route => route.fulfill({json:{items:[],catalog_status:"ready"}}));
  await page.route("**/api/v1/design/jobs", route => route.fulfill({status:202,json:{id,state:"queued",kind:"dsrna_design",created_at:"2026-10-29T10:00:00Z",progress:{stage:"queued",operation:"Esperando que el worker tome el trabajo"}}}));
  await page.route(`**/api/v1/jobs/${id}`, route => route.fulfill({json:{id,state:"succeeded",kind:"dsrna_design",created_at:"2026-10-29T10:00:00Z",finished_at:"2026-10-29T10:01:10Z",progress:{stage:"complete",operation:"Diseño completado"}}}));
  await page.route(`**/api/v1/jobs/${id}/results`, route => route.fulfill({json:{candidates:[candidate],warnings:[]}}));
  await page.route(`**/api/v1/design/jobs/${id}/candidates/${candidate.candidate_id}/simulate`, route => route.fulfill({status:202,json:{id:"223e4567-e89b-42d3-a456-426614174000",state:"queued"}}));
  await page.goto("/design");
  const fasta = page.getByRole("textbox", {name:"Genes objetivo en multi-FASTA"});
  await fasta.fill(`>gene_a receptor transcript\n${"A".repeat(42)}\n>gene_b ligand transcript\n${"C".repeat(42)}`);
  await expect(page.getByText("2 genes reconocidos")).toBeVisible();
  const designRequest = page.waitForRequest(request => request.url().endsWith("/api/v1/design/jobs") && request.method() === "POST");
  await page.getByRole("button", {name:"Diseñar candidatos"}).click();
  const submitted = await designRequest;
  expect(submitted.postDataJSON().targets).toEqual([
    {gene_id:"gene_a",sequence_rna:"A".repeat(42)},
    {gene_id:"gene_b",sequence_rna:"C".repeat(42)},
  ]);
  await expect(page.getByText("Duración total: 00:01:10")).toBeVisible({timeout:10000});
  await expect(page.getByText("#1 · 42 nt")).toBeVisible({timeout:10000});
  await page.getByRole("button", {name:"Simular con Dicer"}).click();
  await expect(page.getByText(/Simulación Dicer en cola/)).toBeVisible();
});
