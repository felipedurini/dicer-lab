import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fase import rendimiento_un_extremo, rendimiento_dos_extremos

N = 15
pos = np.arange(1, N + 1)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

for e, c in zip((0.02, 0.05, 0.10, 0.20), ("#1D9E75", "#378ADD", "#BA7517", "#D85A30")):
    axes[0].plot(pos, rendimiento_un_extremo(N, e), "o-", color=c, ms=4, label=f"ε = {e:.0%}")
axes[0].set_title("Corte desde un extremo", fontsize=11)

for e, c in zip((0.02, 0.05, 0.10, 0.20), ("#1D9E75", "#378ADD", "#BA7517", "#D85A30")):
    axes[1].plot(pos, rendimiento_dos_extremos(N, e), "o-", color=c, ms=4, label=f"ε = {e:.0%}")
axes[1].set_title("Corte desde los dos extremos", fontsize=11)

for ax in axes:
    ax.axhline(1/21, ls=":", color="#888780", lw=1)
    ax.set_xlabel("Posición de la unidad en la quimera")
    ax.set_ylim(0, 1)
    ax.set_xticks(pos)
    ax.grid(alpha=0.25, lw=0.6)
    ax.legend(fontsize=8, frameon=False)
axes[0].set_ylabel("P(la unidad sale en fase)")
axes[1].text(12.2, 1/21 + 0.035, "piso 1/21", fontsize=8, color="#5F5E5A")

fig.suptitle("Rendimiento en fase por posición — quimera de 15 unidades (315 pb)", fontsize=12)
fig.tight_layout()
fig.savefig(pathlib.Path(__file__).resolve().parent.parent / "figuras" / "rendimiento_en_fase.png", dpi=190)
print("ok")
