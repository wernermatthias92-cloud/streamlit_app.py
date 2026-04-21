import math
from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel


def berechne_netzwerk(
    hat_t_stueck,
    d_a, l_a, sub_a,
    d_a1, l_a1, d_a2, l_a2,
    d_b, l_b, sub_b,
    d_b1, l_b1, d_b2, l_b2
):
    
    # Default-Werte
    r_netzwerk = 0
    pct_a, pct_b, pct_a1, pct_b1 = 1.0, 0.0, 0.0, 0.0

    if not hat_t_stueck:
        return r_netzwerk, pct_a, pct_b, pct_a1, pct_b1

    # --- Strang A ---
    if sub_a:
        r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], 0)
        r_a2 = berechne_hydraulischen_widerstand(d_a2, l_a2, [], 0)
        r_a_sub = r_parallel(r_a1, r_a2)
    else:
        r_a_sub = 0
        r_a1, r_a2 = 0, 0

    r_a_main = berechne_hydraulischen_widerstand(d_a, l_a, [], 0)
    r_a_tot = r_a_main + r_a_sub

    # --- Strang B ---
    if sub_b:
        r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], 0)
        r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], 0)
        r_b_sub = r_parallel(r_b1, r_b2)
    else:
        r_b_sub = 0
        r_b1, r_b2 = 0, 0

    r_b_main = berechne_hydraulischen_widerstand(d_b, l_b, [], 0)
    r_b_tot = r_b_main + r_b_sub

    # --- Gesamt-Netzwerk ---
d_a1, l_a1, d_a2, l_a2 = 0, 0, 0, 0
d_b1, l_b1, d_b2, l_b2 = 0, 0, 0, 0

r_netzwerk, pct_a, pct_b, pct_a1, pct_b1 = berechne_netzwerk(
    hat_t_stueck,
    d_a, l_a, sub_a,
    d_a1 if sub_a else 0, l_a1 if sub_a else 0,
    d_a2 if sub_a else 0, l_a2 if sub_a else 0,
    d_b, l_b, sub_b,
    d_b1 if sub_b else 0, l_b1 if sub_b else 0,
    d_b2 if sub_b else 0, l_b2 if sub_b else 0
)
