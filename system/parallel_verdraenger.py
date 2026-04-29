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

    # Feed ist bei Verdrängerpumpen stur und fix!
    q_feed_total = pump_fest_flow
    c_d = 0.71
    area_drossel_m2 = math.pi * ((drossel_vorgabe_mm / 1000.0) / 2)**2
    rho = get_dichte_wasser(temp)
    n_seg = 10
    area_seg = m_flaeche / n_seg
    flow_fractions = [1.0 / anzahl_membranen] * anzahl_membranen
    
    q_p_branch_guess = [q_feed_total * 0.4 / anzahl_membranen] * anzahl_membranen
    total_permeat_guess = sum(q_p_branch_guess)

    for outer_it in range(15):
        p_min = 0.1
        p_max = 25.0 # Wir suchen den Systemdruck bis 25 bar
        
        final_q_c_total_calc = 0
        final_p_t_stueck_list = []
        final_r_eff_list = []
        final_q_p_total_calc = 0
        final_q_p_branch_calc_list = []
        
        # Statt q_feed iterieren wir hier den Druck (p_aktuell_guess)
        for bisection_it in range(60): 
            p_aktuell_guess = (p_min + p_max) / 2.0
            
            p_split = p_aktuell_guess - calc_dp(q_feed_total, hydraulik['druck_haupt'])
            
            if p_split <= 0.1:
                p_min = p_aktuell_guess
                continue

            p_back_main = calc_dp(total_permeat_guess, hydraulik['p_out']) + calc_dp(total_permeat_guess, hydraulik['p_schlauch']) + (hydraulik['p_schlauch'].get('h', 0.0) * 0.0981)
            
            q_c_total_calc = 0
            q_p_total_calc = 0
            p_t_stueck_list = []
            r_eff_list = []
            membran_daten_temp = []
            max_spacer_dp = 0
            total_permeat_salzfracht = 0
            
            q_p_branch_calc_list = []

            for i in range(anzahl_membranen):
                f_in = max(0.001, q_feed_total * flow_fractions[i])
                p_verlust_feed = sum([calc_dp(f_in * seg['flow_factor'], seg) for seg in hydraulik['feed_pfade'][i]])
                
                p_local = p_split - p_verlust_feed
                flow_local = f_in
                
                tds_hard_local = tds_feed * frac_hard
                tds_light_local = tds_feed * frac_light
                
                q_p_sum_branch = 0
                salzfracht_sum_branch = 0
                p_drop_spacer_total = 0
                
                p_back_branch = calc_dp(q_p_branch_guess[i], hydraulik['p_zweige'][i])
                p_back_total = p_back_main + p_back_branch

                for j in range(n_seg):
                    q_p_seg = flow_local * 0.1 
                    for _ in range(5):
                        q_c_seg = max(0.001, flow_local - q_p_seg)
                        
                        tds_hard_c_temp = ((flow_local * tds_hard_local) - (q_p_seg * (tds_hard_local * pass_hard))) / q_c_seg if q_c_seg > 0 else tds_hard_local
                        tds_light_c_temp = ((flow_local * tds_light_local) - (q_p_seg * (tds_light_local * pass_light))) / q_c_seg if q_c_seg > 0 else tds_light_local
                        
                        tds_hard_avg = (tds_hard_local + tds_hard_c_temp) / 2.0
                        tds_light_avg = (tds_light_local + tds_light_c_temp) / 2.0
                        
                        cp_factor = berechne_cp_faktor(q_p_seg, flow_local, q_c_seg, temp, m_flaeche, area_seg)
                        
                        tds_hard_wall = min(tds_hard_avg * cp_factor, 150000.0)
                        tds_light_wall = min(tds_light_avg * cp_factor, 150000.0)
                        
                        tds_p_target_hard = tds_hard_wall * pass_hard
                        tds_p_target_light = tds_light_wall * pass_light
                        tds_p_target = tds_p_target_hard + tds_p_target_light
                        
                        p_verlust_spacer_j = berechne_spacer_dp_segment(flow_local, q_c_seg, temp, n_seg)
                        p_eff_mitte = p_local - (p_verlust_spacer_j / 2)
                        
                        pi_wall = berechne_osmotischen_druck(tds_hard_wall + tds_light_wall, temp)
                        
                        ndp = max(0.0, p_eff_mitte - pi_wall - p_back_total)
                        q_p_target_j = area_seg * a_wert * ndp * tcf_real
                        q_p_seg = q_p_seg * 0.5 + q_p_target_j * 0.5
                        if q_p_seg >= flow_local: q_p_seg = flow_local * 0.99

                    q_p_sum_branch += q_p_seg
                    salzfracht_sum_branch += (q_p_seg * tds_p_target)
                    p_drop_spacer_total += p_verlust_spacer_j
                    
                    flow_local -= q_p_seg
                    p_local -= p_verlust_spacer_j
                    if flow_local <= 0.001: 
                        flow_local = 0.001
                        break
                    
                    tds_hard_local = ((flow_local + q_p_seg) * tds_hard_local - q_p_seg * tds_p_target_hard) / flow_local
                    tds_light_local = ((flow_local + q_p_seg) * tds_light_local - q_p_seg * tds_p_target_light) / flow_local

                q_c_total_calc += flow_local
                q_p_total_calc += q_p_sum_branch
                q_p_branch_calc_list.append(q_p_sum_branch)
                total_permeat_salzfracht += salzfracht_sum_branch
                if p_drop_spacer_total > max_spacer_dp: max_spacer_dp = p_drop_spacer_total
                
                p_verlust_konz = calc_dp(flow_local, hydraulik['k_zweige'][i])
                p_t_stueck_list.append(p_local - p_verlust_konz)
                
                p_drop_branch = p_verlust_feed + p_drop_spacer_total + p_verlust_konz
                q_ms_f_in = (f_in / 1000) / 3600
                r_eff = p_drop_branch / (q_ms_f_in**2) if q_ms_f_in > 0 else 1e9
                r_eff_list.append(r_eff)
                
                tds_local_total = tds_hard_local + tds_light_local
                permeate_tds_branch = salzfracht_sum_branch / q_p_sum_branch if q_p_sum_branch > 0 else 0
                
                membran_daten_temp.append({
                    "Membran": membran_namen[i],
                    "Eingangsdruck (bar)": round(p_split - p_verlust_feed, 2),
                    "Flux (LMH)": round(q_p_sum_branch / m_flaeche, 1),
                    "Permeat (l/h)": round(q_p_sum_branch, 1),
                    "Gegendruck (bar)": round(p_back_total, 3),
                    "Konzentrat (l/h)": round(flow_local, 1),
                    "Feed TDS (ppm)": round(tds_feed, 0),
                    "Permeat TDS (ppm)": round(permeate_tds_branch, 1),
                    "Konz. TDS (ppm)": round(tds_local_total, 0),
                    "Feed µS/cm": round(tds_feed / 0.6, 0),
                    "Permeat µS/cm": round(permeate_tds_branch / 0.6, 1),
                    "Konz. µS/cm": round(tds_local_total / 0.6, 0)
                })

            p_vor_ventil = max(p_t_stueck_list) - calc_dp(q_c_total_calc, hydraulik['k_out'])

            if p_vor_ventil <= 0.0:
                p_min = p_aktuell_guess
                continue

            v_theo = math.sqrt(2 * (p_vor_ventil * 100000.0) / rho)
            q_c_throttle = c_d * area_drossel_m2 * v_theo * 3600.0 * 1000.0

            final_q_c_total_calc = q_c_total_calc
            final_p_t_stueck_list = p_t_stueck_list
            final_r_eff_list = r_eff_list
            final_q_p_total_calc = q_p_total_calc
            final_q_p_branch_calc_list = q_p_branch_calc_list

            # Wenn das Konzentrat nicht durch die Drossel passt, brauchen wir mehr Druck!
            if q_c_total_calc > q_c_throttle:
                p_min = p_aktuell_guess  
            else:
                p_max = p_aktuell_guess  

            if abs(p_max - p_min) < 0.01:
                break

        total_permeat_guess = final_q_p_total_calc
        q_p_branch_guess = final_q_p_branch_calc_list
        
        sum_c = sum(1.0 / math.sqrt(r) for r in final_r_eff_list)
        flow_fractions = [(1.0 / math.sqrt(r)) / sum_c for r in final_r_eff_list]

    p_verlust_saug = calc_dp(q_feed_total, hydraulik['saug'])
    p_pumpe_real = p_aktuell_guess + p_verlust_saug
    
    error_msg = None
    if p_pumpe_real > pump_max_druck:
        error_msg = f"Achtung: Der errechnete Systemdruck ({p_pumpe_real:.1f} bar) übersteigt den Abschaltdruck der Pumpe ({pump_max_druck} bar)! Die Pumpe schaltet in den Bypass. Bitte Drossel weiter öffnen."

    avg_permeat_tds = total_permeat_salzfracht / final_q_p_total_calc if final_q_p_total_calc > 0 else 0
    final_konzentrat_tds = (q_feed_total * tds_feed - total_permeat_salzfracht) / final_q_c_total_calc if final_q_c_total_calc > 0 else tds_feed

    return {
        "error": error_msg,
        "q_feed_start_lh": q_feed_total,
        "total_permeat": final_q_p_total_calc,
        "total_permeat_tds": avg_permeat_tds,
        "final_konzentrat_tds": final_konzentrat_tds,
        "end_konzentrat_flow": final_q_c_total_calc,
        "max_spacer_dp": max_spacer_dp,
        "membran_daten": membran_daten_temp,
        "p_verlust_saug": p_verlust_saug,
        "p_verlust_druck_haupt": calc_dp(q_feed_total, hydraulik['druck_haupt']),
        "p_effektiv_start": p_split,
        "konzentrat_druck_verlauf": max(0.0, p_vor_ventil),
        "abzubauender_druck": max(0.0, p_vor_ventil),
        "empfohlene_drossel_mm": drossel_vorgabe_mm,
        "realer_pumpendruck": p_pumpe_real 
    }
