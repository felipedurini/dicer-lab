"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { History, RefreshCw } from "lucide-react";

type Row = { id: string; label: string; state: string; progress: { stage?: string }; error?: { message: string } };
export default function RunsPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [message, setMessage] = useState("Cargando historial local…");
  async function refresh() {
    try { const response = await fetch("/api/v1/jobs", { cache: "no-store" }); if (!response.ok) throw new Error(); const data = await response.json() as { items: Row[] }; setRows(data.items); setMessage(data.items.length ? "" : "Todavía no hay corridas guardadas."); }
    catch { setMessage("Iniciá el simulador local para consultar el historial privado."); }
  }
  useEffect(() => {
    let active = true;
    fetch("/api/v1/jobs", { cache: "no-store" })
      .then((response) => { if (!response.ok) throw new Error(); return response.json() as Promise<{ items: Row[] }>; })
      .then((data) => { if (active) { setRows(data.items); setMessage(data.items.length ? "" : "Todavía no hay corridas guardadas."); } })
      .catch(() => { if (active) setMessage("Iniciá el simulador local para consultar el historial privado."); });
    return () => { active = false; };
  }, []);
  return <main className="subpage"><Link href="/lab" title="Regresar al laboratorio">← Volver al laboratorio</Link><div className="subpage-card"><div className="runs-head"><div><span className="sub-icon"><History/></span><p className="eyebrow">HISTORIAL PRIVADO</p><h1>Corridas recientes</h1><p>Trabajos almacenados localmente en esta instalación.</p></div><button className="quiet-button" title="Volver a consultar el servicio y actualizar el historial" onClick={() => void refresh()}><RefreshCw size={14}/> Actualizar</button></div>{message && <div className="info-box">{message}</div>}{rows.map((row) => <Link className="run-row" title="Abrir el estado, los resultados y los archivos exportables de esta corrida" href={`/runs/${row.id}`} key={row.id}><b>{row.label}</b><span>{row.state} · {row.progress.stage ?? ""}</span><code>{row.id}</code></Link>)}</div></main>;
}
