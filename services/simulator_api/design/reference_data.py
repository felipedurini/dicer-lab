"""Seed bundled, versioned FASTA assets into the persistent DATA_DIR reference store."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .references import ReferenceError


def bootstrap_references(references_dir: Path | str, *, assets_dir: Path | str | None = None) -> list[str]:
    """Install bundled references once and merge metadata without dropping user imports.

    The compressed source ships with the API image. Expanded FASTA and the active
    catalog live under DATA_DIR/references, which must be mounted persistently in
    production. Existing files are verified, never silently replaced.
    """
    root = Path(references_dir).resolve()
    assets = Path(assets_dir) if assets_dir is not None else Path(__file__).resolve().parents[1] / "reference_data"
    root.mkdir(parents=True, exist_ok=True)
    try:
        manifest = json.loads((assets / "catalog.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1 or not isinstance(manifest.get("references"), list):
            raise ReferenceError("unsupported bundled reference catalog schema")
        bundled = manifest["references"]
        current_path = root / "catalog.json"
        current = json.loads(current_path.read_text(encoding="utf-8")) if current_path.exists() else {"schema_version": 1, "references": []}
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise ReferenceError("bundled or persistent reference catalog is unavailable or invalid") from exc
    if not isinstance(current, dict) or current.get("schema_version") != 1 or not isinstance(current.get("references"), list):
        raise ReferenceError("unsupported persistent reference catalog schema")
    entries = current["references"]
    if not all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in entries):
        raise ReferenceError("persistent reference catalog has malformed entries")
    existing = {item["id"]: item for item in entries}
    installed: list[str] = []
    for item in bundled:
        if not isinstance(item, dict):
            raise ReferenceError("bundled reference entry is malformed")
        required = ("id", "relative_path", "sha256", "length_nt", "record_count", "asset_relative_path", "asset_sha256")
        if any(key not in item for key in required):
            raise ReferenceError("bundled reference metadata is incomplete")
        asset_rel = Path(item["asset_relative_path"])
        if asset_rel.is_absolute() or ".." in asset_rel.parts:
            raise ReferenceError("bundled reference asset path escapes the image")
        source = (assets / asset_rel).resolve(strict=True)
        source.relative_to(assets.resolve())
        relative = Path(item["relative_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ReferenceError("bundled reference destination escapes DATA_DIR")
        destination = (root / relative).resolve()
        destination.relative_to(root)
        if destination.exists():
            checksum, _, _ = _validate_bundled_fasta(destination, item["id"])
            if checksum != item["sha256"]:
                raise ReferenceError(f"persistent FASTA checksum differs from bundled version for {item['id']}")
        else:
            if _sha256(source) != item["asset_sha256"]:
                raise ReferenceError(f"bundled source archive checksum failed for {item['id']}")
            if item.get("asset_md5") and _md5(source) != item["asset_md5"]:
                raise ReferenceError(f"NCBI source checksum failed for {item['id']}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            _expand_archive(source, destination, item["id"])
            checksum, length_nt, record_count = _validate_bundled_fasta(destination, item["id"])
            if (checksum, length_nt, record_count) != (item["sha256"], item["length_nt"], item["record_count"]):
                destination.unlink(missing_ok=True)
                raise ReferenceError(f"expanded FASTA metadata/checksum differs from manifest for {item['id']}")
        prior = existing.get(item["id"])
        if prior is not None and prior.get("sha256") != item["sha256"]:
            raise ReferenceError(f"reference ID {item['id']} is already registered with different sequence data")
        if prior != item:
            if prior is not None:
                entries[entries.index(prior)] = item
            else:
                entries.append(item)
                existing[item["id"]] = item
            installed.append(item["id"])
    if installed or not current_path.exists():
        _atomic_write(current_path, (json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    return installed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expand_archive(source: Path, destination: Path, reference_id: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output, gzip.open(source, "rb") as compressed:
            for raw_line in compressed:
                if raw_line.startswith(b">"):
                    try:
                        source_header = raw_line[1:].decode("ascii").strip()
                    except UnicodeDecodeError as exc:
                        raise ReferenceError("NCBI FASTA header is not ASCII") from exc
                    if not source_header or "\n" in source_header or "\r" in source_header:
                        raise ReferenceError("NCBI FASTA contains an invalid header")
                    output.write(f">{reference_id}|{source_header}\n".encode("ascii"))
                else:
                    sequence = b"".join(raw_line.split()).upper()
                    if sequence:
                        output.write(sequence + b"\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, destination)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _validate_bundled_fasta(path: Path, reference_id: str) -> tuple[str, int, int]:
    # Local import avoids exposing private validation as part of the public API.
    from .references import _validate_fasta_file

    return _validate_fasta_file(path, reference_id)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
