# Documentación de Dicer Lab

El [README principal](../README.md) presenta el proyecto, su instalación y sus
límites. Estas guías describen el código y los modelos disponibles.

| Documento | Contenido |
| --- | --- |
| [Uso del motor Python](USAGE.md) | Escenarios, métricas, comparación y manifiestos reproducibles |
| [Arquitectura científica](ARCHITECTURE.md) | Modelo finito, coordenadas, programación dinámica y referencia estacionaria |
| [Diseño de dsRNA](DSRNA_DESIGN.md) | Ventanas, bloques, termodinámica, ranking y transferencia al simulador |
| [Arquitectura web](web/ARCHITECTURE.md) | Interfaz, API, autenticación, worker y persistencia |
| [Desarrollo local](web/LOCAL_DEVELOPMENT.md) | Entorno, ejecución y verificaciones |
| [Despliegue](web/DEPLOYMENT.md) | Configuración autenticada, almacenamiento y operación |
| [Referencias de secuencias](web/REFERENCE_STORAGE.md) | Catálogo persistente, importación y trazabilidad de FASTA |
| [Licencias](LICENSING.md) | Condiciones de uso y redistribución de código, bibliotecas y datos |
| [Parámetros termodinámicos](RNA_NN4_PROVENANCE.md) | Fuentes, licencias y límites de las 23 parejas de parámetros |
| [Inventario de dependencias](licenses/dependencies.csv) | Versiones y licencias declaradas |
| [Demostración sintética](../reports/dicer_demo_315/REPORT.md) | Ejemplo reproducible de 315 nt, resultados y receta |

Los datos de la demostración son sintéticos. El notebook y las figuras
originales se conservan como material científico; la sección 2.1 de la
arquitectura explica sus límites de interpretación. Ninguno de estos
materiales demuestra eficacia biológica.

Para contribuir, consultar [CONTRIBUTING.md](../CONTRIBUTING.md). Para reportar
vulnerabilidades, seguir [SECURITY.md](../SECURITY.md).
