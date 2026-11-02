"""Prepare a locally supplied FASTA as an immutable off-target catalog entry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


_ALLOWED = set("ACGTRYSWKMBDHVN")
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


def _parse(path: Path, reference_id: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    header: str | None = None
    sequence: list[str] = []
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("input FASTA must be a readable ASCII file") from exc
    for line in lines:
        value = line.strip()
        if not value:
            continue
        if value.startswith(">"):
            if header is not None:
                if not sequence:
                    raise ValueError(f"empty sequence in FASTA record {header!r}")
                records.append((header, "".join(sequence)))
            header = value[1:].strip()
            if not header:
                raise ValueError("FASTA headers must be nonempty")
            sequence = []
            continue
        if header is None:
            raise ValueError("sequence data occurred before the first FASTA header")
        normalized = value.upper().replace("U", "T")
        if any(base not in _ALLOWED for base in normalized):
            raise ValueError(f"unsupported sequence symbol in FASTA record {header!r}")
        sequence.append(normalized)
    if header is not None:
        if not sequence:
            raise ValueError(f"empty sequence in FASTA record {header!r}")
        records.append((header, "".join(sequence)))
    if not records:
        raise ValueError("input FASTA contains no records")
    normalized_headers = [f"{reference_id}|{header}" for header, _ in records]
    if len(set(normalized_headers)) != len(normalized_headers):
        raise ValueError("FASTA contains duplicate headers")
    return records


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def prepare_reference(reference_id: str, organism: str, version: str, source_uri: str,
                      license_name: str, input_fasta: Path, data_dir: Path) -> dict[str, object]:
    if not _ID.fullmatch(reference_id) or not _ID.fullmatch(version):
        raise ValueError("reference ID and version must be stable alphanumeric identifiers")
    if not all(value.strip() for value in (organism, source_uri, license_name)):
        raise ValueError("organism, source URI, and license are required")
    references_dir = data_dir.resolve() / "references"
    records = _parse(input_fasta, reference_id)
    relative_path = Path(reference_id) / f"{version}.fa"
    fasta = "".join(
        f">{reference_id}|{header}\n" + "\n".join(sequence[i:i + 80] for i in range(0, len(sequence), 80)) + "\n"
        for header, sequence in records
    ).encode("ascii")
    destination = references_dir / relative_path
    catalog_path = references_dir / "catalog.json"
    catalog = {"schema_version": 1, "references": []}
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("existing reference catalog is invalid") from exc
        if catalog.get("schema_version") != 1 or not isinstance(catalog.get("references"), list):
            raise ValueError("existing reference catalog schema is unsupported")
    if any(item.get("id") == reference_id for item in catalog["references"]):
        raise ValueError("reference ID is immutable; choose a new versioned reference ID")
    if destination.exists():
        raise ValueError("reference FASTA already exists; refusing to overwrite")
    entry = {
        "id": reference_id,
        "organism": organism.strip(),
        "version": version,
        "source_uri": source_uri.strip(),
        "license": license_name.strip(),
        "relative_path": relative_path.as_posix(),
        "sha256": hashlib.sha256(fasta).hexdigest(),
        "length_nt": sum(len(sequence) for _, sequence in records),
        "record_count": len(records),
    }
    catalog["references"].append(entry)
    _atomic_write(destination, fasta)
    try:
        _atomic_write(catalog_path, json.dumps(catalog, ensure_ascii=False, sort_keys=True,
                                               indent=2).encode("utf-8"))
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-id", required=True)
    parser.add_argument("--organism", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-uri", required=True)
    parser.add_argument("--license", dest="license_name", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_reference(args.reference_id, args.organism, args.version, args.source_uri,
                               args.license_name, args.input, args.data_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
