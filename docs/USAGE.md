# Uso del simulador

El paquete nuevo se importa desde `src.dicer_sim`. El ejemplo crea un
constructo sintético con dos tramos, compara una epsilon constante con una
política por tramos y guarda los resultados como JSON reproducible:

```python
from src.dicer_sim import (
    Construct, Segment, RunConfig, ConstantEpsilon, PiecewiseEpsilon,
    EpsilonCutModel, run_scenario, compare_scenarios, save_result,
)

construct = Construct(
    length_nt=84,
    segments=(Segment("region_a", "gene_a", 0, 42),
              Segment("region_b", "gene_b", 42, 84)),
    phase_origin_nt=0,
)
constant = EpsilonCutModel(ConstantEpsilon(0.2), p22=0.5)
variable = EpsilonCutModel(
    PiecewiseEpsilon(breakpoints=(40, 65), values=(0.05, 0.25, 0.4)),
    p22=0.5,
)

baseline = run_scenario(construct, constant, RunConfig(50_000, seed=101, f_left=0.5))
candidate = run_scenario(construct, variable, RunConfig(50_000, seed=202, f_left=0.5))
comparison = compare_scenarios(baseline, candidate)

print(comparison["proportion21"])
print(baseline.summary.segment_counts)
save_result(baseline, "baseline.json")
save_result(candidate, "variable.json")
```

Las políticas disponibles incluyen también `LinearEpsilon`,
`QuadraticEpsilon`, `ExponentialEpsilon` y `CustomEpsilon`. Las tres curvas
paramétricas reciben `N` (longitud inicial del constructo) durante la
simulación. Por ejemplo, `CustomEpsilon("0.05 + β * sqrt(1 - L/N)", {"β":
0.15})` permite explorar una expresión matemática segura; sólo admite
aritmética explícita y `sqrt`, `exp`, `log`, `abs`. Las expresiones inválidas,
no finitas o fuera de `[0,1]` se rechazan, nunca se recortan. Para reproducir
una corrida se guarda la expresión y sus parámetros junto con la semilla.

`f_left` es la probabilidad de iniciar en el extremo izquierdo. Cada corrida
usa su semilla explícita, y las comparaciones requieren semillas distintas.
Las direcciones y las propuestas de corte usan streams aleatorios separados.
Para repetir una corrida se conservan constructo, política, configuración,
versiones registradas y versión/código identificado por el manifiesto JSON.

## Cómo leer las métricas

- `n_molecules` cuenta moléculas simuladas; `n_products` cuenta productos
  observados. El remanente terminal no es un producto.
- `proportion21` es productos de 21 nt dividido por todos los productos. Con
  denominador cero se informa `None` (`null` al serializar).
- Fase relativa, fase global y alineación de 21 nt son observables geométricos
  diferentes. La proporción agrupada no es el promedio de proporciones por
  molécula.
- Contenencia, contacto, cruce de juntura, solapamiento y recuperación exacta
  de una unidad física tienen denominadores distintos, indicados en sus tipos
  de resumen. `crossing_count`/`segment_crossing_count` conserva cruces de toda
  frontera de segmento; `gene_crossing_count` sólo cuenta fronteras entre
  segmentos con distintos `gene_id`. Un producto que cruce segmentos del mismo
  gen no es por eso un cruce entre genes. Ninguna métrica demuestra actividad o
  eficacia biológica.
- En `PiecewiseEpsilon`, si el umbral es `b`, el valor nuevo ya aplica en
  `L == b`. Para varios umbrales, los valores corresponden a
  `L < b[0]`, `[b[0], b[1])`, ... y `L >= b[-1]`.
- `expected_summary` calcula conteos esperados por DP finita. Sus cocientes son
  cocientes de expectativas, no expectativas de cocientes; no produce
  trayectorias ni incertidumbre Monte Carlo.
- `compare_scenarios` reporta la diferencia candidate menos baseline y un
  intervalo conservador por Hoeffding. El intervalo cuantifica sólo error de
  Monte Carlo bajo el modelo simulado, no incertidumbre biológica ni causalidad.

La referencia Fourier heredada es aplicable únicamente a prefijos estacionarios
con `L0 >= 24*K`. No compara por sí misma el remanente terminal ni una población
finita con epsilon variable. Los valores epsilon de este ejemplo son escenarios
de sensibilidad sintéticos, no estimaciones biológicas.

## Comparación con resultados externos de junturas

La entrada de comparación debe identificar procedencia/versión, coordenadas
semiabiertas y origen de fase, dirección o mezcla, soporte y regla terminal,
observable, numerador/denominador y resultado esperado. Se deben comparar sólo
eventos y denominadores coincidentes. La implementación no acredita equivalencia
con un resultado externo sin un fixture verificable que especifique esos datos.
