"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";

export type EpsilonConfig =
  | { type: "constant"; schema_version: 1; epsilon: number }
  | { type: "piecewise"; schema_version: 1; breakpoints: number[]; values: number[] }
  | { type: "linear"; schema_version: 1; epsilon_start: number; epsilon_end: number }
  | { type: "quadratic"; schema_version: 1; epsilon_start: number; epsilon_end: number; curvature: number }
  | { type: "exponential"; schema_version: 1; epsilon_start: number; epsilon_end: number; rate: number }
  | { type: "custom"; schema_version: 1; expression: string; parameters: Record<string, number> };

type Profile = { length_nt: number; epsilon: number }[];
const defaultConfig: EpsilonConfig = { type: "constant", schema_version: 1, epsilon: 0.1 };
const buttons = [
  ["√", "sqrt()", 5], ["x²", "**2", 3], ["( )", "()", 1], ["+", "+", 1], ["−", "-", 1],
  ["×", "*", 1], ["÷", "/", 1], ["exp", "exp()", 4], ["log", "log()", 4],
  ["L", "L", 1], ["N", "N", 1],
] as const;

export default function EpsilonEditor({ lengthNt, value = defaultConfig, onChange, lockModel = false }: {
  lengthNt: number; value?: EpsilonConfig; onChange: (value: EpsilonConfig) => void; lockModel?: boolean;
}) {
  const [profile, setProfile] = useState<Profile>([]);
  const [profileError, setProfileError] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);
  const selection = useRef<[number, number]>([0, 0]);
  const request = useMemo(() => ({
    web_schema_version: 1, construct: { length_nt: lengthNt, phase_origin_nt: 0,
      segments: [{ segment_id: "profile", gene_id: "profile", start: 0, end: lengthNt }] },
    p22: 0.5, f_left: 0.5, seed: 1, epsilon: value,
  }), [lengthNt, value]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch("/api/v1/epsilon-profile", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request) });
        const body = await response.json();
        if (!response.ok) throw new Error(body?.error?.message ?? body?.detail ?? "No se pudo evaluar el perfil");
        if (active) { setProfile(Array.isArray(body.points) ? body.points : []); setProfileError(""); }
      } catch (cause) {
        if (active) { setProfile([]); setProfileError(cause instanceof Error ? cause.message : "Expresión inválida"); }
      }
    }, 180);
    return () => { active = false; window.clearTimeout(timer); };
  }, [request]);

  function insertToken(token: string, caretOffset: number) {
    const input = textarea.current;
    if (!input || value.type !== "custom") return;
    const [start, end] = selection.current;
    const expression = value.expression.slice(0, start) + token + value.expression.slice(end);
    onChange({ ...value, expression });
    const cursor = start + Math.min(caretOffset, token.length);
    window.requestAnimationFrame(() => { input.focus(); input.setSelectionRange(cursor, cursor); selection.current = [cursor, cursor]; });
  }

  function patchEndpoint(key: "epsilon_start" | "epsilon_end", raw: string) {
    if (value.type === "linear" || value.type === "quadratic" || value.type === "exponential")
      onChange({ ...value, [key]: Math.max(0, Math.min(1, Number(raw) || 0)) });
  }

  const plot = profile.length > 0 ? profile.filter((_, i) => i % Math.max(1, Math.ceil(profile.length / 180)) === 0 || i === profile.length - 1) : [];
  const path = plot.map((point, index) => `${index ? "L" : "M"}${12 + 276 * (point.length_nt - 21) / Math.max(lengthNt - 21, 1)},${92 - 72 * point.epsilon}`).join(" ");
  const expression = value.type === "custom" ? value.expression : "";

  return <section className="epsilon-editor" aria-label="Editor de epsilon">
    <label className="epsilon-model-label" title="Elegir la regla matemática que determina epsilon para cada longitud restante">Modelo de ε
      <select title="Cambiar entre epsilon constante, por tramos o una curva matemática" aria-label="Modelo de epsilon" value={value.type} disabled={lockModel} onChange={(event) => {
        const type = event.target.value;
        if (type === "constant") onChange({ type, schema_version: 1, epsilon: 0.1 });
        else if (type === "piecewise") onChange({ type, schema_version: 1, breakpoints: [106, 211], values: [0.2, 0.1, 0.05] });
        else if (type === "linear") onChange({ type, schema_version: 1, epsilon_start: 0.1, epsilon_end: 0.3 });
        else if (type === "quadratic") onChange({ type, schema_version: 1, epsilon_start: 0.1, epsilon_end: 0.3, curvature: 0.5 });
        else if (type === "exponential") onChange({ type, schema_version: 1, epsilon_start: 0.1, epsilon_end: 0.3, rate: 2 });
        else onChange({ type: "custom", schema_version: 1, expression: "α + β * sqrt(1 - L/N)", parameters: { α: 0.05, β: 0.15 } });
      }}>
        <option value="constant" title="Mantiene epsilon fijo para toda longitud restante">Constante</option><option value="linear" title="Interpola epsilon linealmente entre los extremos">Lineal</option><option value="quadratic" title="Usa una curva cuadratica con los extremos fijados">Cuadrática</option>
        <option value="exponential" title="Interpola epsilon con una curva exponencial">Exponencial</option><option value="piecewise" title="Asigna un valor de epsilon a cada intervalo de longitud">Por tramos</option><option value="custom" title="Eval?a una f?rmula personalizada de L y N">Personalizada</option>
      </select>
    </label>
    {value.type === "constant" && <label className="epsilon-parameter" title="Probabilidad de seleccionar un producto de 22 o 24 nt; epsilon complementa la probabilidad de 21 nt">ε constante <input title="Probabilidad de elegir un corte de 22 o 24 nt; el valor restante corresponde a 21 nt" aria-label="Epsilon constante" type="number" min="0" max="1" step="0.01" value={value.epsilon} onChange={(event) => onChange({ ...value, epsilon: Math.max(0, Math.min(1, Number(event.target.value) || 0)) })}/></label>}
    {(value.type === "linear" || value.type === "quadratic" || value.type === "exponential") && <div className="epsilon-formula-fields">
      <label title="Epsilon inicial cuando L es igual a la longitud inicial N">ε inicial (L=N)<input title="Valor de epsilon cuando la molécula conserva su longitud inicial" aria-label="Epsilon inicial" type="number" min="0" max="1" step="0.01" value={value.epsilon_start} onChange={(event) => patchEndpoint("epsilon_start", event.target.value)}/></label>
      <label title="Limite de epsilon cuando L tiende a cero">ε final (L=0)<input title="Valor límite matemático de epsilon cuando L tiende a cero" aria-label="Epsilon final" type="number" min="0" max="1" step="0.01" value={value.epsilon_end} onChange={(event) => patchEndpoint("epsilon_end", event.target.value)}/></label>
      {value.type === "exponential" && <label title="Controla c?mo se curva el cambio exponencial entre epsilon inicial y final">Curvatura<input title="Controla qué tan rápido cambia la curva exponencial entre sus extremos" aria-label="Curvatura exponencial" type="number" min="-20" max="20" step="0.25" value={value.rate} onChange={(event) => onChange({ ...value, rate: Math.max(-20, Math.min(20, Number(event.target.value) || 0)) })}/></label>}
      {value.type === "quadratic" && <label title="Desv?a la curva cuadr?tica de la interpolaci?n lineal entre sus extremos">Curvatura <input title="Desvía la curva cuadrática de una interpolación lineal sin cambiar sus extremos" aria-label="Curvatura cuadrática" type="number" min="-1" max="1" step="0.1" value={value.curvature} onChange={(event) => onChange({ ...value, curvature: Math.max(-1, Math.min(1, Number(event.target.value) || 0)) })}/></label>}
      <output className="math-preview">{value.type === "linear" ? "x = 1−L/N; ε = ε₀ + (ε₁−ε₀)x" : value.type === "quadratic" ? `x = 1−L/N; ε = ε₀ + (ε₁−ε₀)[x + c·x(1−x)] · c=${value.curvature}` : "x = 1−L/N; ε = ε₀ + (ε₁−ε₀)(eʳˣ−1)/(eʳ−1); r=0: lineal"}</output>
    </div>}
    {value.type === "piecewise" && <div className="epsilon-piecewise-fields">{value.values.map((item, index) => <label key={index} title={`Epsilon aplicado al intervalo de longitud restante ${index + 1}`}>{index === 0 ? `L < ${value.breakpoints[0]}` : index === value.values.length - 1 ? `L ≥ ${value.breakpoints[index - 1]}` : `${value.breakpoints[index - 1]} ≤ L < ${value.breakpoints[index]}`}<input title={`Valor de epsilon usado cuando la longitud restante cae en el tramo ${index + 1}`} aria-label={`Epsilon por tramo ${index + 1}`} type="number" min="0" max="1" step="0.01" value={item} onChange={(event) => onChange({ ...value, values: value.values.map((v, i) => i === index ? Math.max(0, Math.min(1, Number(event.target.value) || 0)) : v) })}/></label>)}</div>}
    {value.type === "custom" && <div className="custom-epsilon-editor">
      <div className="math-toolbar" title="Inserta operadores, funciones, variables o parametros en la formula" aria-label="Insertar símbolos">{buttons.map(([label, token, caret]) => <button type="button" key={label} title={`Insertar ${label} en el cursor de la expresión`} aria-label={`Insertar ${label}`} onMouseDown={(event) => event.preventDefault()} onClick={() => insertToken(token, caret)}>{label}</button>)}{Object.keys(value.parameters).map((name) => <button type="button" key={name} title={`Insertar el parámetro ${name} en el cursor`} aria-label={`Insertar ${name}`} onMouseDown={(event) => event.preventDefault()} onClick={() => insertToken(name, name.length)}>{name}</button>)}</div>
      <label className="sr-only" htmlFor="epsilon-expression">Expresión de epsilon</label>
      <textarea title="Escribir la fórmula de epsilon. L es longitud restante y N longitud inicial" id="epsilon-expression" ref={textarea} value={expression} spellCheck={false} rows={2} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => { onChange({ ...value, expression: event.target.value }); selection.current = [event.target.selectionStart, event.target.selectionEnd]; }} onSelect={(event) => { const target = event.currentTarget; selection.current = [target.selectionStart, target.selectionEnd]; }} aria-describedby="epsilon-expression-help" />
      <div className="parameter-fields">{Object.entries(value.parameters).map(([name, parameter]) => <label key={name} title={`Valor de ${name} usado en la f?rmula personalizada`}>{name}<input title={`Ajustar el valor numérico del parámetro ${name} usado por la fórmula`} aria-label={`Parámetro ${name}`} type="number" step="0.01" value={parameter} onChange={(event) => onChange({ ...value, parameters: { ...value.parameters, [name]: Number(event.target.value) || 0 } })}/></label>)}
        <button type="button" title="Añadir un parámetro griego editable para usar en la fórmula" disabled={Object.keys(value.parameters).length >= 16} onClick={() => {
          const next = ["α", "β", "γ", "δ", "θ", "κ", "λ", "μ", "ν", "ξ", "π", "ρ", "σ", "τ", "φ", "ω"].find((name) => !(name in value.parameters));
          if (next) onChange({ ...value, parameters: { ...value.parameters, [next]: 0.1 } });
        }}>+ Parámetro</button>
      </div>
      <small id="epsilon-expression-help" title="L es longitud restante, N longitud inicial; las funciones disponibles son sqrt, exp, log y abs">Variables L (longitud restante), N (longitud inicial); funciones sqrt, exp, log y abs.</small>
      <output className="math-preview" title="Vista legible de la expresion ingresada" aria-label="Fórmula legible">{expression.replaceAll("sqrt", "√").replaceAll("**", "^").replaceAll("*", " × ").replaceAll("/", " ÷ ") || "Escribí una expresión"}</output>
    </div>}
    <div className="epsilon-profile-chart" title="Perfil epsilon(L) evaluado por el motor Python; muestra la probabilidad para cada longitud restante">
      <div className="profile-chart-heading"><b>Perfil ε(L)</b><span>L: 21–{lengthNt} nt · ε: 0–1</span></div>
      <svg viewBox="0 0 300 110" role="img" aria-label="Gráfico de epsilon según longitud restante">
        <path d="M12 20H288 M12 56H288 M12 92H288 M12 20V92H288" fill="none" stroke="#34495f" strokeWidth="1"/>
        <text x="1" y="23">1</text><text x="1" y="59">0.5</text><text x="4" y="95">0</text>
        {path && <path data-testid="epsilon-profile-line" d={path} fill="none" stroke="#69d6e4" strokeWidth="2.5" strokeLinejoin="round"/>}
        {plot.length === 1 && <circle cx="12" cy={92 - 72 * plot[0].epsilon} r="3" fill="#69d6e4"/>}
        <text x="12" y="107">21 nt</text><text x="266" y="107">{lengthNt} nt</text>
      </svg>
      {profileError ? <p role="alert">{profileError}</p> : <small>La curva refleja las evaluaciones del motor Python; no es una función biológica validada.</small>}
    </div>
  </section>;
}
