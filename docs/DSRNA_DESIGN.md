# Diseño exploratorio de dsRNA

El flujo de `/design` construye candidatos multigen y los evalúa con criterios
computacionales. Su implementación está en `services/simulator_api/design/`
y en el adaptador Go de `vendor/dsrnamax/`. Las predicciones no demuestran
silenciamiento, especificidad biológica ni seguridad ambiental.

## Objetivos y referencias

La solicitud contiene entre dos y ocho objetivos, uno por gen, con secuencias
orientadas 5′→3′ e identificadores únicos. Se normaliza T→U y se rechazan bases
ambiguas en objetivos. Se admiten hasta 20.000 nt de objetivos, bloques de al
menos 21 nt y constructos de hasta 1.000 nt. La API admite longitud por gen;
la interfaz utiliza una longitud común.

Las referencias se eligen por ID del catálogo, con versión y checksum. Los
registros individuales importados de NCBI son referencias parciales, no
transcriptomas completos. Las consultas NCBI buscan y descargan registros;
no ejecutan BLAST. Ver [catálogo y almacenamiento](web/REFERENCE_STORAGE.md).

## Ventanas, bloques y combinaciones

dsRNAmax descubre ventanas de 21 nt y conserva sus ocurrencias. Con referencias
seleccionadas, elimina coincidencias exactas en cualquiera de las dos
orientaciones. Las bases ambiguas de referencias interrumpen ventanas; no se
unen sus flancos. Se contabilizan las ventanas omitidas.

El modo `blocks` del adaptador recorre intervalos contiguos de cada objetivo
y conserva sólo aquellos cuyas ventanas son todas elegibles. Puntúa cada
bloque sumando los pesos de sus 21-mers distintos y devuelve hasta cinco
secuencias distintas por gen. Python concatena un bloque por gen, sin linker, en el orden de la
solicitud. Explora hasta 100 combinaciones con semilla, elimina secuencias
duplicadas y vuelve a examinar todas las ventanas del candidato, incluidas
las que cruzan junturas. Un candidato que coincide con una referencia excluida
se rechaza. Si no se seleccionan referencias, se informa explícitamente que
no hubo screening.

La procedencia por ventana y los intervalos de cada bloque en su objetivo
se conservan en los resultados. Cada bloque de este flujo es contiguo en su
objetivo; el constructo multigen completo concatena bloques de objetivos
distintos y no representa un único intervalo de un transcrito.

## Termodinámica y plegamiento

El perfil independiente `lucid_end3_v1` suma entalpías y entropías de vecinos
próximos para un dúplex complementario. Usa 22 °C, Na=20 mM, K=50 mM y una
corrección entrópica salina. Para una ventana `k` de 21 nt calcula:

```text
Gs = G(k[0:3])
Ga = G(k[16:19])
delta = Ga − Gs
h(k) = 1 si delta >= 1 kcal/mol; 0 en otro caso
peso(k) = 1 + lambda × h(k), con lambda en {0, 1}
```

Estos extremos son una convención exploratoria; no una geometría de corte
inferida por el simulador. El perfil combina datos de Zuber 2022 y
Chen 2012/Biopython y simplifica efectos terminales. La
[procedencia de las 23 parejas](RNA_NN4_PROVENANCE.md) detalla valores,
licencias y limitaciones. No se calcula Tm, accesibilidad del transcrito ni
equivalencia completa con LUCID.

ViennaRNA 2.7.2 evalúa ambas hebras y el dímero con el perfil
`vienna_turner2004_v1`: Turner2004, 22 °C, `dangles=2` y sal monovalente
0,07 M. Para cada hebra se calculan MFE, función de partición y centroide.
Para el dímero se compara su MFE con la energía evaluada del dúplex perfecto.
Su modelo salino es distinto del perfil anterior; no se suman energías de
ambos modelos.

## Métricas y ranking

| Criterio | Definición implementada | Preferencia |
| --- | --- | --- |
| Cobertura por gen `Cg` | Ventanas por posición del bloque de ese gen que pertenecen a sus 21-mers elegibles, divididas por `longitud_del_bloque − 20` | Maximizar el mínimo entre genes |
| Fracción terminal `H` | Fracción de todas las ventanas por posición del candidato con `delta >= 1` | Maximizar |
| Brecha dimérica `P` | `(E_duplex_perfecto − MFE_dimero) / longitud_del_candidato` | Minimizar |

La cobertura está entre cero y uno; no cuenta coincidencias en otros bloques
como cobertura adicional del gen. Las ventanas repetidas se cuentan por
posición. Una brecha cero puede indicar que el dúplex perfecto ya es la
estructura MFE; no es por sí sola un fallo de cálculo ni una medida de eficacia.

Se ordena por frentes Pareto. Dentro de cada frente se desempata por cobertura
mínima descendente, H descendente, P ascendente e ID de candidato. Se devuelven
hasta 20 candidatos. Los objetivos no finitos invalidan la evaluación.

## Transferencia a Dicer y exportaciones

El endpoint de transferencia crea un constructo a partir de los bloques y
conserva un snapshot de la secuencia. El motor mantiene sus reglas y semillas.
Para un intervalo de corte `[a,b)`, la proyección produce `S[a:b]` y su
complemento inverso; las coordenadas antisentido son `[L−b,L−a)`. Procesar desde
la derecha no invierte el orden de generación ni cambia esas convenciones.

Los fragmentos representan un dúplex ideal alineado. No modelan overhangs,
cortes independientes por hebra, cinética ni selección por RISC. Comparar
políticas epsilon sobre una geometría no equivale a comparar constructos
distintos como si fueran el mismo experimento.

Las exportaciones de diseño son `design-manifest.json`, `kmers.jsonl`,
`candidates.fasta` y `ranking.csv`. Conservar perfiles, versiones, semilla,
referencias y advertencias al interpretar resultados. Los permisos de software
y datos están en [LICENSING.md](LICENSING.md) y
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
