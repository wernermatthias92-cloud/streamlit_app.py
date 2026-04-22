import numpy as np
from scipy.optimize import least_squares
import math

RHO = 1000  # kg/m³

# -----------------------------
# Rohrwiderstand
# -----------------------------
def pipe_k(d, L, zeta=0.0):
    A = math.pi * d**2 / 4
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
        return 0.008 * self.tds  # bar (empirisch verbessert)

    def permeate_flow(self, p_feed, p_perm):
        pi = self.osmotic_pressure()
        ndp = max(p_feed - p_perm - pi, 0)
        return self.A * self.area * ndp


# -----------------------------
# Solver
# -----------------------------
def solve_parallel_system(
    n,
    p_feed,
    p_perm,
    membranes,
    k_in_list,
    k_out_list,
    k_drossel_list=None,
    target_recovery=None
):

    if k_drossel_list is None:
        k_drossel_list = [0.0] * n

    x0 = np.ones(n) * 1e-4

    def residuals(Qf_vec):
        res = []

        Qp_total = 0
        Qf_total = 0

        for i in range(n):
            Qf = Qf_vec[i]

            k_in = k_in_list[i]
            k_out = k_out_list[i] + k_drossel_list[i]
            mem = membranes[i]

            # Druck vor Membran
            p_in = p_feed - k_in * Qf * abs(Qf)

            # Iteration für Permeat
            Qp = 0.2 * Qf
            for _ in range(5):
                Qc = Qf - Qp
                p_out = k_out * Qc * abs(Qc)
                Qp = mem.permeate_flow(p_in, p_perm)

            Qc = Qf - Qp
            p_out = k_out * Qc * abs(Qc)

            # Druckkonsistenz
            res.append(p_in - p_out - 1e5)

            Qp_total += Qp
            Qf_total += Qf

        # Recovery-Bedingung
        if target_recovery is not None:
            recovery = Qp_total / max(Qf_total, 1e-9)
            res.append(recovery - target_recovery)

        return res

    sol = least_squares(residuals, x0)

    Qf_vec = sol.x

    # -----------------------------
    # Ergebnisaufbereitung
    # -----------------------------
    details = []
    Qp_total = 0
    Qf_total = 0

    for i in range(n):
        Qf = Qf_vec[i]

        k_in = k_in_list[i]
        k_out = k_out_list[i] + k_drossel_list[i]
        mem = membranes[i]

        p_in = p_feed - k_in * Qf * abs(Qf)
        Qp = mem.permeate_flow(p_in, p_perm)
        Qc = Qf - Qp

        Qp_total += Qp
        Qf_total += Qf

        details.append({
            "membrane": i,
            "feed_flow_lh": Qf * 3600 * 1000,
            "permeate_flow_lh": Qp * 3600 * 1000,
            "concentrate_flow_lh": Qc * 3600 * 1000,
            "pressure_in_bar": p_in / 1e5
        })

    recovery = Qp_total / max(Qf_total, 1e-9)

    return {
        "permeat_total": Qp_total * 3600 * 1000,
        "concentrate_total": (Qf_total - Qp_total) * 3600 * 1000,
        "feed_total": Qf_total * 3600 * 1000,
        "recovery": recovery,
        "details": details
    }
