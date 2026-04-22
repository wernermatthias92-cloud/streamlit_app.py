from hydraulik.netzwerk_solver import *

def berechne_parallel_drossel(
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

    membranes = []
    k_in_list = []
    k_out_list = []
    k_drossel_list = []

    for _ in range(n_membranes):

        membranes.append(Membrane(A, area, tds))

        k_in_list.append(pipe_k(d_in, L_in))
        k_out_list.append(pipe_k(d_out, L_out))

        k_drossel_list.append(
            pipe_k(d_drossel, L_drossel, zeta=2.0)
        )

    return solve_parallel_system(
        n=n_membranes,
        p_feed=p_feed,
        p_perm=p_perm,
        membranes=membranes,
        k_in_list=k_in_list,
        k_out_list=k_out_list,
        k_drossel_list=k_drossel_list
    )
