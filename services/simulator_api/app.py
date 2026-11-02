"""HTTP v1 del laboratorio; no ejecuta lógica científica al importar."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import json
import asyncio
import csv
import hashlib
import io
import logging
import multiprocessing
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import require_principal
from .schemas import ErrorEnvelope, JobRequest, validate_job_request
from .schemas import PreviewRequest, TrajectoryDTO
from .settings import Settings, SettingsError, validate_data_dir
from .trajectory import trajectory_payload
from src.dicer_sim.domain import RunConfig
from src.dicer_sim.simulation import iter_population
from .storage import JobStore
from .worker import worker_loop
from .design.schemas import DesignRequest
from .design.references import ReferenceCatalog, ReferenceError
from .design.reference_data import bootstrap_references
from .design.executor import verify_artifact
from .design.ncbi import NCBIClient, NCBIError

logger = logging.getLogger("dicer.web.api")
bearer = HTTPBearer(auto_error=False)


class JobResponse(BaseModel):
    web_schema_version: int
    id: str
    label: str
    kind: str
    state: str
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    attempt: int
    progress: dict[str, Any]
    error: dict[str, Any] | None
    result_available: bool


class JobListResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None


class NCBIImportRequest(BaseModel):
    accessions: list[str] = Field(min_length=1, max_length=8)


class NCBIRecordResponse(BaseModel):
    accession: str
    organism: str
    description: str
    length_nt: int
    molecule_type: str
    source_uri: str
    sequence_dna: str | None = None
    sequence_rna: str | None = None


class NCBISearchResponse(BaseModel):
    items: list[NCBIRecordResponse]


class NCBISequencesResponse(BaseModel):
    items: list[NCBIRecordResponse]


class NCBIReferenceResponse(BaseModel):
    id: str
    organism: str
    version: str
    source_uri: str
    license: str
    sha256: str
    length_nt: int
    record_count: int
    scope: str | None = None
    completeness: str | None = None
    molecule_type: str | None = None
    provenance: str | None = None
    assembly_accession: str | None = None
    annotation_release: int | None = None


class NCBIReferencesResponse(BaseModel):
    items: list[NCBIReferenceResponse]
    catalog_status: str


class BodyLimitMiddleware:
    """Limita JSON antes de que Pydantic valide el contenido recibido."""

    def __init__(self, app, *, max_bytes: int = 65_536):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError:
                return await self._error(send, request_id, 400, "invalid_content_length", "Content-Length inválido")
            if length < 0:
                return await self._error(send, request_id, 400, "invalid_content_length", "Content-Length inválido")
            if length > self.max_bytes:
                return await self._error(send, request_id, 413, "request_too_large", "El cuerpo excede 64 KiB")

        chunks: list[bytes] = []
        size = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                return await self._error(send, request_id, 413, "request_too_large", "El cuerpo excede 64 KiB")
            chunks.append(chunk)
            more = message.get("more_body", False)

        body = b"".join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    async def _error(send, request_id: str, status: int, code: str, message: str):
        body = json.dumps({"error": {
            "code": code, "message": message, "fields": [],
            "request_id": request_id, "retryable": False,
        }}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"private, no-store"),
            (b"x-request-id", request_id.encode("ascii")),
            (b"x-content-type-options", b"nosniff"),
        ]})
        await send({"type": "http.response.body", "body": body})


def _error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    *,
    fields: list[dict[str, str]] | None = None,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request.scope.get("state", {}).get("request_id", str(uuid4()))
    response_headers = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(
        status_code=status,
        content={"error": {
            "code": code,
            "message": message,
            "fields": fields or [],
            "request_id": request_id,
            "retryable": retryable,
        }},
        headers=response_headers,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    try:
        validate_data_dir(settings)
        if settings.app_env != "test":
            bootstrap_references(settings.data_dir / "references")
    except (OSError, SettingsError, ReferenceError) as exc:
        raise RuntimeError("DATA_DIR o la instalación de referencias biológicas no está disponible") from exc
    app.state.http_client = httpx.AsyncClient(
        headers={"Accept": "application/json"}, follow_redirects=False,
        timeout=httpx.Timeout(5.0, connect=3.0),
    )
    app.state.ncbi_http_client = httpx.AsyncClient(
        headers={"Accept": "application/json"}, follow_redirects=False,
        timeout=httpx.Timeout(20.0, connect=5.0),
    )
    app.state.ncbi = NCBIClient(app.state.ncbi_http_client, settings.data_dir / "references")
    store: JobStore = app.state.job_store
    store.initialize()
    worker = None
    stop_event = None
    supervisor = None
    worker_lock = None
    if app.state.start_worker:
        lock_path = settings.data_dir / "worker.lock"
        worker_lock = lock_path.open("a+b")
        try:
            if __import__("os").name == "nt":
                import msvcrt
                worker_lock.seek(0); worker_lock.write(b"0"); worker_lock.flush(); worker_lock.seek(0)
                msvcrt.locking(worker_lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(worker_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            worker_lock.close(); worker_lock = None
            logger.error("worker lock is held by another API process")
        if worker_lock is not None:
            context = multiprocessing.get_context("spawn")
            stop_event = context.Event()
            def start_child():
                child = context.Process(target=worker_loop, args=(str(settings.data_dir), stop_event),
                                        name="dicer-simulator-worker", daemon=False)
                child.start()
                return child
            worker = start_child()
            app.state.worker_process = worker
            app.state.worker_available = True
            async def supervise_worker():
                nonlocal worker
                while not stop_event.is_set():
                    await asyncio.sleep(1)
                    if not worker.is_alive() and not stop_event.is_set():
                        logger.error("worker exited; restarting worker process")
                        await asyncio.to_thread(worker.join, 1)
                        worker = start_child()
                        app.state.worker_process = worker
                        app.state.worker_available = True
            supervisor = asyncio.create_task(supervise_worker())
    try:
        yield
    finally:
        app.state.worker_available = False
        if stop_event is not None:
            stop_event.set()
        if supervisor is not None:
            supervisor.cancel()
            try: await supervisor
            except asyncio.CancelledError: pass
        if worker is not None:
            await asyncio.to_thread(worker.join, 5)
            if worker.is_alive():
                worker.terminate()
                await asyncio.to_thread(worker.join, 5)
        if worker_lock is not None:
            try:
                if __import__("os").name == "nt":
                    import msvcrt
                    worker_lock.seek(0); msvcrt.locking(worker_lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(worker_lock.fileno(), fcntl.LOCK_UN)
            finally:
                worker_lock.close()
        await app.state.http_client.aclose()
        await app.state.ncbi_http_client.aclose()
        store.close()


def create_app(settings: Settings | None = None, *, start_worker: bool | None = None) -> FastAPI:
    """Construye la API; inyectable en tests y local con identidad loopback fija."""
    active_settings = settings or Settings.from_env()
    app = FastAPI(
        title="Dicer Lab API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan,
    )
    app.state.settings = active_settings
    app.state.jwks_cache = None
    app.state.jwks_lock = __import__("asyncio").Lock()
    app.state.preview_semaphore = __import__("asyncio").Semaphore(1)
    app.state.job_store = JobStore(active_settings.data_dir / "jobs.sqlite3")
    app.state.start_worker = (settings is None) if start_worker is None else start_worker
    app.state.worker_available = False

    @app.middleware("http")
    async def response_security(request: Request, call_next):
        response = await call_next(request)
        request_id = request.scope.get("state", {}).get("request_id")
        if request_id:
            response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = []
        for error in exc.errors():
            location = [str(part) for part in error.get("loc", ()) if part not in {"body", "query", "path"}]
            fields.append({"path": ".".join(location), "message": str(error.get("msg", "Entrada inválida"))})
        return _error_response(
            request, 422, "invalid_request", "La solicitud no cumple el contrato web v1",
            fields=fields,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            code = detail["code"]
            message = str(detail.get("message", "La solicitud no pudo procesarse"))
        else:
            code, message = {
                401: ("unauthorized", "Autenticación requerida"),
                403: ("forbidden", "Acceso denegado"),
                404: ("not_found", "Recurso no encontrado"),
                409: ("conflict", "El recurso está en un estado incompatible"),
                413: ("request_too_large", "El cuerpo excede 64 KiB"),
                422: ("invalid_request", "La solicitud no es válida"),
                429: ("quota_exceeded", "Se alcanzó el límite de trabajos"),
                503: ("service_unavailable", "El servicio no puede aceptar la solicitud"),
            }.get(exc.status_code, ("request_failed", "La solicitud no pudo procesarse"))
        return _error_response(request, exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        logger.exception("Unhandled API error request_id=%s", request.scope.get("state", {}).get("request_id"))
        return _error_response(request, 500, "internal_error", "Error interno; compartir el ID con el equipo", retryable=True)

    async def principal(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> str:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("origin") != active_settings.app_origin:
                raise HTTPException(status_code=403, detail="Origen no permitido")
        return await require_principal(request, credentials)

    @app.get("/health/live", include_in_schema=False)
    async def health_live():
        return {"status": "ok"}

    @app.get("/v1/capabilities")
    async def capabilities(_owner: str = Depends(principal)):
        return {
            "web_schema_version": 1,
            "api_version": "1.0.0",
            "terminal_rule": "stop_on_overshoot_v1",
            "supported_support_nt": [21, 22, 24],
            "supported_epsilon": ["constant", "piecewise", "linear", "quadratic", "exponential", "custom"],
            "limits": {
                "max_construct_length_nt": 5000,
                "max_segments": 32,
                "max_scenarios": 4,
                "max_molecules_per_scenario": 100000,
                "max_work_units": 30000000,
                "max_breakpoints": 16,
                "max_request_bytes": 65536,
                "max_response_bytes": 3145728,
                "max_exact_length_nt": 1000,
                "max_exact_segments": 16,
            },
            "worker_available": bool(getattr(app.state, "worker_available", False)),
        }

    @app.post("/v1/trajectories", response_model=TrajectoryDTO)
    async def create_trajectory(
        body: PreviewRequest,
        _owner: str = Depends(principal),
    ):
        construct = body.to_domain()
        model = body.to_model()
        config = RunConfig(n_molecules=1, seed=body.seed, f_left=body.f_left)
        async with app.state.preview_semaphore:
            molecule = await run_in_threadpool(
                lambda: next(iter_population(construct, model, config))
            )
        return trajectory_payload(construct, model, config, molecule, source_kind="preview")

    @app.post("/v1/epsilon-profile")
    async def epsilon_profile(body: PreviewRequest, _owner: str = Depends(principal)):
        """Return the exact model epsilon at every usable integer remaining length."""
        model = body.to_model()
        length_nt = body.construct_config.length_nt
        points = [
            {"length_nt": remaining, "epsilon": model.epsilon_value(remaining, length_nt)}
            for remaining in range(21, length_nt + 1)
        ]
        return {"length_nt": length_nt, "points": points}

    def job_dto(job):
        return {"web_schema_version": 1, "id": job.id, "label": job.request.get("label", "Corrida"),
                "kind": job.kind,
                "state": job.state, "created_at": job.created_at, "updated_at": job.updated_at,
                "finished_at": job.finished_at,
                "attempt": max(1, job.attempts), "progress": job.progress, "error": job.error,
                "result_available": job.state == "succeeded" and job.result is not None}

    def ensure_store():
        app.state.job_store.initialize()

    @app.get("/v1/design/references")
    async def design_references(_owner: str = Depends(principal)):
        catalog = active_settings.data_dir / "references" / "catalog.json"
        if not catalog.is_file():
            return {"items": [], "catalog_status": "missing"}
        try:
            return {"items": ReferenceCatalog(active_settings.data_dir / "references").list_public(),
                    "catalog_status": "ready"}
        except ReferenceError as exc:
            raise HTTPException(status_code=503, detail={"code": "reference_catalog_invalid", "message": str(exc)}) from exc

    @app.get("/v1/ncbi/search", response_model=NCBISearchResponse, response_model_exclude_none=True)
    async def ncbi_search(request: Request, organism: str | None = None, query: str | None = None,
                          accession: str | None = None, _owner: str = Depends(principal)):
        try:
            records = await app.state.ncbi.search(
                organism=organism, query=query, accession=accession)
        except NCBIError as exc:
            raise HTTPException(status_code=502, detail={"code": "ncbi_unavailable", "message": str(exc)}) from exc
        return {"items": [{key: value for key, value in record.items() if key not in {"sequence_dna", "sequence_rna"}}
                           for record in records]}

    @app.post("/v1/ncbi/sequences", response_model=NCBISequencesResponse)
    async def ncbi_sequences(body: NCBIImportRequest, _owner: str = Depends(principal)):
        accessions = body.accessions
        try:
            records = await app.state.ncbi.fetch_records(accessions, max_total_nt=20_000)
            if sum(len(record["sequence_rna"]) for record in records) > 20_000:
                raise NCBIError("Las secuencias objetivo seleccionadas superan el límite de 20.000 nt del formulario.")
            for record in records:
                if len(record["sequence_rna"]) < 21 or any(base not in "ACGU" for base in record["sequence_rna"]):
                    raise NCBIError(f"{record['accession']} no es una secuencia objetivo compatible (se requieren ≥21 bases A/C/G/U sin ambigüedades).")
        except NCBIError as exc:
            raise HTTPException(status_code=422 if any(term in str(exc).lower() for term in ("compatible", "20.000", "límite de tamaño")) else 502,
                                detail={"code": "ncbi_sequence_invalid", "message": str(exc)}) from exc
        return {"items": records}

    @app.post("/v1/ncbi/references", response_model=NCBIReferencesResponse)
    async def ncbi_references(body: NCBIImportRequest, _owner: str = Depends(principal)):
        accessions = body.accessions
        client = app.state.ncbi
        try:
            records = await client.fetch_records(accessions)
            references = await run_in_threadpool(client.persist_references, records)
        except NCBIError as exc:
            raise HTTPException(status_code=502, detail={"code": "ncbi_import_failed", "message": str(exc)}) from exc
        return {"items": references, "catalog_status": "ready"}

    @app.post("/v1/design/jobs", status_code=202, response_model=JobResponse)
    async def submit_design(body: DesignRequest, request: Request,
                            idempotency_key: UUID = Header(alias="Idempotency-Key"),
                            _owner: str = Depends(principal)):
        ensure_store()
        try:
            ReferenceCatalog(active_settings.data_dir / "references").resolve(body.reference_ids)
        except ReferenceError as exc:
            raise HTTPException(status_code=422, detail={"code": "reference_invalid", "message": str(exc)}) from exc
        payload = body.model_dump(mode="json", by_alias=True)
        canonical = json.dumps({"kind": "dsrna_design", "profile": body.thermo_profile, "references": body.reference_ids, "request": payload}, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        try:
            job, created = app.state.job_store.submit(_owner, str(idempotency_key), digest, payload, kind="dsrna_design")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code": "idempotency_conflict", "message": "La clave ya se usó con otros parámetros"}) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=429, detail={"code": "quota_exceeded", "message": "La cola alcanzó su límite"}, headers={"Retry-After": "5"}) from exc
        return JSONResponse(status_code=202 if created else 200, content=job_dto(job), headers={"Location": f"/v1/jobs/{job.id}", "Idempotency-Replayed": "false" if created else "true"})

    @app.post("/v1/design/jobs/{job_id}/candidates/{candidate_id}/simulate", status_code=202, response_model=JobResponse)
    async def simulate_design_candidate(job_id: str, candidate_id: str, raw: dict[str, Any],
                                        idempotency_key: UUID = Header(alias="Idempotency-Key"),
                                        _owner: str = Depends(principal)):
        ensure_store()
        source_job = app.state.job_store.get_owned(_owner, job_id)
        if source_job is None or source_job.kind != "dsrna_design" or source_job.state != "succeeded" or not source_job.result:
            raise HTTPException(status_code=404, detail="Candidate not found")
        candidate = next((row for row in source_job.result.get("candidates", []) if row.get("candidate_id") == candidate_id), None)
        if candidate is None: raise HTTPException(status_code=404, detail="Candidate not found")
        try:
            if not isinstance(raw, dict): raise ValueError("request must be an object")
            blocks = candidate["blocks"]
            raw["web_schema_version"] = 1
            raw["construct"] = {"length_nt": candidate["length_nt"], "phase_origin_nt": 0,
                                "segments": [{"segment_id": f"design_{i+1}", "gene_id": b["gene_id"],
                                              "start": b["start"], "end": b["end"]} for i,b in enumerate(blocks)]}
            from .schemas import JobRequest, validate_job_request
            body = JobRequest.model_validate(raw); validate_job_request(body)
        except Exception as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_request", "message": "Simulation parameters are invalid"}) from exc
        payload = body.model_dump(mode="json", by_alias=True)
        snapshot = {"sequence_rna": candidate["sequence_rna"], "candidate_id": candidate_id,
                    "source_job_id": job_id, "sha256": hashlib.sha256(candidate["sequence_rna"].encode()).hexdigest()}
        payload["_sequence_source"] = snapshot
        digest = hashlib.sha256(json.dumps({"kind":"simulation","request":payload},sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        try:
            child, created = app.state.job_store.submit(_owner, str(idempotency_key), digest, payload, kind="simulation")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={"code":"idempotency_conflict","message":"La clave ya se usó con otros parámetros"}) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=429, detail={"code":"quota_exceeded","message":"La cola alcanzó su límite"}) from exc
        return JSONResponse(status_code=202 if created else 200, content=job_dto(child), headers={"Location":f"/v1/jobs/{child.id}","Idempotency-Replayed":"false" if created else "true"})

    @app.post("/v1/jobs", status_code=202, response_model=JobResponse)
    async def submit_job(
        body: JobRequest,
        request: Request,
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        _owner: str = Depends(principal),
    ):
        validate_job_request(body)
        ensure_store()
        payload = body.model_dump(mode="json", by_alias=True)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        try:
            job, created = app.state.job_store.submit(_owner, str(idempotency_key), digest, payload)
        except ValueError as exc:
            if str(exc) == "idempotency_conflict":
                raise HTTPException(status_code=409, detail={"code": "idempotency_conflict", "message": "La clave ya se usó con otros parámetros"}) from exc
            raise
        except RuntimeError as exc:
            raise HTTPException(status_code=429, detail={"code": "quota_exceeded", "message": "La cola alcanzó su límite"}, headers={"Retry-After": "5"}) from exc
        response = JSONResponse(status_code=202 if created else 200, content=job_dto(job), headers={"Location": f"/v1/jobs/{job.id}"})
        response.headers["Idempotency-Replayed"] = "false" if created else "true"
        return response

    @app.get("/v1/jobs", response_model=JobListResponse)
    async def list_jobs(limit: int = 20, before: str | None = None, kind: str | None = None, _owner: str = Depends(principal)):
        ensure_store()
        try:
            jobs = app.state.job_store.list_owned(_owner, limit, before, kind)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 50") from exc
        return {"items": [job_dto(job) for job in jobs], "next_cursor": jobs[-1].created_at if len(jobs) == limit else None}

    @app.get("/v1/jobs/{job_id}", response_model=JobResponse)
    async def get_job(job_id: str, _owner: str = Depends(principal)):
        ensure_store()
        job = app.state.job_store.get_owned(_owner, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job_dto(job)

    @app.post("/v1/jobs/{job_id}/cancel", status_code=202, response_model=JobResponse)
    async def cancel_job(job_id: str, _owner: str = Depends(principal)):
        ensure_store()
        job = app.state.job_store.get_owned(_owner, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.state in {"succeeded", "failed", "cancelled", "deleted"}:
            return JSONResponse(status_code=200, content=job_dto(job))
        app.state.job_store.cancel(_owner, job_id)
        return job_dto(app.state.job_store.get_owned(_owner, job_id))

    @app.get("/v1/jobs/{job_id}/results")
    async def get_results(job_id: str, _owner: str = Depends(principal)):
        ensure_store()
        job = app.state.job_store.get_owned(_owner, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.state != "succeeded" or job.result is None:
            raise HTTPException(status_code=409, detail={"code": "result_not_ready", "message": "El resultado completo todavía no está disponible"})
        return job.result

    @app.get("/v1/jobs/{job_id}/exports/{artifact}")
    async def export_job(job_id: str, artifact: str, _owner: str = Depends(principal)):
        ensure_store()
        job = app.state.job_store.get_owned(_owner, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.state != "succeeded" or job.result is None:
            raise HTTPException(status_code=409, detail={"code": "result_not_ready", "message": "El resultado completo todavía no está disponible"})
        if job.kind == "dsrna_design":
            record = app.state.job_store.get_artifact(job.id, artifact)
            if record is None: raise HTTPException(status_code=404, detail="Artifact not found")
            try: payload = verify_artifact(str(active_settings.data_dir), dict(record))
            except ValueError as exc: raise HTTPException(status_code=500, detail="Artifact integrity failure") from exc
            return Response(payload, media_type="text/csv; charset=utf-8" if artifact.endswith(".csv") else "application/json", headers={"Content-Disposition": f'attachment; filename="{artifact}"'})
        result = job.result
        filename = "dicer"
        if artifact == "results.json":
            content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
            media_type = "application/json"
        elif artifact == "configuration.json":
            content = json.dumps(job.request, ensure_ascii=False, indent=2, allow_nan=False)
            media_type = "application/json"
        elif artifact == "metrics.csv":
            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\r\n")
            writer.writerow(("scenario_id", "metric", "scope", "scope_id", "numerator", "denominator", "value", "basis", "unit", "source_kind"))
            for scenario in result.get("scenarios", []):
                for metric in scenario.get("metrics", []):
                    writer.writerow((scenario["id"], metric["key"], metric["scope"], metric.get("scope_id"),
                                     metric["numerator"], metric["denominator"], metric.get("value"),
                                     metric["basis"], metric["unit"], metric["source_kind"]))
            content, media_type = output.getvalue(), "text/csv; charset=utf-8"
        elif artifact.startswith("manifest-") and artifact.endswith(".json"):
            scenario_id = artifact[len("manifest-"):-len(".json")]
            scenario = next((item for item in result.get("scenarios", []) if item.get("id") == scenario_id), None)
            if scenario is None:
                raise HTTPException(status_code=404, detail="Artifact not found")
            content = json.dumps(scenario["manifest"], ensure_ascii=False, indent=2, allow_nan=False)
            media_type = "application/json"
            filename = f"manifest-{scenario_id}"
        else:
            raise HTTPException(status_code=404, detail="Artifact not found")
        suffix = ".csv" if artifact == "metrics.csv" else ".json"
        return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}{suffix}"'})

    @app.delete("/v1/jobs/{job_id}", status_code=204)
    async def delete_job(job_id: str, _owner: str = Depends(principal)):
        ensure_store()
        job = app.state.job_store.get_owned(_owner, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if not app.state.job_store.delete_owned(_owner, job_id):
            raise HTTPException(status_code=409, detail={"code": "job_active", "message": "Solo se pueden borrar trabajos terminales"})
        if job.kind == "dsrna_design":
            from .design.executor import delete_job_artifacts
            delete_job_artifacts(str(active_settings.data_dir), job_id)
            import shutil
            shutil.rmtree(active_settings.data_dir / "design" / job_id, ignore_errors=True)
        return Response(status_code=204)

    app.add_middleware(BodyLimitMiddleware, max_bytes=65_536)
    return app


app = create_app()
