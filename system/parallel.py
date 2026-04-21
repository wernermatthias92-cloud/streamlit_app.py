import math
from membrane.modell import berechne_tcf, berechne_a_wert
from hydraulik.widerstand import berechne_hydraulischen_widerstand, empfehle_drossel_durchmesser

def simuliere_parallel(anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow,
                       m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
                       r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz):
    
    tcf = berechne_tcf(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck)

    ndp_start = p_system - ((tds_feed / 100) * 0.07)
    q_p_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0, ndp_start) * tcf * 1000
    q_feed_start_lh = q_p_approx / (ausbeute_pct / 100) if (ausbeute_pct > 0 and q_p_approx > 0) else 0

    if ndp_start <= 0:
        return {"error": "Systemdruck zu gering!"}

    q_ms = (q_feed_start_lh / 1000) / 3600
    p_verlust_saug = (r_saug * q_ms**2) / 100000 
    p_verlust_druck_haupt = (r_druck_haupt * q_ms**2) / 100000
    p_verlust_netzwerk = (r_netzwerk * q_ms**2) / 100000 if hat_t_stueck else 0
    p_effektiv_start = p_system - p_verlust_druck_haupt - p_verlust_netzwerk

    total_permeat = 0
    total_permeat_salzfracht = 0
    membran_daten = []
    f_in = q_feed_start_lh / anzahl_membranen
    
    for i in range(anzahl_membranen):
        pi = (tds_feed / 100) * 0.07
        ndp = max(0, p_effektiv_start - pi)
        q_p = m_flaeche * a_wert * ndp * tcf * 1000
        if q_p > f_in * 0.95: q_p = f_in * 0.95
        
        q_c = f_in - q_p
        tds_p = tds_feed * (1 - m_rueckhalt)
        tds_c = ((f_in * tds_feed) - (q_p * tds_p)) / q_c if q_c > 0 else tds_feed
        
        total_permeat += q_p
        total_permeat_salzfracht += (q_p * tds_p)
        
        membran_daten.append({
            "Membran": f"Modul {i+1}",
            "Eingangsdruck (bar)": round(p_effektiv_start, 2),
            "Permeat (l/h)": round(q_p, 1),
            "Konzentrat (l/h)": round(q_c, 1),
            "Feed TDS (ppm)": round(tds_feed, 0),
            "Permeat TDS (ppm)": round(tds_p, 1),
            "Konz. TDS (ppm)": round(tds_c, 0)
        })

    avg_permeat_tds = total_permeat_salzfracht / total_permeat if total_permeat > 0 else 0
    # In der Parallelschaltung ist der End-TDS gleich dem Modul-TDS
    final_konzentrat_tds = tds_c 

    current_sammel_flow = q_c
    p_sammel = p_effektiv_start - 0.2
    for i in range(anzahl_membranen - 1):
        l_cfg = leitungen_konz[i]
        r_sammel = berechne_hydraulischen_widerstand(l_cfg['d'], l_cfg['l'], [], l_cfg['b'])
        p_verlust_sammel = (r_sammel * ((current_sammel_flow / 1000) / 3600)**2) / 100000
        p_sammel -= (p_verlust_sammel + 0.05) 
        current_sammel_flow += (f_in - membran_daten[i+1]["Permeat (l/h)"])

    end_konzentrat_flow = q_feed_start_lh - total_permeat
    abzubauender_druck = max(0.1, p_sammel - 0.5)
    empfohlene_drossel_mm = empfehle_drossel_durchmesser(end_konzentrat_flow, abzubauender_druck)

    return {
        "error": None,
        "q_feed_start_lh": q_feed_start_lh,
        "total_permeat": total_permeat,
        "total_permeat_tds": avg_permeat_tds,
        "final_konzentrat_tds": final_konzentrat_tds,
        "end_konzentrat_flow": end_konzentrat_flow,
        "membran_daten": membran_daten,
        "p_verlust_saug": p_verlust_saug,
        "p_verlust_druck_haupt": p_verlust_druck_haupt,
        "p_verlust_netzwerk": p_verlust_netzwerk,
        "p_effektiv_start": p_effektiv_start,
        "konzentrat_druck_verlauf": p_sammel,
        "abzubauender_druck": abzubauender_druck,
        "empfohlene_drossel_mm": empfohlene_drossel_mm
    }
