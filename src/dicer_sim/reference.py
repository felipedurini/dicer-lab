"""Adaptadores a las funciones de referencia del paseo estacionario existente."""

from numbers import Real

from .models import ConstantEpsilon, EpsilonCutModel
from .domain import _require_integer
from src.fase import p_fase_cero, rendimiento_un_extremo


def stationary_prefix_reference(
    K: int,
    epsilon: float,
    p22: float = 0.5,
    *,
    length_nt: int,
) -> dict[str, object]:
    """Devuelve Fourier para un prefijo de K cortes garantizados del modelo constante."""
    K = _require_integer("K", K)
    if K <= 0:
        raise ValueError("K debe ser positivo")
    length_nt = _require_integer("length_nt", length_nt)
    if length_nt < 24 * K:
        raise ValueError("length_nt debe ser al menos 24*K para garantizar el prefijo")
    if isinstance(epsilon, bool) or not isinstance(epsilon, Real):
        raise TypeError("epsilon debe ser un valor constante de tipo real")
    epsilon = float(epsilon)
    if not isinstance(p22, Real) or isinstance(p22, bool):
        raise TypeError("p22 debe ser un número real")
    p22 = float(p22)

    model = EpsilonCutModel(ConstantEpsilon(epsilon), p22=p22)
    # Validar también los parámetros constantes del modelo antes de consultar Fourier.
    model.probabilities(length_nt)
    return {
        "cut_indices": tuple(range(1, K + 1)),
        "phase_zero_after": tuple(
            float(p_fase_cero(k, epsilon, p22)) for k in range(1, K + 1)
        ),
        "aligned21_relative": tuple(
            float(value)
            for value in rendimiento_un_extremo(K, epsilon, p22)
        ),
        "epsilon": epsilon,
        "p22": p22,
        "n_guaranteed_cuts": K,
        "guaranteed_length_nt": length_nt,
        "denominator": "all_molecules",
        "phase_origin": "initiating_end",
    }
