"""Contratos HTTP v1; la geometría ejecutable se valida además en el dominio."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from src.dicer_sim.domain import Construct, Segment


Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def _json_number(value: object) -> float:
    """Acepta números JSON, convierte enteros exactamente y rechaza bool/texto."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("debe ser un número JSON")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("debe ser finito")
    return result


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SegmentInput(StrictModel):
    segment_id: Id
    gene_id: Id
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)


class ConstructInput(StrictModel):
    length_nt: int = Field(ge=1, le=5000, strict=True)
    phase_origin_nt: int = Field(default=0, ge=0, le=20, strict=True)
    segments: list[SegmentInput] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def complete_partition(self) -> ConstructInput:
        cursor = 0
        seen: set[str] = set()
        for segment in self.segments:
            if segment.segment_id in seen:
                raise ValueError("segment_id debe ser único")
            seen.add(segment.segment_id)
            if segment.start != cursor or segment.end <= segment.start:
                raise ValueError("segments debe ser una partición ordenada y contigua desde 0")
            if segment.end > self.length_nt:
                raise ValueError("un segmento excede length_nt")
            cursor = segment.end
        if cursor != self.length_nt:
            raise ValueError("segments debe cubrir length_nt completo")
        return self

    def to_domain(self) -> Construct:
        return Construct(
            length_nt=self.length_nt,
            phase_origin_nt=self.phase_origin_nt,
            segments=tuple(
                Segment(item.segment_id, item.gene_id, item.start, item.end)
                for item in self.segments
            ),
        )


class ConstantEpsilonInput(StrictModel):
    type: Literal["constant"]
    schema_version: Literal[1]
    epsilon: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]

    @field_validator("epsilon", mode="before")
    @classmethod
    def parse_number(cls, value: object) -> float:
        return _json_number(value)


class PiecewiseEpsilonInput(StrictModel):
    type: Literal["piecewise"]
    schema_version: Literal[1]
    breakpoints: list[int] = Field(max_length=16)
    values: list[Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]]

    @field_validator("values", mode="before")
    @classmethod
    def parse_values(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            raise ValueError("values debe ser una secuencia numérica")
        return [_json_number(item) for item in value]

    @model_validator(mode="after")
    def validate_policy(self) -> PiecewiseEpsilonInput:
        if len(self.values) != len(self.breakpoints) + 1:
            raise ValueError("values debe tener un elemento más que breakpoints")
        previous = 0
        for breakpoint in self.breakpoints:
            if breakpoint <= previous or breakpoint > 5000:
                raise ValueError("breakpoints deben ser crecientes, positivos y <= 5000")
            previous = breakpoint
        return self


class EndpointEpsilonInput(StrictModel):
    schema_version: Literal[1]
    epsilon_start: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    epsilon_end: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]

    @field_validator("epsilon_start", "epsilon_end", mode="before")
    @classmethod
    def parse_endpoints(cls, value: object) -> float:
        return _json_number(value)


class LinearEpsilonInput(EndpointEpsilonInput):
    type: Literal["linear"]


class QuadraticEpsilonInput(EndpointEpsilonInput):
    type: Literal["quadratic"]
    curvature: Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)] = 0.5

    @field_validator("curvature", mode="before")
    @classmethod
    def parse_curvature(cls, value: object) -> float:
        return _json_number(value)


class ExponentialEpsilonInput(EndpointEpsilonInput):
    type: Literal["exponential"]
    rate: Annotated[float, Field(ge=-20, le=20, allow_inf_nan=False)] = 2.0

    @field_validator("rate", mode="before")
    @classmethod
    def parse_rate(cls, value: object) -> float:
        return _json_number(value)


class CustomEpsilonInput(StrictModel):
    type: Literal["custom"]
    schema_version: Literal[1]
    expression: str = Field(min_length=1, max_length=256)
    parameters: dict[str, Annotated[float, Field(allow_inf_nan=False)]] = Field(max_length=16)

    @field_validator("parameters", mode="before")
    @classmethod
    def parse_parameters(cls, value: object) -> object:
        if not isinstance(value, dict):
            raise ValueError("parameters debe ser un objeto")
        return {key: _json_number(item) for key, item in value.items()}


EpsilonInput = Annotated[
    ConstantEpsilonInput | PiecewiseEpsilonInput | LinearEpsilonInput |
    QuadraticEpsilonInput | ExponentialEpsilonInput | CustomEpsilonInput,
    Field(discriminator="type"),
]


class PreviewRequest(StrictModel):
    web_schema_version: Literal[1]
    construct_config: ConstructInput = Field(
        validation_alias=AliasChoices("construct", "construct_config"),
        serialization_alias="construct",
    )
    p22: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    f_left: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    seed: int = Field(ge=0, le=4_294_967_295, strict=True)
    epsilon: EpsilonInput

    @field_validator("p22", "f_left", mode="before")
    @classmethod
    def parse_probabilities(cls, value: object) -> float:
        return _json_number(value)

    @model_validator(mode="after")
    def validate_epsilon_domain(self) -> PreviewRequest:
        validate_epsilon_domain(epsilon_policy(self.epsilon), self.construct_config.length_nt)
        return self

    def to_domain(self) -> Construct:
        return self.construct_config.to_domain()

    def to_model(self):
        from src.dicer_sim.models import EpsilonCutModel

        policy = epsilon_policy(self.epsilon)
        validate_epsilon_domain(policy, self.construct_config.length_nt)
        return EpsilonCutModel(policy, self.p22)


class ScenarioInput(StrictModel):
    id: Id
    label: Label
    seed: int = Field(ge=0, le=4_294_967_295, strict=True)
    epsilon: EpsilonInput


def epsilon_policy(value):
    from src.dicer_sim.models import (
        ConstantEpsilon, PiecewiseEpsilon, LinearEpsilon, QuadraticEpsilon,
        ExponentialEpsilon, CustomEpsilon,
    )
    if isinstance(value, ConstantEpsilonInput):
        return ConstantEpsilon(value.epsilon)
    if isinstance(value, PiecewiseEpsilonInput):
        return PiecewiseEpsilon(tuple(value.breakpoints), tuple(value.values))
    if isinstance(value, LinearEpsilonInput):
        return LinearEpsilon(value.epsilon_start, value.epsilon_end)
    if isinstance(value, QuadraticEpsilonInput):
        return QuadraticEpsilon(value.epsilon_start, value.epsilon_end, value.curvature)
    if isinstance(value, ExponentialEpsilonInput):
        return ExponentialEpsilon(value.epsilon_start, value.epsilon_end, value.rate)
    if isinstance(value, CustomEpsilonInput):
        return CustomEpsilon(value.expression, value.parameters)
    raise ValueError("política epsilon desconocida")


def validate_epsilon_domain(policy, length_nt: int) -> None:
    """Reject invalid epsilon anywhere it can be queried for this construct."""
    for remaining_nt in range(21, length_nt + 1):
        policy.value(remaining_nt, length_nt)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_by_name=True)

    web_schema_version: Literal[1]
    label: Label
    construct_config: ConstructInput = Field(
        validation_alias=AliasChoices("construct", "construct_config"),
        serialization_alias="construct",
    )
    n_molecules: int = Field(ge=1, le=100_000, strict=True)
    f_left: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    p22: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    scenarios: list[ScenarioInput] = Field(min_length=1, max_length=4)
    baseline_id: Id
    alpha_family: Literal[0.05]
    compute_exact: bool

    @field_validator("f_left", "p22", mode="before")
    @classmethod
    def parse_probabilities(cls, value: object) -> float:
        return _json_number(value)

    @model_validator(mode="after")
    def validate_scenario_family(self) -> JobRequest:
        ids = [scenario.id for scenario in self.scenarios]
        seeds = [scenario.seed for scenario in self.scenarios]
        if len(set(ids)) != len(ids):
            raise ValueError("scenario IDs deben ser únicos")
        if len(set(seeds)) != len(seeds):
            raise ValueError("cada escenario requiere una semilla distinta")
        by_id = {scenario.id: scenario for scenario in self.scenarios}
        baseline = by_id.get(self.baseline_id)
        if baseline is None:
            raise ValueError("baseline_id debe identificar un escenario del trabajo")
        if len(self.scenarios) > 1 and not isinstance(baseline.epsilon, ConstantEpsilonInput):
            raise ValueError("baseline_id debe señalar epsilon constante en una comparación")
        for scenario in self.scenarios:
            validate_epsilon_domain(epsilon_policy(scenario.epsilon), self.construct_config.length_nt)
        maximum_work = sum(
            self.n_molecules
            * max(1, self.construct_config.length_nt // 21)
            * len(self.construct_config.segments)
            for _scenario in self.scenarios
        )
        if maximum_work > 30_000_000:
            raise ValueError("el trabajo estimado supera el presupuesto de capabilities")
        if self.compute_exact and (
            self.construct_config.length_nt > 1000 or len(self.construct_config.segments) > 16
        ):
            raise ValueError("DP exacta requiere length_nt <= 1000 y hasta 16 segmentos")
        return self

    @property
    def estimated_work(self) -> int:
        return sum(
            self.n_molecules
            * max(1, self.construct_config.length_nt // 21)
            * len(self.construct_config.segments)
            for _scenario in self.scenarios
        )

    @property
    def baseline(self) -> ScenarioInput:
        return next(item for item in self.scenarios if item.id == self.baseline_id)

    @property
    def scenario_count(self) -> int:
        return len(self.scenarios)


@dataclass(frozen=True)
class ValidatedJob:
    request: JobRequest
    construct: Construct
    estimated_work: int
    baseline: ScenarioInput
    scenario_count: int


def validate_job_request(request: JobRequest) -> ValidatedJob:
    """Cruza DTO y dominio antes de persistir o encolar trabajo."""
    if not isinstance(request, JobRequest):
        raise TypeError("request debe ser JobRequest")
    construct = request.construct_config.to_domain()
    return ValidatedJob(
        request=request,
        construct=construct,
        estimated_work=request.estimated_work,
        baseline=request.baseline,
        scenario_count=request.scenario_count,
    )


class ErrorField(StrictModel):
    path: str
    message: str


class ErrorBody(StrictModel):
    code: str
    message: str
    fields: tuple[ErrorField, ...] = ()
    request_id: str
    retryable: bool


class ErrorEnvelope(StrictModel):
    error: ErrorBody


class TrajectorySource(StrictModel):
    kind: Literal["preview", "population_first"]
    molecule_index: Literal[1]
    population_size: int = Field(ge=1)


class TrajectoryRunConfig(StrictModel):
    n_molecules: Literal[1]
    seed: int = Field(ge=0, le=4_294_967_295)
    f_left: float = Field(ge=0, le=1, allow_inf_nan=False)


class TrajectoryConfiguration(StrictModel):
    construct_config: ConstructInput = Field(
        validation_alias=AliasChoices("construct", "construct_config"),
        serialization_alias="construct",
    )
    model: dict[str, object]
    run_config: TrajectoryRunConfig


class ProductAnnotationDTO(StrictModel):
    relative_phase_before: int = Field(ge=0, le=20)
    relative_phase_after: int = Field(ge=0, le=20)
    global_phase_before: int = Field(ge=0, le=20)
    aligned21_local: bool
    aligned21_global: bool
    contained_segment_id: str | None
    touching_segment_ids: list[str]
    crossed_segment_boundaries: list[int]
    crossed_gene_boundaries: list[int]
    overlap_nt_by_segment: list[dict[str, int | str]]


class CutEventDTO(StrictModel):
    kind: Literal["cut"]
    cut_index: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    length_nt: Literal[21, 22, 24]
    remaining_before: int = Field(ge=21)
    remaining_after: int = Field(ge=0)
    epsilon_before: float = Field(ge=0, le=1, allow_inf_nan=False)
    probabilities_before: dict[Literal["21", "22", "24"], float]
    contained_gene_id: str | None
    touching_gene_ids: list[str]
    annotation: ProductAnnotationDTO


class TerminalEventDTO(StrictModel):
    kind: Literal["terminal"]
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    length_nt: int = Field(ge=0, le=23)
    reason: Literal["exhausted", "shorter_than_min", "proposal_exceeds_remaining"]
    proposed_length: Literal[21, 22, 24] | None
    remaining_before: int = Field(ge=0)
    epsilon_before: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    probabilities_before: dict[Literal["21", "22", "24"], float] | None


TrajectoryEventDTO = Annotated[
    CutEventDTO | TerminalEventDTO,
    Field(discriminator="kind"),
]


class RemainderDTO(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    length_nt: int = Field(ge=0, le=23)
    reason: Literal["exhausted", "shorter_than_min", "proposal_exceeds_remaining"]
    proposed_length: Literal[21, 22, 24] | None


class ScientificProvenanceDTO(StrictModel):
    python: str
    numpy: str
    rng: Literal["numpy.random.Generator(PCG64)"]
    terminal_rule: Literal["stop_on_overshoot_v1"]
    engine_sha256: dict[str, str]


class TrajectoryDTO(StrictModel):
    web_schema_version: Literal[1]
    source: TrajectorySource
    config: TrajectoryConfiguration
    direction: Literal["left", "right"]
    events: list[TrajectoryEventDTO]
    remainder: RemainderDTO
    scientific_provenance: ScientificProvenanceDTO
    trajectory_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
