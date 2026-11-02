# Persistencia de referencias para screening

## Referencia inicial

El conjunto incluido es el FASTA de transcritos RefSeq de *Apis mellifera*, assembly `GCF_003254395.2` (`Amel_HAv3.1`), Annotation Release 104. Procede del endpoint oficial NCBI indicado en `services/simulator_api/reference_data/catalog.json`. Contiene 27.887 registros y 98.645.700 nt; el SHA-256 del FASTA normalizado está registrado en ese catálogo. El archivo de origen comprimido (`services/simulator_api/reference_data/apis_mellifera_amel_hav3_1_annotation_104_rna.fna.gz`) pesa unos 19 MB.

En el primer arranque, FastAPI verifica el checksum del archivo empaquetado, lo expande y verifica checksum, longitud y cantidad de registros. La instalación usa rename atómico. Los FASTA expandidos y el catálogo activo se guardan en `DATA_DIR/references/`; los siguientes screenings leen esos archivos locales. No se consulta NCBI durante un diseño. El catálogo activo combina referencias incluidas y referencias parciales importadas por NCBI, y el bootstrap preserva entradas dinámicas al añadir metadatos empaquetados.

El screening examina todas las ventanas no ambiguas de 21 nt de cada registro FASTA, también a través de la orientación complementaria inversa. Es una búsqueda de coincidencias exactas; no detecta mismatches. Las letras ambiguas interrumpen ventanas y se contabilizan como omitidas. El transcriptoma inicial se refiere al conjunto de transcritos anotados de esa versión, no a toda transcripción biológica posible.

## Almacenamiento persistente

Para que el conjunto expandido y las importaciones sobrevivan a reinicios y despliegues, montar un volumen persistente y configurar `DATA_DIR` con esa ruta; por ejemplo, `/var/data`. Reservar al menos 1 GB para este conjunto inicial, SQLite y artefactos, y aumentar según el uso de referencias importadas. Verificar los requisitos del proveedor y los permisos del volumen.

En un filesystem efímero, la referencia empaquetada puede reconstruirse en cada arranque, pero las referencias dinámicas y los trabajos no son durables. Configurar el volumen antes de confiar importaciones o resultados a una instalación remota.

Las secuencias descargadas por la integración NCBI existente se registran como referencias `partial_reference`, con organism, accession.version, procedencia, checksum y metadata; no son transcriptomas completos. El deduplicado usa el ID de accession.version y rechaza que un ID inmutable cambie de contenido. El límite actual por lote dinámico es 20 millones de nt; el límite de referencias seleccionables para screening es 1.000 millones de nt.
