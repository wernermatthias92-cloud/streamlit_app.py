from hydraulik.netzwerk_solver import *

def simuliere_parallel(
    n_membranes,
    p_feed_bar,
    p_perm_bar,
    A,
    area,
    tds,
    d_in,
    d_out,
    L_in,
    L_out,
    target_recovery
):
    p_feed = p_feed_bar * 1e5
    p_perm = p_perm_bar * 1e5

    membranes = [Membrane(A, area, tds) for _ in range(n_membranes)]

    k_in = [pipe_k(d_in, L_in) for _ in range(n_membranes)]
    k_out = [pipe_k(d_out, L_out) for _ in range(n_membranes)]

    result = solve_parallel(
        n_membranes,
        p_feed,
        p_perm,
        membranes,
        k_in,
        k_out,
        target_recovery=target_recovery
    )

    return result
