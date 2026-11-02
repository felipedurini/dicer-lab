# Demostración sintética del simulador: constructo de 315 nt

**No es evidencia experimental.** Se definieron tres secuencias RNA sintéticas de 105 nt y sus complementos; los nombres de gen son etiquetas ficticias. El simulador sólo utiliza sus longitudes y fronteras, no las bases.

## Diseño

- Constructo de 315 nt, tres segmentos contiguos de 105 nt y fronteras en 105 y 210.
- 50,000 moléculas por escenario; mezcla de direcciones 50/50; p22=0.5; regla terminal stop_on_overshoot_v1.
- Epsilon constante 0.10 como referencia ilustrativa del chequeo en el archivo original; el original no estima un epsilon único.
- El baseline constante aplica el núcleo constante en la simulación finita; no es una comparación directa con Fourier. Para K=15 la condición L0>=24*K exige 360 nt, mayor que este constructo de 315 nt.
- Tres perfiles variables con valores 0.05/0.10/0.20 elegidos como sensibilidades, no como parámetros biológicos.
- Cada escenario se repitió con la misma semilla; resúmenes idénticos. IC simultáneos: alpha=0.05, presupuesto m=50 (48 medias calculadas), delta=0.008718.

## Resultados Monte Carlo

| Escenario | Productos 21 nt | Interior gen A | Interior gen B | Interior gen C | Cruza segmento | Cruza entre genes |
|---|---:|---:|---:|---:|---:|---:|
| constante_0.10 | 90.15% | 30.96% | 30.61% | 30.96% | 7.48% | 7.48% |
| epsilon_aumenta_al_acortar | 89.01% | 31.51% | 31.48% | 31.53% | 5.48% | 5.48% |
| epsilon_disminuye_al_acortar | 88.00% | 29.95% | 29.64% | 29.96% | 10.45% | 10.45% |
| epsilon_pico_intermedio | 86.54% | 30.85% | 29.69% | 30.82% | 8.64% | 8.64% |

Las fracciones interiores usan todos los productos como denominador. El cruce cuenta una vez cada producto que atraviesa al menos una frontera; el producto que cruza dos junturas sigue siendo una observación. CSV/JSON contienen numeradores, denominadores, intervalos y expectativas DP.

El CSV distingue cruce de cualquier frontera de segmento y cruce entre genes. En este ejemplo todas las fronteras separan genes, por lo que ambos conteos coinciden.

## Diferencias frente a epsilon constante

- **proporción de 21 nt:** epsilon_aumenta_al_acortar: -1.14 pp (IC diferencia -4.64, +2.35); epsilon_disminuye_al_acortar: -2.16 pp (IC diferencia -5.65, +1.33); epsilon_pico_intermedio: -3.61 pp (IC diferencia -7.09, -0.13).
- **interior gen A:** epsilon_aumenta_al_acortar: +0.55 pp (IC diferencia -1.87, +2.97); epsilon_disminuye_al_acortar: -1.01 pp (IC diferencia -3.41, +1.40); epsilon_pico_intermedio: -0.11 pp (IC diferencia -2.53, +2.31).
- **interior gen B:** epsilon_aumenta_al_acortar: +0.87 pp (IC diferencia -1.54, +3.29); epsilon_disminuye_al_acortar: -0.97 pp (IC diferencia -3.37, +1.43); epsilon_pico_intermedio: -0.91 pp (IC diferencia -3.32, +1.49).
- **interior gen C:** epsilon_aumenta_al_acortar: +0.57 pp (IC diferencia -1.85, +2.99); epsilon_disminuye_al_acortar: -1.00 pp (IC diferencia -3.41, +1.41); epsilon_pico_intermedio: -0.14 pp (IC diferencia -2.56, +2.28).
- **cruce de frontera de segmento:** epsilon_aumenta_al_acortar: -1.99 pp (IC diferencia -3.96, -0.03); epsilon_disminuye_al_acortar: +2.98 pp (IC diferencia +0.97, +4.99); epsilon_pico_intermedio: +1.16 pp (IC diferencia -0.83, +3.16).
- **cruce de juntura entre genes:** epsilon_aumenta_al_acortar: -1.99 pp (IC diferencia -3.96, -0.03); epsilon_disminuye_al_acortar: +2.98 pp (IC diferencia +0.97, +4.99); epsilon_pico_intermedio: +1.16 pp (IC diferencia -0.83, +3.16).

## Alcance del contraste matemático

El modelo original calcula fase estacionaria por ordinal en Z/21Z mediante Fourier. El baseline aquí conserva su núcleo de epsilon constante, pero se ejecuta con el simulador finito (no como contraste Fourier directo). Para K=15, el criterio documentado L0>=24*K requiere 360 nt, condición que 315 nt no cumple. El simulador agrega epsilon(L) sobre la longitud restante real, terminales finitos sin reintento, coordenadas, direcciones, clasificación por gen y métricas de cruce. La DP exacta valida las expectativas geométricas del mismo modelo; no implica que el modelo tenga validez biológica superior.

La recompensa exacta por transición es g(L,s,d): por ejemplo, un cruce de frontera b vale 1 si start < b < end. Si v[L] es la masa de visita, E[R]=sum_L v[L] sum_{s<=L} q_s(L)g(L,s,d). Esta recompensa acumulada de una cadena absorbente es consistente con el método de matriz fundamental de Grinstead y Snell, cap. 11 ([texto](https://chance.dartmouth.edu/teaching_aids/books_articles/probability_book/pdf.html)). La referencia estacionaria por fase es el paseo en Z/21Z evaluado mediante Fourier cíclica ([teorema de convolución para paseos finitos](https://math.uchicago.edu/~may/REU2020/REUPapers/Zhuang%2CYuerong.pdf)). El procesamiento phased desde extremos definidos se describe en Axtell 2010 ([PubMed](https://pubmed.ncbi.nlm.nih.gov/19802589/)).

Estas referencias apoyan los métodos generales. La demostración contrasta Monte Carlo con la DP del mismo modelo; no acredita equivalencia con resultados externos ni validación experimental.

## Archivos

- results.csv: estimandos observados, numeradores, denominadores, intervalos y DP.
- study.json: supuestos, semillas, hashes, reproducibilidad, resultados y DP.
- comparison.png: comparación visual con valores DP como rombos.
- scenario_*.json: manifiestos de cada corrida.
- reproduce_demo.py: receta completa para volver a generar la demostración.

Tiempo de simulaciones (incluye replays) y DP en este entorno: 251.4 s; no se extrapola como benchmark general.
