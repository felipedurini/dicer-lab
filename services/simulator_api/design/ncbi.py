"""Small, rate-limited NCBI E-utilities client and persistent sequence importer."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any
from urllib.parse import quote

import httpx

from .references import ReferenceCatalog, ReferenceError

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_ACCESSION = re.compile(r"^[A-Za-z]{1,6}[A-Za-z0-9_]*\.?[0-9]+(?:\.[0-9]+)?$")
_NUCLEOTIDES = set("ACGTURYSWKMBDHVN")
_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")
MAX_DYNAMIC_REFERENCE_IMPORT_NT = 20_000_000


class NCBIError(ValueError):
    """An NCBI lookup, response, or persistence error suitable for an API message."""


class NCBIClient:
    def __init__(self, client: httpx.AsyncClient, references_dir: Path):
        self.client = client
        self.references_dir = Path(references_dir).resolve()
        self._rate_lock = asyncio.Lock()
        self._persist_lock = threading.Lock()
        self._last_request = 0.0
        self.email = os.getenv("NCBI_EMAIL", "")
        self.api_key = os.getenv("NCBI_API_KEY", "")
        self.tool = os.getenv("NCBI_TOOL", "DicerLab")

    async def _get(self, utility: str, params: dict[str, str], *, max_bytes: int | None = None) -> httpx.Response:
        async with self._rate_lock:
            delay = 0.34 - (time.monotonic() - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            query = {"tool": self.tool, **params}
            if self.email:
                query["email"] = self.email
            if self.api_key:
                query["api_key"] = self.api_key
            try:
                if max_bytes is None:
                    response = await self.client.get(f"{_BASE}/{utility}.fcgi", params=query)
                    response.raise_for_status()
                else:
                    content = bytearray()
                    async with self.client.stream("GET", f"{_BASE}/{utility}.fcgi", params=query) as streamed:
                        streamed.raise_for_status()
                        async for chunk in streamed.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > max_bytes:
                                raise NCBIError("El registro excede el límite de tamaño de importación local.")
                        headers = streamed.headers.copy()
                        # aiter_bytes() has already decoded compression and transfer framing.
                        for header in ("content-encoding", "content-length", "transfer-encoding"):
                            headers.pop(header, None)
                        response = httpx.Response(status_code=streamed.status_code, headers=headers,
                                                  content=bytes(content), request=streamed.request)
            except httpx.HTTPError as exc:
                raise NCBIError("NCBI no está disponible en este momento; reintentá más tarde.") from exc
            self._last_request = time.monotonic()
            if "<ERROR>" in response.text or "<ErrorList" in response.text:
                raise NCBIError("NCBI rechazó la consulta; revisá el organismo, término o accession.")
            return response

    async def search(self, *, organism: str | None, query: str | None, accession: str | None) -> list[dict[str, Any]]:
        if accession:
            value = accession.strip()
            if not _ACCESSION.fullmatch(value):
                raise NCBIError("El accession no tiene un formato válido.")
            lookup = await self._get("esearch", {"db": "nuccore", "term": f'"{value}"[Accession]', "retmode": "json", "retmax": "1"})
            try:
                ids = lookup.json()["esearchresult"]["idlist"]
            except (ValueError, KeyError, TypeError) as exc:
                raise NCBIError("NCBI devolvió una respuesta de accession inválida.") from exc
            if ids:
                summary = await self._get("esummary", {"db": "nuccore", "id": ids[0], "retmode": "json", "version": "2.0"})
                try:
                    item = summary.json()["result"][ids[0]]
                    return [self._summary_record(item)]
                except (ValueError, KeyError, TypeError) as exc:
                    raise NCBIError("NCBI no pudo describir el accession solicitado.") from exc
            # Some TSA accessions are not indexed by ESearch's Accession field.
            # Fall back to one bounded GenBank fetch, never a project-wide download.
            record = await self._get("efetch", {"db": "nuccore", "id": value, "rettype": "gb",
                                                 "retmode": "text"},
                                     max_bytes=65_536)
            try:
                return [_parse_genbank(record.text)[0]]
            except (IndexError, NCBIError) as exc:
                raise NCBIError("NCBI no pudo describir el accession solicitado.") from exc
        if not organism or not query or len(organism) > 160 or len(query) > 120:
            raise NCBIError("Indicá organismo y nombre de gen para buscar.")
        # Search nucleotide records because non-model organisms often lack Gene→RefSeq
        # links; all query syntax stays constrained to Entrez field expressions.
        term = f'("{_entrez_phrase(organism)}"[Organism]) AND ({_entrez_phrase(query)}[All Fields])'
        response = await self._get("esearch", {"db": "nuccore", "term": term, "retmode": "json", "retmax": "8"})
        try:
            ids = response.json()["esearchresult"]["idlist"]
        except (ValueError, KeyError, TypeError) as exc:
            raise NCBIError("NCBI devolvió resultados de búsqueda inválidos.") from exc
        if not ids:
            return []
        summary = await self._get("esummary", {"db": "nuccore", "id": ",".join(ids), "retmode": "json", "version": "2.0"})
        try:
            data = summary.json()["result"]
            return [self._summary_record(data[uid]) for uid in ids]
        except (ValueError, KeyError, TypeError) as exc:
            raise NCBIError("NCBI no pudo describir los resultados encontrados.") from exc

    @staticmethod
    def _summary_record(item: dict[str, Any]) -> dict[str, Any]:
        accession = str(item["accessionversion"])
        return {
            "accession": accession,
            "organism": str(item.get("organism") or "Organismo no informado"),
            "description": str(item.get("title") or accession),
            "length_nt": int(item.get("slen") or 0),
            "molecule_type": str(item.get("moltype") or "nucleotide"),
            "source_uri": f"https://www.ncbi.nlm.nih.gov/nuccore/{quote(accession, safe='.')}",
        }

    async def fetch_records(self, accessions: list[str], *, max_total_nt: int = MAX_DYNAMIC_REFERENCE_IMPORT_NT) -> list[dict[str, Any]]:
        if not accessions or len(accessions) > 8:
            raise NCBIError("Seleccioná entre 1 y 8 secuencias.")
        normalized = [item.strip() for item in accessions]
        if any(not _ACCESSION.fullmatch(item) for item in normalized):
            raise NCBIError("Uno de los accessions tiene un formato inválido.")
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise NCBIError("La lista contiene accessions duplicados.")
        # Fetch by accession directly: this also supports TSA records whose accession is
        # accepted by EFetch but is not discoverable through ESearch's Accession field.
        response = await self._get("efetch", {"db": "nuccore", "id": ",".join(normalized), "rettype": "gb", "retmode": "text"},
                                  max_bytes=max_total_nt * 2 + 65_536)
        records = _parse_genbank(response.text)
        if sum(row["length_nt"] for row in records) > max_total_nt:
            raise NCBIError("Las secuencias superan el límite de tamaño de importación local.")
        by_accession = {row["accession"].casefold(): row for row in records}
        if len(records) != len(normalized):
            raise NCBIError("NCBI no encontró todos los accessions; comprobá las versiones solicitadas.")
        for requested in normalized:
            if requested.casefold() not in by_accession:
                raise NCBIError(f"NCBI no devolvió exactamente {requested}; comprobá accession.version.")
        return [by_accession[item.casefold()] for item in normalized]

    def persist_references(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Persist immutable partial-sequence references in the same DATA_DIR catalog."""
        with self._persist_lock:
            return self._persist_references_locked(records)

    def _persist_references_locked(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        root = self.references_dir
        root.mkdir(parents=True, exist_ok=True)
        catalog_path = root / "catalog.json"
        try:
            previous_catalog = catalog_path.read_bytes() if catalog_path.exists() else None
            catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {"schema_version": 1, "references": []}
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise NCBIError("El catálogo de referencias existente no se puede leer.") from exc
        if catalog.get("schema_version") != 1 or not isinstance(catalog.get("references"), list):
            raise NCBIError("El catálogo de referencias tiene una versión no compatible.")
        if sum(int(record.get("length_nt", 0)) for record in records) > MAX_DYNAMIC_REFERENCE_IMPORT_NT:
            raise NCBIError("Las referencias seleccionadas superan el límite local de 20.000.000 nt.")
        existing = {entry["id"]: entry for entry in catalog["references"]}
        added: list[dict[str, Any]] = []
        new_files: list[Path] = []
        for record in records:
            accession = record["accession"]
            reference_id = "ncbi_" + _SAFE_ID.sub("_", accession)
            fasta = f">{reference_id}|{accession} {record['description']}\n" + "\n".join(record["sequence_dna"][i:i+80] for i in range(0, len(record["sequence_dna"]), 80)) + "\n"
            content = fasta.encode("ascii")
            checksum = hashlib.sha256(content).hexdigest()
            entry = {
                "id": reference_id, "organism": record["organism"], "version": accession,
                "source_uri": record["source_uri"], "license": "NCBI GenBank public record; see source record and NCBI data usage policy",
                "relative_path": f"ncbi/{reference_id}.fa", "sha256": checksum,
                "length_nt": len(record["sequence_dna"]), "record_count": 1,
                "scope": "partial_reference", "completeness": "not_complete_genome_or_transcriptome",
                "molecule_type": record["molecule_type"],
                "provenance": "NCBI E-utilities nuccore EFetch GenBank record; accession.version",
            }
            prior = existing.get(reference_id)
            if prior:
                if prior.get("sha256") != checksum:
                    raise NCBIError(f"{accession} ya existe en el catálogo con otro contenido; las referencias son inmutables.")
                added.append(prior)
                continue
            destination = (root / entry["relative_path"]).resolve()
            try:
                destination.relative_to(root)
            except ValueError as exc:
                raise NCBIError("El accession generó una ruta de referencia inválida.") from exc
            if destination.exists():
                if hashlib.sha256(destination.read_bytes()).hexdigest() != checksum:
                    raise NCBIError(f"Ya existe un archivo distinto para la referencia {accession}.")
            else:
                _atomic_write(destination, content)
                new_files.append(destination)
            catalog["references"].append(entry)
            existing[reference_id] = entry
            added.append(entry)
        try:
            _atomic_write(catalog_path, json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
            # Verify exactly as the design pipeline will resolve these references.
            ReferenceCatalog(root).resolve([entry["id"] for entry in added])
        except Exception as exc:
            for path in new_files:
                path.unlink(missing_ok=True)
            if previous_catalog is None:
                catalog_path.unlink(missing_ok=True)
            else:
                _atomic_write(catalog_path, previous_catalog)
            if isinstance(exc, NCBIError):
                raise
            raise NCBIError("No se pudieron registrar las referencias en el catálogo local.") from exc
        return [ReferenceCatalog(root).resolve([item["id"]])[0].public_metadata() | {
            "scope": "partial_reference", "completeness": "not_complete_genome_or_transcriptome",
            "molecule_type": item.get("molecule_type"),
            "provenance": item.get("provenance"),
        } for item in added]


def _entrez_phrase(value: str) -> str:
    value = value.strip()
    if not value or any(ord(char) < 32 for char in value):
        raise NCBIError("La búsqueda contiene caracteres no válidos.")
    # Quote as a phrase and escape embedded quotes; Entrez expression is not user raw syntax.
    return value.replace('"', " ").replace("[", " ").replace("]", " ")


def _parse_genbank(text: str, *, require_complete: bool = True) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw_record in text.split("//"):
        lines = raw_record.splitlines()
        locus = next((line for line in lines if line.startswith("LOCUS       ")), None)
        if not locus:
            continue
        locus_parts = locus.split()
        if len(locus_parts) < 5 or not locus_parts[2].isdigit():
            raise NCBIError("NCBI devolvió un registro GenBank con LOCUS inválido.")
        fields: dict[str, list[str]] = {}
        current = ""
        in_sequence = False
        sequence_chunks: list[str] = []
        for line in lines:
            if line.startswith("FEATURES             "):
                current = ""; in_sequence = True
                continue
            if in_sequence:
                match = re.match(r"^\s*\d+\s+([A-Za-z\s]+)$", line)
                if match:
                    sequence_chunks.append("".join(match.group(1).split()).upper())
                continue
            label = line[:12].strip()
            value = line[12:].strip()
            if label:
                current = label
                if label in {"VERSION", "DEFINITION", "SOURCE", "ORGANISM"} and value:
                    fields.setdefault(label, []).append(value)
            elif current == "DEFINITION" and value:
                fields["DEFINITION"].append(value)
        if not fields.get("VERSION") or not fields.get("ORGANISM"):
            raise NCBIError("NCBI devolvió metadatos incompletos en un registro GenBank.")
        accession = fields["VERSION"][0].split()[0]
        sequence = "".join(sequence_chunks).replace("U", "T")
        if not sequence or any(base not in _NUCLEOTIDES for base in sequence):
            raise NCBIError(f"{accession} no contiene una secuencia nucleotídica compatible.")
        declared_length = int(locus_parts[2])
        if require_complete and len(sequence) != declared_length:
            raise NCBIError(f"La longitud de {accession} no coincide con su registro GenBank.")
        description = " ".join(fields.get("DEFINITION", [accession])).strip()
        result.append({
            "accession": accession, "organism": fields["ORGANISM"][0],
            "description": description, "length_nt": declared_length if not require_complete else len(sequence),
            "sequence_dna": sequence, "sequence_rna": sequence.replace("T", "U"),
            "molecule_type": locus_parts[4] if len(locus_parts) > 4 else "nucleotide",
            "source_uri": f"https://www.ncbi.nlm.nih.gov/nuccore/{quote(accession, safe='.')}",
        })
    if not result:
        raise NCBIError("NCBI no devolvió registros GenBank; revisá los identificadores.")
    return result


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
