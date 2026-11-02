# Procedencia del perfil termodinámico local

Revisión: **2026-11-02**. Se reconstruyeron y compararon las **23 parejas
ΔH/ΔS** de `services/simulator_api/design/thermo.py` con fuentes autorizadas:
21 de Zuber et al. (2022), CC BY 4.0, y dos de `RNA_NN3` de Biopython 1.86,
BSD-3-Clause. Los 46 valores coinciden exactamente; no se alteró el cálculo.
La base de redistribución de estos datos queda documentada sin depender de
resolver la licencia contradictoria de LUCID.

## Fuentes, permisos y créditos

**Z — Jeffrey Zuber, Susan J. Schroeder, Hongying Sun, Douglas H. Turner y
David H. Mathews (2022).** *Nearest neighbor rules for RNA helix folding
thermodynamics: improved end effects*. Nucleic Acids Research 50(9), 5251–5262.
[DOI](https://doi.org/10.1093/nar/gkac261),
[artículo y tablas 1–2](https://pmc.ncbi.nlm.nih.gov/articles/PMC9122537/),
[XML del artículo depositado](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9122537/fullTextXML).
Copyright © The Author(s) 2022; publicado por Oxford University Press en
nombre de Nucleic Acids Research. El apartado `permissions` del original
enlaza explícitamente [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Permite compartir y adaptar con atribución, enlace de licencia e indicación
de cambios. No se infiere ese permiso de la mera disponibilidad del artículo.
Se mantienen estas condiciones para las filas Z; la licencia MIT raíz no las
sustituye. No hay restricción no comercial en este permiso.

**B — Biopython Contributors; Sebastian Bassi (copyright 2004–2008) y Markus
Piotrowski (copyright 2013–2018).** La cabecera de
[`Bio/SeqUtils/MeltingTemp.py`, tag `biopython-186`](https://github.com/biopython/biopython/blob/biopython-186/Bio/SeqUtils/MeltingTemp.py)
ofrece expresamente Biopython License Agreement **o BSD-3-Clause**. Para las
dos entradas de `RNA_NN3` se elige BSD-3-Clause. Se conserva el
[texto de licencia](../vendor/licenses/Biopython-1.86-LICENSE.txt), copyright
1999–2024 The Biopython Contributors, junto con los créditos del archivo.
La obligación es conservar copyright, condiciones y descargo en fuente y
distribuciones binarias; no usar los nombres para insinuar respaldo.
No se incorpora el módulo completo ni se añade Biopython como dependencia.

La referencia científica de esas dos filas es **Jonathan L. Chen, Abigael L.
Dishler, Scott D. Kennedy, Ilyas Yildirim, Biao Liu, Douglas H. Turner y Martin
J. Serra (2012)**, *Testing the nearest neighbor model for canonical RNA base
pairs: revision of GU parameters*, Biochemistry 51(16), 3508–3522,
[doi:10.1021/bi3002709](https://doi.org/10.1021/bi3002709).
Se verificaron en la [tabla 3](https://pmc.ncbi.nlm.nih.gov/articles/PMC3335265/)
y su [XML original](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3335265/fullTextXML):
son los valores **entre paréntesis**, derivados de una base ampliada según
la nota c, no los valores principales de Xia et al. (1998). El artículo
indica copyright 2012 American Chemical Society y ACS AuthorChoice;
**no se le atribuye CC BY 4.0**. La copia local de esas dos entradas se
respalda en la licencia explícita del archivo Biopython, no en una supuesta
licencia universal del artículo ACS.

## Correspondencia completa

ΔH en kcal/mol; ΔS en cal/(mol·K). Las filas Z usan la columna **New Model**.
Se transcriben estimaciones centrales; no se incluyen ni propagan sus errores
experimentales. Las claves usan T como notación interna de U, no parámetros
de ADN. Para pasos equivalentes se intercambian hebras y se invierte su orden:
`XY/ZW` equivale a `WZ/YX`. Se indica la clave original para evitar confundir
esa simetría con un simple complemento inverso de una sola hebra.

| Clave local | ΔH | ΔS | Fuente y fila original | Licencia |
| --- | ---: | ---: | --- | --- |
| `init` | 4.66 | 1.78 | Z: tabla 1, `Initiation` | CC-BY-4.0 |
| `init_at` | 4.36 | 13.35 | Z: tabla 1, `AU End on AU` | CC-BY-4.0 |
| `AA/TT` | -7.44 | -20.98 | Z: tabla 1, `AA/UU` | CC-BY-4.0 |
| `AT/TA` | -8.91 | -25.22 | Z: tabla 1, `AU/UA` | CC-BY-4.0 |
| `TA/AT` | -9.16 | -25.40 | Z: tabla 1, `UA/AU` | CC-BY-4.0 |
| `CA/GT` | -10.47 | -27.08 | Z: tabla 1, `CA/GU` | CC-BY-4.0 |
| `GT/CA` | -11.98 | -31.37 | Z: tabla 1, `AC/UG` | CC-BY-4.0 |
| `CT/GA` | -10.90 | -28.50 | B: RNA_NN3, `CT/GA` | BSD-3-Clause |
| `GA/CT` | -13.21 | -34.90 | B: RNA_NN3, `GA/CT` | BSD-3-Clause |
| `CG/GC` | -9.61 | -23.46 | Z: tabla 1, `CG/GC` | CC-BY-4.0 |
| `GC/CG` | -16.52 | -42.13 | Z: tabla 1, `GC/CG` | CC-BY-4.0 |
| `GG/CC` | -13.94 | -34.41 | Z: tabla 1, `CC/GG` | CC-BY-4.0 |
| `GT/TG` | -7.66 | -24.11 | Z: tabla 2, `GU/UG` | CC-BY-4.0 |
| `GG/TT` | -9.06 | -28.57 | Z: tabla 2, `GG/UU` | CC-BY-4.0 |
| `AG/TT` | -5.10 | -16.53 | Z: tabla 2, `AG/UU` | CC-BY-4.0 |
| `TG/AT` | -2.72 | -8.08 | Z: tabla 2, `UA/GU` | CC-BY-4.0 |
| `TT/AG` | -10.58 | -32.19 | Z: tabla 2, `GA/UU` | CC-BY-4.0 |
| `TG/GT` | -8.76 | -27.04 | Z: tabla 2, `UG/GU` | CC-BY-4.0 |
| `AT/TG` | -9.23 | -27.32 | Z: tabla 2, `AU/UG` | CC-BY-4.0 |
| `CG/GT` | -5.64 | -14.83 | Z: tabla 2, `CG/GU` | CC-BY-4.0 |
| `CT/GG` | -9.26 | -23.64 | Z: tabla 2, `CU/GG` | CC-BY-4.0 |
| `GG/CT` | -12.41 | -34.23 | Z: tabla 2, `GG/CU` | CC-BY-4.0 |
| `GT/CG` | -14.73 | -40.32 | Z: tabla 2, `GC/UG` | CC-BY-4.0 |

## Alcance científico de la adaptación

La selección, el cambio de notación, el reordenamiento, la omisión de errores
y la combinación de fuentes son adaptaciones locales. No hay respaldo de
los autores a Dicer Lab. `RNA_NN4` es el nombre del antecedente en LUCID;
**no describe aquí una implementación íntegra del modelo Zuber 2022**:

- `CT/GA` y `GA/CT` conservan Chen/Biopython; Zuber usa respectivamente
  `AG/UC` = (−9.34, −23.66) y `GA/CU` = (−13.75, −36.53).
- `init_at` aplica el valor `AU End on AU` a todo extremo AU, incluso si
  el vecino es CG. El modelo completo distingue ese contexto.
- Sólo se calcula una hebra con su complemento perfecto. Las 11 entradas
  con GU se conservan por compatibilidad de tabla, pero no son alcanzables
  por las entradas A/C/G/U actuales. No implementa mismatches ni el término
  especial `GGUC/CUGG`, ni aplica la corrección de simetría de autocomplementos.
- La corrección entrópica `0.368 × (n−1) × ln([Na]+[K])`, a 70 mM y 22 °C,
  y las ventanas terminales de tres bases son convenciones exploratorias
  heredadas del perfil. No se validó aquí su precisión para esas condiciones
  o para predecir carga de RISC. No se calcula Tm ni dependencia de concentración.

El perfil `lucid_end3_v1` y sus resultados se preservan para reproducibilidad.
Migrar a un conjunto coherente completo de Zuber requeriría otro perfil,
verificación científica y reevaluación del ranking; no se hace como una
corrección de licencias. El permiso de redistribución y la correspondencia
numérica **no constituyen validación experimental ni equivalencia con LUCID**.

## Evidencia reproducible de la revisión

Se extrajeron ΔH/ΔS directamente de las tablas XML 1 y 2, se normalizaron los
signos y las orientaciones, y se leyeron las dos entradas Biopython mediante
AST sin ejecutar código descargado. Se comparó el diccionario reconstruido
con `_NN`: 23/23 parejas iguales. Las dos filas también se contrastaron con
Chen tabla 3, nota c. SHA-256 de los archivos consultados:

- XML Zuber: `e7e9a9fb2c8eb5a92cbc52c9c95ae49eaf6a65a384f6158e8ead151fe2fbc2aa`.
- XML Chen: `5f35717ca90cde8ffb370e9b6d742f5e37730a306537e0baf668000bcc309d3a`.
- `MeltingTemp.py` Biopython 1.86, texto UTF-8/LF conservado:
  `4f3cbc585ffd68d54386d40f5edb113a7c2eae4aa4388c6b496bceecdec06500`.

Los XML son documentos vivos: una modificación editorial puede cambiar el
hash sin cambiar las tablas. Se documenta una reconstrucción verificable en
esta revisión, no un supuesto proceso clean-room histórico ni una resolución
de los avisos GPL/MIT contradictorios de LUCID. No se incorpora su código.
