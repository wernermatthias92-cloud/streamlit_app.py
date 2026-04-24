import math
from membrane.modell import berechne_tcf, berechne_tcf_salz, berechne_a_wert, berechne_osmotischen_druck, berechne_cp_faktor
from hydraulik.widerstand import empfehle_drossel_durchmesser, berechne_hydraulischen_widerstand, berechne_spacer_dp_segment, get_dichte_wasser

def simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow,
                       m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, p_system):
    
    tcf_real = berechne_tcf(temp)
    tcf_salz = berechne_tcf_salz(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck, m_test_tds)
    
    salzdurchgang_basis = 1.0 - m_rueckhalt
    if trocken_modus:
        a_wert *= 1.15                
        salzdurchgang_basis = 1.0 - max(0.0, (m_rueckhalt - 0.025))

    salzdurchgang_real = salzdurchgang_basis * tcf_salz

    membran_namen = hydraulik['membran_namen']
    anzahl_membranen = len(membran_namen)
    if anzahl_membranen == 0:
        return {"error": "Keine Membranen im System definiert."}

    def calc_dp(flow_lh, cfg):
        if flow_lh <= 0 or cfg.get('l', 0) <= 0: return 0.0
        r_val = berechne_hydraulischen_widerstand(flow_lh, cfg['d'], cfg['l'], temp, bögen=cfg.get('b', 0))
        q_ms = (flow_lh / 1000.0) / 3600.0
        return (r_val * q_ms**2) / 100000.0

    q_min = 1.0
    q_max = 20000.0 
    
    n_seg = 10
    area_seg = m_flaeche / n_seg
    flow_fractions = [1.0 / anzahl_membranen] * anzahl_membranen

    for outer_it in range(5):
        total_permeat_guess = 200.0
        
        for bisection_it in range(60):
            q_feed_guess = (q_min + q_max) / 2.0
            p_verlust_saug = calc_dp(q_feed_guess, hydraulik['saug']) 
            p_verlust_druck_haupt = calc_dp(q_feed_guess, hydraulik['druck_haupt'])
            p_split = p_system - p_verlust_druck_haupt
            
            if p_split <= 0.1:
                q_max = q_feed_guess
                continue

            p_back_main = calc_dp(total_permeat_guess, hydraulik['p_out']) + calc_dp(total_permeat_guess, hydraulik['p_schlauch']) + (hydraulik['p_schlauch'].get('h', 0.0) * 0.0981)
            
            q_c_total_calc = 0
            q_p_total_calc = 0
            p_t_stueck_sum = 0
            r_eff_list = []
            membran_daten_temp = []
            max_spacer_dp = 0
            total_permeat_salzfracht = 0

            for i in range(anzahl_membranen):
                f_in = max(0.001, q_feed_guess * flow_fractions[i])
                p_verlust_feed = sum([calc_dp(f_in * seg['flow_factor'], seg) for seg in hydraulik['feed_pfade'][i]])
                
                p_local = p_split - p_verlust_feed
                flow_local = f_in
                tds_local = tds_feed
                
                q_p_sum_branch = 0
                salzfracht_sum_branch = 0
                p_drop_spacer_total = 0
                
                p_back_branch = calc_dp(total_permeat_guess / anzahl_membranen, hydraulik['p_zweige'][i])
                p_back_total = p_back_main + p_back_branch

                for j in range(n_seg):
                    q_p_seg = flow_local * 0.1 
                    for _ in range(5):
                        q_c_seg = max(0.001, flow_local - q_p_seg)
                        tds_c_temp = ((flow_local * tds_local) - (q_p_seg * (tds_local * salzdurchgang_real))) / q_c_seg if q_c_seg > 0 else tds_local
                        tds_avg = (tds_local + tds_c_temp) / 2.0
                        
                        cp_factor = berechne_cp_faktor(q_p_seg, flow_local, q_c_seg, temp, m_flaeche, area_seg)
                        tds_wall = min(tds_avg * cp_factor, 150000.0)
                        tds_p_target = tds_wall * salzdurchgang_real
                        
                        p_verlust_spacer_j = berechne_spacer_dp_segment(flow_local, q_c_seg, temp, n_seg)
                        p_eff_mitte = p_local - (p_verlust_spacer_j / 2)
                        pi_wall = berechne_osmotischen_druck(tds_wall, temp)
                        
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
                    tds_local = ((flow_local + q_p_seg) * tds_local - q_p_seg * tds_p_target) / flow_local

                q_c_total_calc += flow_local
                q_p_total_calc += q_p_sum_branch
                total_permeat_salzfracht += salzfracht_sum_branch
                if p_drop_spacer_total > max_spacer_dp: max_spacer_dp = p_drop_spacer_total
                
                p_verlust_konz = calc_dp(flow_local, hydraulik['k_zweige'][i])
                p_t_stueck_sum += (p_local - p_verlust_konz)
                
                p_drop_branch = p_verlust_feed + p_drop_spacer_total + p_verlust_konz
                q_ms_f_in = (f_in / 1000) / 3600
                r_eff = p_drop_branch / (q_ms_f_in**2) if q_ms_f_in > 0 else 1e9
                r_eff_list.append(r_eff)
                
                membran_daten_temp.append({
                    "Membran": membran_namen[i],
                    "Eingangsdruck (bar)": round(p_split - p_verlust_feed, 2),
                    "Flux (LMH)": round(q_p_sum_branch / m_flaeche, 1),
                    "Permeat (l/h)": round(q_p_sum_branch, 1),
                    "Gegendruck (bar)": round(p_back_total, 3),
                    "Konzentrat (l/h)": round(flow_local, 1),
                    "Feed TDS (ppm)": round(tds_feed, 0),
                    "Permeat TDS (ppm)": round(salzfracht_sum_branch / q_p_sum_branch if q_p_sum_branch > 0 else 0, 1),
                    "Konz. TDS (ppm)": round(tds_local, 0)
                })

            total_permeat_guess = q_p_total_calc
            ausbeute_calc = (q_p_total_calc / q_feed_guess) * 100.0

            # Abgleich: Ist die Ausbeute zu hoch, müssen wir den Fluss erhöhen (Druckabfall steigt -> Ausbeute sinkt)
            if ausbeute_calc > ausbeute_pct:
                q_min = q_feed_guess
            else:
                q_max = q_feed_guess

            if abs(q_max - q_min) < 0.5:
                break

        sum_c = sum(1.0 / math.sqrt(r) for r in r_eff_list)
        flow_fractions = [(1.0 / math.sqrt(r)) / sum_c for r in r_eff_list]

    avg_permeat_tds = total_permeat_salzfracht / q_p_total_calc if q_p_total_calc > 0 else 0
    final_konzentrat_tds = (q_feed_guess * tds_feed - total_permeat_salzfracht) / q_c_total_calc if q_c_total_calc > 0 else tds_feed
    p_t_stueck_avg = p_t_stueck_sum / anzahl_membranen
    p_vor_ventil = p_t_stueck_avg - calc_dp(q_c_total_calc, hydraulik['k_out'])

    abzubauender_druck = max(0.1, p_vor_ventil - 0.5)
    empfohlene_drossel_mm = empfehle_drossel_durchmesser(q_c_total_calc, abzubauender_druck, temp)

    return {
        "error": None,
        "q_feed_start_lh": q_feed_guess,
        "total_permeat": q_p_total_calc,
        "total_permeat_tds": avg_permeat_tds,
        "final_konzentrat_tds": final_konzentrat_tds,
        "end_konzentrat_flow": q_c_total_calc,
        "max_spacer_dp": max_spacer_dp,
        "membran_daten": membran_daten_temp,
        "p_verlust_saug": p_verlust_saug,
        "p_verlust_druck_haupt": p_verlust_druck_haupt,
        "p_effektiv_start": p_split,
        "konzentrat_druck_verlauf": max(0.0, p_vor_ventil),
        "abzubauender_druck": abzubauender_druck,
        "empfohlene_drossel_mm": empfohlene_drossel_mm
    }
