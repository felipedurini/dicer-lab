# Licencias y procedencia

Fuentes y versiones documentadas al **2026-11-02**. Las condiciones de cada
componente se conservan por separado; la licencia del proyecto no sustituye
las licencias de terceros ni concede derechos sobre otros materiales.

## Código propio y materiales originales

`LICENSE` contiene la licencia MIT, copyright 2026 Malena Zogbi, que se
conserva íntegra. El código y los materiales propios mantienen sus créditos.
Las contribuciones deben respetar los derechos de sus titulares; los datos,
dependencias y recursos de terceros se rigen por las condiciones siguientes.

## dsRNAmax y modificaciones

Se verificó `LICENSE` contra la revisión
[`674b5b513248ea551dcc9217f1059d593f827766`](https://github.com/sfletc/dsRNAmax/tree/674b5b513248ea551dcc9217f1059d593f827766).
El texto coincide: **BSD-3-Clause**, Stephen Fletcher, 2023. Permite fuente y
binarios, con o sin modificaciones, manteniendo copyright, condiciones y
exención de responsabilidad; no permite insinuar respaldo de sus autores.

La comparación de archivos con esa revisión identifica cambios en `main.go`
y `main_test.go`, más `protocol.go` y `protocol_test.go` añadidos. Los restantes
archivos upstream conservados, incluidos fixtures, coinciden al normalizar
finales de línea. `UPSTREAM_REVISION` y el aviso local identifican la derivación.
El README vendorizado enlaza a la ilustración upstream; esa imagen no se
incorpora al repositorio.
El protocolo JSON aporta discover/assemble/blocks/screen y trazabilidad; no es
un release oficial de dsRNAmax. Las modificaciones locales se distribuyen bajo
BSD-3-Clause según sus avisos.

Las tres dependencias de `go.mod` tienen licencia MIT verificada en las fuentes
de sus versiones dentro de la caché de módulos. Sus textos se conservan en
`vendor/licenses/`. El ejecutable incluye el runtime Go (BSD-3-Clause).
El Dockerfile del API incorpora esos avisos junto al binario.

## LUCID y datos termodinámicos

Revisión examinada: `37910bd6744b2ce6ce4c9b2582819b130e7ea509`.

- [`software/sifi21_plus/LICENSE`](https://github.com/Brunxi/LUCID/blob/37910bd6744b2ce6ce4c9b2582819b130e7ea509/software/sifi21_plus/LICENSE)
  contiene GPL versión 3.
- [`pyproject.toml`](https://github.com/Brunxi/LUCID/blob/37910bd6744b2ce6ce4c9b2582819b130e7ea509/software/sifi21_plus/pyproject.toml)
  declara MIT. Eso no elimina las obligaciones del archivo LICENSE ni otorga
  permiso para código de otros titulares.
- [`free_energy.py`](https://github.com/Brunxi/LUCID/blob/37910bd6744b2ce6ce4c9b2582819b130e7ea509/software/sifi21_plus/sifi21_plus/free_energy.py)
  identifica a Biopython como antecedente y atribuye `RNA_NN4` a **Zuber et al.
  (2022)**, no a Freier (1986). La referencia es
  [doi:10.1093/nar/gkac261](https://doi.org/10.1093/nar/gkac261).

`services/simulator_api/design/thermo.py` implementa una suma independiente
de entalpías/entropías para dúplex complementarios, corrección salina y energías
de ventanas terminales. No importa LUCID ni Biopython ni incluye sus pipelines.
La tabla numérica usa las entradas seleccionadas del perfil RNA_NN4, con
fuentes y permisos documentados por separado.

**Fuentes y permisos de los datos termodinámicos.**
La [correspondencia completa](RNA_NN4_PROVENANCE.md) registra cada una de las
23 parejas ΔH/ΔS, su clave original, fuente, licencia y transformaciones.
Se extrajeron 21 de las tablas 1–2 de Zuber 2022, cuyo original declara
**CC BY 4.0**; las dos restantes (`CT/GA`, `GA/CT`) se verificaron en
`RNA_NN3` de Biopython 1.86, con elección explícita **BSD-3-Clause**.
Estas últimas corresponden a Chen 2012, tabla 3, valores entre paréntesis,
no a Zuber 2022. Se conserva el texto de licencia Biopython y sus créditos;
las filas Zuber mantienen atribución, enlace CC BY 4.0 e identificación de
adaptaciones. Los 46 números coinciden; no se cambió el perfil científico.

No se presume que los datos sean libres por ser hechos ni que todo LUCID
sea BSD/MIT. El artículo Chen declara ACS AuthorChoice, no CC BY 4.0;
la vía de reutilización elegida para esas dos entradas es el archivo Biopython
con licencia explícita. Los permisos de estos datos no resuelven la
contradicción GPL/MIT de LUCID ni conceden permiso para incorporar su código.

`lucid_end3_v1` es un identificador de perfil propio. No significa integración
oficial, equivalencia numérica validada, método completo de Zuber ni respaldo
de los autores. Es un perfil híbrido con simplificaciones de términos terminales,
documentadas en el registro de procedencia. Concentraciones declaradas son metadatos del perfil; la suma
de ΔG implementada no calcula una Tm dependiente de concentración.

## ViennaRNA 2.7.2

Se verificaron el `COPYING` del wheel instalado y
[`v2.7.2/COPYING`](https://github.com/ViennaRNA/ViennaRNA/blob/v2.7.2/COPYING).
Su licencia permite uso y modificación para investigación, educación y uso
comercial, pero condiciona la redistribución a no cobrar más que el costo del
medio y exige crédito a los autores y al instituto. Para incluirlo en un
producto comercial, indica contactar a los autores. **No es MIT ni una
autorización comercial irrestricta.**

`vendor/licenses/` conserva el COPYING y AUTHORS del wheel. La raíz publica
código que depende del paquete; no contiene el wheel. Al distribuir una imagen
o instalador, deben mantenerse los avisos del paquete y de sus componentes,
incluido NAVIEW, cuyo aviso separado limita las copias a fines no comerciales
sin permiso adicional de Robert E. Bruccoleri. En v2.7.2 está en
[`src/ViennaRNA/plotting/naview/naview.c`](https://github.com/ViennaRNA/ViennaRNA/blob/v2.7.2/src/ViennaRNA/plotting/naview/naview.c);
se conserva el [aviso](../vendor/licenses/ViennaRNA-2.7.2-naview-notice.txt).
Dicer Lab no invoca el dibujo NAVIEW, pero eso no demuestra que un wheel no
incluya ese componente. La composición y los avisos deben comprobarse para cada imagen distribuida.
No vender un binario agregado bajo la sola licencia MIT del proyecto.

## Secuencias NCBI

La [política oficial](https://www.ncbi.nlm.nih.gov/home/about/policies/), sección
Molecular Data Usage, no impone restricciones propias a estos datos. También
aclara que no hay transferencia de derechos de depositantes a NCBI y que pueden
existir reclamos de propiedad intelectual. Por tanto **no se declara CC0, MIT
ni dominio público universal para el FASTA**.

El catálogo identifica RefSeq, assembly `GCF_003254395.2`, Annotation Release
104, URL de descarga, checksum del gzip y del FASTA expandido. El informe
oficial atribuye el assembly a Uppsala University. El [aviso del dataset](../services/simulator_api/reference_data/NOTICE.md)
conserva esos créditos. La referencia corresponde al conjunto anotado, no a
todos los transcritos biológicamente posibles.

No se identificó una restricción específica adicional en las fuentes revisadas;
eso no equivale a una garantía sobre cada registro ni sobre patentes o usos
comerciales. Las importaciones posteriores necesitan su propia revisión de
procedencia. No incluir las importaciones privadas de `DATA_DIR` al publicar.

## Dependencias y distribuciones

El [inventario](licenses/dependencies.csv) registra el lock npm completo, el
lock Python y las dependencias científicas instaladas usadas en la revisión.
Las filas npm representan también alternativas opcionales de plataforma, no
necesariamente paquetes presentes en cada instalación. Los textos de paquetes
instalados se revisaron para las dependencias directas y casos de licencias
especiales; los metadatos transitivos no constituyen una auditoría de todos los
archivos internos de cada wheel o paquete nativo.

- MIT/BSD/ISC: conservar avisos y exenciones de responsabilidad.
- Apache-2.0: conservar licencia y avisos pertinentes, incluido NOTICE cuando
  exista; documentar modificaciones redistribuidas.
- MPL-2.0 (certifi, lightningcss, axe-core): revisar las obligaciones de fuente
  de los archivos cubiertos al distribuir ejecutables o modificaciones.
- LGPL-3.0-or-later (libvips, transitivo de sharp/Next): conservar los avisos y
  cumplir disponibilidad de fuente y requisitos aplicables a la biblioteca
  combinada. Publicar este código fuente con un lock no equivale a distribuir
  automáticamente esos binarios; una imagen standalone sí requiere revisión.
- CC-BY-4.0 (caniuse-lite): atribución y aviso de licencia al redistribuir datos.
- NumPy/Matplotlib: conservar sus licencias y los avisos de bibliotecas incluidas
  en wheels; una etiqueta del paquete no cubre todos sus componentes.

`node_modules`, entornos virtuales y binarios locales están excluidos de Git.
Las licencias de imágenes base de Docker, compiladores y dependencias nativas
deben revisarse sobre la imagen final antes de publicarla en un registro.
