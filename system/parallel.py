import math
from hydraulik.widerstand import berechne_hydraulischen_widerstand, empfehle_drossel_durchmesser

def simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow,
                       m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
                       r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, 
                       leitungen_konz, leitung_out,
                       p_leitungen_konz, p_leitung_out, p_schlauch_out):
    
    # 1. Wissenschaftliche Temperatur-Korrektur (TCF)
    # Basis 25°C (298.15 K), Aktivierungsenergie 3020 K
    tcf_real = math.exp(3020 * (1/298.15 - 1/(273.15 + temp)))
    
    # 2. A-Wert (Wasserpermeabilitäts-Koeffizient) basierend auf Testbedingungen
    a_wert = m_test_flow / (m_flaeche * m_test_druck * 1.0 * 1000)
    
    anzahl_membranen = len(flow_fractions)
    if anzahl_membranen == 0:
        return {"error": "Keine Membranen im System definiert."}

    # 3. Erste Abschätzung für den Feed-Bedarf basierend auf der Ziel-Ausbeute
    # Wir schätzen einen mittleren NDP für den Start
    ndp_approx = p_system - ((tds_feed / 100) * 0.07) - 0.5 # 0.5 bar Puffer für Gegendruck
    q_p_total_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0.1, ndp_approx) * tcf_real * 1000
    q_feed_start_lh = q_p_total_approx / (ausbeute_pct / 100) if ausbeute_pct > 0 else q_p_total_approx * 2

    # 4. Hydraulik der Zuleitung (Druckverluste bis zum Moduleingang)
    q_ms_feed = (q_feed_start_lh / 1000) / 3600
    p_verlust_saug = (r_saug * q_ms_feed**2) / 100000 
    p_verlust_druck_haupt = (r_druck_haupt * q_ms_feed**2) / 100000
    p_verlust_netzwerk = (r_netzwerk * q_ms_feed**2) / 100000 if hat_t_stueck else 0
    
    # Der effektive Druck am Eingang der Membran-Module
    p_effektiv_start = p_system - p_verlust_druck_haupt - p_verlust_netzwerk

    # 5. Permeat-Hydraulik vorab berechnen
    r_p_out = berechne_hydraulischen_widerstand(p_leitung_out['d'], p_leitung_out['l'], [], p_leitung_out['b']) if p_leitung_out else 0
    r_p_schlauch = berechne_hydraulischen_widerstand(p_schlauch_out['d'], p_schlauch_out['l'], [], 0) if p_schlauch_out else 0
    p_back_height = (p_schlauch_out['h'] * 1000 * 9.81) / 100000 if p_schlauch_out else 0
    
    r_p_branches = []
    for i in range(anzahl_membranen):
        if i < len(p_leitungen_konz):
            r_p_branches.append(berechne_hydraulischen_widerstand(p_leitungen_konz[i]['d'], p_leitungen_konz[i]['l'], [], p_leitungen_konz[i]['b']))
        else:
            r_p_branches.append(0)

    # 6. Iterative Berechnung der Membran-Performance pro Modul
    total_permeat = 0
    total_permeat_salzfracht = 0
    membran_daten = []
    
    # Haupt-Gegendruck basierend auf geschätztem Permeatfluss
    q_ms_p_total = (q_p_total_approx / 1000) / 3600
    p_back_main = ((r_p_out + r_p_schlauch) * q_ms_p_total**2) / 100000 + p_back_height

    for i in range(anzahl_membranen):
        f_in = q_feed_start_lh * flow_fractions[i]
        r_p_branch = r_p_branches[i]
        
        # Startwerte für interne Modul-Iteration
        q_p = (f_in / anzahl_membranen) * 0.5 
        tds_p = tds_feed * (1 - m_rueckhalt)
        
        for _ in range(20):
            # Sicherheitsdeckelung (max 95% Recovery pro Modul)
            if q_p > f_in * 0.95: q_p = f_in * 0.95
            if q_p < 0: q_p = 0
            
            q_c_temp = max(0.001, f_in - q_p)
            recovery_modul = q_p / f_in if f_in > 0 else 0
            
            # Konzentrationspolarisation (CP) Effekt
            tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c_temp
            tds_avg = (tds_feed + tds_c_temp) / 2
            cp_factor = math.exp(0.7 * recovery_modul) 
            tds_wall = tds_avg * cp_factor
            
            # TDS-Durchgang basierend auf Wandkonzentration
            tds_p_target = tds_wall * (1 - m_rueckhalt)
            tds_p = tds_p * 0.5 + tds_p_target * 0.5
            
            # Dynamischer Permeat-Gegendruck
            p_back_branch = (r_p_branch * ((q_p / 1000) / 3600)**2) / 100000
            p_back_total = p_back_main + p_back_branch
            
            # Druckverlust im Spacer (Druckseite)
            p_verlust_modul = 0.2 * (f_in / 1000)**1.5
            p_effektiv_mitte = p_effektiv_start - (p_verlust_modul / 2)
            
            # Netto-Triebkraft (NDP)
            pi_wall = (tds_wall / 100) * 0.07
            ndp = max(0.0, p_effektiv_mitte - pi_wall - p_back_total)
            
            # Neuer Permeatfluss-Zielwert
            q_p_target = m_flaeche * a_wert * ndp * tcf_real * 1000
            q_p = q_p * 0.5 + q_p_target * 0.5
            
            # Finales Sicherheitsnetz am Ende der Schleife
            if q_p > f_in * 0.95: q_p = f_in * 0.95

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

    # 7. Gesamtergebnisse und Konzentrat-Hydraulik
    avg_permeat_tds = total_permeat_salzfracht / total_permeat if total_permeat > 0 else 0
    end_konzentrat_flow = q_feed_start_lh - total_permeat
    final_konzentrat_tds = (q_feed_start_lh * tds_feed - total_permeat_salzfracht) / end_konzentrat_flow if end_konzentrat_flow > 0 else tds_feed

    # Druckverlust im Konzentrat-Sammelrohr vor dem Ventil
    p_nach_spacer_avg = p_effektiv_start - 0.2
    p_verluste_konz_zweige = []
    for i, cfg in enumerate(leitungen_konz):
        r_z = berechne_hydraulischen_widerstand(cfg['d'], cfg['l'], [], cfg['b'])
        p_verluste_konz_zweige.append(r_z * ((membran_daten[i]["Konzentrat (l/h)"]/1000)/3600)**2 / 100000)
    
    p_t_stueck = p_nach_spacer_avg - (max(p_verluste_konz_zweige) if p_verluste_konz_zweige else 0)
    r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
    p_vor_ventil = p_t_stueck - (r_out * ((end_konzentrat_flow/1000)/3600)**2 / 100000)

    # Empfehlung für das Regelventil
    abzubauender_druck = max(0.1, p_vor_ventil - 0.5) # Ziel: 0.5 bar Restdruck nach Ventil
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
        "konzentrat_druck_verlauf": max(0.0, p_vor_ventil),
        "abzubauender_druck": abzubauender_druck,
        "empfohlene_drossel_mm": empfohlene_drossel_mm
    }
