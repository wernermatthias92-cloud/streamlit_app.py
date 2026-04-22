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
    """
    Hauptfunktion für App (NICHT ändern im Namen!)
    """

    p_feed = p_feed_bar * 1e5
    p_perm = p_perm_bar * 1e5

    membranes = []
    k_in_list = []
    k_out_list = []

    for _ in range(n_membranes):
        membranes.append(Membrane(A, area, tds))
        k_in_list.append(pipe_k(d_in, L_in))
        k_out_list.append(pipe_k(d_out, L_out))

    result = solve_parallel_system(
        n=n_membranes,
        p_feed=p_feed,
        p_perm=p_perm,
        membranes=membranes,
        k_in_list=k_in_list,
        k_out_list=k_out_list,
        target_recovery=target_recovery
    )

    return result


# 👉 OPTIONAL: Rückwärtskompatibilität
def berechne_parallel(*args, **kwargs):
    return simuliere_parallel(*args, **kwargs)
