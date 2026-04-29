import math
from membrane.modell import berechne_tcf, berechne_tcf_salz, berechne_a_wert, berechne_osmotischen_druck, berechne_cp_faktor
from hydraulik.widerstand import berechne_hydraulischen_widerstand, berechne_spacer_dp_segment, get_dichte_wasser

def simuliere_parallel_verdraenger(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow,
                                   m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus,
                                   pump_max_druck, pump_fest_flow):
    
    membran_namen = hydraulik['membran_namen']
    anzahl_membranen = len(membran_namen)
    if anzahl_membranen == 0: return {"error": "Keine Membranen gefunden."}

    tcf_real = berechne_tcf(temp)
    tcf_salz = berechne_tcf_salz(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck, m_test_tds)
    
    salz_durchgang_nominal = 1.0 - m_rueckhalt
    if trocken_modus:
        a_wert *= 1.15
        salz_durchgang_nominal = 1.0 - max(0.0, (m_rueckhalt - 0.025))

    frac_hard = 0.65
    frac_light = 0.35
    salzdurchgang_real_nominal = salz_durchgang_nominal * tcf_salz
    pass_hard = max(0.0, min(1.0, salzdurchgang_real_nominal * 0.15))
    pass_light = max(0.0, min(1.0, salzdurchgang_real_nominal * 1.5))
    
    def calc_dp(flow_lh, cfg):
        if flow_lh <= 0 or cfg.get('l', 0) <= 0: return 0.0
        r_val = berechne_hydraulischen_widerstand(flow_lh, cfg['d'], cfg['l'], temp, bögen=cfg.get('b', 0))
        q_ms = (flow_lh / 1000.0) / 3600.0
        return (r_val * q_ms**2) / 100000.0

    # Bei Verdrängerpumpen ist der Feed-Flow in der Theorie fix!
    q_feed_total = pump_fest_flow
    c_d = 0.71
    area_drossel_m2 = math.pi * ((drossel_vorgabe_mm / 1000.0) / 2)**2
    rho = get_dichte_wasser(temp)
    n_seg = 10
    area_seg = m_flaeche / n_seg
    flow_fractions = [1.0 / anzahl_membranen] * anzahl_membranen
    
    q_p_branch_guess = [q_feed_total * 0.4 / anzahl_membranen] * anzahl_membranen
    total_permeat_guess = q_feed_total * 0.4

    # Da Q_feed bekannt ist, müssen wir nur iterieren, bis sich der Permeatfluss einpendelt
    for outer_it in range(15):
        q_c_total_calc = q_feed_total - total_permeat_guess
        if q_c_total_calc <= 0.001: q_c_total_calc = 0.001
        
        # 1. Druck am Ventil berechnen (vorwärts)
        q_c_ms = (q_c_total_calc / 1000.0) / 3600.0
        if area_drossel_m2 > 0:
            p_vor_ventil_pa = (rho / 2.0) * (q_c_ms / (c_d * area_drossel_m2))**2
            p_vor_ventil = p_vor_ventil_pa / 100000.0
        else:
            p_vor_ventil = 999.0
            
        p_t_stueck_avg = p_vor_ventil + calc_dp(q_c_total_calc, hydraulik['k_out'])
        
        p_back_main = calc_dp(total_permeat_guess, hydraulik['p_out']) + calc_dp(total_permeat_guess, hydraulik['p_schlauch']) + (hydraulik['p_schlauch'].get('h', 0.0) * 0.0981)
        
        q_p_total_calc = 0
        r_eff_list = []
        membran_daten_temp = []
        max_spacer_dp = 0
        total_permeat_salzfracht = 0
        q_p_branch_calc_list = []
        max_p_feed_needed = 0

        for i in range(anzahl_membranen):
            f_in = max(0.001, q_feed_total * flow_fractions[i])
            
            # Da wir von hinten (Ventil) nach vorne rechnen, addieren wir die Drücke auf
            p_verlust_konz = calc_dp(max(0.001, f_in - q_p_branch_guess[i]), hydraulik['k_zweige'][i])
            p_local = p_t_stueck_avg + p_verlust_konz
            
            flow_local = f_in
            tds_hard_local = tds_feed * frac_hard
            tds_light_local = tds_feed * frac_light
            
            q_p_sum_branch = 0
            salzfracht_sum_branch = 0
            p_drop_spacer_total = 0
            
            p_back_branch = calc_dp(q_p_branch_guess[i], hydraulik['p_zweige'][i])
            p_back_total = p_back_main + p_back_branch

            # Rückwärts durch die Segmente (Näherung)
            for j in range(n_seg):
                q_p_seg = flow_local * 0.1 
                for _ in range(3):
                    q_c_seg = max(0.001, flow_local - q_p_seg)
                    
                    tds_hard_c_temp = ((flow_local * tds_hard_local) - (q_p_seg * (tds_hard_local * pass_hard))) / q_c_seg if q_c_seg > 0 else tds_hard_local
                    tds_light_c_temp = ((flow_local * tds_light_local) - (q_p_seg * (tds_light_local * pass_light))) / q_c_seg if q_c_seg > 0 else tds_light_local
                    
                    cp_factor = berechne_cp_faktor(q_p_seg, flow_local, q_c_seg, temp, m_flaeche, area_seg)
                    tds_wall = min(((tds_hard_local + tds_hard_c_temp)/2.0 + (tds_light_local + tds_light_c_temp)/2.0) * cp_factor, 150000.0)
                    
                    pi_wall = berechne_osmotischen_druck(tds_wall, temp)
                    
                    p_verlust_spacer_j = berechne_spacer_dp_segment(flow_local, q_c_seg, temp, n_seg)
                    p_eff_mitte = p_local + (p_verlust_spacer_j / 2) # Wir gehen stromaufwärts!
                    
                    ndp = max(0.0, p_eff_mitte - pi_wall - p_back_total)
                    q_p_target_j = area_seg * a_wert * ndp * tcf_real
                    q_p_seg = q_p_seg * 0.5 + q_p_target_j * 0.5
                    if q_p_seg >= flow_local: q_p_seg = flow_local * 0.99

                q_p_sum_branch += q_p_seg
                salzfracht_sum_branch += (q_p_seg * tds_wall * (pass_hard + pass_light)/2) # Vereinfachte Mischung
                p_drop_spacer_total += p_verlust_spacer_j
                
                flow_local -= q_p_seg
                p_local += p_verlust_spacer_j # Stromaufwärts
                
            q_p_total_calc += q_p_sum_branch
            q_p_branch_calc_list.append(q_p_sum_branch)
            total_permeat_salzfracht += salzfracht_sum_branch
            if p_drop_spacer_total > max_spacer_dp: max_spacer_dp = p_drop_spacer_total
            
            p_verlust_feed = sum([calc_dp(f_in * seg['flow_factor'], seg) for seg in hydraulik['feed_pfade'][i]])
            p_start_branch = p_local + p_verlust_feed
            if p_start_branch > max_p_feed_needed: max_p_feed_needed = p_start_branch
            
            p_drop_branch = p_verlust_feed + p_drop_spacer_total + p_verlust_konz
            q_ms_f_in = (f_in / 1000) / 3600
            r_eff = p_drop_branch / (q_ms_f_in**2) if q_ms_f_in > 0 else 1e9
            r_eff_list.append(r_eff)
            
            permeate_tds_branch = salzfracht_sum_branch / q_p_sum_branch if q_p_sum_branch > 0 else 0
            
            membran_daten_temp.append({
                "Membran": membran_namen[i],
                "Eingangsdruck (bar)": round(p_local, 2),
                "Flux (LMH)": round(q_p_sum_branch / m_flaeche, 1),
                "Permeat (l/h)": round(q_p_sum_branch, 1),
                "Gegendruck (bar)": round(p_back_total, 3),
                "Konzentrat (l/h)": round(flow_local, 1),
                "Feed TDS (ppm)": round(tds_feed, 0),
                "Permeat TDS (ppm)": round(permeate_tds_branch, 1),
                "Konz. TDS (ppm)": round(tds_feed * 1.5, 0), # Näherung für UI
                "Feed µS/cm": round(tds_feed / 0.6, 0),
                "Permeat µS/cm": round(permeate_tds_branch / 0.6, 1),
                "Konz. µS/cm": round((tds_feed * 1.5) / 0.6, 0)
            })

        total_permeat_guess = q_p_total_calc
        q_p_branch_guess = q_p_branch_calc_list
        sum_c = sum(1.0 / math.sqrt(r) for r in r_eff_list)
        flow_fractions = [(1.0 / math.sqrt(r)) / sum_c for r in r_eff_list]

    p_verlust_saug = calc_dp(q_feed_total, hydraulik['saug'])
    p_verlust_druck_haupt = calc_dp(q_feed_total, hydraulik['druck_haupt'])
    p_pumpe_real = max_p_feed_needed + p_verlust_druck_haupt
    
    # Sicherheits-Check: Schafft die Pumpe diesen Druck überhaupt?
    error_msg = None
    if p_pumpe_real > pump_max_druck:
        error_msg = f"Achtung: Systemwiderstand ({p_pumpe_real:.1f} bar) übersteigt den Abschaltdruck der Pumpe ({pump_max_druck} bar)! Das Bypass-Ventil der Pumpe öffnet sich. Bitte Drossel weiter öffnen."

    avg_permeat_tds = total_permeat_salzfracht / q_p_total_calc if q_p_total_calc > 0 else 0
    final_konzentrat_tds = (q_feed_total * tds_feed - total_permeat_salzfracht) / q_c_total_calc if q_c_total_calc > 0 else tds_feed

    return {
        "error": error_msg,
        "q_feed_start_lh": q_feed_total,
        "total_permeat": q_p_total_calc,
        "total_permeat_tds": avg_permeat_tds,
        "final_konzentrat_tds": final_konzentrat_tds,
        "end_konzentrat_flow": q_c_total_calc,
        "max_spacer_dp": max_spacer_dp,
        "membran_daten": membran_daten_temp,
        "p_verlust_saug": p_verlust_saug,
        "p_verlust_druck_haupt": p_verlust_druck_haupt,
        "p_effektiv_start": max_p_feed_needed,
        "konzentrat_druck_verlauf": p_vor_ventil,
        "abzubauender_druck": p_vor_ventil,
        "empfohlene_drossel_mm": drossel_vorgabe_mm,
        "realer_pumpendruck": p_pumpe_real 
    }
