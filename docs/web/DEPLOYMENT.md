# Despliegue de Dicer Lab

Esta guía describe los requisitos para operar Dicer Lab con autenticación,
almacenamiento persistente y acceso HTTPS. Cada instalación debe verificar
su configuración y recursos; el repositorio no proporciona un servicio alojado.

## Componentes necesarios

- Next.js con runtime Node.js 24 y un origen HTTPS estable.
- API Python 3.13 con un worker científico, dsRNAmax compilado y ViennaRNA 2.7.2.
- Disco persistente para SQLite, referencias y artefactos bajo `DATA_DIR`.
- Supabase Auth con cuentas autorizadas y firma asimétrica ES256/RS256.

No se usan Supabase Database/Storage, Redis ni Celery. SQLite y el worker
requieren una instancia de API con `workers=1`; no escalar réplicas sin rediseñar
la coordinación. Elegir un proveedor con persistencia real. No depender del
filesystem efímero de una función ni asumir que un plan gratuito incluye disco.

## Configuración

Usar `apps/web/.env.example` y `services/simulator_api/.env.example` como lista
de variables, nunca como archivo con credenciales reales. En ambos servicios:
`APP_ENV=production`, `AUTH_MODE=supabase`, origen correcto y allowlists
`ALLOWED_USER_IDS` idénticas. Next usa `APP_ORIGIN`, `SIMULATOR_API_URL`,
`NEXT_PUBLIC_SUPABASE_URL` y la clave publicable del proyecto. Python usa
`SUPABASE_URL`, `SUPABASE_JWT_ALGORITHMS`, `DATA_DIR`, `API_HOST` y `PORT`.

Python lee variables del proceso y no carga `.env` automáticamente. Configurar
`NCBI_EMAIL` con un contacto válido y, si corresponde, `NCBI_API_KEY` en el
servidor. No registrar Authorization, cookies ni URLs de consultas que incluyan
la clave/contacto NCBI. Las únicas variables públicas de Auth son las declaradas
con `NEXT_PUBLIC_`; no exponer allowlists ni claves `service_role`.

Deshabilitar registros públicos/anónimos en Supabase si el servicio se destina
al equipo; crear o invitar únicamente las cuentas previstas. Mantener URLs de
redirección limitadas. El código no configura esas opciones del proveedor.
No habilitar `AUTH_MODE=local` en hosting ni por túneles: ese modo no identifica
a un usuario remoto.

## Imágenes y almacenamiento

Desde la raíz:

```bash
docker build -f services/simulator_api/Dockerfile -t dicer-api:local .
docker build -f apps/web/Dockerfile -t dicer-web:local apps/web
```

El contexto web contiene su propia `.dockerignore` para excluir secretos y
artefactos locales. Las variables públicas de Next necesarias en el build deben
configurarse con el mecanismo de build del destino; no incrustar secretos en
capas Docker. Probar el arranque de ambas imágenes con la configuración del destino.

Montar un volumen persistente en `DATA_DIR`. Al arrancar, se verifica y expande
la referencia RefSeq incluida. Prever al menos el tamaño del FASTA expandido
(aproximadamente 100 MB), base de datos, resultados, espacio de trabajo y backups.
Las importaciones y trabajos pueden aumentar ese consumo; no existe una garantía
de tiempo máximo para los diseños ni un benchmark remoto vigente.

El Dockerfile del API conserva avisos de dsRNAmax y dependencias Go. pip conserva
los avisos del wheel ViennaRNA. Antes de distribuir imágenes, verificar su
contenido y cumplir las [licencias](../LICENSING.md), incluidas ViennaRNA/NAVIEW,
libvips y bibliotecas de las imágenes base. Una compilación exitosa no acredita
permiso de redistribución comercial.

## Verificación antes de habilitar acceso

1. Completar las pruebas locales y revisar los `skipped`; Go debe estar instalado.
2. Probar inicio/cierre de sesión con cuentas de prueba autorizadas, rechazo de
   tokens inválidos y bloqueo de acceso a trabajos de otro propietario.
3. Probar diseño, polling, cancelación, exportación y transferencia a Dicer a
   través de Next y la API reales, no sólo con mocks de Playwright.
4. Reiniciar el servicio y comprobar persistencia e integridad de referencias,
   SQLite y artefactos. Probar el comportamiento de un worker interrumpido.
5. Verificar HTTPS, reglas del proxy, límites de recursos, logs sin datos
   sensibles y acceso restringido al volumen. Publicar únicamente los puertos
   necesarios; no exponer una API local sin autenticación.
6. Probar backup y restauración en un directorio/volumen separado. No copiar
   únicamente `jobs.sqlite3` mientras hay WAL activo: usar un procedimiento
   consistente y preservar los artefactos referenciados.

No hay herramienta administrativa de backup/restore completada ni una política
de recuperación de producción incluida en el proyecto. El operador debe
resolver esos puntos antes de confiar datos irremplazables al servicio.
