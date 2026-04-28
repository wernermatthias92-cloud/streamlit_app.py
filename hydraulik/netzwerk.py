def berechne_feed_widerstaende(**cfg):
    """
    Übersetzt die Netzwerkkonfiguration in eine Liste von Geometrien für jeden Membran-Pfad.
    Gibt (Dummy, Membran_Namen, Feed_Pfade) zurück.
    """
    m_namen = []
    pfade = []
    
    if not cfg.get("hat_t_stueck", False):
        m_namen.append("Membran 1")
        pfade.append([]) # Keine extra Zuleitung
    else:
        # Strang A
        seg_a = {"d": cfg.get("d_a", 13.2), "l": cfg.get("l_a", 150), "b": cfg.get("b_a", 1), "flow_factor": 2.0 if cfg.get("sub_a", False) else 1.0}
        if cfg.get("sub_a", False):
            m_namen.extend(["A1", "A2"])
            pfade.append([seg_a, {"d": cfg.get("d_a1", 10), "l": cfg.get("l_a1", 500), "b": cfg.get("b_a1", 0), "flow_factor": 1.0}])
            pfade.append([seg_a, {"d": cfg.get("d_a2", 10), "l": cfg.get("l_a2", 500), "b": cfg.get("b_a2", 0), "flow_factor": 1.0}])
        else:
            m_namen.append("A")
            pfade.append([seg_a])
            
        # Strang B
        seg_b = {"d": cfg.get("d_b", 13.2), "l": cfg.get("l_b", 150), "b": cfg.get("b_b", 1), "flow_factor": 2.0 if cfg.get("sub_b", False) else 1.0}
        if cfg.get("sub_b", False):
            m_namen.extend(["B1", "B2"])
            pfade.append([seg_b, {"d": cfg.get("d_b1", 10), "l": cfg.get("l_b1", 500), "b": cfg.get("b_b1", 0), "flow_factor": 1.0}])
            pfade.append([seg_b, {"d": cfg.get("d_b2", 10), "l": cfg.get("l_b2", 500), "b": cfg.get("b_b2", 0), "flow_factor": 1.0}])
        else:
            m_namen.append("B")
            pfade.append([seg_b])
    
    # Der erste Wert (None) fängt die alte r_pfade Variable der app.py ab, die wir nicht mehr brauchen.
    return None, m_namen, pfade

def analysiere_gesamte_topologie(saug_cfg, druck_cfg, netzwerk_cfg, konz_zweige, konz_out, perm_zweige, perm_out, perm_schlauch):
    """
    Bündelt alle Geometrien zentral für die dynamischen Solver.
    """
    _, m_namen, feed_pfade = berechne_feed_widerstaende(**netzwerk_cfg)
    
    return {
        "membran_namen": m_namen,
        "saug": saug_cfg,
        "druck_haupt": druck_cfg,
        "feed_pfade": feed_pfade,
        "k_zweige": konz_zweige,
        "k_out": konz_out,
        "p_zweige": perm_zweige,
        "p_out": perm_out,
        "p_schlauch": perm_schlauch
    }
