# Seguridad y privacidad

Dicer Lab es software de investigación. El modo `AUTH_MODE=local` sólo admite
loopback y no debe exponerse por un túnel ni utilizarse como autenticación en
hosting. Una instalación remota requiere Supabase, allowlist coherente en web
y API, HTTPS y almacenamiento con acceso restringido.

No publicar contraseñas, tokens, correos privados, UUID de cuentas, secuencias
confidenciales, respaldos, logs ni bases de datos. Usar `.env.example` como
referencia y guardar valores reales fuera de Git. El servicio Python no carga
automáticamente archivos `.env`. No usar claves `service_role` en el cliente.
NCBI recibe los términos/accessions de consultas y el contacto configurado;
no enviarle material confidencial como consulta.

Contactar al mantenedor por un canal privado acordado, sin adjuntar secretos a
issues públicos. No se promete un plazo de respuesta ni soporte de producción.

Antes de publicar una versión, inspeccionar también todas las ramas, etiquetas,
mensajes y metadatos de commits, y los artefactos remotos. Un archivo eliminado
puede permanecer en el historial. Si aparece un secreto real, revocarlo o rotarlo
antes de considerar saneado el incidente; borrar el texto no revoca una clave.
No reescribir ni purgar historia compartida sin autorización del propietario.

Las herramientas de escaneo no prueban ausencia absoluta de secretos.
Mantener informes de revisión, logs y configuraciones de instalaciones en
almacenamiento privado; no adjuntarlos a issues, releases ni al árbol de fuentes.

Los locks actuales incluyen Starlette 0.50.0 y versiones de minimatch con
avisos upstream. El API no usa `StaticFiles`, `HTTPEndpoint`, parsers de
formularios ni `request.url` para autorizar; minimatch pertenece a las
herramientas de desarrollo. Esto no corrige las bibliotecas. Revisar los
[avisos de Starlette](https://github.com/Kludex/starlette/security/advisories)
y el [aviso de minimatch](https://github.com/advisories/GHSA-g3hv-75wg-m249)
antes de cambiar esas funciones o desplegar. Actualizar dentro de las
restricciones de compatibilidad y ejecutar las pruebas correspondientes.
