import math
from membrane.modell import berechne_tcf, berechne_a_wert
from hydraulik.widerstand import berechne_hydraulischen_widerstand

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

def simuliere_parallel_drossel(flow_fractions, membran_namen, drossel_vorgabe_mm, m_flaeche, m_test_flow,
                       m_test_druck, m_rueckhalt, tds_feed, temp, p_max, q_max, p_zulauf,
                       r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, 
                       leitungen_konz, leitung_out,
                       p_leitungen_konz, p_leitung_out, p_schlauch_out):
    
    anzahl_membranen = len(flow_fractions)
    if anzahl_membranen == 0: return {"error": "Keine Membranen gefunden."}

    tcf_real = berechne_tcf(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck)

    r_p_out = berechne_hydraulischen_widerstand(p_leitung_out['d'], p_leitung_out['l'], [], p_leitung_out['b']) if p_leitung_out else 0
    r_p_schlauch = berechne_hydraulischen_widerstand(p_schlauch_out['d'], p_schlauch_out['l'], [], 0) if p_schlauch_out else 0
    p_back_height = (p_schlauch_out['h'] * 1000 * 9.81) / 100000 if p_schlauch_out else 0
    
    r_p_branches = []
    if anzahl_membranen > 1 and p_leitungen_konz:
        for p_cfg in p_leitungen_konz:
            r_p_branches.append(berechne_hydraulischen_widerstand(p_cfg['d'], p_cfg['l'], [], p_cfg['b']))
    else:
        r_p_branches = [0] * anzahl_membranen
            
    feed_min = 5.0
    feed_max = min(20000.0, q_max * 0.99) 
    best_result = {"error": "Solver konnte kein Gleichgewicht finden."}

    for iteration in range(60): 
        q_feed_start_lh = (feed_min + feed_max) / 2
        q_ms = (q_feed_start_lh / 1000) / 3600
        
        p_verlust_saug = (r_saug * q_ms**2) / 100000 
        p_vor_pumpe = p_zulauf - p_verlust_saug
        if p_vor_pumpe < 0: p_vor_pumpe = 0 
        
        p_pumpen_boost = berechne_pumpendruck(q_feed_start_lh, p_max, q_max)
        p_aktuell = p_vor_pumpe + p_pumpen_boost
        
        p_verlust_druck_haupt = (r_druck_haupt * q_ms**2) / 100000
        p_verlust_netzwerk = (r_netzwerk * q_ms**2) / 100000 if hat_t_stueck else 0
        p_effektiv_start = p_aktuell - p_verlust_druck_haupt - p_verlust_netzwerk
        
        if p_effektiv_start <= 0.5:
            feed_max = q_feed_start_lh
            continue

        total_permeat = 0
        total_permeat_salzfracht = 0
        membran_daten = []
        
        q_p_approx_total = q_feed_start_lh * 0.4
        q_ms_p = (q_p_approx_total / 1000) / 3600
        p_back_main = ((r_p_out + r_p_schlauch) * q_ms_p**2) / 100000 + p_back_height

        for i in range(anzahl_membranen):
            f_in = q_feed_start_lh * flow_fractions[i]
            r_p_branch = r_p_branches[i] if i < len(r_p_branches) else 0
            
            q_p = (f_in / anzahl_membranen) * 0.5 
            tds_p = tds_feed * (1 - m_rueckhalt)
            
            for _ in range(20):
                if q_p > f_in * 0.95: q_p = f_in * 0.95 
                if q_p < 0: q_p = 0
                
                q_c_temp = f_in - q_p
                recovery = q_p / f_in if f_in > 0 else 0
                
                if q_c_temp <= 0: q_c_temp = 0.001
                tds_c_temp = ((f_in * tds_feed) - (q_p * tds_p)) / q_c_temp
                tds_avg = (tds_feed + tds_c_temp) / 2
                cp_factor = math.exp(0.7 * recovery) 
                tds_wall = tds_avg * cp_factor
                
                tds_p_target = tds_wall * (1 - m_rueckhalt)
                tds_p = tds_p * 0.5 + tds_p_target * 0.5
                
                p_back_branch = (r_p_branch * ((q_p / 1000) / 3600)**2) / 100000
                p_back_total = p_back_main + p_back_branch
                
                p_verlust_modul = 0.2 * (f_in / 1000)**1.5
                p_effektiv_mitte = p_effektiv_start - (p_verlust_modul / 2)
                
                pi_wall = (tds_wall / 100) * 0.07
                ndp = max(0.0, p_effektiv_mitte - pi_wall - p_back_total)
                
                q_p_target = m_flaeche * a_wert * ndp * tcf_real * 1000
                q_p = q_p * 0.5 + q_p_target * 0.5
                
                if q_p > f_in * 0.95: q_p = f_in * 0.95
                
            q_c = f_in - q_p
            if q_c <= 0: q_c = 0.001 
            tds_c = ((f_in * tds_feed) - (q_p * tds_p)) / q_c
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
        if end_konzentrat_flow <= 0: end_konzentrat_flow = 0.001

        p_nach_spacer = p_effektiv_start - 0.2
        if anzahl_membranen == 1:
            if leitung_out:
                r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
                p_vor_ventil = p_nach_spacer - (r_out * ((end_konzentrat_flow/1000)/3600)**2 / 100000)
            else:
                p_vor_ventil = p_nach_spacer
        else:
            p_verluste_zweige = []
            for i, cfg in enumerate(leitungen_konz):
                r_z = berechne_hydraulischen_widerstand(cfg['d'], cfg['l'], [], cfg['b'])
                p_verluste_zweige.append(r_z * ((membran_daten[i]["Konzentrat (l/h)"]/1000)/3600)**2 / 100000)
            p_t_stueck = p_nach_spacer - (max(p_verluste_zweige) if p_verluste_zweige else 0)
            
            if leitung_out:
                r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
                p_vor_ventil = p_t_stueck - (r_out * ((end_konzentrat_flow/1000)/3600)**2 / 100000)
            else:
                p_vor_ventil = p_t_stueck

        p_verlust_drossel = berechne_drossel_druckabfall(end_konzentrat_flow, drossel_vorgabe_mm)
        restdruck_nach_ventil = p_vor_ventil - p_verlust_drossel

        if restdruck_nach_ventil > 0.0:
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
            "konzentrat_druck_verlauf": max(0.0, p_vor_ventil),
            "abzubauender_druck": min(max(0.0, p_vor_ventil), p_verlust_drossel),
            "empfohlene_drossel_mm": drossel_vorgabe_mm,
            "realer_pumpendruck": p_aktuell 
        }

    return best_result
