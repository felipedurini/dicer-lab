"""Tipos de dominio y validaciones geométricas básicas."""

from dataclasses import dataclass
import math
from numbers import Real


def _require_integer(name: str, value: object) -> int:
    """Valida un entero de coordenadas y excluye bool, que es subclase de int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} debe ser un entero")
    return value


@dataclass(frozen=True)
class Segment:
    """Tramo objetivo semiabierto `[start, end)` de un gen."""

    segment_id: str
    gene_id: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not isinstance(self.gene_id, str):
            raise TypeError("segment_id y gene_id deben ser cadenas")
        if not self.segment_id or not self.gene_id:
            raise ValueError("segment_id y gene_id no pueden estar vacíos")
        start = _require_integer("start", self.start)
        end = _require_integer("end", self.end)
        if start < 0:
            raise ValueError("start no puede ser negativo")
        if end <= start:
            raise ValueError("un tramo debe cumplir end > start")


@dataclass(frozen=True)
class Construct:
    """Eje nucleotídico `[0, length_nt)` particionado en tramos contiguos."""

    length_nt: int
    segments: tuple[Segment, ...]
    phase_origin_nt: int = 0

    def __post_init__(self) -> None:
        length = _require_integer("length_nt", self.length_nt)
        origin = _require_integer("phase_origin_nt", self.phase_origin_nt)
        if length <= 0:
            raise ValueError("length_nt debe ser positivo")
        if not 0 <= origin < 21:
            raise ValueError("phase_origin_nt debe estar entre 0 y 20")
        if not isinstance(self.segments, tuple):
            raise TypeError("segments debe ser una tupla inmutable")

        cursor = 0
        seen_ids: set[str] = set()
        for segment in self.segments:
            if not isinstance(segment, Segment):
                raise TypeError("cada elemento de segments debe ser un Segment")
            if segment.segment_id in seen_ids:
                raise ValueError(f"segment_id duplicado: {segment.segment_id!r}")
            seen_ids.add(segment.segment_id)
            if segment.start != cursor:
                raise ValueError(
                    "segments debe particionar el constructo en orden, "
                    f"sin huecos ni solapamientos (se esperaba start={cursor})"
                )
            if segment.end > length:
                raise ValueError("ningún tramo puede exceder length_nt")
            cursor = segment.end

        if cursor != length:
            raise ValueError("segments debe cubrir el constructo completo")


@dataclass(frozen=True)
class Product:
    """Producto emitido; su longitud siempre se deriva de sus coordenadas."""

    cut_index: int
    start: int
    end: int
    remaining_before: int

    def __post_init__(self) -> None:
        cut_index = _require_integer("cut_index", self.cut_index)
        start = _require_integer("start", self.start)
        end = _require_integer("end", self.end)
        remaining = _require_integer("remaining_before", self.remaining_before)
        if cut_index < 1:
            raise ValueError("cut_index empieza en 1")
        if start < 0 or end <= start:
            raise ValueError("un producto debe tener coordenadas no negativas y end > start")
        if end - start not in (21, 22, 24):
            raise ValueError("la longitud de un producto debe ser 21, 22 o 24 nt")
        if remaining < end - start:
            raise ValueError("remaining_before no puede ser menor que el producto emitido")

    @property
    def length_nt(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class TerminalRemainder:
    """Sustrato no procesado al terminar una trayectoria."""

    start: int
    end: int
    reason: str
    proposed_length: int | None = None

    def __post_init__(self) -> None:
        start = _require_integer("start", self.start)
        end = _require_integer("end", self.end)
        if start < 0 or end < start:
            raise ValueError("el remanente debe tener coordenadas válidas")
        if self.reason not in (
            "exhausted",
            "shorter_than_min",
            "proposal_exceeds_remaining",
        ):
            raise ValueError(f"motivo terminal desconocido: {self.reason!r}")

        length = end - start
        if self.reason == "exhausted":
            if length != 0 or self.proposed_length is not None:
                raise ValueError("exhausted requiere remanente vacío y ninguna propuesta")
        elif self.reason == "shorter_than_min":
            if not 0 < length < 21 or self.proposed_length is not None:
                raise ValueError("shorter_than_min requiere un remanente de 1 a 20 nt")
        else:
            proposed = _require_integer("proposed_length", self.proposed_length)
            if proposed not in (21, 22, 24) or not 21 <= length < proposed:
                raise ValueError("la propuesta fallida debe exceder un remanente de 21 a 23 nt")

    @property
    def length_nt(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class MoleculeResult:
    """Productos en orden de generación y un único sentido de procesamiento."""

    direction: str
    products: tuple[Product, ...]
    remainder: TerminalRemainder

    def __post_init__(self) -> None:
        if self.direction not in ("left", "right"):
            raise ValueError("direction debe ser 'left' o 'right'")
        if not isinstance(self.products, tuple):
            raise TypeError("products debe ser una tupla inmutable")
        for index, product in enumerate(self.products, start=1):
            if not isinstance(product, Product):
                raise TypeError("cada producto debe ser Product")
            if product.cut_index != index:
                raise ValueError("cut_index debe seguir el orden de generación empezando en 1")
        if not isinstance(self.remainder, TerminalRemainder):
            raise TypeError("remainder debe ser TerminalRemainder")


@dataclass(frozen=True)
class RunConfig:
    """Parámetros de tamaño, semilla y mezcla de extremos de una corrida."""

    n_molecules: int
    seed: int
    f_left: float = 1.0

    def __post_init__(self) -> None:
        n_molecules = _require_integer("n_molecules", self.n_molecules)
        seed = _require_integer("seed", self.seed)
        if n_molecules <= 0:
            raise ValueError("n_molecules debe ser positivo")
        if seed < 0:
            raise ValueError("seed debe ser no negativo")
        if isinstance(self.f_left, bool) or not isinstance(self.f_left, Real):
            raise TypeError("f_left debe ser un número real")
        f_left = float(self.f_left)
        if not math.isfinite(f_left) or not 0.0 <= f_left <= 1.0:
            raise ValueError("f_left debe ser finito y estar entre 0 y 1")
        object.__setattr__(self, "f_left", f_left)
