"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Dna, LockKeyhole, ShieldCheck } from "lucide-react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const supabase = createSupabaseBrowserClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (signInError) throw signInError;
      router.push("/lab");
      router.refresh();
    } catch {
      setError("No se pudo iniciar sesión. Revisá el correo y la contraseña.");
    }
    finally { setBusy(false); }
  }
  return <main className="login-page"><section className="login-card"><Link className="brand login-brand" title="Ir a la página principal de Dicer Lab" href="/"><span className="brand-mark"><Dna size={20}/></span><span><b>Dicer Lab</b><small>Procesamiento de dsRNA</small></span></Link><div className="login-symbol"><LockKeyhole size={23}/></div><p className="eyebrow">ACCESO PRIVADO</p><h1>Entrá al laboratorio</h1><p className="login-copy">Iniciá sesión con el correo y la contraseña de tu cuenta autorizada.</p><form onSubmit={submit}><label title="Correo asociado a la cuenta autorizada" htmlFor="email">Correo electrónico</label><input title="Correo asociado a tu cuenta autorizada de Dicer Lab" id="email" type="email" name="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@institución.edu"/><label title="Clave de acceso de la cuenta autorizada" htmlFor="password">Contraseña</label><input title="Contraseña de la cuenta autorizada" id="password" type="password" name="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)}/><button className="primary-button" title="Autenticar la cuenta y abrir el laboratorio" type="submit" disabled={busy}>{busy ? "Ingresando…" : "Iniciar sesión"}</button></form>{error && <p className="login-error" role="alert">{error}</p>}<div className="login-privacy"><ShieldCheck size={15}/> Solo usuarios autorizados pueden ejecutar o consultar simulaciones.</div></section></main>;
}
