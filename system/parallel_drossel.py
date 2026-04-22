from hydraulik.netzwerk_solver import *

def simuliere_parallel_drossel(
    n_membranes,
    p_feed_bar,
    p_perm_bar,
    A,
    area,
    tds,
    d_in,
    d_out,
    d_drossel,
    L_in,
    L_out,
    L_drossel
):
    p_feed = p_feed_bar * 1e5
    p_perm = p_perm_bar * 1e5

    membranes = [Membrane(A, area, tds) for _ in range(n_membranes)]

    k_in = [pipe_k(d_in, L_in) for _ in range(n_membranes)]
    k_out = [pipe_k(d_out, L_out) for _ in range(n_membranes)]
    k_drossel = [pipe_k(d_drossel, L_drossel, zeta=2.0) for _ in range(n_membranes)]

    return solve_parallel(
        n_membranes,
        p_feed,
        p_perm,
        membranes,
        k_in,
        k_out,
        k_drossel=k_drossel
    )
