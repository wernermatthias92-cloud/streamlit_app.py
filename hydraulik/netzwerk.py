import math
from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel

def berechne_feed_widerstaende(hat_t_stueck, d_a, l_a, b_a, sub_a, d_a1, l_a1, b_a1, d_a2, l_a2, b_a2,
                               d_b, l_b, b_b, sub_b, d_b1, l_b1, b_b1, d_b2, l_b2, b_b2):
    """
    Berechnet ausschließlich die statischen hydraulischen Widerstände (R-Werte) 
    des T-Stück-Netzwerks nach der Pumpe, um sie dem Solver zur Verfügung zu stellen.
    """
    
    if not hat_t_stueck:
        # Kein Netzwerk, nur 1 Hauptmodul
        return 0, ["Modul 1 (Haupt)"], [0]

    membran_namen = []
    r_pfade = [] # Liste der kumulierten Widerstände für jeden Endpunkt (jedes Modul)

    # --- Strang A ---
    r_a_main = berechne_hydraulischen_widerstand(d_a, l_a, [], b_a)
    
    if sub_a:
        r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], b_a1)
        r_a2 = berechne_hydraulischen_widerstand(d_a2, l_a2, [], b_a2)
        r_a_sub = r_parallel(r_a1, r_a2)
        r_a_tot = r_a_main + r_a_sub
        
        membran_namen.extend(["A1", "A2"])
        # Der Weg zu A1 besteht aus der Hauptleitung A + der Zweigleitung A1
        r_pfade.extend([r_a_main + r_a1, r_a_main + r_a2])
    else:
        r_a_tot = r_a_main
        membran_namen.append("A")
        r_pfade.append(r_a_main)

    # --- Strang B ---
    r_b_main = berechne_hydraulischen_widerstand(d_b, l_b, [], b_b)
    
    if sub_b:
        r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], b_b1)
        r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], b_b2)
        r_b_sub = r_parallel(r_b1, r_b2)
        r_b_tot = r_b_main + r_b_sub
        
        membran_namen.extend(["B1", "B2"])
        r_pfade.extend([r_b_main + r_b1, r_b_main + r_b2])
    else:
        r_b_tot = r_b_main
        membran_namen.append("B")
        r_pfade.append(r_b_main)

    # Gesamtwiderstand des T-Stück Netzwerks (für den Gesamtdruckabfall der Pumpe)
    r_netzwerk = r_parallel(r_a_tot, r_b_tot)

    return r_netzwerk, membran_namen, r_pfade


def analysiere_gesamte_topologie(saug_cfg, druck_cfg, netzwerk_cfg, konz_zweige, konz_out, perm_zweige, perm_out, perm_schlauch):
    """
    Nimmt alle Rohrleitungsdaten entgegen und liefert ein sauberes Dictionary
    mit allen statischen Widerständen für den Solver.
    """
    
    # 1. Zuleitungen
    r_saug = berechne_hydraulischen_widerstand(saug_cfg['d'], saug_cfg['l'], [], saug_cfg['b'])
    r_druck_haupt = berechne_hydraulischen_widerstand(druck_cfg['d'], druck_cfg['l'], [], druck_cfg['b'])
    
    # 2. Feed-Netzwerk (Nur noch Namen und R-Werte, keine % mehr!)
    r_netzwerk, membran_namen, r_feed_pfade = berechne_feed_widerstaende(**netzwerk_cfg)
    
    # 3. Konzentrat-Abfluss
    r_k_zweige = []
    for z in konz_zweige:
        r_k_zweige.append(berechne_hydraulischen_widerstand(z['d'], z['l'], [], z['b']))
    r_k_out = berechne_hydraulischen_widerstand(konz_out['d'], konz_out['l'], [], konz_out['b']) if konz_out else 0
    
    # 4. Permeat-Abfluss
    r_p_zweige = []
    for z in perm_zweige:
        r_p_zweige.append(berechne_hydraulischen_widerstand(z['d'], z['l'], [], z['b']))
    r_p_out = berechne_hydraulischen_widerstand(perm_out['d'], perm_out['l'], [], perm_out['b']) if perm_out else 0
    r_p_schlauch = berechne_hydraulischen_widerstand(perm_schlauch['d'], perm_schlauch['l'], [], 0) if perm_schlauch else 0
    p_back_height = (perm_schlauch['h'] * 1000 * 9.81) / 100000 if perm_schlauch else 0

    return {
        "r_saug": r_saug,
        "r_druck_haupt": r_druck_haupt,
        "r_netzwerk": r_netzwerk,
        "membran_namen": membran_namen,
        "r_feed_pfade": r_feed_pfade, # Neu: Der Widerstand auf der Zulaufseite FÜR JEDES MODUL
        "r_k_zweige": r_k_zweige,
        "r_k_out": r_k_out,
        "r_p_zweige": r_p_zweige,
        "r_p_out": r_p_out,
        "r_p_schlauch": r_p_schlauch,
        "p_back_height": p_back_height
    }
