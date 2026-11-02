# Dicer Lab — aplicación web

Interfaz Next.js/React/TypeScript y BFF que accede al servicio FastAPI. Las
pantallas principales son `/design`, `/lab`, `/compare`, `/runs` y `/help`.

La instalación completa, el contexto científico y las limitaciones están en
el [README del repositorio](../../README.md). Para desarrollar: Node.js 24,
`npm ci` y `npm run dev` desde esta carpeta; iniciar la API por separado.

`AUTH_MODE=local` sólo permite desarrollo en loopback. Para hosting, usar
Supabase y configurar la misma allowlist en Next y Python. `.env.example` es
una plantilla; los valores reales van en `.env.local` o en el entorno del
servicio, fuera de Git.

Comprobaciones: `npm run test -- --run`, `npm run typecheck`, `npm run lint`,
`npm run build`. Playwright requiere Chromium (`npx playwright install chromium`)
y se ejecuta con `npm run test:e2e`; sus respuestas API están simuladas.

Los tipos de `generated/api.ts` proceden de `contracts/web/v1/openapi.json`.
Usar `npm run generate:api` después de actualizar el contrato. No agregar
cálculos científicos al cliente: corresponden al motor Python y sus adaptadores.

Antes de redistribuir una imagen standalone, revisar los avisos de todas las
dependencias incluidas, especialmente sharp/libvips. Ver
[licencias](../../docs/LICENSING.md) y [despliegue](../../docs/web/DEPLOYMENT.md).
