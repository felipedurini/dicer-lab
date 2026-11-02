# Desarrollo local de Dicer Lab

La aplicación funciona sin Supabase, Vercel, Render ni servicios pagos. En
desarrollo, la identidad local se habilita únicamente cuando Next está en
`NODE_ENV=development`, el navegador entra por loopback, y el API escucha en
`127.0.0.1`. El modo local no es válido para producción ni proveedores hosteados.

## Requisitos

- Python 3.13.x y Node.js 24.x.
- Go para el diseño dsRNA (verificado con 1.24.4); disponible en PATH o mediante
  `DICER_GO`. El launcher no instala Go. Instalar también el lock con ViennaRNA
  antes de usar `/design`, aunque el simulador ya arranque.
- Dependencias científicas de `requirements.txt`, además del lock aislado del API.

Desde la raíz del repositorio, preparar los entornos:

```powershell
py -3.13 -m venv .venv-web
.venv-web\Scripts\python.exe -m pip install -r requirements.txt
.venv-web\Scripts\python.exe -m pip install --require-hashes -r services/simulator_api/requirements.lock
npm ci --prefix apps/web
```

```bash
python3.13 -m venv .venv-web
.venv-web/bin/python -m pip install -r requirements.txt
.venv-web/bin/python -m pip install --require-hashes -r services/simulator_api/requirements.lock
npm ci --prefix apps/web
```

## Iniciar con un comando en Windows

Desde la raíz del repositorio, después de instalar las dependencias, ejecutar:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-DicerLab.ps1
```

El script usa su propia carpeta como raíz, comprueba/crea el entorno y las
dependencias si faltan, arranca API y Next en loopback, envia un preview real
por el BFF y abre `/lab` en el navegador predeterminado. Los logs quedan en
`.local/dicer-web/`. Para detener los procesos iniciados por el script, ejecutar:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-DicerLab.ps1 -Stop
```

## Iniciar

Abrir dos terminales en la raíz del repositorio:

```powershell
.venv-web\Scripts\python.exe -m services.simulator_api
```

```powershell
npm --prefix apps/web run dev
```

Abrir <http://127.0.0.1:3000>. El API escucha en <http://127.0.0.1:8000>, crea
SQLite y los datos en `.local/dicer-web/`, e inicia un proceso de cálculo
separado. Al detenerlo, SQLite conserva trabajos e historial.

El preset de 315 nt, tres segmentos de 105 nt, usa geometría sintética; no
contiene bases nucleotídicas ni resultados experimentales. El preview se calcula
solo al presionar «Generar trayectoria». Para una población, el formulario crea
una corrida de epsilon constante o compara esa referencia con la política por
tramos. Trabajos activos se pueden cancelar desde el panel de resultados.

## Verificaciones reproducibles

```powershell
.venv-web\Scripts\python.exe -m unittest discover -s tests/web -t . -v
npm --prefix apps/web run test -- --run
npm --prefix apps/web run test:e2e
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run build
.venv-web\Scripts\python.exe scripts/web/export_openapi.py --check
```

La medición de rendimiento local requiere ambos procesos activos:

```powershell
.venv-web\Scripts\python.exe scripts/web/benchmark_local.py --output .local/performance.json
```

Esta medición crea trabajos sintéticos de 5.000 y 50.000 moléculas por
escenario; cada trabajo compara epsilon constante con epsilon por tramos.
Incluye espera de cola, HTTP, cálculo y polling. No extrapolarla a otras CPU,
versiones o instalaciones. Puede tardar varios minutos.

## Variables para una instalación autenticada

La integración Supabase requiere configurar, fuera de Git, las variables de
`apps/web/.env.example` y `services/simulator_api/.env.example`. Python lee el
entorno del proceso, no carga `.env` automáticamente. Next admite `.env.local`.
Para consultas NCBI, exportar `NCBI_EMAIL` fuera de Git. Crear cuentas
de usuarios por invitación, desactivar registros públicos y mantener idéntica
la allowlist UUID en los dos procesos. La aplicación nunca necesita una clave
`service_role`. Esta guía no acredita un despliegue ni cuentas configuradas.
Los Dockerfiles preparan el empaquetado. Consultar las
[licencias de los componentes](../LICENSING.md) y la guía de
[despliegue](DEPLOYMENT.md) para configurar almacenamiento persistente,
autenticación y operación remota. Los resultados de benchmarks son locales
y deben mantenerse fuera de Git.
