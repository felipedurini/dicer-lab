"""Políticas de epsilon y distribución de longitudes de corte."""

from dataclasses import dataclass, field
from bisect import bisect_right
import ast
import math
from numbers import Real
import inspect
from functools import lru_cache
import keyword
from types import MappingProxyType
from typing import Protocol


def _probability(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} debe ser un número real")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{name} debe ser finito y estar entre 0 y 1")
    return numeric


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} debe ser un entero")
    return value


def _remaining_length(value: object) -> int:
    value = _integer("remaining_nt", value)
    if value <= 0:
        raise ValueError("remaining_nt debe ser positivo")
    return value


class EpsilonPolicy(Protocol):
    """Política determinista para la fracción de cortes distintos de 21 nt."""

    def value(self, remaining_nt: int, initial_nt: int | None = None) -> float: ...

    def describe(self) -> dict[str, object]: ...


class CutModel(Protocol):
    """Núcleo probabilístico con soporte fijo `(21, 22, 24)`."""

    def probabilities(self, remaining_nt: int, initial_nt: int | None = None) -> tuple[float, float, float]: ...

    def describe(self) -> dict[str, object]: ...


def validate_probabilities(probabilities: object) -> tuple[float, float, float]:
    """Comprueba un núcleo externo sin recortarlo ni renormalizarlo."""
    if isinstance(probabilities, (str, bytes)):
        raise TypeError("las probabilidades deben ser una secuencia de tres números")
    try:
        values = tuple(probabilities)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError("las probabilidades deben ser una secuencia de tres números") from exc
    if len(values) != 3:
        raise ValueError("el núcleo debe tener probabilidades para 21, 22 y 24 nt")
    validated = tuple(_probability(f"probabilidad[{index}]", value) for index, value in enumerate(values))
    if abs(math.fsum(validated) - 1.0) > 1e-12:
        raise ValueError("las probabilidades del núcleo deben sumar 1")
    return validated  # type: ignore[return-value]


@lru_cache(maxsize=None)
def _accepts_initial_length(policy_type: type) -> bool:
    try:
        inspect.signature(policy_type.value).bind(None, 1, 1)
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _policy_value(policy: EpsilonPolicy, remaining_nt: int, initial_nt: int | None) -> float:
    """Keep supporting pre-existing one-argument user policies."""
    if initial_nt is None:
        return policy.value(remaining_nt)
    if _accepts_initial_length(type(policy)):
        return policy.value(remaining_nt, initial_nt)
    return policy.value(remaining_nt)


@dataclass(frozen=True)
class ConstantEpsilon:
    """Fracción constante de cortes de 22 o 24 nt."""

    epsilon: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "epsilon", _probability("epsilon", self.epsilon))

    def value(self, remaining_nt: int, initial_nt: int | None = None) -> float:
        _remaining_length(remaining_nt)
        return self.epsilon

    def describe(self) -> dict[str, object]:
        return {"type": "constant", "schema_version": 1, "epsilon": self.epsilon}


@dataclass(frozen=True)
class PiecewiseEpsilon:
    """Política por tramos; cada umbral pertenece al intervalo que sigue.

    Para un umbral ``b``, ``remaining_nt == b`` selecciona el valor siguiente,
    de acuerdo con ``bisect_right``.
    """

    breakpoints: tuple[int, ...]
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.breakpoints, tuple) or not isinstance(self.values, tuple):
            raise TypeError("breakpoints y values deben ser tuplas inmutables")
        if len(self.values) != len(self.breakpoints) + 1:
            raise ValueError("values debe tener exactamente un elemento más que breakpoints")

        previous = 0
        for index, breakpoint in enumerate(self.breakpoints):
            _integer(f"breakpoints[{index}]", breakpoint)
            if breakpoint <= previous:
                raise ValueError("breakpoints deben ser positivos y estrictamente crecientes")
            previous = breakpoint

        validated_values = tuple(
            _probability(f"values[{index}]", value)
            for index, value in enumerate(self.values)
        )
        object.__setattr__(self, "values", validated_values)

    def value(self, remaining_nt: int, initial_nt: int | None = None) -> float:
        remaining_nt = _remaining_length(remaining_nt)
        return self.values[bisect_right(self.breakpoints, remaining_nt)]

    def describe(self) -> dict[str, object]:
        return {
            "type": "piecewise",
            "schema_version": 1,
            "breakpoints": list(self.breakpoints),
            "values": list(self.values),
        }


def _initial_length(remaining_nt: int, initial_nt: int | None) -> int:
    if initial_nt is None:
        return remaining_nt
    initial_nt = _remaining_length(initial_nt)
    if initial_nt < remaining_nt:
        raise ValueError("initial_nt no puede ser menor que remaining_nt")
    return initial_nt


@dataclass(frozen=True)
class LinearEpsilon:
    """Interpolación lineal entre epsilon_start (L=N) y epsilon_end (L=0)."""
    epsilon_start: float
    epsilon_end: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "epsilon_start", _probability("epsilon_start", self.epsilon_start))
        object.__setattr__(self, "epsilon_end", _probability("epsilon_end", self.epsilon_end))

    def value(self, remaining_nt: int, initial_nt: int | None = None) -> float:
        remaining_nt = _remaining_length(remaining_nt)
        initial_nt = _initial_length(remaining_nt, initial_nt)
        x = 1.0 - remaining_nt / initial_nt
        return _probability("epsilon(L)", self.epsilon_start + (self.epsilon_end - self.epsilon_start) * x)

    def describe(self) -> dict[str, object]:
        return {"type": "linear", "schema_version": 1, "epsilon_start": self.epsilon_start, "epsilon_end": self.epsilon_end}


@dataclass(frozen=True)
class QuadraticEpsilon:
    """Curva cuadrática normalizada entre valores inicial y final."""
    epsilon_start: float
    epsilon_end: float
    curvature: float = 0.5

    def __post_init__(self) -> None:
        object.__setattr__(self, "epsilon_start", _probability("epsilon_start", self.epsilon_start))
        object.__setattr__(self, "epsilon_end", _probability("epsilon_end", self.epsilon_end))
        if isinstance(self.curvature, bool) or not isinstance(self.curvature, Real):
            raise TypeError("curvature debe ser un número real")
        curvature = float(self.curvature)
        if not math.isfinite(curvature) or not -1.0 <= curvature <= 1.0:
            raise ValueError("curvature debe estar entre -1 y 1")
        object.__setattr__(self, "curvature", curvature)

    def value(self, remaining_nt: int, initial_nt: int | None = None) -> float:
        remaining_nt = _remaining_length(remaining_nt)
        initial_nt = _initial_length(remaining_nt, initial_nt)
        x = 1.0 - remaining_nt / initial_nt
        shaped = x + self.curvature * x * (1.0 - x)
        return _probability("epsilon(L)", self.epsilon_start + (self.epsilon_end - self.epsilon_start) * shaped)

    def describe(self) -> dict[str, object]:
        return {"type": "quadratic", "schema_version": 1, "epsilon_start": self.epsilon_start, "epsilon_end": self.epsilon_end, "curvature": self.curvature}


@dataclass(frozen=True)
class ExponentialEpsilon:
    """Interpolación exponencial normalizada; rate=0 equivale a lineal."""
    epsilon_start: float
    epsilon_end: float
    rate: float = 2.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "epsilon_start", _probability("epsilon_start", self.epsilon_start))
        object.__setattr__(self, "epsilon_end", _probability("epsilon_end", self.epsilon_end))
        if isinstance(self.rate, bool) or not isinstance(self.rate, Real):
            raise TypeError("rate debe ser un número real")
        rate = float(self.rate)
        if not math.isfinite(rate) or abs(rate) > 20:
            raise ValueError("rate debe ser finito y estar entre -20 y 20")
        object.__setattr__(self, "rate", rate)

    def value(self, remaining_nt: int, initial_nt: int | None = None) -> float:
        remaining_nt = _remaining_length(remaining_nt)
        initial_nt = _initial_length(remaining_nt, initial_nt)
        x = 1.0 - remaining_nt / initial_nt
        factor = x if self.rate == 0 else math.expm1(self.rate * x) / math.expm1(self.rate)
        return _probability("epsilon(L)", self.epsilon_start + (self.epsilon_end - self.epsilon_start) * factor)

    def describe(self) -> dict[str, object]:
        return {"type": "exponential", "schema_version": 1, "epsilon_start": self.epsilon_start, "epsilon_end": self.epsilon_end, "rate": self.rate}


_ALLOWED_FUNCTIONS = {"sqrt": math.sqrt, "exp": math.exp, "log": math.log, "abs": abs}
_ALLOWED_BINARY = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
                   ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
                   ast.Pow: lambda a, b: a ** b}


def _compile_expression(expression: str, parameter_names: set[str]):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 256:
        raise ValueError("La expresión debe tener entre 1 y 256 caracteres")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ValueError("La expresión matemática no es válida") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > 64:
        raise ValueError("La expresión es demasiado compleja")
    allowed_names = {"L", "N", *parameter_names}
    for node in nodes:
        if isinstance(node, ast.Expression | ast.Load):
            continue
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            continue
        if isinstance(node, ast.Name) and node.id in allowed_names | set(_ALLOWED_FUNCTIONS):
            continue
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINARY:
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCTIONS and len(node.args) == 1 and not node.keywords:
            continue
        if isinstance(node, ast.operator | ast.unaryop):
            continue
        raise ValueError("La expresión contiene una operación no permitida")
    return tree.body


def _interpret(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"Variable no disponible: {node.id}")
        return variables[node.id]
    if isinstance(node, ast.UnaryOp):
        value = _interpret(node.operand, variables)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _interpret(node.left, variables), _interpret(node.right, variables)
        if isinstance(node.op, ast.Pow) and abs(right) > 32:
            raise ValueError("El exponente debe estar entre -32 y 32")
        return _ALLOWED_BINARY[type(node.op)](left, right)
    if isinstance(node, ast.Call):
        return _ALLOWED_FUNCTIONS[node.func.id](_interpret(node.args[0], variables))
    raise ValueError("Operación no permitida")


@dataclass(frozen=True)
class CustomEpsilon:
    """Intérprete aritmético seguro; sólo admite operadores y funciones listados."""
    expression: str
    parameters: dict[str, float]
    _compiled: ast.AST = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, dict) or len(self.parameters) > 16:
            raise ValueError("parameters debe ser un mapa de hasta 16 parámetros")
        values = {}
        for name, value in self.parameters.items():
            if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name) or name in {"L", "N", *_ALLOWED_FUNCTIONS}:
                raise ValueError("Nombre de parámetro no permitido")
            if isinstance(value, bool) or not isinstance(value, Real):
                raise TypeError("Los parámetros deben ser números reales")
            values[name] = float(value)
            if not math.isfinite(values[name]):
                raise ValueError("Los parámetros deben ser finitos")
        object.__setattr__(self, "parameters", MappingProxyType(values))
        object.__setattr__(self, "expression", self.expression.strip() if isinstance(self.expression, str) else self.expression)
        object.__setattr__(self, "_compiled", _compile_expression(self.expression, set(values)))

    def value(self, remaining_nt: int, initial_nt: int | None = None) -> float:
        remaining_nt = _remaining_length(remaining_nt)
        initial_nt = _initial_length(remaining_nt, initial_nt)
        try:
            result = _interpret(self._compiled, {**self.parameters, "L": float(remaining_nt), "N": float(initial_nt)})
        except (ArithmeticError, OverflowError, ValueError) as exc:
            raise ValueError(f"No se pudo evaluar epsilon(L): {exc}") from exc
        return _probability("epsilon(L)", result)

    def describe(self) -> dict[str, object]:
        return {"type": "custom", "schema_version": 1, "expression": self.expression, "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class EpsilonCutModel:
    """Modelo `q=(1-epsilon, epsilon*p22, epsilon*(1-p22))`."""

    epsilon: EpsilonPolicy
    p22: float = 0.5

    def __post_init__(self) -> None:
        if not callable(getattr(self.epsilon, "value", None)):
            raise TypeError("epsilon debe implementar value(remaining_nt)")
        if not callable(getattr(self.epsilon, "describe", None)):
            raise TypeError("epsilon debe implementar describe()")
        object.__setattr__(self, "p22", _probability("p22", self.p22))

    def probabilities(self, remaining_nt: int, initial_nt: int | None = None) -> tuple[float, float, float]:
        remaining_nt = _remaining_length(remaining_nt)
        if initial_nt is not None:
            _initial_length(remaining_nt, initial_nt)
        epsilon = _probability("epsilon(L)", _policy_value(self.epsilon, remaining_nt, initial_nt))
        return validate_probabilities(
            (
                1.0 - epsilon,
                epsilon * self.p22,
                epsilon * (1.0 - self.p22),
            )
        )

    def epsilon_value(self, remaining_nt: int, initial_nt: int | None = None) -> float:
        remaining_nt = _remaining_length(remaining_nt)
        if initial_nt is not None:
            _initial_length(remaining_nt, initial_nt)
        return _probability("epsilon(L)", _policy_value(self.epsilon, remaining_nt, initial_nt))

    def describe(self) -> dict[str, object]:
        return {
            "type": "epsilon_cut_model",
            "schema_version": 1,
            "support_nt": [21, 22, 24],
            "epsilon": self.epsilon.describe(),
            "p22": self.p22,
        }
