"""
Degradacion del registro de corte en un dsRNA quimerico.

Modelo
------
El dsRNA tiene N unidades contiguas de 21 pb. Dicer arranca en un extremo y
corta procesivamente. Las longitudes de paso S_1, S_2, ... son iid:

    P(S = 21) = 1 - eps        (corte "correcto", DCL4)
    P(S = 22) = eps * p22      (DCL2)
    P(S = 24) = eps * (1-p22)  (DCL3)

La fase acumulada tras k cortes es Phi_k = (S_1 + ... + S_k) mod 21, un paseo
al azar sobre Z/21Z con incrementos 0, 1, 3 (= 21, 22, 24 mod 21).

El k-esimo producto coincide con una unidad disenada si y solo si
    Phi_{k-1} = 0   y   S_k = 21,
de modo que

    w_k = P(unidad k utilizable) = (1 - eps) * P(Phi_{k-1} = 0).

P(Phi_k = 0) se calcula exacto por Fourier discreta sobre Z/21Z: la matriz de
transicion es circulante, con autovalores

    psi(j) = (1-eps) + eps*p22*omega^j + eps*(1-p22)*omega^{3j},   omega = e^{2*pi*i/21}

y entonces  P(Phi_k = 0) = (1/21) * sum_j psi(j)^k.

Nota: P(Phi_k = 0) -> 1/21, no a 0. Una fraccion 1/21 de los cortes cae en
fase por azar aun con la fase completamente perdida.
"""

import numpy as np

M = 21


def psi(eps, p22=0.5):
    """Autovalores de la matriz de transicion (circulante) sobre Z/21Z."""
    j = np.arange(M)
    w = np.exp(2j * np.pi * j / M)
    return (1 - eps) + eps * p22 * w + eps * (1 - p22) * w**3


def p_fase_cero(k, eps, p22=0.5):
    """P(Phi_k = 0) exacto."""
    return np.real(np.mean(psi(eps, p22) ** k))


def rendimiento_un_extremo(N, eps, p22=0.5):
    """w_k para k = 1..N, corte iniciado en un solo extremo."""
    return np.array([(1 - eps) * p_fase_cero(k - 1, eps, p22) for k in range(1, N + 1)])


def rendimiento_dos_extremos(N, eps, p22=0.5, f=0.5):
    """
    Mezcla de moleculas: una fraccion f inicia en el extremo izquierdo y
    1-f en el derecho. La posicion j rinde el promedio ponderado.
    """
    w = rendimiento_un_extremo(N, eps, p22)
    return f * w + (1 - f) * w[::-1]


def longitud_util(eps, p22=0.5, umbral=0.5):
    """Primera posicion cuyo rendimiento cae por debajo de umbral*w_1."""
    w = rendimiento_un_extremo(200, eps, p22)
    bajo = np.where(w < umbral * w[0])[0]
    return int(bajo[0] + 1) if len(bajo) else None


def tasa_decaimiento(eps, p22=0.5):
    """Modulo del autovalor subdominante: gobierna la velocidad de perdida."""
    return float(np.max(np.abs(psi(eps, p22)[1:])))


if __name__ == "__main__":
    N = 15  # quimera de 315 pb

    print(f"Quimera de N = {N} unidades (= {N*21} pb)\n")

    print("Rendimiento en fase por posicion, corte desde UN extremo")
    print("pos  " + "  ".join(f"e={e:.2f}" for e in (0.02, 0.05, 0.10, 0.20)))
    tablas = {e: rendimiento_un_extremo(N, e) for e in (0.02, 0.05, 0.10, 0.20)}
    for k in range(N):
        fila = "  ".join(f"{tablas[e][k]:6.3f}" for e in (0.02, 0.05, 0.10, 0.20))
        print(f"{k+1:3d}   {fila}")

    print("\nRendimiento en fase por posicion, corte desde LOS DOS extremos")
    print("pos  " + "  ".join(f"e={e:.2f}" for e in (0.02, 0.05, 0.10, 0.20)))
    tablas2 = {e: rendimiento_dos_extremos(N, e) for e in (0.02, 0.05, 0.10, 0.20)}
    for k in range(N):
        fila = "  ".join(f"{tablas2[e][k]:6.3f}" for e in (0.02, 0.05, 0.10, 0.20))
        print(f"{k+1:3d}   {fila}")

    print("\nResumen por valor de eps")
    print("eps    |psi_sub|   L_util   rend.medio(N=15)   rend.pos15/pos1")
    for e in (0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30):
        w = rendimiento_un_extremo(N, e)
        Lu = longitud_util(e)
        print(
            f"{e:.2f}   {tasa_decaimiento(e):.4f}     "
            f"{Lu if Lu else '>200':>4}      {w.mean():.3f}              {w[-1]/w[0]:.3f}"
        )

    print("\nControl: convergencia a 1/21 =", round(1 / M, 4))
    for e in (0.05, 0.20):
        print(f"  eps={e:.2f}:  P(Phi_200=0) = {p_fase_cero(200, e):.4f}")

    # chequeo por simulacion
    rng = np.random.default_rng(0)
    e = 0.10
    sim = rng.choice([0, 1, 3], size=(200_000, N), p=[1 - e, e / 2, e / 2])
    fase = np.cumsum(sim, axis=1) % M
    emp = [(sim[:, 0] == 0).mean()] + [
        ((fase[:, k - 1] == 0) & (sim[:, k] == 0)).mean() for k in range(1, N)
    ]
    exact = rendimiento_un_extremo(N, e)
    print(f"\nChequeo Monte Carlo (eps=0.10), max |exacto - simulado| = "
          f"{np.max(np.abs(np.array(emp) - exact)):.4f}")
