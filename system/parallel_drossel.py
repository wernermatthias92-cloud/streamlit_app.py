import math
from membrane.modell import berechne_tcf, berechne_tcf_salz, berechne_a_wert

def berechne_drossel_druckabfall(flow_lh, drossel_mm):
    if flow_lh <= 0.001 or drossel_mm <= 0: return 9999.0 
    q_ms = (flow_lh / 1000) / 3600
    d_m = drossel_mm / 1000.0
    area_m2 = math.pi * (d_m / 2)**2
    c_d = 0.6
    v_spalt = q_ms / (area_m2 * c_d)
    delta_p_pa = (1000 * v_spalt**2) / 2
    return delta_p_pa / 100000.0

def berechne_pumpendruck(flow_lh, p_max, q_max):
    if flow_lh >= q_max: return 0.0
    return p_max * (1.0 - (flow_lh / q_max)**2)

def simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow,
                               m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, 
                               pumpen_modus, p_max, q_max, p_zulauf, p_fix):
    
    membran_namen = hydraulik['membran_namen']
    anzahl_membranen = len(membran_namen)
    if anzahl_membranen == 0: return {"error": "Keine Membranen gefunden."}

    tcf_real = berechne_tcf(temp)
    tcf_salz = berechne_tcf_salz(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck, m_test_tds)
    salzdurchgang_basis = 1.0 - m_rueckhalt
    salzdurchgang_real = salzdurchgang_basis * tcf_salz
            
    feed_min = 5.0
    feed_max = 30000.0 if pumpen_modus == "Gemessenen Druck eintragen (Manometer)" else min(30000.0, q_max * 0.99) 
    best_result = {"error": "Solver konnte kein Gleichgewicht finden."}
    
    flow_fractions = [1.0 / anzahl_membranen] * anzahl_membranen
    q_p_array = [200.0 / anzahl_membranen] * anzahl_membranen
    tds_p_array = [tds_feed * salzdurchgang_real] * anzahl_membranen
    
    max_spacer_dp = 0

    for iteration in range(60): 
        q_feed_start_lh = (feed_min + feed_max) / 2
        q_ms = (q_feed_start_lh / 1000) / 3600
        
        if pumpen_modus == "Gemessenen Druck eintragen (Manometer)":
            p_aktuell = p_fix
            p_verlust_saug = 0.0
        else:
            p_verlust_saug = (hydraulik['r_saug'] * q_ms**2) / 100000 
            p_vor_pumpe = max(0.0, p_zulauf - p_verlust_saug)
            p_pumpen_boost = berechne_pumpendruck(q_feed_start_lh, p_max, q_max)
            p_aktuell = p_vor_pumpe + p_pumpen_boost
        
        p_verlust_druck_haupt = (hydraulik['r_druck_haupt'] * q_ms**2) / 100000
        p_split = p_aktuell - p_verlust_druck_haupt
        
        if p_split <= 0.5:
            feed_max = q_feed_start_lh
            continue

        total_permeat = sum(q_p_array)
        q_ms_p_total = (total_permeat / 1000) / 3600
        p_back_main = (hydraulik['r_p_out'] + hydraulik['r_p_schlauch']) * q_ms_p_total**2 / 100000 + hydraulik['p_back_height']
        
        r_eff_list = []
        p_nach_zweigen = []
        membran_daten_temp = []
        total_permeat_salzfracht = 0
        max_spacer_dp = 0

        for i in range(anzahl_membranen):
            f_in = max(0.001, q_feed_start_lh * flow_fractions[i])
            q_p = q_p_array[i]
            tds_p = tds_p_array[i]
            
            for _ in range(15):
                if q_p > f_in * 0.95: q_p = f_in * 0.95 
                q_c_temp = max(0.001, f_in - q_p)
                recovery = q_p / f_in
                
                tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c_temp
                tds_avg = (tds_feed + tds_c_temp) / 2
                cp_factor = math.exp(0.7 * recovery) 
                
                tds_wall = min(tds_avg * cp_factor, 150000.0) 
                
                tds_p_target = tds_wall * salzdurchgang_real
                tds_p = tds_p * 0.5 + tds_p_target * 0.5
                
                q_ms_f_in = (f_in / 1000) / 3600
                p_verlust_feed = (hydraulik['r_feed_pfade'][i] * q_ms_f_in**2) / 100000
                p_in = p_split - p_verlust_feed
                
                p_verlust_spacer = 0.2 * (f_in / 1000)**1.5
                if p_verlust_spacer > max_spacer_dp: max_spacer_dp = p_verlust_spacer
                
                p_effektiv_mitte = p_in - (p_verlust_spacer / 2)
                q_ms_p_i = (q_p / 1000) / 3600
                p_back_branch = (hydraulik['r_p_zweige'][i] * q_ms_p_i**2) / 100000
                p_back_total = p_back_main + p_back_branch
                
                pi_wall = (tds_wall / 100) * 0.07
                ndp = max(0.0, p_effektiv_mitte - pi_wall - p_back_total)
                q_p_target = m_flaeche * a_wert * ndp * tcf_real * 1000
                q_p = q_p * 0.5 + q_p_target * 0.5
                
            # DER WICHTIGSTE SCHUTZ (Auch hier wieder eingefügt)
            if q_p > f_in * 0.95: q_p = f_in * 0.95 
            
            q_p_array[i] = q_p
            tds_p_array[i] = tds_p
            q_c = max(0.001, f_in - q_p)
            q_ms_c_i = (q_c / 1000) / 3600
            p_verlust_konz = (hydraulik['r_k_zweige'][i] * q_ms_c_i**2) / 100000
            p_nach_zweigen.append(p_in - p_verlust_spacer - p_verlust_konz)
            p_drop_branch = p_verlust_feed + p_verlust_spacer + p_verlust_konz
            r_eff = p_drop_branch / (q_ms_f_in**2) if q_ms_f_in > 0 else 1e9
            r_eff_list.append(r_eff)
            
            tds_c = ((f_in * tds_feed) - (q_p * tds_p)) / q_c
            total_permeat_salzfracht += (q_p * tds_p)
            flux_lmh = q_p / m_flaeche
            
            membran_daten_temp.append({
                "Membran": membran_namen[i],
                "Eingangsdruck (bar)": round(p_in, 2),
                "Flux (LMH)": round(flux_lmh, 1),
                "Permeat (l/h)": round(q_p, 1),
                "Gegendruck (bar)": round(p_back_total, 3),
                "Konzentrat (l/h)": round(q_c, 1),
                "Feed TDS (ppm)": round(tds_feed, 0),
                "Permeat TDS (ppm)": round(tds_p, 1),
                "Konz. TDS (ppm)": round(tds_c, 0)
            })

        sum_c = sum(1.0 / math.sqrt(r) for r in r_eff_list)
        flow_fractions = [(1.0 / math.sqrt(r)) / sum_c for r in r_eff_list]
        
        total_permeat = sum(q_p_array)
        end_konzentrat_flow = max(0.001, q_feed_start_lh - total_permeat)
        p_t_stueck_konz = sum(p_nach_zweigen) / anzahl_membranen
        q_ms_c_total = (end_konzentrat_flow / 1000) / 3600
        p_vor_ventil = p_t_stueck_konz - (hydraulik['r_k_out'] * q_ms_c_total**2) / 100000
        p_verlust_drossel = berechne_drossel_druckabfall(end_konzentrat_flow, drossel_vorgabe_mm)
        restdruck_nach_ventil = p_vor_ventil - p_verlust_drossel

        if restdruck_nach_ventil > 0.0: feed_min = q_feed_start_lh
        else: feed_max = q_feed_start_lh

        avg_permeat_tds = total_permeat_salzfracht / total_permeat if total_permeat > 0 else 0
        final_konzentrat_tds = (q_feed_start_lh * tds_feed - total_permeat_salzfracht) / end_konzentrat_flow

        best_result = {
            "error": None,
            "q_feed_start_lh": q_feed_start_lh,
            "total_permeat": total_permeat,
            "total_permeat_tds": avg_permeat_tds,
            "final_konzentrat_tds": final_konzentrat_tds,
            "end_konzentrat_flow": end_konzentrat_flow,
            "max_spacer_dp": max_spacer_dp,
            "membran_daten": membran_daten_temp,
            "p_verlust_saug": p_verlust_saug,
            "p_verlust_druck_haupt": p_verlust_druck_haupt,
            "p_effektiv_start": p_split,
            "konzentrat_druck_verlauf": max(0.0, p_vor_ventil),
            "abzubauender_druck": min(max(0.0, p_vor_ventil), p_verlust_drossel),
            "empfohlene_drossel_mm": drossel_vorgabe_mm,
            "realer_pumpendruck": p_aktuell 
        }
    return best_result
