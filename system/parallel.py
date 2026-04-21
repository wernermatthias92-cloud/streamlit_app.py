import math
from membrane.modell import berechne_tcf, berechne_a_wert
from hydraulik.widerstand import berechne_hydraulischen_widerstand, empfehle_drossel_durchmesser

def simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow,
                       m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
                       r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, 
                       leitungen_konz, leitung_out,
                       p_leitungen_konz, p_leitung_out):
    
    tcf = berechne_tcf(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck)
    anzahl_membranen = len(flow_fractions)

    # 1. NDP Schätzung für Feed-Bedarf
    ndp_start = p_system - ((tds_feed / 100) * 0.07)
    q_p_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0, ndp_start) * tcf * 1000
    q_feed_start_lh = q_p_approx / (ausbeute_pct / 100) if (ausbeute_pct > 0 and q_p_approx > 0) else 0

    if ndp_start <= 0:
        return {"error": "Systemdruck zu gering!"}

    # 2. Hydraulik Druckseite
    q_ms = (q_feed_start_lh / 1000) / 3600
    p_verlust_saug = (r_saug * q_ms**2) / 100000 
    p_verlust_druck_haupt = (r_druck_haupt * q_ms**2) / 100000
    p_verlust_netzwerk = (r_netzwerk * q_ms**2) / 100000 if hat_t_stueck else 0
    p_effektiv_start = p_system - p_verlust_druck_haupt - p_verlust_netzwerk

    # 3. Permeat-Widerstände vorab berechnen
    r_p_out = berechne_hydraulischen_widerstand(p_leitung_out['d'], p_leitung_out['l'], [], p_leitung_out['b'])
    r_p_branches = []
    if anzahl_membranen > 1:
        for p_cfg in p_leitungen_konz:
            r_p_branches.append(berechne_hydraulischen_widerstand(p_cfg['d'], p_cfg['l'], [], p_cfg['b']))
    
    # Gegendruck der Hauptleitung (Schätzwert basierend auf q_p_approx)
    p_back_main = (r_p_out * ((q_p_approx / 1000) / 3600)**2) / 100000

    total_permeat = 0
    total_permeat_salzfracht = 0
    membran_daten = []
    
    for i in range(anzahl_membranen):
        f_in = q_feed_start_lh * flow_fractions[i]
        r_p_branch = r_p_branches[i] if anzahl_membranen > 1 else 0
        
        # Startwerte für Iteration
        q_p = (f_in / anzahl_membranen) * 0.5 
        tds_p = tds_feed * (1 - m_rueckhalt)
        
        # Physik-Schleife mit CP und Permeat-Gegendruck
        for _ in range(15):
            if q_p > f_in * 0.90: q_p = f_in * 0.90 
            if q_p < 0: q_p = 0
            
            q_c_temp = f_in - q_p
            recovery = q_p / f_in if f_in > 0 else 0
            
            # TDS Logik
            tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c_temp if q_c_temp > 0 else tds_feed
            tds_avg = (tds_feed + tds_c_temp) / 2
            cp_factor = math.exp(0.7 * recovery) 
            tds_wall = tds_avg * cp_factor
            tds_p_target = tds_wall * (1 - m_rueckhalt)
            tds_p = tds_p * 0.5 + tds_p_target * 0.5
            
            # --- NEU: Permeat Gegendruck ---
            p_back_branch = (r_p_branch * ((q_p / 1000) / 3600)**2) / 100000
            p_back_total = p_back_main + p_back_branch
            
            pi_wall = (tds_wall / 100) * 0.07
            ndp = max(0, p_effektiv_start - pi_wall - p_back_total)
            
            q_p_target = m_flaeche * a_wert * ndp * tcf * 1000
            q_p = q_p * 0.5 + q_p_target * 0.5
            
        q_c = f_in - q_p
        tds_c = ((f_in * tds_feed) - (q_p * tds_p)) / q_c if q_c > 0 else tds_feed
        
        total_permeat += q_p
        total_permeat_salzfracht += (q_p * tds_p)
        
        membran_daten.append({
            "Membran": membran_namen[i],
            "Eingangsdruck (bar)": round(p_effektiv_start, 2),
            "Permeat (l/h)": round(q_p, 1),
            "Gegendruck (bar)": round(p_back_total, 3),
            "Konzentrat (l/h)": round(q_c, 1),
            "Feed TDS (ppm)": round(tds_feed, 0),
            "Permeat TDS (ppm)": round(tds_p, 1),
            "Konz. TDS (ppm)": round(tds_c, 0)
        })

    # Massenbilanz & Finale Werte
    avg_permeat_tds = total_permeat_salzfracht / total_permeat if total_permeat > 0 else 0
    end_konzentrat_flow = q_feed_start_lh - total_permeat
    final_konzentrat_tds = (q_feed_start_lh * tds_feed - total_permeat_salzfracht) / end_konzentrat_flow if end_konzentrat_flow > 0 else tds_feed

    # Konzentrat-Druckverlust
    p_nach_spacer = p_effektiv_start - 0.2
    if anzahl_membranen == 1:
        r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
        p_vor_ventil = p_nach_spacer - (r_out * ((end_konzentrat_flow/1000)/3600)**2 / 100000)
    else:
        p_verluste_zweige = []
        for i, cfg in enumerate(leitungen_konz):
            r_z = berechne_hydraulischen_widerstand(cfg['d'], cfg['l'], [], cfg['b'])
            p_verluste_zweige.append(r_z * ((membran_daten[i]["Konzentrat (l/h)"]/1000)/3600)**2 / 100000)
        p_t_stueck = p_nach_spacer - max(p_verluste_zweige)
        r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
        p_vor_ventil = p_t_stueck - (r_out * ((end_konzentrat_flow/1000)/3600)**2 / 100000)

    abzubauender_druck = max(0.1, p_vor_ventil - 0.5)
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
        "konzentrat_druck_verlauf": p_vor_ventil,
        "abzubauender_druck": abzubauender_druck,
        "empfohlene_drossel_mm": empfohlene_drossel_mm
    }
