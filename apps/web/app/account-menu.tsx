"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut } from "lucide-react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

const authConfigured = Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);

export default function AccountMenu() {
  const router = useRouter();
  const root = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    function closeOutside(event: MouseEvent) {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  useEffect(() => {
    if (!open || !authConfigured) return;
    let active = true;
    void createSupabaseBrowserClient().auth.getUser().then(({ data }) => {
      if (active) setEmail(data.user?.email ?? "");
    }).catch(() => {
      if (active) setError("No se pudo consultar la cuenta.");
    });
    return () => { active = false; };
  }, [open]);

  async function signOut() {
    setBusy(true); setError("");
    try {
      const { error: signOutError } = await createSupabaseBrowserClient().auth.signOut();
      if (signOutError) throw signOutError;
      router.replace("/login");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo cerrar la sesión.");
    } finally { setBusy(false); }
  }

  const initials = email ? email.slice(0, 2).toUpperCase() : "ML";
  return <div className="account-menu" ref={root}>
    <button className="account" type="button" title="Abrir opciones de cuenta, consultar el historial o cerrar sesión" aria-label="Cuenta local" aria-expanded={open} aria-controls="account-options" onClick={() => { setOpen((value) => !value); setError(""); }}>
      <span>{initials}</span><ChevronDown size={14} aria-hidden="true"/>
    </button>
    {open && <div className="account-popover" id="account-options" role="region" aria-label="Opciones de cuenta">
      <div className="account-summary"><b>{authConfigured ? (email || "Cuenta autorizada") : "Entorno local de desarrollo"}</b><small>{authConfigured ? "Sesión privada de Dicer Lab" : "Sesión local en este equipo"}</small></div>
      <Link href="/runs" title="Consultar tus corridas guardadas" onClick={() => setOpen(false)}>Ver resultados</Link>
      {authConfigured ? <button type="button" title="Cerrar la sesión de esta cuenta en el navegador" onClick={() => void signOut()} disabled={busy}><LogOut size={14}/>{busy ? "Cerrando sesión…" : "Cerrar sesión"}</button> : <button type="button" title="Ocultar el menú de cuenta" onClick={() => setOpen(false)}>Cerrar menú</button>}
      {error && <p role="alert">{error}</p>}
    </div>}
  </div>;
}
