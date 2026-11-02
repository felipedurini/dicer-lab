# Arquitectura: procesamiento de dsRNA con probabilidades dependientes de la longitud

El modelo está implementado en `src/dicer_sim/`. Las pruebas deterministas y
estadísticas están en `tests/unit/` y `tests/statistical/`. El código de
referencia y los materiales originales se conservan con sus créditos.
Las rutas se expresan respecto de la carpeta que contiene `README.md`,
`requirements.txt`, `src/` y `notebooks/`. Esa es la raíz del proyecto.

## 1. Objetivo, alcance y antecedentes

Estudiar las consecuencias computacionales de sustituir una distribución
estacionaria de longitudes de corte por una distribución dependiente de la
longitud restante real `L`, medida en posiciones nucleotídicas sobre el eje
del dúplex:

\[
q_{21}(L)=1-\epsilon(L),\qquad
q_{22}(L)=\epsilon(L)p_{22},\qquad
q_{24}(L)=\epsilon(L)(1-p_{22}).
\]

`p22` permanece constante durante cada escenario y vale `0.5` por defecto.
`epsilon(L)` constante debe recuperar el núcleo probabilístico original.
No implica que todas las métricas de una molécula finita coincidan con las
curvas originales: cambian el objeto observado y la condición terminal.

La contribución es implementar y contrastar escenarios no estacionarios,
con trazabilidad de sus supuestos. No se conoce una función biológicamente
validada `epsilon(L)`. Ninguna política o cifra de los ejemplos constituye
una medición experimental.

El motor distingue fase, pertenencia a un tramo y cruce de junturas mediante
coordenadas y denominadores explícitos. Los créditos del trabajo original se
conservan en el README y la licencia.

Este documento describe el motor geométrico. Las secuencias y el screening
se implementan en adaptadores descritos en [DSRNA_DESIGN.md](DSRNA_DESIGN.md);
la interfaz y persistencia están en la [arquitectura web](web/ARCHITECTURE.md).
El motor no modela eficacia biológica, tasas cinéticas, tiempo físico,
inicios internos ni dos frentes simultáneos en una molécula.

## 2. Referencia estacionaria y materiales científicos

`src/fase.py`, `src/grafico.py` y `notebooks/exploracion.ipynb` contienen la
referencia estacionaria y sus exploraciones. Sus límites se detallan abajo.

| Componente existente | Uso en la extensión | Límite de ese uso |
| --- | --- | --- |
| `src.fase.psi` | Espectro del paseo estacionario; referencia existente | No usar con un promedio de `epsilon(L)` |
| `src.fase.p_fase_cero` | Oráculo de fase por número de corte con epsilon constante | No es una probabilidad de recuperar una unidad física dada |
| `src.fase.rendimiento_un_extremo` | Oráculo del evento «fase local anterior cero y producto21» por corte | No incorpora longitud finita ni remanente |
| `src.fase.rendimiento_dos_extremos` | Caracterizar y conservar su mezcla algebraica `f*w+(1-f)*w[::-1]` | No convertirla en oráculo espacial del nuevo motor |
| `longitud_util`, `tasa_decaimiento` | Conservar para exploraciones originales | No son longitud óptima biológica ni rendimiento finito |
| Monte Carlo en `fase.py` y notebook | Antecedente de validación estacionaria | Está embebido y usa un número fijo de pasos; no copiarlo como motor nuevo |
| `src/grafico.py`, notebook | Referencias de exploración y presentación | No importarlos como biblioteca: hay ejecución y gráficos al nivel superior |
| `requirements.txt` | Reutilizar NumPy; Matplotlib ya existe para gráficos | El núcleo nuevo no requiere Matplotlib ni dependencias adicionales |

Las referencias se importan como `from src.fase import ...` desde la raíz.
El adaptador valida entradas, llama a esas funciones y explicita el evento
medido. Ejecutar `grafico.py` regenera una figura; no es una prueba sin efectos
sobre los archivos.

### 2.1 Límites matemáticos y de interpretación de la referencia

1. **Número de corte y posición física son índices diferentes.** El código
   calcula `w_k = P(Phi_(k-1)=0, S_k=21)` para el producto ordinal `k`.
   El README original, etiquetas de figuras y notebook lo describen en varios lugares
   como probabilidad de recuperar la unidad física `k`. Siete cortes de
   24 nt consumen 168 nt: el octavo corte, si mide 21, produce `[168,189)`,
   que es la novena unidad física de la retícula de 21. Para `L0=168`, ese
   octavo producto ni siquiera puede generarse. La fórmula de Fourier sigue
   siendo válida para su evento ordinal; la interpretación espacial necesita
   otra magnitud.
2. **Límite de fase y límite de rendimiento.** Bajo convergencia a uniforme,
   `P(Phi_k=0)` tiende a `1/21`, pero `w_k` tiende a `(1-epsilon)/21`.
   La línea `1/21` de `grafico.py` y del notebook se dibuja sobre curvas de
   `w_k`, y el README original mezcla ambos límites. Con epsilon `0.2`, las funciones
   originales dan `w_1000 ≈ 0.0380952381`, no `0.0476190476`.
3. **No hay un piso ni una caída geométrica exacta universal.** Fourier es
   una suma de modos; el autovalor subdominante controla una envolvente
   asintótica bajo condiciones apropiadas, no una exponencial única ni
   monotonía para todo `k`. Con epsilon `0.1`, p22 `0.5`,
   `w_49 ≈ 0.01145065`, por debajo de su límite `0.9/21`.
   La fase puede recuperarse por acumulación modular; «estar en fase» no
   equivale a «no haber salido nunca de fase».
4. **Las afirmaciones de ergodicidad tienen condiciones.** Con epsilon `0`,
   la fase permanece cero. Si `0<epsilon<1` y `p22=0`, sólo se visita el
   subgrupo de múltiplos de 3 y el límite de fase cero es `1/7`. Si epsilon
   `1` y p22 `0` o `1`, el paseo es periódico (períodos 7 y 21).
   Para `0<epsilon<1, p22>0`, o epsilon `1` con `0<p22<1`, sí hay
   convergencia a uniforme sobre los 21 estados. No aplicar los límites
   genéricos a todo el dominio permitido.
5. **Mezcla de extremos.** La docstring de `rendimiento_dos_extremos` sí
   especifica una mezcla de moléculas; «bidireccional» en otras descripciones
   puede prestarse a confusión. El nuevo motor fija una dirección por
   molécula. La simetría exacta de un perfil reflejado requiere mezcla 50/50
   y geometría/observable correspondientes; no demuestra cortes simultáneos.
6. **Fase, pertenencia, actividad y off-target son distintos.** Un producto
   desfasado puede permanecer dentro de un tramo continuo. Las afirmaciones
   del README original que equiparan desfase con pérdida total o juntura
   no describen las métricas del motor finito. Contenencia tampoco demuestra eficacia ni un cruce demuestra
   off-target.
7. **No hay tiempo ni tendencia biológica demostrada.** El modelo no permite
   deducir evolución con tiempo de reacción ni que epsilon necesariamente
   aumente al acortarse el sustrato. Tampoco garantiza que una política
   creciente empeore todas las métricas. Esas afirmaciones del README original
   son hipótesis, no resultados biológicos comprobados por el simulador.
8. **Otras limitaciones de interfaz.** `fase.py` no valida probabilidades ni
   tamaños; `longitud_util` busca solamente las primeras 200 posiciones
   (no hallar umbral no demuestra que nunca exista). El README original y el notebook dicen
   «único parámetro» aunque `p22` es configurable. Los pequeños residuos
   complejos/redondeos de Fourier pueden dar valores reales apenas negativos;
   se comparan con tolerancia numérica, sin editar la referencia.

Estos hallazgos se documentan como advertencias de interpretación, no como
modificaciones al trabajo original ni invalidación de su cálculo espectral.

## 3. Convenciones del modelo finito

### 3.1 Coordenadas, tramos y dirección

El constructo ocupa `[0,L0)`, con coordenadas enteras y `L0>0`.
Cada tramo objetivo ocupa `[a,b)`, con `0<=a<b<=L0`. Los tramos, ordenados,
forman una partición completa, sin huecos ni solapamientos. `segment_id` es
único; `gene_id` puede repetirse en tramos distintos. Si sólo interesa la
longitud, el usuario declara explícitamente un único tramo con un ID neutro.
No introducir tramos biológicos ficticios automáticamente.

Cada molécula elige una vez `left` con probabilidad `f_left` o `right` con
probabilidad `1-f_left`; esa dirección no cambia. Ambos grupos usan el mismo
`epsilon(L)` y `p22`. No se modela orientación de hebras ni extremo químico 5'.

Antes de un corte, sea `L` la longitud restante y `D=L0-L` la consumida:

| Dirección | Sustrato restante | Producto propuesto de longitud `s<=L` |
| --- | --- | --- |
| `left` | `[D,L0)` | `[D,D+s)` |
| `right` | `[0,L)` | `[L-s,L)` |

Los productos se guardan en orden de generación, no ordenados por coordenada.
En la dirección derecha sus coordenadas descienden. La transformación espejo
de un intervalo `[a,b)` es `[L0-b,L0-a)`.

### 3.2 Política terminal elegida: `stop_on_overshoot_v1`

1. Si `L=0`, terminar con motivo `exhausted` y remanente vacío.
2. Si `0<L<21`, terminar con `shorter_than_min`; no consultar el modelo ni RNG.
3. Si `L>=21`, evaluar el núcleo completo en esa `L` y sortear `s`.
4. Si `s<=L`, emitir el producto completo y actualizar `L := L-s`.
5. Si `s>L`, terminar con `proposal_exceeds_remaining`, conservando intacto
   el remanente y registrando `proposed_length=s`.

No truncar, renormalizar las probabilidades factibles ni volver a sortear.
La convención conserva la ley de propuestas del modelo hasta la terminación
y simplifica el contraste con el paseo original. Es una decisión matemática
versionada, no un mecanismo demostrado de Dicer. Detenerse cuando `L<24`
descartaría cortes de 21/22 todavía posibles; renormalizar impondría otro
modelo. Cualquier alternativa futura se compara como política explícita.

El remanente puede medir 21, 22 o 23 nt si se sortea una propuesta imposible.
No es un producto de corte y no se incluye en sus distribuciones. Su longitud
está entre 0 y 23, pero se conserva también el motivo terminal y su intervalo.
En cada trayectoria, `sum(longitudes_productos)+longitud_remanente=L0`.

Ejemplo exacto: con `L0=22`, epsilon `0.5`, p22 `0.5`, las ramas son
`(producto21, remanente1)` con probabilidad `.5`, `(producto22, remanente0)`
con `.25`, y `(ningún producto, remanente22)` con `.25`.
El número esperado de productos es `.75`; la proporción agrupada de productos21
tiende a `2/3`, no a `1-epsilon=.5`. Con `L0=21` la proporción agrupada es 1
si se observan productos, aunque sólo la mitad de las moléculas los emita.

### 3.3 Estado probabilístico

`epsilon(L)` se evalúa **antes** de cada propuesta y con la longitud real.
No se reemplaza por `epsilon(k)`, `epsilon(L0-21*k)` ni una longitud promedio.
Por ejemplo, después de un corte21 desde70 se consulta49; después de uno24,
se consulta46, aunque el número de corte siguiente sea el mismo.

El estado `L` es suficiente para la transición: longitud inicial y dirección
fijas determinan posición y fase. Las propuestas usan aleatoriedad nueva y
son condicionalmente independientes dado el estado; en general sus longitudes
sucesivas no son i.i.d. Los tramos y los genes no alteran el núcleo inicial.

## 4. Arquitectura concreta

El paquete `src/dicer_sim/` separa dominio, políticas, simulación, análisis y
contrastes exactos. No utiliza un framework de plugins.

```text
src/fase.py                  referencia existente, sin cambios
src/grafico.py               presentación existente, sin cambios
src/dicer_sim/
    __init__.py              API pública pequeña, sin trabajo al importar
    domain.py                datos inmutables, geometría e invariantes
    models.py                políticas epsilon, núcleo y validación
    simulation.py            trayectoria, RNG inyectado y población serial
    analysis.py              clasificación, conteos y denominadores
    reference.py             adaptación semántica a src.fase
    exact.py                 DP finita de conteos esperados y remanente
    experiments.py           ejecución, metadatos, comparación y JSON
tests/unit/                  reglas deterministas y referencias exactas
tests/statistical/           contrastes Monte Carlo preespecificados
```

Dependencias: `domain` no conoce simulación; `models` no conoce genes ni
análisis; `simulation` conoce `domain/models`, nunca `analysis` o Fourier;
`analysis` conoce los datos; `reference` llama a `src.fase`;
`exact` conoce `domain/models` y clasificación pura de `analysis`, sin llamar
al motor aleatorio; `experiments` orquesta. Ni el modelo ni el análisis
consumen RNG. No hay I/O dentro del motor ni al importar módulos.

El entorno documentado usa Python 3.13, NumPy para RNG y referencia,
`dataclasses`, `typing.Protocol`, `json`, `unittest` y otras utilidades estándar.
Matplotlib se utiliza para gráficos, no como dependencia del núcleo. Pydantic
pertenece a los contratos HTTP, fuera de este paquete.

### 4.1 Estructuras de datos

Usar `dataclass(frozen=True)` y tuplas para los registros públicos.
No almacenar valores derivados que puedan contradecir las coordenadas.

| Tipo | Campos/contrato |
| --- | --- |
| `Segment` | `segment_id: str`, `gene_id: str`, `start: int`, `end: int`; IDs no vacíos |
| `Construct` | `length_nt: int`, `segments: tuple[Segment,...]`, `phase_origin_nt: int=0`; origen es residuo de retícula entre 0 y 20 |
| `Product` | `cut_index: int` (desde1), `start`, `end`, `remaining_before: int`; longitud derivada `end-start` |
| `TerminalRemainder` | `start`, `end`, `reason` de la sección 3.2, `proposed_length: int \| None`; propuesta sólo para sobrepaso |
| `MoleculeResult` | `direction`, `products: tuple[Product,...]`, `remainder`; validable contra un `Construct` |
| `RunConfig` | `n_molecules: int>0`, `seed: int>=0` obligatorio, `f_left: float=1.0` |
| `ProductAnnotation` | fase de entrada local/global, producto21 alineado local/global, `contained_segment_id` opcional, IDs de tramos tocados, fronteras de segmento cruzadas, subconjunto de fronteras entre genes cruzadas y solapamiento nt por tramo |
| `CountSummary` | número de moléculas/productos, conteos y denominadores de §5, cruces de segmentos y cruces entre genes, acumulados por dirección/tramo/gen, longitud remanente total e histograma, motivos terminales |
| `ExpectedSummary` | expectativas de conteos por molécula, distribución del remanente, recompensas geométricas y razones de expectativas; no simula individuos |
| `RunResult` | configuración completa, metadatos, `CountSummary` y métricas derivadas; sin lista de toda la población |

Validar enteros sin aceptar `bool` como longitud, índice o semilla; tipos
incorrectos producen `TypeError`, valores fuera de dominio `ValueError`.
También validar `f_left`, epsilon y p22 finitos en `[0,1]`, incluidos cuando
su valor no influiría en una rama concreta. No corregir entradas silenciosamente.

### 4.2 Interfaces y políticas

Las siguientes firmas describen contratos del simulador y su extensión de
políticas epsilon:

```text
EpsilonPolicy.value(remaining_nt: int, initial_nt: int | None = None) -> float
EpsilonPolicy.describe() -> dict JSON
ConstantEpsilon(epsilon: float)
PiecewiseEpsilon(breakpoints: tuple[int,...], values: tuple[float,...])
LinearEpsilon(epsilon_start: float, epsilon_end: float)
QuadraticEpsilon(epsilon_start: float, epsilon_end: float, curvature: float)
ExponentialEpsilon(epsilon_start: float, epsilon_end: float, rate: float)
CustomEpsilon(expression: str, parameters: dict[str,float])

CutModel.probabilities(remaining_nt: int, initial_nt: int | None = None) -> tuple[float,float,float]
CutModel.describe() -> dict JSON
EpsilonCutModel(epsilon: EpsilonPolicy, p22: float=0.5)

UniformSource.random() -> float                 # en [0,1)
simulate_molecule(construct, model, direction, rng: UniformSource) -> MoleculeResult
iter_population(construct, model, config: RunConfig) -> Iterator[MoleculeResult]
classify_product(product, construct, direction) -> ProductAnnotation
summarize(results: Iterable[MoleculeResult], construct) -> CountSummary
stationary_prefix_reference(K: int, epsilon: float, p22: float=0.5, *, length_nt: int) -> dict
expected_summary(construct, model, f_left: float=1.0) -> ExpectedSummary
run_scenario(construct, model, config) -> RunResult
compare_scenarios(baseline: RunResult, candidate: RunResult) -> dict
save_result(result: RunResult, path) -> None
result_manifest(result: RunResult) -> dict
serialize_manifest(manifest: dict) -> str
deserialize_manifest(serialized: str) -> dict
model_from_description(description: dict) -> EpsilonCutModel
```

`CutModel` y `EpsilonPolicy` son protocolos estructurales pequeños. El soporte
de `CutModel` es fijo, ordenado `(21,22,24)`, durante esta versión. Se podrán
introducir nuevas políticas puras sin tocar el motor. Variar `p22(L)` es una
ampliación posterior del modelo que implementa el mismo protocolo, justificada
sólo si una pregunta científica lo requiere; otros soportes exigirán revisar
también fase, terminación y tests, no sólo pasar una nueva lista.

Cada consulta del núcleo verifica tres números finitos en `[0,1]` y suma1
con tolerancia absoluta `1e-12`. No renormalizar ni recortar. La CDF asigna
21 si `u<q21`, 22 si `u<q21+q22`, y 24 en otro caso; usa un uniforme escalar
por propuesta, incluso en los casos deterministas. El error de cierre de
coma flotante admitido se limita a esa tolerancia. Un uniforme de prueba
fuera de `[0,1)` se rechaza. Validar también respuestas de modelos externos.

`PiecewiseEpsilon` usa umbrales enteros positivos estrictamente crecientes,
`len(values)=len(breakpoints)+1` y valores finitos en `[0,1]`.
Para breakpoints `b[0] < ... < b[m-1]`, selecciona `values[0]` si
`L < b[0]`; `values[i]` si `b[i-1] <= L < b[i]`; y `values[m]` si
`L >= b[m-1]`. En particular, `L == b[i]` usa `values[i+1]`
(`bisect_right`). Un conjunto vacío equivale a una constante.
No extrapola curvas ajustadas ni impone monotonía. Las políticas lineal,
cuadrática y exponencial normalizan `x=1-L/N` entre sus parámetros inicial y
final; no representan estimaciones biológicas. La política custom interpreta
un subconjunto seguro de aritmética y funciones, recibe `L` y la longitud
inicial `N`, y rechaza errores, resultados no finitos o epsilon fuera de
`[0,1]`; no usa `eval`, `exec` ni código del usuario.

`describe()` incluye nombre de modelo, versión del esquema y todos los
parámetros; las políticas personalizadas deben ser puras, sin estado ni RNG,
con identificación/versionado de su código. No aceptar una lambda anónima
como descripción reproducible de un experimento. Los errores durante una
corrida se propagan con molécula y longitud implicadas; `run_scenario` no
devuelve ni persiste un resultado parcial como exitoso.

## 5. Observables y denominadores

Sea `n` el número de moléculas, `T_i` sus productos emitidos y `T=sum_i T_i`.
Las proporciones principales son cocientes de conteos agrupados, no promedios
de proporciones por molécula. Siempre devolver numerador y denominador;
si el denominador es cero, el valor es `None` (`null` en JSON), no cero/NaN.
Se cuentan también las moléculas que no producen fragmentos.

### 5.1 Fase: tres preguntas diferentes

Sea `o=phase_origin_nt`, `D=L0-remaining_before` y `s=end-start`:

- **Registro local de entrada:** `D mod21`; tras el producto, `(D+s) mod21`.
  Es el registro relativo al extremo iniciador y el comparable con Fourier.
- **Registro global de entrada:** `(start-o) mod21` desde izquierda y
  `(end-o) mod21` desde derecha. Representa la retícula original del constructo.
- **Producto21 alineado globalmente:** `s=21` y `(start-o) mod21=0`.
  El evento local correspondiente es `s=21` y `D mod21=0`.

Con `L0=43`, epsilon0 y `o=0`, desde la derecha se emiten `[22,43)` y `[1,22)`:
ambos están alineados localmente, ninguno globalmente. No reiniciar el origen
global para obtener coincidencia artificial. Para `o=0,L0` múltiplo21, los
eventos de fase cero local/global sí coinciden en ambas direcciones.

«Conservación» en los informes significa ocupación del registro en ese
instante, con posibles retornos. No se afirma conservación ininterrumpida;
una métrica «nunca salió de fase» sería distinta y queda fuera de la API inicial.

### 5.2 Métricas obligatorias

| Métrica | Numerador y denominador / unidad |
| --- | --- |
| Distribución de longitudes | `count_length[s]/T`, para21,22,24, incluidos ceros explícitos |
| Proporción21 | `count_length[21]/T`; no llamarla eficacia |
| Entrada en fase global/local | productos con respectivo residuo de entrada cero, divididos por `T` |
| Producto21 alineado global/local | productos que cumplen ambos criterios, divididos por `T` |
| Contenido en un tramo | `contained_count/T`, con un único tramo que contiene todo `[start,end)` |
| Atraviesa fronteras de segmento | `crossing_count/T` (alias `segment_crossing_count`); cada producto cuenta una sola vez, aunque cruce varias fronteras |
| Atraviesa junturas entre genes | `gene_crossing_count/T`; cuenta una vez el producto si cruza al menos una frontera entre segmentos con `gene_id` distintos |
| Media de producción | `T/n` y conteos de cada clase divididos por `n` |
| Remanente | distribución por longitud y motivo, longitud media, fracción de moléculas sin productos; denominador `n` |
| Por dirección | los mismos conteos con denominadores propios; una dirección no observada tiene denominador0 |
| Perfil ordinal | por `k`: moléculas con producto `k`, entrada/salida local en fase y producto21 alineado; ver denominadores abajo |
| Recuperación de unidad física | para cada celda completa `[o+21*j,o+21*(j+1))` dentro de `[0,L0)`, moléculas que emiten exactamente ese intervalo, dividido por `n` |

En el perfil ordinal guardar `n_reached_k`, éxitos y `n`.
`success_k/n` es la probabilidad conjunta de existencia y evento;
`success_k/n_reached_k` es condicional a existencia. No etiquetar ambos igual.
Sólo en el prefijo garantizado de §8 son iguales y comparables con Fourier.
Un `k` sin productos observados tiene probabilidad conjunta0 y condicional
indefinida. No comparar curvas físicas y ordinales por el mismo nombre de eje.

Una frontera de segmento `b` se cruza exactamente si `start<b<end`; tocarla no
es cruzarla. `crossed_boundaries` y `crossing_count` conservan su definición
histórica sobre toda frontera de segmento. `crossed_gene_boundaries` es el
subconjunto de fronteras interiores cuyos segmentos adyacentes tienen genes
distintos; `gene_crossing_count` cuenta cada producto una vez dentro de ese
subconjunto. Con partición completa, `contained_count+crossing_count=T`.

### 5.3 Desagregación por tramo y gen

Por tramo registrar: productos contenidos, productos que lo tocan con
solapamiento positivo, productos con cruce que lo tocan, y nt emitidos
solapados con ese tramo. Informar `contained/touching`, `crossing_touching/touching`,
productos contenidos por molécula y `overlap_nt/(n*segment_length)`.
Esta última es cobertura de masa procesada; ninguna es actividad biológica.
Un cruce nunca se asigna entero y arbitrariamente a un gen.

Por gen, sumar productos contenidos en sus tramos y nt solapados; unir los
productos tocantes/de cruce para evitar duplicarlos si tocan dos tramos del
mismo gen. `crossing_touching_count` conserva el cruce de cualquier frontera
de segmento incidente al gen; `gene_crossing_touching_count` sólo incluye
productos que cruzan una juntura entre genes y toca ese gen. Sumar conteos
antes de dividir; no promediar proporciones de tramos. Los conteos tocantes/de
cruce por varios genes no son aditivos entre genes. La cobertura del gen usa la
suma de las longitudes de sus tramos.

Una frontera entre dos `segment_id` del mismo `gene_id` sigue siendo una
frontera de segmento, pero no es una juntura entre genes. «Contenido en un
tramo» tampoco equivale a «pertenece a un único gen»: un producto puede tocar
dos segmentos del mismo gen, quedar fuera de `contained_count` y aun así no
cruzar ninguna juntura entre genes.

### 5.4 Comparación entre escenarios

El candidato cambia únicamente la política epsilon respecto de la referencia
constante: mismo constructo, retícula, `p22`, mezcla de direcciones y convención
terminal. Si no coinciden, `compare_scenarios` rechaza una comparación que se
presente como efecto de epsilon(L). Puede haber distintos tamaños muestrales,
pero se registran y usan sus denominadores propios. Usar semillas distintas
y explícitas para los dos escenarios; no afirmar emparejamiento por compartir
semilla ni hacer tests que obliguen a una tendencia científica particular.

Presentar `delta=candidato-referencia` en medias/proporciones comparables,
con resultados globales y por tramo/gen. No exigir diferencia significativa
ni mejora. Si una métrica es indefinida en algún escenario, su delta lo es.
La incertidumbre se calcula con moléculas como unidades independientes (§8).

## 6. Elección computacional

### 6.1 Monte Carlo secuencial como motor principal

Una trayectoria ejecuta las reglas de §3 hasta terminar. Produce coordenadas
reales y permite inspeccionar caminos, tramos y distribuciones sin enumerar
un árbol exponencial. El núcleo no almacena una fase independiente: se deriva
de la geometría. Cada corte reduce `L` al menos21, por lo que hay a lo sumo
`floor(L0/21)` productos y una propuesta terminal fallida.

Costo del motor: `O(n*L0/21)` consultas y sorteos; memoria de una trayectoria
`O(L0/21)`. `iter_population` entrega moléculas de a una y `summarize` acumula
en línea, sin una matriz de todas las moléculas. La primera clasificación
puede recorrer los `G` tramos: `O(G)` por producto, adecuado para pocos genes.
No vectorizar todas las trayectorias con un número fijo de cortes, pues se
perdería la dependencia en `L`. Optimizar sólo después de medir un caso real.

### 6.2 Programación dinámica como control exacto finito

La DP de `exact.py` es exacta para el modelo discretizado, salvo redondeo de
coma flotante. Propaga probabilidades y suma las observaciones geométricas
definidas aquí; no establece por sí misma validez biológica.

Para cada dirección, inicializar probabilidad de visita `v[L0]=1` y el resto0.
Recorrer `L` de `L0` a0; como toda transición reduce `L`, no hay ciclos:

1. Si `L<21`, acumular `v[L]` en la masa terminal `t[L]` y terminar esa rama.
2. Para `L>=21`, obtener `q(L)`. Para cada `s` en21,22,24, usar
   `a=v[L]*q_s(L)`.
3. Si `s>L`, acumular `a` en `t[L]`, con motivo y propuesta correspondientes.
4. Si `s<=L`, propagar `a` a `v[L-s]` y sumar `a*r(L,s,direction)` para cada
   recompensa: producto total, producto21, alineación, contenencia, cruce,
   solapamiento, o recuperación de una celda física.

No normalizar `v` sobre todas las longitudes: son probabilidades de visita a
estados diferentes, no una distribución en un único instante. Sí exigir
`sum_L t[L]=1` y `sum_s s*E[count_s]+sum_L L*t[L]=L0`.
Combinar resultados direccionales por `f_left*E_left+(1-f_left)*E_right`.
Para conteos globales de longitudes/remanente, las direcciones deben coincidir.

El costo básico es `O(3*L0)` y memoria `O(L0)` más acumuladores; recompensas
por tramo agregan su costo de clasificación. No se requiere otra dimensión
de fase porque `L` determina posición. Esta DP no calcula perfiles ordinales
ni distribuciones conjuntas completas. Si se necesitaran, habría que añadir
estado para `k` o conteos, con otro costo y otros tests.

Su razón `E[count21]/E[T]` corresponde al límite de la proporción agrupada
de productos, no a `E[count21/T]`. No derivar varianzas de conteos ni una
media de cocientes a partir de expectativas únicamente.

### 6.3 Alternativas descartadas inicialmente

Fourier no se extiende sustituyendo epsilon por su promedio: la longitud
remanente es aleatoria y está acoplada a fase y trayectoria. Una DP sola es
muy eficiente para expectativas, pero no proporciona el historial muestral
que se necesita inspeccionar. Enumerar todos los caminos sirve como control
manual en casos diminutos, no como motor general. No hay tasas que justifiquen
Gillespie o un reloj de eventos; introducirlos añadiría supuestos no disponibles.

## 7. Reproducibilidad y persistencia mínima

`RunConfig` exige semilla entera. `SeedSequence(seed).spawn(2)` genera dos
fuentes `Generator(PCG64(...))`: hijo0 para direcciones, hijo1 para cortes.
Hay exactamente un `random()` escalar de dirección por molécula, también
para `f_left=0/1`, y uno por propuesta de corte. Nunca usar el RNG global.
La población se recorre en orden creciente de índice y sin paralelismo.
La separación de fuentes evita que un cambio en el consumo de cortes cambie
la lista de direcciones. Es una decisión apoyada en el mecanismo de
[SeedSequence de NumPy](https://numpy.org/doc/stable/reference/random/parallel.html).

Guardar: constructo y tramos, origen de fase, modelo completo y descripción
de hipótesis, epsilon/parámetros, p22, `n`, `f_left`, semilla, PCG64, claves de
los hijos `(0,)` y `(1,)`, política terminal y esquema de consumo RNG,
versiones Python/NumPy y del esquema de salida, plataforma, revisión de código
y estado de cambios si hay Git. Si no hay Git,
registrar hashes SHA-256 de las fuentes involucradas. Para código personalizado,
registrar también su fuente/versionado. Un timestamp no determina la secuencia.

La garantía es repetir el mismo experimento con código, parámetros, orden y
entorno iguales; no prometer identidad binaria entre versiones o plataformas.
NumPy condiciona su reproducibilidad al generador, secuencia de llamadas y
entorno; véase su [política de compatibilidad](https://numpy.org/doc/stable/reference/random/compatibility.html).

Guardar un JSON con esquema versionado usando biblioteca estándar,
`allow_nan=False`; convertir contadores NumPy a tipos nativos. No usar pickle,
evaluar expresiones arbitrarias ni cargar plugins desde el archivo. Las
políticas iniciales se reconstruyen por sus nombres y campos explícitos.
La persistencia es opcional y exterior al cálculo; la API devuelve resultados
en memoria. No implementar inicialmente reanudación de corridas.

## 8. Estrategia de validación

### 8.1 Validación determinista de contratos

Usar `unittest` y una fuente de uniformes programados, sin semillas mágicas
para forzar reglas geométricas. Probar:

- epsilon0, epsilon1 con p22 en0/1, longitudes20/21/22/23/24 y no múltiplos21.
- Longitud inicial0, no entera, negativa, probabilidades inválidas/NaN/inf,
  tramos sin partición e IDs repetidos: errores explícitos.
- CDF en0 y en cada umbral, probabilidades cero y consultas al modelo.
- Desde70, propuestas22,24,21 consultan longitudes70,48,24 y dejan3 sin
  nueva consulta; dos historias de igual índice alcanzan longitudes distintas.
- epsilon0 desde64 produce tres21 y remanente1. Desde43 verificar ambos
  espejos, fase global/local y remanentes en extremos opuestos.
- Contacto exacto con frontera no cruza; un producto que cruza dos fronteras
  cuenta uno global y dos incidencias; genes repetidos no duplican tocantes.
- `[22,43)` dentro de `[0,63)` es contenido y desfasado; el contraejemplo
  siete24+21 distingue índice8 de unidad física9.
- Conservación de masa, cobertura disjunta de productos+remanente, índices
  consecutivos, longitudes permitidas y dirección constante.
- Denominador0, moléculas sin productos, JSON sin NaN y sin pérdida de parámetros.
- Misma semilla/configuración/entorno reproduce; analizar no altera el RNG.

Los tests de geometría deben usar resultados calculados a mano: si simulación
y DP comparten un clasificador con un error, su coincidencia no lo detectaría.

### 8.2 Contraste correcto con Fourier existente

Elegir epsilon constante, `K` fijo y `L0>=24*K`; todas las moléculas generan
al menos `K` productos y ningún corte de ese prefijo está censurado.
Para cada molécula registrar `D_k=sum_{i<=k} S_i` y contrastar:

\[
\widehat P(D_k\bmod21=0)\quad\text{con}\quad
\texttt{p_fase_cero}(k,\epsilon,p22),
\]
\[
\widehat P(D_{k-1}\bmod21=0, S_k=21)\quad\text{con}\quad
\texttt{rendimiento_un_extremo}(K,\epsilon,p22)[k-1].
\]

El denominador es **todas las moléculas**, no los productos totales ni sólo
las trayectorias que sobrevivieron a una selección. Usar fase local desde
cualquier extremo; si se desea cotejarla con retícula global, fijar `o=0` y
`L0` múltiplo21 además de cumplir la cota de longitud.
Después de generar la trayectoria finita, analizar sólo el prefijo garantizado;
no prolongar artificialmente el sustrato ni cortar un producto para hacerlo caber.

No comparar la curva `rendimiento_dos_extremos(N)` con recuperación espacial
de unidades del motor: invertir el índice de un evento ordinal no lo convierte
en posición física. Su identidad de mezcla se caracteriza algebraicamente.
La mezcla física nueva se valida por espejo y por DP direccional ponderada.

Fuera del prefijo garantizado, incluso epsilon constante presenta censura
terminal y selección por longitud; comparar con DP finita, no con Fourier.
No usar `N=floor(L0/21)` como si garantizara `N` productos para todos los caminos.

### 8.3 Controles de DP y escenarios no estacionarios

Primero comprobar árboles pequeños a mano, incluyendo las tres ramas de
`L0=22` de §3, epsilon0 y mezclas direccionales. Después validar la DP con
invariantes de masa terminal y nt, y contrastar Monte Carlo mediante medias
de conteos por molécula. Incluir una política por tramos no constante y
fronteras de genes que no coincidan con múltiplos21.

Una tolerancia numérica determinista inicial para probabilidades es `1e-12`
absoluta; para conservación de nt, `1e-10*max(1,L0)`. Son límites de redondeo
para casos de prueba pequeños, no incertidumbre Monte Carlo ni permiso para
recortar probabilidades inválidas. La DP debe validarse sin reutilizar el
bucle aleatorio ni la lógica CDF del motor.

### 8.4 Pruebas estadísticas e incertidumbre

La unidad independiente es la molécula. Para `n` moléculas y variables
`X_i` acotadas en `[0,B]`, usar la cota bilateral de Hoeffding y unión de
`m` contrastes predeclarados:

\[
\delta=\sqrt{\log(2m/\alpha)/(2n)},\qquad
|\overline X-E[X]|\le B\delta.
\]

La probabilidad total de falsa alarma queda acotada por `alpha`, suponiendo
independencia entre moléculas; no se exige independencia entre los `m`
observables. La fórmula procede de la desigualdad para sumas acotadas de
[Hoeffding (1963)](https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf);
la corrección por unión y su aplicación a esta suite son decisiones del diseño.

Suite inicial: `n=50_000` por escenario, presupuesto máximo `m=128` afirmaciones
estadísticas y `alpha=1e-6`, de donde `delta≈0.01391427`.
Fijar semillas y contabilizar todos los contrastes antes de ejecutar. Si se
amplía la suite, recalcular el presupuesto por diseño; no modificar tolerancias,
semillas ni repetir hasta obtener un resultado favorable después de un fallo.
Es una cota conservadora de regresión; no promete detectar efectos menores
que esa precisión. Para precisión deseada `eta` en una variable normalizada,
elegir `n>=log(2m/alpha)/(2*eta^2)` antes del experimento.

Usar `B=1` para indicadores por ordinal, celda física o motivo terminal;
`B=floor(L0/21)` para conteos de productos por molécula; `B=L0` para nt
solapados o remanente (se puede predeclarar una cota más ajustada).
Para `L0<21`, resolver conteos cero determinísticamente, sin dividir por `B=0`.
No aplicar pruebas binomiales a todos los fragmentos agrupados como si fueran
independientes. Verificar numerador y denominador contra sus expectativas
DP antes de interpretar su cociente.

Para un intervalo conservador de una proporción agrupada, acotar por separado
las medias de numerador `A` y denominador `T`, incluyendo ambos en `m`.
Si sus intervalos son `[a_lo,a_hi]` y `[t_lo,t_hi]` con `t_lo>0`, usar
`[max(0,a_lo/t_hi), min(1,a_hi/t_lo)]`. Si el denominador no se separa de0,
el intervalo es no informativo `[0,1]`; si el observado es0, la estimación
sigue siendo `None`. Para delta entre escenarios, restar intervalos:
`[candidate_lo-baseline_hi, candidate_hi-baseline_lo]`.
Reportar nivel y método, con corrección conjunta para los dos escenarios.
Esto evita una dependencia inicial de bootstrap/SciPy y separa incertidumbre
de Monte Carlo de incertidumbre biológica, que no está cuantificada.

## 9. Integración y límites científicos

Documentar junto a cada resultado: propuestas de soporte21/22/24; longitud
como único determinante del núcleo; p22 fijo; independencia entre moléculas;
una dirección por molécula; ausencia de reloj; geometría de tramos como
entrada; retícula de fase explícita; convención terminal; política epsilon
identificada como escenario de sensibilidad; ausencia de inferencia de actividad.

La entrada común para comparar resultados externos de junturas es la tabla
de tramos y fronteras en las mismas coordenadas, con dirección y origen de
fase. La salida aporta conteos, denominadores y masas de solapamiento.
Una comparación externa debe identificar versión, convenciones, evento y
resultado esperado, con fixtures verificables y atribución de la fuente.

### Referencia matemática verificable para métricas de juntura

La DP finita de `exact.py` también sirve como una evaluación exacta de
recompensas geométricas en este modelo. Para cada dirección, `v[L]` es la masa
esperada que alcanza la longitud restante `L`; para una métrica aditiva `g`,

`E[R] = sum_L v[L] * sum_{s<=L} q_s(L) * g(L,s,direction)`.

La recompensa de cruce de una frontera `b` es el indicador estricto
`start < b < end`; la de contención usa el intervalo semiabierto completo del
producto dentro de un único tramo. Las ramas terminales no emiten recompensas
de producto. Este cálculo es una especialización finita de la descomposición
por recompensa esperada de una cadena de Markov absorbente; puede contrastarse
con la formulación de matriz fundamental y recompensa de Grinstead y Snell,
capítulo 11 ([texto y capítulo](https://chance.dartmouth.edu/teaching_aids/books_articles/probability_book/pdf.html)).
El proceso de fase del modelo estacionario es un paseo sobre `Z/21Z`; Fourier
diagonaliza convoluciones en grupos cíclicos finitos (véase el tratamiento de
paseos y convolución en [Random Walks on Finite Groups](https://math.uchicago.edu/~may/REU2020/REUPapers/Zhuang%2CYuerong.pdf)).

Estas referencias respaldan los métodos matemáticos generales, no valores
históricos de una quimera de tres genes. La literatura de siRNAs phased
describe el procesamiento secuencial desde un extremo definido, pero tampoco
fija la geometría ni el evento de cruce de las junturas sintéticas de este
ejemplo ([Axtell, 2010](https://pubmed.ncbi.nlm.nih.gov/19802589/)). No se afirma
equivalencia cuantitativa con resultados externos que carezcan de una
definición coincidente de evento, parámetros y denominadores.

El riesgo científico principal es confundir propuesta, producto observado,
fase, contención y actividad. El riesgo computacional principal es comparar
estadísticos distintos o validar dos implementaciones que compartan el mismo
error. La terminación elegida puede afectar mucho a sustratos cortos; la
DP y los conteos de remanentes la hacen visible, sin resolver su adecuación
biológica. La reproducibilidad de una simulación no valida sus hipótesis.

## 10. Verificación reproducible

Ejecutar desde la raíz, con las dependencias instaladas según el README:

```powershell
python -B -m unittest discover -s tests/unit -t . -v
python -B -m unittest discover -s tests/statistical -t . -v
python -B -m unittest discover -s tests -t . -v
```

La receta de uso está en [USAGE.md](USAGE.md). Los criterios de contribución
están en [CONTRIBUTING.md](../CONTRIBUTING.md). Las pruebas contrastan reglas
y expectativas computacionales; no sustituyen validación experimental.
