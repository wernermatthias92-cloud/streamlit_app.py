# hydraulik/netzwerk.py

def berechne_feed_widerstaende(hat_t_stueck, d_a, l_a, b_a, sub_a, d_a1, l_a1, b_a1, d_a2, l_a2, b_a2,
                              d_b, l_b, b_b, sub_b, d_b1, l_b1, b_b1, d_b2, l_b2, b_b2):
    pfade = []
    namen = []
    
    if not hat_t_stueck:
        # Nur eine Membran (Standardfall)
        pfade.append([{'d': d_a, 'l': l_a, 'b': b_a, 'flow_factor': 1.0}])
        namen.append("A")
    else:
        # Pfad zu A / A1 / A2
        if not sub_a:
            pfade.append([{'d': d_a, 'l': l_a, 'b': b_a, 'flow_factor': 1.0}])
            namen.append("A")
        else:
            pfade.append([
                {'d': d_a, 'l': l_a, 'b': b_a, 'flow_factor': 1.0}, # Gemeinsames Stück A
                {'d': d_a1, 'l': l_a1, 'b': b_a1, 'flow_factor': 0.5} # Einzelstück A1
            ])
            pfade.append([
                {'d': d_a, 'l': l_a, 'b': b_a, 'flow_factor': 1.0}, # Gemeinsames Stück A
                {'d': d_a2, 'l': l_a2, 'b': b_a2, 'flow_factor': 0.5} # Einzelstück A2
            ])
            namen.extend(["A1", "A2"])

        # Pfad zu B / B1 / B2
        if not sub_b:
            pfade.append([{'d': d_b, 'l': l_b, 'b': b_b, 'flow_factor': 1.0}])
            namen.append("B")
        else:
            pfade.append([
                {'d': d_b, 'l': l_b, 'b': b_b, 'flow_factor': 1.0}, # Gemeinsames Stück B
                {'d': d_b1, 'l': l_b1, 'b': b_b1, 'flow_factor': 0.5} # Einzelstück B1
            ])
            pfade.append([
                {'d': d_b, 'l': l_b, 'b': b_b, 'flow_factor': 1.0}, # Gemeinsames Stück B
                {'d': d_b2, 'l': l_b2, 'b': b_b2, 'flow_factor': 0.5} # Einzelstück B2
            ])
            namen.extend(["B1", "B2"])
            
    return pfade, namen, len(pfade)

def analysiere_gesamte_topologie(saug_cfg, druck_cfg, netzwerk_cfg, konz_zweige, konz_out, perm_zweige, perm_out, perm_schlauch):
    pfade, namen, anzahl = berechne_feed_widerstaende(**netzwerk_cfg)
    
    return {
        'saug': saug_cfg,
        'druck_haupt': druck_cfg,
        'feed_pfade': pfade,
        'membran_namen': namen,
        'k_zweige': konz_zweige,
        'k_out': konz_out,
        'p_zweige': perm_zweige,
        'p_out': perm_out,
        'p_schlauch': perm_schlauch
    }
