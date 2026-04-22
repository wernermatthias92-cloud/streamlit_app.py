import math

class Membrane1D:
    def __init__(self, A, area, tds, n_segments=20):
        self.A = A
        self.area = area
        self.tds = tds
        self.n_segments = n_segments

    def osmotic_pressure(self, c):
        return 0.008 * c  # bar

    def mass_transfer_coeff(self, Q, d_h=0.001):
        # sehr vereinfachte Sherwood-Korrelation
        v = Q / (math.pi * d_h**2 / 4)
        Re = v * d_h / 1e-6
        Sc = 1000
        Sh = 0.023 * Re**0.83 * Sc**0.33
        D = 1e-9
        return Sh * D / d_h

    def simulate(self, Qf_in, p_in, p_perm):
        dx = 1.0 / self.n_segments
        area_seg = self.area / self.n_segments

        Qf = Qf_in
        c = self.tds
        p = p_in

        Qp_total = 0

        for _ in range(self.n_segments):

            k = self.mass_transfer_coeff(Qf)

            # iterative Lösung lokal
            J = 1e-6
            for _ in range(5):
                c_m = c * math.exp(J / max(k,1e-9))
                pi = self.osmotic_pressure(c_m)
                J = self.A * (p - p_perm - pi)

                if J < 0:
                    J = 0

            Qp = J * area_seg
            Qp_total += Qp

            # Update Feed
            Qf = max(Qf - Qp, 1e-9)

            # Konzentration steigt
            c = c * (Qf_in / Qf)

            # Druckverlust (vereinfacht)
            dp = 1e5 * (Qf_in - Qf)
            p -= dp

        return {
            "Qp": Qp_total,
            "Qc": Qf,
            "c_out": c,
            "p_out": p
        }
