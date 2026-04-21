import math
from membrane.modell import berechne_tcf, berechne_a_wert
from hydraulik.widerstand import berechne_hydraulischen_widerstand, empfehle_drossel_durchmesser

def simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow,
                       m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
                       r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz):
    
    tcf = berechne_tcf(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck)
    anzahl_membranen = len(flow_fractions)

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
    
    for i in range(anzahl_membranen):
        f_in = q_feed_start_lh * flow_fractions[i]
        
        # Startwerte
        pi_inlet = (tds_feed / 100) * 0.07
        q_p = m_flaeche * a_wert * max(0, p_effektiv_start - pi_inlet) * tcf * 1000
        tds_p = tds_feed * (1 - m_rueckhalt)
        
        # --- PHYSIK-UPDATE v2: Konzentrationspolarisation & TDS-Durchschlag ---
        for _ in range(15): # 15 Durchläufe für stabile Konvergenz
            if q_p > f_in * 0.90: q_p = f_in * 0.90 # Harte Grenze: Max 90% Ausbeute pro Modul
            if q_p < 0: q_p = 0
            
            q_c_temp = f_in - q_p
            recovery = q_p / f_in if f_in > 0 else 0
            
            # 1. Mittlere Bulk-Salzkonzentration im Modul
            tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c_temp if q_c_temp > 0 else tds_feed
            tds_avg = (tds_feed + tds_c_temp) / 2
            
            # 2. Konzentrationspolarisation (CP): Erzeugt die fiktive Grenzschicht an der Membran
            cp_factor = math.exp(0.7 * recovery) 
            
            # 3. Tatsächliche Salzkonzentration direkt an der Membranwand
            tds_wall = tds_avg * cp_factor
            
            # 4. NEU: Permeat-TDS ist abhängig von der Wandkonzentration!
            tds_p_target = tds_wall * (1 - m_rueckhalt)
            tds_p = tds_p * 0.5 + tds_p_target * 0.5 # Gedämpfte Anpassung
            
            # 5. Osmotischer Gegendruck der hochkonzentrierten Grenzschicht
            pi_wall = (tds_wall / 100) * 0.07
            ndp = max(0, p_effektiv_start - pi_wall)
            
            # 6. Neue Permeatmenge
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
            "Konzentrat (l/h)": round(q_c, 1),
            "Feed TDS (ppm)": round(tds_feed, 0),
            "Permeat TDS (ppm)": round(tds_p, 1),
            "Konz. TDS (ppm)": round(tds_c, 0)
        })

    # Gesamtergebnisse berechnen
    avg_permeat_tds = total_permeat_salzfracht / total_permeat if total_permeat > 0 else 0
    end_konzentrat_flow = q_feed_start_lh - total_permeat
    
    # Korrekte Berechnung des finalen Misch-Konzentrats (Massenbilanz der Gesamtanlage)
    total_feed_salzfracht = q_feed_start_lh * tds_feed
    total_konzentrat_salzfracht = total_feed_salzfracht - total_permeat_salzfracht
    final_konzentrat_tds = total_konzentrat_salzfracht / end_konzentrat_flow if end_konzentrat_flow > 0 else tds_feed

    # Sammelleitungen berechnen
    current_sammel_flow = membran_daten[0]["Konzentrat (l/h)"]
    p_sammel = p_effektiv_start - 0.2
    
    for i in range(anzahl_membranen - 1):
        l_cfg = leitungen_konz[i]
        r_sammel = berechne_hydraulischen_widerstand(l_cfg['d'], l_cfg['l'], [], l_cfg['b'])
        p_verlust_sammel = (r_sammel * ((current_sammel_flow / 1000) / 3600)**2) / 100000
        p_sammel -= (p_verlust_sammel + 0.05) 
        current_sammel_flow += membran_daten[i+1]["Konzentrat (l/h)"]

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
