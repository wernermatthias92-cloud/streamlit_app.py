import math
from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel

def berechne_parallel_netzwerk(hat_t_stueck, d_a, l_a, b_a, sub_a, d_a1, l_a1, b_a1, d_a2, l_a2, b_a2,
                              d_b, l_b, b_b, sub_b, d_b1, l_b1, b_b1, d_b2, l_b2, b_b2):
    """Berechnet den Gesamtwiderstand und die Flussaufteilung für das parallele Netzwerk."""
    
    R_MEM_BASE = 50000.0  # Basis-Widerstand der Membran für Conductance-Berechnung
    
    if not hat_t_stueck:
        return 0, [1.0], ["Modul 1 (Haupt)"]

    # --- Strang A ---
    r_a_sub = 0
    r_a1, r_a2 = 0, 0
    if sub_a:
        r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], b_a1)
        r_a2 = berechne_hydraulischen_widerstand(d_a2, l_a2, [], b_a2)
        r_a_sub = r_parallel(r_a1, r_a2)
    
    r_a_main = berechne_hydraulischen_widerstand(d_a, l_a, [], b_a)
    r_a_tot = r_a_main + r_a_sub

    # --- Strang B ---
    r_b_sub = 0
    r_b1, r_b2 = 0, 0
    if sub_b:
        r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], b_b1)
        r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], b_b2)
        r_b_sub = r_parallel(r_b1, r_b2)
    
    r_b_main = berechne_hydraulischen_widerstand(d_b, l_b, [], b_b)
    r_b_tot = r_b_main + r_b_sub

    r_netzwerk = r_parallel(r_a_tot, r_b_tot)

    # --- Physikalische Fluss-Aufteilung (Conductance) ---
    r_path_a1 = (r_a_tot - r_a_sub + r_a1) if sub_a else r_a_tot
    r_path_a2 = (r_a_tot - r_a_sub + r_a2) if sub_a else r_a_tot
    r_path_b1 = (r_b_tot - r_b_sub + r_b1) if sub_b else r_b_tot
    r_path_b2 = (r_b_tot - r_b_sub + r_b2) if sub_b else r_b_tot
    
    c_a = 0 if sub_a else 1.0 / math.sqrt(r_path_a1 + R_MEM_BASE)
    c_a1 = 1.0 / math.sqrt(r_path_a1 + R_MEM_BASE) if sub_a else 0
    c_a2 = 1.0 / math.sqrt(r_path_a2 + R_MEM_BASE) if sub_a else 0
    
    c_b = 0 if sub_b else 1.0 / math.sqrt(r_path_b1 + R_MEM_BASE)
    c_b1 = 1.0 / math.sqrt(r_path_b1 + R_MEM_BASE) if sub_b else 0
    c_b2 = 1.0 / math.sqrt(r_path_b2 + R_MEM_BASE) if sub_b else 0
    
    c_total = c_a + c_a1 + c_a2 + c_b + c_b1 + c_b2
    
    if sub_a and sub_b:
        flow_fractions, membran_namen = [c_a1/c_total, c_a2/c_total, c_b1/c_total, c_b2/c_total], ["A1","A2","B1","B2"]
    elif sub_a:
        flow_fractions, membran_namen = [c_a1/c_total, c_a2/c_total, c_b/c_total], ["A1","A2","B"]
    elif sub_b:
        flow_fractions, membran_namen = [c_a/c_total, c_b1/c_total, c_b2/c_total], ["A","B1","B2"]
    else:
        flow_fractions, membran_namen = [c_a/c_total, c_b/c_total], ["A","B"]
        
    return r_netzwerk, flow_fractions, membran_namen
