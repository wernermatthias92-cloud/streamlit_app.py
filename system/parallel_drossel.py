import math
from membrane.modell import berechne_tcf, berechne_tcf_salz, berechne_a_wert, berechne_osmotischen_druck, berechne_cp_faktor
from hydraulik.widerstand import berechne_hydraulischen_widerstand, berechne_spacer_dp_segment, get_dichte_wasser

def berechne_drossel_druckabfall(flow_lh, drossel_mm, temp_c):
    if flow_lh <= 0.001 or drossel_mm <= 0: return 9999.0 
    q_ms = (flow_lh / 1000) / 3600
    d_m = drossel_mm / 1000.0
    area_m2 = math.pi * (d_m / 2)**2
    c_d = 0.71 
    rho = get_dichte_wasser(temp_c)
    
    term = q_ms / (c_d * area_m2)
    delta_p_pa = (term**2) * (rho / 2.0)
    return delta_p_pa / 100000.0

def berechne_pumpendruck(flow_lh, p_max, q_max):
    if flow_lh >= q_max: return 0.0
    return p_max * (1.0 - (flow_lh / q_max)**2)

def simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow,
                               m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus,
                               pumpen_modus, p_max, q_max, p_zulauf, p_fix):
    
    membran_namen = hydraulik['membran_namen']
    anzahl_membranen = len(membran_namen)
    if anzahl_membranen == 0: return {"error": "Keine Membranen gefunden."}

    tcf_real = berechne_tcf(temp)
    tcf_salz = berechne_tcf_salz(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck, m_test_tds)
    salzdurchgang_basis = 1.0 - m_rueckhalt

    if trocken_modus:
        a_wert *= 1.15
        salzdurchgang_basis = 1.0 - max(0.0, (m_rueckhalt - 0.025))

    salzdurchgang_real = salzdurchgang_basis * tcf_salz
    
    def calc_dp(flow_lh, cfg):
        if flow_lh <= 0 or cfg.get('l', 0) <= 0: return 0.0
        r_val = berechne_hydraulischen_widerstand(flow_lh, cfg['d'], cfg['l'], temp, bögen=cfg.get('b', 0))
        q_ms = (flow_lh / 1000.0) / 3600.0
        return (r_val * q_ms**2) / 100000.0
            
    feed_min = 5.0
    feed_max = 30000.0 if pumpen_modus == "Gemessenen Druck eintragen (Manometer)" else min(30000.0, q_max * 0.99) 
    best_result = {"error": "Solver konnte kein Gleichgewicht finden."}
    
    n_seg = 10
    area_seg = m_flaeche / n_seg
    flow_fractions = [1.0 / anzahl_membranen] * anzahl_membranen
    
    q_p_matrix = [[(200.0 / anzahl_membranen) / n_seg] * n_seg for _ in range(anzahl_membranen)]
    tds_p_matrix = [[tds_feed * salzdurchgang_real] * n_seg for _ in range(anzahl_membranen)]
    q_p_array = [0] * anzahl_membranen
    tds_p_array = [0] * anzahl_membranen
    
    max_spacer_dp = 0

    for iteration in range(60): 
        if abs(feed_max - feed_min) < 0.01:
            break
            
        q_feed_start_lh = (feed_min + feed_max) / 2
        
        if pumpen_modus == "Gemessenen Druck eintragen (Manometer)":
            p_aktuell = p_fix
            p_verlust_saug = 0.0
        else:
            p_verlust_saug = calc_dp(q_feed_start_lh, hydraulik['saug'])
            p_vor_pumpe = max(0.0, p_zulauf - p_verlust_saug)
            p_pumpen_boost = berechne_pumpendruck(q_feed_start_lh, p_max, q_max)
            p_aktuell = p_vor_pumpe + p_pumpen_boost
        
        p_verlust_druck_haupt = calc_dp(q_feed_start_lh, hydraulik['druck_haupt'])
        p_split = p_aktuell - p_verlust_druck_haupt
        
        if p_split <= 0.5:
            feed_max = q_feed_start_lh
            continue

        # --- NEU: INNERE STABILISIERUNGSSCHLEIFE FÜR DIE MEMBRANSCHEIBEN ---
        for inner_iter in range(10):
            total_permeat = sum(sum(m) for m in q_p_matrix)
            p_back_main = calc_dp(total_permeat, hydraulik['p_out']) + calc_dp(total_permeat, hydraulik['p_schlauch']) + (hydraulik['p_schlauch'].get('h', 0.0) * 0.0981)
            
            r_eff_list = []
            p_nach_zweigen = []
            membran_daten_temp = []
            total_permeat_salzfracht = 0
            max_spacer_dp = 0

            for i in range(anzahl_membranen):
                f_in = max(0.001, q_feed_start_lh * flow_fractions[i])
                
                p_verlust_feed = 0.0
                for seg in hydraulik['feed_pfade'][i]:
                    seg_flow = f_in * seg['flow_factor']
                    p_verlust_feed += calc_dp(seg_flow, seg)
                    
                p_in_j = p_split - p_verlust_feed
                f_in_j = f_in
                tds_in_j = tds_feed
                
                q_p_sum = 0
                salzfracht_sum = 0
                p_drop_spacer_total = 0
                
                p_back_branch = calc_dp(sum(q_p_matrix[i]), hydraulik['p_zweige'][i])
                p_back_total = p_back_main + p_back_branch

                for j in range(n_seg):
                    q_p_j = q_p_matrix[i][j]
                    tds_p_j = tds_p_matrix[i][j]
                    
                    if q_p_j > f_in_j * 0.95: q_p_j = f_in_j * 0.95 
                    
                    q_c_j = max(0.001, f_in_j - q_p_j)
                    tds_c_temp = ((f_in_j * tds_in_j) - (q_p_j * tds_p_j)) / q_c_j
                    tds_avg = (tds_in_j + tds_c_temp) / 2.0
                    
                    cp_factor = berechne_cp_faktor(q_p_j, f_in_j, q_c_j, temp, m_flaeche, area_seg)
                    tds_wall = min(tds_avg * cp_factor, 150000.0) 
                    
                    tds_p_target = tds_wall * salzdurchgang_real
                    tds_p_matrix[i][j] = tds_p_j * 0.5 + tds_p_target * 0.5
                    
                    p_verlust_spacer_j = berechne_spacer_dp_segment(f_in_j, q_c_j, temp, n_seg)
                    p_eff_mitte = p_in_j - (p_verlust_spacer_j / 2)
                    
                    pi_wall = berechne_osmotischen_druck(tds_wall, temp)
                    
                    ndp = max(0.0, p_eff_mitte - pi_wall - p_back_total)
                    
                    q_p_target_j = area_seg * a_wert * ndp * tcf_real 
                    
                    q_p_j_neu = q_p_j * 0.5 + q_p_target_j * 0.5
                    if q_p_j_neu > f_in_j * 0.95: q_p_j_neu = f_in_j * 0.95 
                    
                    q_p_matrix[i][j] = q_p_j_neu
                    q_p_sum += q_p_j_neu
                    salzfracht_sum += (q_p_j_neu * tds_p_matrix[i][j])
                    p_drop_spacer_total += p_verlust_spacer_j
                    
                    f_in_neu = max(0.001, f_in_j - q_p_j_neu)
                    tds_in_j = ((f_in_j * tds_in_j) - (q_p_j_neu * tds_p_matrix[i][j])) / f_in_neu
                    f_in_j = f_in_neu
                    p_in_j -= p_verlust_spacer_j
                    
                q_p_array[i] = q_p_sum
                q_c = f_in_j
                tds_p_array[i] = salzfracht_sum / q_p_sum if q_p_sum > 0 else 0
                
                if p_drop_spacer_total > max_spacer_dp: max_spacer_dp = p_drop_spacer_total
                
                p_verlust_konz = calc_dp(q_c, hydraulik['k_zweige'][i])
                p_nach_zweigen.append(p_in_j - p_verlust_konz)
                
                p_drop_branch = p_verlust_feed + p_drop_spacer_total + p_verlust_konz
                q_ms_f_in = (f_in / 1000) / 3600
                r_eff = p_drop_branch / (q_ms_f_in**2) if q_ms_f_in > 0 else 1e9
                r_eff_list.append(r_eff)
                
                # Nur im letzten Durchlauf der inneren Schleife die Daten für das UI speichern
                if inner_iter == 9:
                    tds_c = tds_in_j 
                    total_permeat_salzfracht += salzfracht_sum
                    flux_lmh = q_p_sum / m_flaeche
                    membran_daten_temp.append({
                        "Membran": membran_namen[i],
                        "Eingangsdruck (bar)": round(p_split - p_verlust_feed, 2),
                        "Flux (LMH)": round(flux_lmh, 1),
                        "Permeat (l/h)": round(q_p_sum, 1),
                        "Gegendruck (bar)": round(p_back_total, 3),
                        "Konzentrat (l/h)": round(q_c, 1),
                        "Feed TDS (ppm)": round(tds_feed, 0),
                        "Permeat TDS (ppm)": round(tds_p_array[i], 1),
                        "Konz. TDS (ppm)": round(tds_c, 0)
                    })

            sum_c = sum(1.0 / math.sqrt(r) for r in r_eff_list)
            flow_fractions = [(1.0 / math.sqrt(r)) / sum_c for r in r_eff_list]
        
        # --- ENDE INNERE SCHLEIFE ---

        total_permeat = sum(q_p_array)
        end_konzentrat_flow = max(0.001, q_feed_start_lh - total_permeat)
        p_t_stueck_konz = sum(p_nach_zweigen) / anzahl_membranen
        
        p_vor_ventil = p_t_stueck_konz - calc_dp(end_konzentrat_flow, hydraulik['k_out'])
        p_verlust_drossel = berechne_drossel_druckabfall(end_konzentrat_flow, drossel_vorgabe_mm, temp)
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
