# Contribuir a Dicer Lab

Preparar el entorno siguiendo el [README](README.md). Abrir cambios pequeños
que expliquen el problema, el comportamiento resultante y las pruebas realizadas.

- Leer la [arquitectura científica](docs/ARCHITECTURE.md) o la
  [arquitectura web](docs/web/ARCHITECTURE.md), según la capa afectada.
- Mantener el motor científico separado de la interfaz. Usar coordenadas
  semiabiertas, conservar semillas y versiones, y validar entradas sin
  recortar probabilidades ni reparar geometrías silenciosamente.
- Conservar los créditos y materiales científicos originales. Los cambios
  de modelo deben explicitar sus supuestos y distinguirse de la referencia
  estacionaria de `src/fase.py`.
- Para cambios de comportamiento, agregar una prueba que reproduzca el problema
  antes de corregirlo. Mantener semillas y tolerancias estadísticas fijadas antes
  de observar resultados; no ajustarlas para conseguir un test verde.
- Conservar la distinción entre resultados matemáticos, predicciones de diseño
  y evidencia experimental. Registrar parámetros, unidades y procedencia.
- No incorporar recursos de terceros sin verificar su licencia, versión y
  atribución. No asumir que la disponibilidad pública concede redistribución.
- Mantener secuencias privadas, entornos, logs y credenciales fuera de Git.
  Utilizar el correo `noreply` verificado de GitHub si no se desea divulgar el
  correo personal en futuros commits; esto no cambia commits anteriores.
- Ejecutar las pruebas pertinentes y revisar `git diff --check` y `git status`.
  Si cambia la API, comprobar OpenAPI y regenerar los tipos correspondientes.

Para problemas de seguridad, seguir [SECURITY.md](SECURITY.md).
