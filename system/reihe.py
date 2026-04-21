import math
from membrane.modell import berechne_tcf, berechne_a_wert
from hydraulik.widerstand import berechne_hydraulischen_widerstand, empfehle_drossel_durchmesser

def simuliere_reihe(anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow,
                    m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
                    r_saug, r_druck_haupt, leitungen_konz, leitung_out):
    
    tcf = berechne_tcf(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck)

    # Feed-Bedarf schätzen
    ndp_start = p_system - ((tds_feed / 100) * 0.07)
    q_p_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0, ndp_start) * tcf * 1000
    q_feed_start_lh = q_p_approx / (ausbeute_pct / 100) if (ausbeute_pct > 0 and q_p_approx > 0) else 0

    if ndp_start <= 0:
        return {"error": "Systemdruck zu gering für osmotischen Druck!"}

    # Druckverluste Zuleitung
    q_ms = (q_feed_start_lh / 1000) / 3600
    p_verlust_saug = (r_saug * q_ms**2) / 100000 
    p_verlust_druck_haupt = (r_druck_haupt * q_ms**2) / 100000
    p_effektiv_start = p_system - p_verlust_druck_haupt

    current_feed_flow = q_feed_start_lh
    current_tds = tds_feed
    current_p = p_effektiv_start
    
    membran_daten = []
    total_permeat = 0

    for i in range(anzahl_membranen):
        f_in = current_feed_flow
        p_in = current_p
        tds_in = current_tds

        pi = (tds_in / 100) * 0.07
        ndp = max(0, p_in - pi)
        q_p = m_flaeche * a_wert * ndp * tcf * 1000
        if q_p > f_in * 0.95: q_p = f_in * 0.95 
        
        q_c = f_in - q_p
        tds_p = tds_in * (1 - m_rueckhalt)
        tds_c = ((f_in * tds_in) - (q_p * tds_p)) / q_c if q_c > 0 else tds_in
        total_permeat += q_p

        membran_daten.append({
            "Membran": f"Modul {i+1}",
            "Eingangsdruck (bar)": round(p_in, 2),
            "Permeat (l/h)": round(q_p, 1),
            "Konzentrat (l/h)": round(q_c, 1),
            "Feed TDS (ppm)": round(tds_in, 0),
            "Permeat TDS (ppm)": round(tds_p, 1),
            "Konz. TDS (ppm)": round(tds_c, 0)
        })

        # Übergabe an nächste Membran
        druck_nach_spacer = p_in - 0.2
        if i < anzahl_membranen - 1:
            l_cfg = leitungen_konz[i]
            r_zwischen = berechne_hydraulischen_widerstand(l_cfg['d'], l_cfg['l'], [], l_cfg['b'])
            p_verlust_zwischen = (r_zwischen * ((q_c / 1000) / 3600)**2) / 100000
            current_p = druck_nach_spacer - p_verlust_zwischen 
        else:
            current_p = druck_nach_spacer 
            
        current_feed_flow = q_c
        current_tds = tds_c

    # Endleitung & Drossel
    r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
    p_verlust_out = (r_out * ((current_feed_flow / 1000) / 3600)**2) / 100000
    konzentrat_druck_vor_ventil = current_p - p_verlust_out
    abzubauender_druck = max(0.1, konzentrat_druck_vor_ventil - 0.5)
    empfohlene_drossel_mm = empfehle_drossel_durchmesser(current_feed_flow, abzubauender_druck)

    return {
        "error": None,
        "q_feed_start_lh": q_feed_start_lh,
        "total_permeat": total_permeat,
        "end_konzentrat_flow": current_feed_flow,
        "membran_daten": membran_daten,
        "p_verlust_saug": p_verlust_saug,
        "p_verlust_druck_haupt": p_verlust_druck_haupt,
        "p_verlust_netzwerk": 0,
        "p_effektiv_start": p_effektiv_start,
        "konzentrat_druck_verlauf": konzentrat_druck_vor_ventil,
        "abzubauender_druck": abzubauender_druck,
        "empfohlene_drossel_mm": empfohlene_drossel_mm
    }
