import math
from membrane.modell import berechne_tcf, berechne_tcf_salz, berechne_a_wert
from hydraulik.widerstand import empfehle_drossel_durchmesser

def simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow,
                       m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, p_system):
    
    tcf_real = berechne_tcf(temp)
    tcf_salz = berechne_tcf_salz(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck, m_test_tds)
    
    salzdurchgang_basis = 1.0 - m_rueckhalt
    salzdurchgang_real = salzdurchgang_basis * tcf_salz

    membran_namen = hydraulik['membran_namen']
    anzahl_membranen = len(membran_namen)
    if anzahl_membranen == 0:
        return {"error": "Keine Membranen im System definiert."}

    ndp_approx = p_system - ((tds_feed / 100) * 0.07) - 0.5
    q_p_total_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0.1, ndp_approx) * tcf_real * 1000
    q_feed_start_lh = q_p_total_approx / (ausbeute_pct / 100) if ausbeute_pct > 0 else q_p_total_approx * 2

    flow_fractions = [1.0 / anzahl_membranen] * anzahl_membranen
    q_p_array = [q_p_total_approx / anzahl_membranen] * anzahl_membranen
    tds_p_array = [tds_feed * salzdurchgang_real] * anzahl_membranen
    
    max_spacer_dp = 0

    for iteration in range(40):
        q_ms_feed = (q_feed_start_lh / 1000) / 3600
        p_verlust_saug = (hydraulik['r_saug'] * q_ms_feed**2) / 100000 
        p_verlust_druck_haupt = (hydraulik['r_druck_haupt'] * q_ms_feed**2) / 100000
        p_split = p_system - p_verlust_druck_haupt
        
        total_permeat = sum(q_p_array)
        q_ms_p_total = (total_permeat / 1000) / 3600
        p_back_main = (hydraulik['r_p_out'] + hydraulik['r_p_schlauch']) * q_ms_p_total**2 / 100000 + hydraulik['p_back_height']
        
        r_eff_list = [] 
        max_spacer_dp = 0
        
        for i in range(anzahl_membranen):
            f_in = max(0.001, q_feed_start_lh * flow_fractions[i])
            q_p = q_p_array[i]
            tds_p = tds_p_array[i]
            
            if q_p > f_in * 0.95: q_p = f_in * 0.95
            
            q_c = max(0.001, f_in - q_p)
            recovery = q_p / f_in
            
            tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c
            tds_avg = (tds_feed + tds_c_temp) / 2
            cp_factor = math.exp(0.7 * recovery) 
            tds_wall = tds_avg * cp_factor
            
            tds_p_target = tds_wall * salzdurchgang_real
            tds_p_array[i] = tds_p * 0.5 + tds_p_target * 0.5
            
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
            q_p_array[i] = q_p * 0.5 + q_p_target * 0.5
            
            q_ms_c_i = (q_c / 1000) / 3600
            p_verlust_konz = (hydraulik['r_k_zweige'][i] * q_ms_c_i**2) / 100000
            
            p_drop_branch = p_verlust_feed + p_verlust_spacer + p_verlust_konz
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
        q_c = f_in - q_p
        tds_p = tds_p_array[i]
        tds_c = ((f_in * tds_feed) - (q_p * tds_p)) / q_c if q_c > 0 else tds_feed
        total_permeat_salzfracht += (q_p * tds_p)
        
        q_ms_f_in = (f_in / 1000) / 3600
        p_in = p_split - (hydraulik['r_feed_pfade'][i] * q_ms_f_in**2) / 100000
        p_back = p_back_main + (hydraulik['r_p_zweige'][i] * ((q_p/1000)/3600)**2) / 100000
        p_spacer = 0.2 * (f_in / 1000)**1.5
        p_konz = (hydraulik['r_k_zweige'][i] * ((q_c/1000)/3600)**2) / 100000
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
    end_konzentrat_flow = q_feed_start_lh - total_permeat
    final_konzentrat_tds = (q_feed_start_lh * tds_feed - total_permeat_salzfracht) / end_konzentrat_flow if end_konzentrat_flow > 0 else tds_feed

    p_t_stueck_konz = sum(p_nach_zweigen) / anzahl_membranen
    q_ms_c_total = (end_konzentrat_flow / 1000) / 3600
    p_vor_ventil = p_t_stueck_konz - (hydraulik['r_k_out'] * q_ms_c_total**2) / 100000

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
        "empfohlene_drossel_mm": empfehle_drossel_mm
    }
