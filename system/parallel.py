import math
from membrane.modell import berechne_tcf, berechne_tcf_salz, berechne_a_wert, berechne_osmotischen_druck, berechne_cp_faktor
from hydraulik.widerstand import empfehle_drossel_durchmesser, berechne_hydraulischen_widerstand, berechne_spacer_dp

def simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow,
                       m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, p_system):
    
    tcf_real = berechne_tcf(temp)
    tcf_salz = berechne_tcf_salz(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck, m_test_tds)
    
    salzdurchgang_basis = 1.0 - m_rueckhalt
    if trocken_modus:
        a_wert *= 1.15                
        salzdurchgang_basis = 1.0 - max(0.0, (m_rueckhalt - 0.06))

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

    # Initiale Schätzung
    pi_feed_approx = berechne_osmotischen_druck(tds_feed, temp)
    ndp_approx = p_system - pi_feed_approx - 0.5
    q_p_total_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0.1, ndp_approx) * tcf_real * 1000
    q_feed_start_lh = q_p_total_approx / (ausbeute_pct / 100) if ausbeute_pct > 0 else q_p_total_approx * 2

    flow_fractions = [1.0 / anzahl_membranen] * anzahl_membranen
    q_p_array = [q_p_total_approx / anzahl_membranen] * anzahl_membranen
    tds_p_array = [tds_feed * salzdurchgang_real] * anzahl_membranen
    
    max_spacer_dp = 0

    for iteration in range(40):
        p_verlust_saug = calc_dp(q_feed_start_lh, hydraulik['saug'])
        p_verlust_druck_haupt = calc_dp(q_feed_start_lh, hydraulik['druck_haupt'])
        p_split = p_system - p_verlust_druck_haupt
        
        total_permeat = sum(q_p_array)
        p_back_main = calc_dp(total_permeat, hydraulik['p_out']) + calc_dp(total_permeat, hydraulik['p_schlauch']) + (hydraulik['p_schlauch'].get('h', 0.0) * 0.0981)
        
        r_eff_list = [] 
        max_spacer_dp = 0
        
        for i in range(anzahl_membranen):
            f_in = max(0.001, q_feed_start_lh * flow_fractions[i])
            q_p = q_p_array[i]
            tds_p = tds_p_array[i]
            
            if q_p > f_in * 0.95: q_p = f_in * 0.95
            
            q_c = max(0.001, f_in - q_p)
            
            tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c
            tds_avg = (tds_feed + tds_c_temp) / 2
            
            # 1. NEU: Exakte Filmtheorie anwenden
            cp_factor = berechne_cp_faktor(q_p, f_in, q_c, temp, m_flaeche)
            
            tds_wall = min(tds_avg * cp_factor, 150000.0)
            tds_p_target = tds_wall * salzdurchgang_real
            tds_p_array[i] = tds_p * 0.5 + tds_p_target * 0.5
            
            p_verlust_feed = 0.0
            for seg in hydraulik['feed_pfade'][i]:
                seg_flow = f_in * seg['flow_factor']
                p_verlust_feed += calc_dp(seg_flow, seg)
                
            p_in = p_split - p_verlust_feed
            
            # 2. NEU: Exakter Spacer-Druckverlust mit Viskosität
            p_verlust_spacer = berechne_spacer_dp(f_in, q_c, temp)
            if p_verlust_spacer > max_spacer_dp: max_spacer_dp = p_verlust_spacer
            
            p_effektiv_mitte = p_in - (p_verlust_spacer / 2)
            
            p_back_branch = calc_dp(q_p, hydraulik['p_zweige'][i])
            p_back_total = p_back_main + p_back_branch
            
            # 3. NEU: Exakter osmotischer Druck nach van-'t-Hoff
            pi_wall = berechne_osmotischen_druck(tds_wall, temp)
            
            ndp = max(0.0, p_effektiv_mitte - pi_wall - p_back_total)
            q_p_target = m_flaeche * a_wert * ndp * tcf_real * 1000
            
            q_p_neu = q_p * 0.5 + q_p_target * 0.5
            if q_p_neu > f_in * 0.95: q_p_neu = f_in * 0.95
            q_p_array[i] = q_p_neu
            
            q_c_neu = max(0.001, f_in - q_p_neu)
            p_verlust_konz = calc_dp(q_c_neu, hydraulik['k_zweige'][i])
            
            p_drop_branch = p_verlust_feed + p_verlust_spacer + p_verlust_konz
            q_ms_f_in = (f_in / 1000) / 3600
            r_eff = p_drop_branch / (q_ms_f_in**2) if q_ms_f_in > 0 else 1e9
            r_eff_list.append(r_eff)
            
        sum_c = sum(1.0 / math.sqrt(r) for r in r_eff_list)
        flow_fractions = [(1.0 / math.sqrt(r)) / sum_c for r in r_eff_list]
        
        if ausbeute_pct > 0:
            q_feed_start_lh = sum(q_p_array) / (ausbeute_pct / 100)

    membran_daten = []
    total_permeat_salzfracht = 0
    p_nach_zweigen = []

    for i in range(anzahl_membranen):
        f_in = q_feed_start_lh * flow_fractions[i]
        q_p = q_p_array[i]
        q_c = max(0.001, f_in - q_p)
        tds_p = tds_p_array[i]
        tds_c = ((f_in * tds_feed) - (q_p * tds_p)) / q_c
        total_permeat_salzfracht += (q_p * tds_p)
        
        p_verlust_feed = sum([calc_dp(f_in * seg['flow_factor'], seg) for seg in hydraulik['feed_pfade'][i]])
        p_in = p_split - p_verlust_feed
        
        p_back = p_back_main + calc_dp(q_p, hydraulik['p_zweige'][i])
        p_spacer = berechne_spacer_dp(f_in, q_c, temp)
        p_konz = calc_dp(q_c, hydraulik['k_zweige'][i])
        
        p_nach_zweigen.append(p_in - p_spacer - p_konz)
        flux_lmh = q_p / m_flaeche

        membran_daten.append({
            "Membran": membran_namen[i],
            "Eingangsdruck (bar)": round(p_in, 2),
            "Flux (LMH)": round(flux_lmh, 1),
            "Permeat (l/h)": round(q_p, 1),
            "Gegendruck (bar)": round(p_back, 3),
            "Konzentrat (l/h)": round(q_c, 1),
            "Permeat TDS (ppm)": round(tds_p, 1),
            "Konz. TDS (ppm)": round(tds_c, 0)
        })

    avg_permeat_tds = total_permeat_salzfracht / total_permeat if total_permeat > 0 else 0
    end_konzentrat_flow = max(0.001, q_feed_start_lh - total_permeat)
    final_konzentrat_tds = (q_feed_start_lh * tds_feed - total_permeat_salzfracht) / end_konzentrat_flow

    p_t_stueck_konz = sum(p_nach_zweigen) / anzahl_membranen
    p_vor_ventil = p_t_stueck_konz - calc_dp(end_konzentrat_flow, hydraulik['k_out'])

    abzubauender_druck = max(0.1, p_vor_ventil - 0.5)
    empfohlene_drossel_mm = empfehle_drossel_durchmesser(end_konzentrat_flow, abzubauender_druck)

    return {
        "error": None,
        "q_feed_start_lh": q_feed_start_lh,
        "total_permeat": total_permeat,
        "total_permeat_tds": avg_permeat_tds,
        "final_konzentrat_tds": final_konzentrat_tds,
        "end_konzentrat_flow": end_konzentrat_flow,
        "max_spacer_dp": max_spacer_dp,
        "membran_daten": membran_daten,
        "p_verlust_saug": p_verlust_saug,
        "p_verlust_druck_haupt": p_verlust_druck_haupt,
        "p_effektiv_start": p_split,
        "konzentrat_druck_verlauf": max(0.0, p_vor_ventil),
        "abzubauender_druck": abzubauender_druck,
        "empfohlene_drossel_mm": empfohlene_drossel_mm
    }
