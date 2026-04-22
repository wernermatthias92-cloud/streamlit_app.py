import numpy as np
from scipy.optimize import least_squares
import math

RHO = 1000  # kg/m³

# -----------------------------
# Rohrmodell
# -----------------------------
def pipe_k(d, L, zeta=0.0):
    return (8 * RHO / (math.pi**2 * d**4)) * (0.02 * L / d + zeta)


# -----------------------------
# Membranmodell
# -----------------------------
class Membrane:
    def __init__(self, A, area, tds):
        self.A = A
        self.area = area
        self.tds = tds

    def osmotic_pressure(self):
        return 0.008 * self.tds  # bar

    def permeate_flow(self, p_feed, p_perm):
        pi = self.osmotic_pressure()
        ndp = max(p_feed - p_perm - pi, 0)
        return self.A * self.area * ndp


# -----------------------------
# Solver
# -----------------------------
def solve_parallel(
    n,
    p_feed,
    p_perm,
    membranes,
    k_in,
    k_out,
    k_drossel=None,
    target_recovery=None
):
    if k_drossel is None:
        k_drossel = [0.0] * n

    x0 = np.ones(n) * 1e-4

    def residuals(Qf_vec):
        res = []
        Qp_total = 0
        Qf_total = 0

        for i in range(n):
            Qf = Qf_vec[i]

            p_in = p_feed - k_in[i] * Qf * abs(Qf)

            Qp = membranes[i].permeate_flow(p_in, p_perm)
            Qc = Qf - Qp

            p_out = (k_out[i] + k_drossel[i]) * Qc * abs(Qc)

            res.append(p_in - p_out - 1e5)

            Qp_total += Qp
            Qf_total += Qf

        if target_recovery is not None:
            res.append(Qp_total / max(Qf_total, 1e-9) - target_recovery)

        return res

    sol = least_squares(residuals, x0)

    Qf_vec = sol.x

    results = []
    Qp_total = 0
    Qf_total = 0

    for i in range(n):
        Qf = Qf_vec[i]
        p_in = p_feed - k_in[i] * Qf * abs(Qf)

        Qp = membranes[i].permeate_flow(p_in, p_perm)
        Qc = Qf - Qp

        results.append({
            "Qf": Qf,
            "Qp": Qp,
            "Qc": Qc,
            "p_in": p_in
        })

        Qp_total += Qp
        Qf_total += Qf

    return {
        "streams": results,
        "Qp_total": Qp_total,
        "Qf_total": Qf_total,
        "recovery": Qp_total / max(Qf_total, 1e-9)
    }
