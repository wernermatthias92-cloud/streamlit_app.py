import numpy as np
from scipy.optimize import least_squares
import math

RHO = 1000  # kg/m³

# -----------------------------
# Basis-Klassen
# -----------------------------

class Node:
    def __init__(self, name, fixed_pressure=None):
        self.name = name
        self.fixed_pressure = fixed_pressure


class Edge:
    def __init__(self, name, n1, n2):
        self.name = name
        self.n1 = n1
        self.n2 = n2


class Pipe(Edge):
    def __init__(self, name, n1, n2, k):
        super().__init__(name, n1, n2)
        self.k = k  # Δp = k * Q^2

    def residual(self, p1, p2, Q):
        return p1 - p2 - self.k * Q * abs(Q)


class Membrane(Edge):
    def __init__(self, name, n_feed, n_conc, n_perm,
                 A, area, tds):
        super().__init__(name, n_feed, n_conc)
        self.n_perm = n_perm
        self.A = A
        self.area = area
        self.tds = tds

    def osmotic_pressure(self):
        # einfache Verbesserung gegenüber deinem Modell
        return 0.008 * self.tds  # bar (empirisch besser als vorher)

    def permeate_flow(self, p_feed, p_perm):
        pi = self.osmotic_pressure()
        ndp = max(p_feed - p_perm - pi, 0)
        return self.A * self.area * ndp  # m³/s

    def residuals(self, p_feed, p_conc, p_perm, Qf, Qc, Qp):
        res = []

        # 1. Massenbilanz
        res.append(Qf - Qc - Qp)

        # 2. Permeatflussgesetz
        Qp_model = self.permeate_flow(p_feed, p_perm)
        res.append(Qp - Qp_model)

        # 3. einfacher Druckverlust Feed→Konzentrat
        k_mem = 1e5
        res.append(p_feed - p_conc - k_mem * Qf * abs(Qf))

        return res


# -----------------------------
# Solver
# -----------------------------

class NetworkSolver:

    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, node):
        self.nodes.append(node)

    def add_edge(self, edge):
        self.edges.append(edge)

    def solve(self):

        n_nodes = len(self.nodes)
        n_edges = len(self.edges)

        # Variablen:
        # [p0, p1, ..., Q0, Q1, ...]
        x0 = np.ones(n_nodes + n_edges) * 1e5

        def residuals(x):
            res = []

            p = x[:n_nodes]
            Q = x[n_nodes:]

            # Mapping
            node_index = {n.name: i for i, n in enumerate(self.nodes)}

            # -------------------------
            # 1. Fixdrücke
            # -------------------------
            for i, node in enumerate(self.nodes):
                if node.fixed_pressure is not None:
                    res.append(p[i] - node.fixed_pressure)

            # -------------------------
            # 2. Knotenbilanzen
            # -------------------------
            for i, node in enumerate(self.nodes):
                flow_sum = 0

                for j, edge in enumerate(self.edges):
                    if edge.n1 == node.name:
                        flow_sum -= Q[j]
                    elif edge.n2 == node.name:
                        flow_sum += Q[j]

                res.append(flow_sum)

            # -------------------------
            # 3. Kanten
            # -------------------------
            for j, edge in enumerate(self.edges):

                i1 = node_index[edge.n1]
                i2 = node_index[edge.n2]

                if isinstance(edge, Pipe):
                    res.append(edge.residual(p[i1], p[i2], Q[j]))

                elif isinstance(edge, Membrane):

                    # zusätzliche Variable für Permeatstrom
                    Qf = Q[j]
                    Qp = 0.2 * abs(Qf)  # initialer Ansatz
                    Qc = Qf - Qp

                    p_perm = p[node_index[edge.n_perm]]

                    res.extend(edge.residuals(
                        p[i1], p[i2], p_perm,
                        Qf, Qc, Qp
                    ))

            return res

        sol = least_squares(residuals, x0, verbose=0)

        return sol
