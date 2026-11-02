"""Strict v1 DTOs and input bounds for sequence-design jobs."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")]
SequenceRNA = Annotated[str, StringConstraints(min_length=21, max_length=20_000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_by_name=True)


class DesignTarget(StrictModel):
    gene_id: Id
    sequence_rna: SequenceRNA

    @field_validator("sequence_rna", mode="before")
    @classmethod
    def normalize_sequence(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("sequence_rna must be text")
        result = "".join(value.split()).upper().replace("T", "U")
        if len(result) < 21 or any(base not in "ACGU" for base in result):
            raise ValueError("sequence_rna requires at least 21 unambiguous A/C/G/U bases")
        return result

    @property
    def sequence_dna(self) -> str:
        return self.sequence_rna.replace("U", "T")


class BlockSpec(StrictModel):
    gene_id: Id
    length_nt: int = Field(ge=21, le=1000, strict=True)


class DesignRequest(StrictModel):
    design_schema_version: Literal[1]
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    targets: list[DesignTarget] = Field(min_length=2, max_length=8)
    blocks: list[BlockSpec] = Field(min_length=2, max_length=8)
    reference_ids: list[Id] = Field(max_length=8)
    seed: int = Field(ge=0, le=2**31 - 1, strict=True)
    lambda_value: int = Field(alias="lambda", ge=0, le=1, strict=True)
    thermo_profile: Literal["lucid_end3_v1"]
    iterations: int = Field(default=100, ge=1, le=100, strict=True)

    @model_validator(mode="after")
    def validate_design(self) -> DesignRequest:
        target_ids = [item.gene_id for item in self.targets]
        block_ids = [item.gene_id for item in self.blocks]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("target gene_id values must be unique")
        if len(set(block_ids)) != len(block_ids) or set(block_ids) != set(target_ids):
            raise ValueError("blocks must assign exactly one length to every target gene")
        if len(set(self.reference_ids)) != len(self.reference_ids):
            raise ValueError("reference_ids must be unique")
        if sum(len(item.sequence_rna) for item in self.targets) > 20_000:
            raise ValueError("total target sequence exceeds 20,000 nt")
        if sum(item.length_nt for item in self.blocks) > 1000:
            raise ValueError("total construct length exceeds 1,000 nt")
        target_lengths = {item.gene_id: len(item.sequence_rna) for item in self.targets}
        if any(item.length_nt > target_lengths[item.gene_id] for item in self.blocks):
            raise ValueError("each block length must fit its target sequence")
        return self

    @property
    def total_construct_length(self) -> int:
        return sum(item.length_nt for item in self.blocks)


def validate_fasta_reference_id(value: str) -> bool:
    """Shared catalog validation for untrusted path-independent identifiers."""
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", value))
