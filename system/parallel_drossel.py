import math
from hydraulik.widerstand import berechne_hydraulischen_widerstand

def berechne_drossel_druckabfall(flow_lh, drossel_mm):
    # Verhindert Division durch 0 und fängt negative Flüsse ab
    if flow_lh <= 0.1 or drossel_mm <= 0: return 1e6 
    
    q_ms = (flow_lh / 1000) / 3600
    d_m = drossel_mm / 1000.0
    area_m2 = math.pi * (d_m / 2)**2
    
    # Reale physikalische Blenden-Gleichung (Orifice Equation)
    # Ein typisches Nadelventil / Drossel hat einen Ausflusskoeffizienten (Cd) von ca. 0.6
    c_d = 0.6
    v_spalt = q_ms / (area_m2 * c_d)
    
    # Delta P = (rho * v^2) / 2
    delta_p_pa = (1000 * v_spalt**2) / 2
    return delta_p_pa / 100000.0 # Umrechnung in bar

def simuliere_parallel_drossel(flow_fractions, membran_namen, drossel_vorgabe_mm, m_flaeche, m_test_flow,
                       m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
                       r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, 
                       leitungen_konz, leitung_out,
                       p_leitungen_konz, p_leitung_out, p_schlauch_out):
    
    anzahl_membranen = len(flow_fractions)

    # 1. Wissenschaftliches TCF (Temperatur-Korrektur-Faktor)
    # Basis: 25°C (298.15 K). Aktivierungsenergie-Konstante = 3020 K.
    tcf_real = math.exp(3020 * (1/298.15 - 1/(273.15 + temp)))
    
    # 2. Reiner A-Wert der Membran bei Testbedingungen (25°C, also TCF=1.0)
    a_wert = m_test_flow / (m_flaeche * m_test_druck * 1.0 * 1000)

    # Vorab-Berechnungen der Leitungs-Widerstände
    r_p_out = berechne_hydraulischen_widerstand(p_leitung_out['d'], p_leitung_out['l'], [], p_leitung_out['b'])
    r_p_schlauch = berechne_hydraulischen_widerstand(p_schlauch_out['d'], p_schlauch_out['l'], [], 0)
    p_back_height = (p_schlauch_out['h'] * 1000 * 9.81) / 100000
    
    r_p_branches = []
    if anzahl_membranen > 1:
        for p_cfg in p_leitungen_konz:
            r_p_branches.append(berechne_hydraulischen_widerstand(p_cfg['d'], p_cfg['l'], [], p_cfg['b']))
            
    # --- NUMERISCHER SOLVER START ---
    feed_min = 10.0
    feed_max = 15000.0
    best_result = None

    for iteration in range(50):
        q_feed_start_lh = (feed_min + feed_max) / 2
        
        q_ms = (q_feed_start_lh / 1000) / 3600
        p_verlust_saug = (r_saug * q_ms**2) / 100000 
        p_verlust_druck_haupt = (r_druck_haupt * q_ms**2) / 100000
        p_verlust_netzwerk = (r_netzwerk * q_ms**2) / 100000 if hat_t_stueck else 0
        p_effektiv_start = p_system - p_verlust_druck_haupt - p_verlust_netzwerk
        
        if p_effektiv_start <= 0:
            feed_max = q_feed_start_lh
            continue

        total_permeat = 0
        total_permeat_salzfracht = 0
        membran_daten = []
        
        # Schätzung Haupt-Gegendruck Permeat
        q_p_approx_total = q_feed_start_lh * 0.4
        q_ms_p = (q_p_approx_total / 1000) / 3600
        p_back_main = ((r_p_out + r_p_schlauch) * q_ms_p**2) / 100000 + p_back_height

        for i in range(anzahl_membranen):
            f_in = q_feed_start_lh * flow_fractions[i]
            r_p_branch = r_p_branches[i] if anzahl_membranen > 1 else 0
            
            q_p = (f_in / anzahl_membranen) * 0.5 
            tds_p = tds_feed * (1 - m_rueckhalt)
            
            # Physik-Schleife Membran
            for _ in range(15):
                # Verhindert Div/0 bei Berechnungen der Konzentration
                if q_p >= f_in: q_p = f_in * 0.99 
                if q_p < 0: q_p = 0
                
                q_c_temp = f_in - q_p
                recovery = q_p / f_in if f_in > 0 else 0
                
                tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c_temp
                tds_avg = (tds_feed + tds_c_temp) / 2
                cp_factor = math.exp(0.7 * recovery) 
                tds_wall = tds_avg * cp_factor
                tds_p_target = tds_wall * (1 - m_rueckhalt)
                tds_p = tds_p * 0.5 + tds_p_target * 0.5
                
                p_back_branch = (r_p_branch * ((q_p / 1000) / 3600)**2) / 100000
                p_back_total = p_back_main + p_back_branch
                
                # Druckabfall IM Modul durch Spacer (ca. 0.2 bar bei 1000 l/h)
                p_verlust_modul = 0.2 * (f_in / 1000)**1.5
                p_effektiv_mitte = p_effektiv_start - (p_verlust_modul / 2)
                
                pi_wall = (tds_wall / 100) * 0.07
                ndp = max(0, p_effektiv_mitte - pi_wall - p_back_total)
                
                q_p_target = m_flaeche * a_wert * ndp * tcf_real * 1000
                q_p = q_p * 0.5 + q_p_target * 0.5
                
                # BUGFIX: Harte Sicherheitsgrenze AM ENDE der Iteration
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

        end_konzentrat_flow = q_feed_start_lh - total_permeat

        p_nach_spacer = p_effektiv_start - 0.2
        if anzahl_membranen == 1:
            r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
            p_vor_ventil = p_nach_spacer - (r_out * ((end_konzentrat_flow/1000)/3600)**2 / 100000)
        else:
            p_verluste_zweige = []
            for i, cfg in enumerate(leitungen_konz):
                r_z = berechne_hydraulischen_widerstand(cfg['d'], cfg['l'], [], cfg['b'])
                p_verluste_zweige.append(r_z * ((membran_daten[i]["Konzentrat (l/h)"]/1000)/3600)**2 / 100000)
            p_t_stueck = p_nach_spacer - (max(p_verluste_zweige) if p_verluste_zweige else 0)
            r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
            p_vor_ventil = p_t_stueck - (r_out * ((end_konzentrat_flow/1000)/3600)**2 / 100000)

        # --- SOLVER LOGIK ---
        p_verlust_drossel = berechne_drossel_druckabfall(end_konzentrat_flow, drossel_vorgabe_mm)
        restdruck_nach_ventil = p_vor_ventil - p_verlust_drossel

        if restdruck_nach_ventil > 0.1:
            feed_min = q_feed_start_lh
        else:
            feed_max = q_feed_start_lh

        avg_permeat_tds = total_permeat_salzfracht / total_permeat if total_permeat > 0 else 0
        final_konzentrat_tds = (q_feed_start_lh * tds_feed - total_permeat_salzfracht) / end_konzentrat_flow if end_konzentrat_flow > 0 else tds_feed

        best_result = {
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
            "abzubauender_druck": p_verlust_drossel,
            "empfohlene_drossel_mm": drossel_vorgabe_mm 
        }

    return best_result
