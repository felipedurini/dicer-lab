// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,describe,expect,it,vi} from "vitest";
import DesignPage from "../app/design/page";
afterEach(()=>{cleanup();vi.restoreAllMocks()});
describe("flujo de diseño dsRNA",()=>{
 it("ofrece el regreso al simulador Dicer",()=>{
  render(<DesignPage/>);
  expect(screen.getByRole("link",{name:"← Volver al laboratorio"}).getAttribute("href")).toBe("/lab");
 });

 it("envía los objetivos parseados con idempotencia",async()=>{
  const fetchMock=vi.spyOn(globalThis,"fetch").mockImplementation(async(input,init)=>{
   const url=String(input);
   if(url.endsWith("/design/references"))return new Response(JSON.stringify({items:[]}));
   if(url.endsWith("/design/jobs")) {expect(new Headers(init?.headers).get("idempotency-key")).toBeTruthy();return new Response(JSON.stringify({id:"123",state:"queued",progress:{stage:"queued",completed:0,total:4}}),{status:202})}
   if(url.endsWith("/jobs/123"))return new Response(JSON.stringify({id:"123",state:"running",progress:{stage:"discover",completed:0,total:4}}));
   throw new Error(url);
  });
  render(<DesignPage/>);
  fireEvent.change(screen.getByRole("textbox",{name:"Genes objetivo en multi-FASTA"}),{target:{value:`>gene_a\n${"A".repeat(42)}\n>gene_b\n${"C".repeat(42)}`}});
  fireEvent.click(screen.getByRole("button",{name:"Diseñar candidatos"}));
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith("/api/v1/design/jobs",expect.objectContaining({method:"POST"})));
  const request=fetchMock.mock.calls.find(([url,options])=>String(url).endsWith("/design/jobs")&&options?.method==="POST")?.[1];
  expect(JSON.parse(String(request?.body)).targets).toEqual([
   {gene_id:"gene_a",sequence_rna:"A".repeat(42)},
   {gene_id:"gene_b",sequence_rna:"C".repeat(42)},
  ]);
 });
});
