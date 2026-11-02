"""Checksum-verified access to preinstalled, allowlisted FASTA references."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterator


MAX_SELECTED_REFERENCE_NT = 1_000_000_000
_ALLOWED_SEQUENCE_BYTES = b"ACGTRYSWKMBDHVN"


class ReferenceError(ValueError):
    """A catalog, identity, path, sequence, or digest failed validation."""


@dataclass(frozen=True)
class Reference:
    id: str
    organism: str
    version: str
    source_uri: str
    license: str
    sha256: str
    length_nt: int
    record_count: int
    path: Path
    scope: str = "unspecified"
    completeness: str | None = None
    molecule_type: str | None = None
    provenance: str | None = None
    assembly_accession: str | None = None
    annotation_release: int | None = None

    def public_metadata(self) -> dict[str, object]:
        result: dict[str, object] = {
            "id": self.id, "organism": self.organism, "version": self.version,
            "source_uri": self.source_uri, "license": self.license, "sha256": self.sha256,
            "length_nt": self.length_nt, "record_count": self.record_count,
        }
        for key, value in (("scope", self.scope), ("completeness", self.completeness),
                           ("molecule_type", self.molecule_type), ("provenance", self.provenance),
                           ("assembly_accession", self.assembly_accession),
                           ("annotation_release", self.annotation_release)):
            if value and (key != "scope" or value != "unspecified"):
                result[key] = value
        return result


class ReferenceCatalog:
    def __init__(self, references_dir: Path | str):
        self.root = Path(references_dir).resolve()
        self.catalog_path = self.root / "catalog.json"

    def list_public(self) -> list[dict[str, object]]:
        # Listing is metadata-only: hashing a whole transcriptome on every page
        # load is wasteful. `resolve()` verifies every selected FASTA before a
        # design is queued, and the worker verifies it again before screening.
        return [self._metadata_only(item) for item in self._entries()]

    @staticmethod
    def _metadata_only(item: dict[str, Any]) -> dict[str, object]:
        required = ("id", "organism", "version", "source_uri", "license", "sha256",
                    "length_nt", "record_count")
        if any(key not in item for key in required):
            raise ReferenceError("reference metadata is incomplete")
        if (not isinstance(item["length_nt"], int) or item["length_nt"] < 1 or
                not isinstance(item["record_count"], int) or item["record_count"] < 1 or
                not re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"]))):
            raise ReferenceError("reference metadata is invalid")
        result: dict[str, object] = {key: item[key] for key in required}
        for key in ("scope", "completeness", "molecule_type", "provenance",
                    "assembly_accession", "annotation_release"):
            if item.get(key) is not None:
                result[key] = item[key]
        return result

    def resolve(self, reference_ids: list[str]) -> list[Reference]:
        if len(set(reference_ids)) != len(reference_ids):
            raise ReferenceError("reference IDs must be unique")
        if not reference_ids:
            return []
        entries = {item["id"]: item for item in self._entries()}
        missing = [item for item in reference_ids if item not in entries]
        if missing:
            raise ReferenceError("unknown reference ID: " + ", ".join(missing))
        resolved = [self._resolve_one(entries[item]) for item in reference_ids]
        total_nt = sum(item.length_nt for item in resolved)
        if total_nt > MAX_SELECTED_REFERENCE_NT:
            raise ReferenceError(f"selected references exceed the {MAX_SELECTED_REFERENCE_NT:,} nt budget")
        return resolved

    def _entries(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ReferenceError("reference catalog is unavailable or invalid") from exc
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("references"), list):
            raise ReferenceError("unsupported reference catalog schema")
        items = data["references"]
        if not all(isinstance(item, dict) for item in items):
            raise ReferenceError("invalid reference catalog entry")
        identifiers = [item.get("id") for item in items]
        if any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", item) for item in identifiers):
            raise ReferenceError("invalid reference identity")
        if len(set(identifiers)) != len(identifiers):
            raise ReferenceError("duplicate reference identity")
        return items

    def _resolve_one(self, item: dict[str, Any]) -> Reference:
        required_text = ("id", "organism", "version", "source_uri", "license", "relative_path", "sha256")
        if any(not isinstance(item.get(key), str) or not item[key] for key in required_text):
            raise ReferenceError("reference metadata is incomplete")
        relative_path = Path(item["relative_path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ReferenceError("reference path must be relative and stay inside DATA_DIR/references")
        try:
            path = (self.root / relative_path).resolve(strict=True)
            path.relative_to(self.root)
        except (OSError, ValueError) as exc:
            raise ReferenceError("reference path is missing or escapes its catalog directory") from exc
        checksum, length, record_count = _validate_fasta_file(path, item["id"])
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) or checksum != item["sha256"]:
            raise ReferenceError("reference SHA-256 does not match the catalog")
        if not isinstance(item.get("length_nt"), int) or item["length_nt"] != length:
            raise ReferenceError("reference length does not match the catalog")
        if not isinstance(item.get("record_count"), int) or item["record_count"] != record_count:
            raise ReferenceError("reference record count does not match the catalog")
        return Reference(
            id=item["id"], organism=item["organism"], version=item["version"],
            source_uri=item["source_uri"], license=item["license"], sha256=checksum,
            length_nt=length, record_count=record_count, path=path,
            scope=item.get("scope", "unspecified"), molecule_type=item.get("molecule_type"),
            completeness=item.get("completeness"), provenance=item.get("provenance"),
            assembly_accession=item.get("assembly_accession"),
            annotation_release=item.get("annotation_release"),
        )


def _validate_fasta_file(path: Path, reference_id: str) -> tuple[str, int, int]:
    """Hash and validate FASTA one line at a time (bounded by the line size)."""
    digest = hashlib.sha256()
    total_length = record_count = current_length = 0
    seen_headers: set[str] = set()
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                digest.update(raw_line)
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith(b">"):
                    if record_count and current_length == 0:
                        raise ReferenceError("reference FASTA contains an empty sequence record")
                    try:
                        header = line[1:].decode("ascii").strip()
                    except UnicodeDecodeError as exc:
                        raise ReferenceError("reference FASTA headers must be ASCII") from exc
                    prefix, separator, _ = header.partition("|")
                    if not header or not separator or prefix != reference_id:
                        raise ReferenceError("FASTA headers must be prefixed with <reference_id>|")
                    if header in seen_headers:
                        raise ReferenceError("reference FASTA contains duplicate headers")
                    seen_headers.add(header)
                    record_count += 1
                    current_length = 0
                    continue
                if not record_count:
                    raise ReferenceError("reference sequence appeared before a header")
                sequence = line.upper()
                if sequence.translate(None, _ALLOWED_SEQUENCE_BYTES):
                    raise ReferenceError("reference FASTA contains an unsupported symbol")
                current_length += len(sequence)
                total_length += len(sequence)
    except OSError as exc:
        raise ReferenceError("reference FASTA cannot be read") from exc
    if not record_count or current_length == 0:
        raise ReferenceError("reference FASTA contains no sequences")
    return digest.hexdigest(), total_length, record_count


def read_sequences(reference: Reference) -> Iterator[tuple[str, str]]:
    """Yield FASTA records one at a time without materializing a transcriptome."""
    header: str | None = None
    chunks: list[str] = []
    try:
        with reference.path.open("rt", encoding="ascii") as handle:
            for raw_line in handle:
                value = raw_line.strip()
                if not value:
                    continue
                if value.startswith(">"):
                    if header is not None:
                        yield header, "".join(chunks)
                    header = value[1:].strip()
                    chunks = []
                else:
                    chunks.append(value.upper())
    except (OSError, UnicodeError) as exc:
        raise ReferenceError("reference FASTA cannot be reopened") from exc
    if header is not None:
        yield header, "".join(chunks)
