"""Reproduce the synthetic 315 nt Dicer sensitivity demonstration."""

import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.dicer_sim.domain import Construct, RunConfig, Segment
from src.dicer_sim.exact import expected_summary
from src.dicer_sim.experiments import ratio_interval_from_bounded_counts, result_manifest, run_scenario
from src.dicer_sim.models import ConstantEpsilon, EpsilonCutModel, PiecewiseEpsilon


OUT = Path(__file__).resolve().parent
N = 50_000
ALPHA = 0.05
# Conservative family budget; the four scenarios and five estimands use 40.
M_BOUNDED_MEANS = 50
B = 315 // 21
DELTA = math.sqrt(math.log(2 * M_BOUNDED_MEANS / ALPHA) / (2 * N))
P22 = 0.5
F_LEFT = 0.5
CONSTRUCT = Construct(
    315,
    (
        Segment("tramo_A", "gen_A", 0, 105),
        Segment("tramo_B", "gen_B", 105, 210),
        Segment("tramo_C", "gen_C", 210, 315),
    ),
    phase_origin_nt=0,
)
SCENARIOS = (
    ("constante_0.10", ConstantEpsilon(0.10), 31501,
     "epsilon constante 0.10; valor ilustrativo, no una estimación"),
    ("epsilon_aumenta_al_acortar", PiecewiseEpsilon((106, 211), (0.20, 0.10, 0.05)), 31502,
     "epsilon aumenta al reducirse L: 0.05 -> 0.10 -> 0.20"),
    ("epsilon_disminuye_al_acortar", PiecewiseEpsilon((106, 211), (0.05, 0.10, 0.20)), 31503,
     "epsilon disminuye al reducirse L: 0.20 -> 0.10 -> 0.05"),
    ("epsilon_pico_intermedio", PiecewiseEpsilon((106, 211), (0.10, 0.20, 0.10)), 31504,
     "epsilon tiene un pico intermedio: 0.10 -> 0.20 -> 0.10"),
)
_PATTERNS = {"gen_A": "ACGU", "gen_B": "CGUA", "gen_C": "GUAC"}
SYNTHETIC_SEQUENCES = {
    gene: (pattern * 27)[:105] for gene, pattern in _PATTERNS.items()
}
_COMPLEMENT = str.maketrans("ACGU", "UGCA")


def main():
    start = time.perf_counter()
    runs, exacts, reproducibility = [], [], []
    for name, epsilon, seed, description in SCENARIOS:
        model = EpsilonCutModel(epsilon, p22=P22)
        config = RunConfig(N, seed, F_LEFT)
        result = run_scenario(CONSTRUCT, model, config)
        replay = run_scenario(CONSTRUCT, model, config)
        same = result.summary == replay.summary
        reproducibility.append({"scenario": name, "same_seed_same_summary": same})
        if not same:
            raise AssertionError(f"el escenario {name} no fue reproducible")
        runs.append((name, description, result))
        exacts.append(expected_summary(CONSTRUCT, model, F_LEFT))
    elapsed = time.perf_counter() - start

    rows = []
    metric_names = ("proporcion_21", "interior_gen_A", "interior_gen_B",
                    "interior_gen_C", "cruce_segmento", "cruce_entre_genes")
    for (name, description, result), exact in zip(runs, exacts):
        summary = result.summary
        length_counts = dict(summary.length_counts)
        metric_counts = {
            "proporcion_21": (length_counts[21], exact.expected_length_counts[21]),
            "interior_gen_A": (summary.gene_counts[0].contained_count,
                               exact.expected_metrics.get("gene:gen_A:contained_count", 0.0)),
            "interior_gen_B": (summary.gene_counts[1].contained_count,
                               exact.expected_metrics.get("gene:gen_B:contained_count", 0.0)),
            "interior_gen_C": (summary.gene_counts[2].contained_count,
                               exact.expected_metrics.get("gene:gen_C:contained_count", 0.0)),
            "cruce_segmento": (summary.crossing_count,
                               exact.expected_metrics.get("crossing_count", 0.0)),
            "cruce_entre_genes": (summary.gene_crossing_count,
                                  exact.expected_metrics.get("gene_crossing_count", 0.0)),
        }
        for metric, (numerator, exact_numerator) in metric_counts.items():
            estimate = numerator / summary.n_products if summary.n_products else None
            exact_ratio = exact_numerator / exact.expected_products if exact.expected_products else None
            interval = ratio_interval_from_bounded_counts(
                numerator / (N * B), summary.n_products / (N * B), DELTA
            )
            rows.append({
                "scenario": name,
                "description": description,
                "metric": metric,
                "numerator": numerator,
                "denominator_products": summary.n_products,
                "n_molecules": N,
                "estimate": estimate,
                "ci95_familywise_low": interval[0],
                "ci95_familywise_high": interval[1],
                "exact_dp_numerator_per_molecule": exact_numerator,
                "exact_dp_products_per_molecule": exact.expected_products,
                "exact_dp_ratio_of_expectations": exact_ratio,
                "mc_minus_exact": estimate - exact_ratio if estimate is not None else None,
                "exact_dp_inside_mc_interval": (
                    interval[0] <= exact_ratio <= interval[1] if exact_ratio is not None else None
                ),
                "hoeffding_delta": DELTA,
                "alpha_familywise": ALPHA,
                "m_bounded_means_family": M_BOUNDED_MEANS,
            })

    baseline = {r["metric"]: r for r in rows if r["scenario"] == SCENARIOS[0][0]}
    for row in rows:
        base = baseline[row["metric"]]
        row["delta_vs_constant"] = (
            row["estimate"] - base["estimate"]
            if row["estimate"] is not None and base["estimate"] is not None else None
        )
        row["delta_ci_low"] = row["ci95_familywise_low"] - base["ci95_familywise_high"]
        row["delta_ci_high"] = row["ci95_familywise_high"] - base["ci95_familywise_low"]

    with (OUT / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    scenario_data = []
    for (name, description, result), exact in zip(runs, exacts):
        summary = result.summary
        scenario_data.append({
            "scenario": name,
            "description": description,
            "model": result.model_description,
            "config": {"n_molecules": N, "seed": result.config.seed,
                       "f_left": F_LEFT, "p22": P22},
            "observed": {
                "n_products": summary.n_products,
                "length_counts": dict(summary.length_counts),
                "proportion21": summary.proportion21,
                "contained_products_by_gene": {
                    g.gene_id: g.contained_count for g in summary.gene_counts
                },
                "touching_products_by_gene": {
                    g.gene_id: g.touching_count for g in summary.gene_counts
                },
                "gene_containment_fraction_among_touching": {
                    g.gene_id: g.containment_fraction for g in summary.gene_counts
                },
                "crossing_products": summary.crossing_count,
                "segment_crossing_fraction_of_products": (
                    summary.crossing_count / summary.n_products if summary.n_products else None
                ),
                "gene_crossing_products": summary.gene_crossing_count,
                "crossing_fraction_of_products": (
                    summary.gene_crossing_count / summary.n_products if summary.n_products else None
                ),
            },
            "exact_dp": {
                "expected_products_per_molecule": exact.expected_products,
                "expected_proportion21_ratio_of_expectations": exact.expected_proportion21,
                "expected_contained_products_per_molecule_by_gene": {
                    g.gene_id: exact.expected_metrics.get(
                        f"gene:{g.gene_id}:contained_count", 0.0
                    ) for g in summary.gene_counts
                },
                "expected_crossing_products_per_molecule": exact.expected_metrics.get(
                    "crossing_count", 0.0
                ),
                "expected_gene_crossing_products_per_molecule": exact.expected_metrics.get(
                    "gene_crossing_count", 0.0
                ),
                "expected_terminal_remainder_nt_per_molecule": exact.expected_remainder_nt,
            },
            "run_manifest": result_manifest(result),
        })

    source_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((OUT.parents[1] / "src" / "dicer_sim").glob("*.py"))
    }
    source_hashes["reproduce_demo.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    study = {
        "title": "Demostración sintética del simulador Dicer, constructo 315 nt",
        "interpretation": "simulación de sensibilidad, no evidencia experimental ni estimación de epsilon",
        "construct": {
            "length_nt": 315,
            "phase_origin_nt": 0,
            "segments": [
                {"segment_id": "tramo_A", "gene_id": "gen_A", "start": 0, "end": 105},
                {"segment_id": "tramo_B", "gene_id": "gen_B", "start": 105, "end": 210},
                {"segment_id": "tramo_C", "gene_id": "gen_C", "start": 210, "end": 315},
            ],
            "synthetic_sequences": [
                {
                    "gene_id_label": gene,
                    "strand_5to3": seq,
                    "complementary_strand_5to3": seq.translate(_COMPLEMENT)[::-1],
                    "length_nt": len(seq),
                    "biological_sequence": False,
                }
                for gene, seq in SYNTHETIC_SEQUENCES.items()
            ],
            "sequence_usage": "identidades de bases documentan el juguete sintético; el simulador sólo usa longitudes y fronteras",
        },
        "assumptions": {
            "support_nt": [21, 22, 24],
            "p22": P22,
            "f_left": F_LEFT,
            "epsilon_baseline": "0.10 es ilustrativo; src/fase.py no define una estimación única",
            "legacy_fourier_comparison": "no se usa como perfil finito: para K=15, 315 nt no satisface L0>=24*K=360",
            "piecewise_breakpoints": [106, 211],
            "values_order": "epsilon para L<106, 106<=L<211, y L>=211",
            "terminal_rule": "stop_on_overshoot_v1",
        },
        "statistics": {
            "n_molecules_per_scenario": N,
            "alpha_familywise": ALPHA,
            "m_bounded_means": M_BOUNDED_MEANS,
            "actual_bounded_means": len(SCENARIOS) * len(metric_names) * 2,
            "hoeffding_delta": DELTA,
            "B_products_per_molecule": B,
            "method": "Hoeffding union bound using budget m=50 for 48 actual numerator/denominator means; conservative ratio interval",
        },
        "reproducibility": {
            "same_seed_replay": reproducibility,
            "all_reproduced": all(x["same_seed_same_summary"] for x in reproducibility),
            "source_sha256": source_hashes,
        },
        "simulation_replays_and_exact_dp_seconds": elapsed,
        "scenarios": scenario_data,
        "estimands": rows,
    }
    (OUT / "study.json").write_text(
        json.dumps(study, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    for name, _description, result in runs:
        (OUT / f"scenario_{name}.json").write_text(
            json.dumps(result_manifest(result), indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )

    labels = [s[0].replace("_", "\n") for s in SCENARIOS]
    colors = ("#345995", "#E26D5A", "#47A025")
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4), constrained_layout=True)
    panels = (
        ("proporcion_21", "Productos 21 nt / todos"),
        ("interior", "Productos interiores / todos"),
        ("cruce_entre_genes", "Cruces de juntura entre genes / todos"),
    )
    for key, title, ax in ((p[0], p[1], a) for p, a in zip(panels, axes)):
        keys = ("interior_gen_A", "interior_gen_B", "interior_gen_C") if key == "interior" else (key,)
        width = 0.22 if len(keys) == 3 else 0.52
        x = list(range(len(SCENARIOS)))
        for j, metric in enumerate(keys):
            subset = [next(r for r in rows if r["scenario"] == s[0] and r["metric"] == metric)
                      for s in SCENARIOS]
            vals = [r["estimate"] for r in subset]
            yerr = [
                [r["estimate"] - r["ci95_familywise_low"] for r in subset],
                [r["ci95_familywise_high"] - r["estimate"] for r in subset],
            ]
            offset = (j - (len(keys) - 1) / 2) * width
            ax.bar([i + offset for i in x], vals, width=width,
                   color=colors[j] if len(keys) == 3 else colors[0],
                   label=metric.replace("interior_", "") if len(keys) == 3 else None)
            ax.errorbar([i + offset for i in x], vals, yerr=yerr, fmt="none",
                        ecolor="#222222", capsize=2.5, linewidth=1)
            dp = [r["exact_dp_ratio_of_expectations"] for r in subset]
            ax.scatter([i + offset for i in x], dp, marker="D", s=24,
                       color="black", label="DP exacta" if j == 0 else None, zorder=4)
        ax.set_title(title)
        ax.set_xticks(x, labels, fontsize=8)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", alpha=0.25)
        exact_handle = Line2D([], [], color="black", marker="D", linestyle="None",
                              markersize=5, label="DP exacta")
        if len(keys) == 3:
            handles = [
                Patch(color=colors[j], label=f"Monte Carlo: gen_{letter}")
                for j, letter in enumerate("ABC")
            ] + [exact_handle]
            ax.legend(handles=handles, fontsize=8, loc="upper right")
        else:
            handles = [
                Patch(color=colors[0], label="Monte Carlo, IC simultáneo"),
                exact_handle,
            ]
            ax.legend(handles=handles, fontsize=8, loc="lower left")
    fig.suptitle(
        "Constructo sintético 315 nt (3 x 105 nt), 50 000 moléculas por escenario\n"
        "Barras: Monte Carlo; rombos: DP exacta; intervalo familiar conservador 95%"
    )
    fig.savefig(OUT / "comparison.png", dpi=180)
    plt.close(fig)

    lines = [
        "# Demostración sintética del simulador: constructo de 315 nt",
        "",
        "**No es evidencia experimental.** Se definieron tres secuencias RNA sintéticas de 105 nt y sus complementos; los nombres de gen son etiquetas ficticias. El simulador sólo utiliza sus longitudes y fronteras, no las bases.",
        "",
        "## Diseño",
        "",
        f"- Constructo de 315 nt, tres segmentos contiguos de 105 nt y fronteras en 105 y 210.",
        f"- {N:,} moléculas por escenario; mezcla de direcciones 50/50; p22=0.5; regla terminal stop_on_overshoot_v1.",
        "- Epsilon constante 0.10 como referencia ilustrativa del chequeo en el archivo original; el original no estima un epsilon único.",
        "- El baseline constante aplica el núcleo constante en la simulación finita; no es una comparación directa con Fourier. Para K=15 la condición L0>=24*K exige 360 nt, mayor que este constructo de 315 nt.",
        "- Tres perfiles variables con valores 0.05/0.10/0.20 elegidos como sensibilidades, no como parámetros biológicos.",
        f"- Cada escenario se repitió con la misma semilla; resúmenes idénticos. IC simultáneos: alpha={ALPHA}, presupuesto m={M_BOUNDED_MEANS} (48 medias calculadas), delta={DELTA:.6f}.",
        "",
        "## Resultados Monte Carlo",
        "",
        "| Escenario | Productos 21 nt | Interior gen A | Interior gen B | Interior gen C | Cruza segmento | Cruza entre genes |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, *_ in SCENARIOS:
        values = {r["metric"]: r for r in rows if r["scenario"] == name}
        fmt = lambda metric: f"{100*values[metric]['estimate']:.2f}%"
        lines.append(
            f"| {name} | {fmt('proporcion_21')} | {fmt('interior_gen_A')} | "
            f"{fmt('interior_gen_B')} | {fmt('interior_gen_C')} | "
            f"{fmt('cruce_segmento')} | {fmt('cruce_entre_genes')} |"
        )
    lines += [
        "",
        "Las fracciones interiores usan todos los productos como denominador. El cruce cuenta una vez cada producto que atraviesa al menos una frontera; el producto que cruza dos junturas sigue siendo una observación. CSV/JSON contienen numeradores, denominadores, intervalos y expectativas DP.",
        "",
        "El CSV distingue cruce de cualquier frontera de segmento y cruce entre genes. En este ejemplo todas las fronteras separan genes, por lo que ambos conteos coinciden.",
        "",
        "## Diferencias frente a epsilon constante",
        "",
    ]
    for metric, title in (
        ("proporcion_21", "proporción de 21 nt"),
        ("interior_gen_A", "interior gen A"),
        ("interior_gen_B", "interior gen B"),
        ("interior_gen_C", "interior gen C"),
        ("cruce_segmento", "cruce de frontera de segmento"),
        ("cruce_entre_genes", "cruce de juntura entre genes"),
    ):
        changes = []
        for name, *_ in SCENARIOS[1:]:
            row = next(r for r in rows if r["scenario"] == name and r["metric"] == metric)
            changes.append(
                f"{name}: {100*row['delta_vs_constant']:+.2f} pp "
                f"(IC diferencia {100*row['delta_ci_low']:+.2f}, {100*row['delta_ci_high']:+.2f})"
            )
        lines.append(f"- **{title}:** " + "; ".join(changes) + ".")
    lines += [
        "",
        "## Alcance del contraste matemático",
        "",
        "El modelo original calcula fase estacionaria por ordinal en Z/21Z mediante Fourier. El baseline aquí conserva su núcleo de epsilon constante, pero se ejecuta con el simulador finito (no como contraste Fourier directo). Para K=15, el criterio documentado L0>=24*K requiere 360 nt, condición que 315 nt no cumple. El simulador agrega epsilon(L) sobre la longitud restante real, terminales finitos sin reintento, coordenadas, direcciones, clasificación por gen y métricas de cruce. La DP exacta valida las expectativas geométricas del mismo modelo; no implica que el modelo tenga validez biológica superior.",
        "",
        "La recompensa exacta por transición es g(L,s,d): por ejemplo, un cruce de frontera b vale 1 si start < b < end. Si v[L] es la masa de visita, E[R]=sum_L v[L] sum_{s<=L} q_s(L)g(L,s,d). Esta recompensa acumulada de una cadena absorbente es consistente con el método de matriz fundamental de Grinstead y Snell, cap. 11 ([texto](https://chance.dartmouth.edu/teaching_aids/books_articles/probability_book/pdf.html)). La referencia estacionaria por fase es el paseo en Z/21Z evaluado mediante Fourier cíclica ([teorema de convolución para paseos finitos](https://math.uchicago.edu/~may/REU2020/REUPapers/Zhuang%2CYuerong.pdf)). El procesamiento phased desde extremos definidos se describe en Axtell 2010 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/19802589/)).",
        "",
        "Estas referencias apoyan los métodos generales. La demostración contrasta Monte Carlo con la DP del mismo modelo; no acredita equivalencia con resultados externos ni validación experimental.",
        "",
        "## Archivos",
        "",
        "- results.csv: estimandos observados, numeradores, denominadores, intervalos y DP.",
        "- study.json: supuestos, semillas, hashes, reproducibilidad, resultados y DP.",
        "- comparison.png: comparación visual con valores DP como rombos.",
        "- scenario_*.json: manifiestos de cada corrida.",
        "- reproduce_demo.py: receta completa para volver a generar la demostración.",
        "",
        f"Tiempo de simulaciones (incluye replays) y DP en este entorno: {elapsed:.1f} s; no se extrapola como benchmark general.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "elapsed_seconds": elapsed,
        "hoeffding_delta": DELTA,
        "reproducibility": reproducibility,
        "summary": [
            {
                "scenario": name,
                "metrics": {
                    metric: next(r["estimate"] for r in rows
                                 if r["scenario"] == name and r["metric"] == metric)
                    for metric in metric_names
                },
            }
            for name, *_ in SCENARIOS
        ],
        "all_exact_expectations_inside_intervals": all(
            r["exact_dp_inside_mc_interval"] for r in rows
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
