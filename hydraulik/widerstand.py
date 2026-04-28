import math

def get_dichte_wasser(temp_c):
    return 1000.0 - ((temp_c - 4.0)**2) / 250.0

def get_viskositaet_wasser(temp_c):
    return 0.001 * math.exp(0.580 - (temp_c / 26.0))

def berechne_hydraulischen_widerstand(q_lh, d_innen_mm, l_mm, temp_c, bögen=0):
    if q_lh <= 0 or d_innen_mm <= 0 or l_mm <= 0: return 0.0
    
    q_ms = (q_lh / 1000.0) / 3600.0
    d_m = d_innen_mm / 1000.0
    l_m = l_mm / 1000.0
    area = math.pi * (d_m / 2)**2
    v = q_ms / area
    
    rho = get_dichte_wasser(temp_c)
    nu = get_viskositaet_wasser(temp_c) / rho
    re = (v * d_m) / nu
    
    if re < 2300:
        lambda_val = 64.0 / max(re, 1)
    elif re > 4000:
        k = 0.0015 / 1000.0
        term = (k / (3.7 * d_m))**1.11 + 6.9 / re
        lambda_val = 1.0 / (-1.8 * math.log10(term))**2
    else:
        lambda_val = 0.028 + ((re - 2300) / 1700) * (0.04 - 0.028)
        
    widerstand_rohr = lambda_val * (l_m / d_m) * (rho / 2.0)
    widerstand_boegen = bögen * 1.5 * (rho / 2.0)
    
    r_total = widerstand_rohr + widerstand_boegen
    return r_total

def berechne_spacer_dp_segment(q_feed_lh, q_konz_lh, temp_c, n_seg=10):
    # KORREKTUR (Punkt 4): Die Formel muss den lokalen Fluss korrekt skalieren
    q_avg = (q_feed_lh + q_konz_lh) / 2.0
    if q_avg <= 0: return 0.0
    
    # Der Faktor 0.48 gilt für die GESAMTE Membran.
    # Da (Q)^1.7 nicht linear ist, müssen wir die Länge aus dem Vorfaktor extrahieren:
    # 0.48 / n_seg ist die korrekte Linearisierung für die reine Längenabhängigkeit
    dp_bar_seg = (0.48 / n_seg) * ((q_avg / 100.0)**1.7)
    
    visk = get_viskositaet_wasser(temp_c)
    visk_ref = get_viskositaet_wasser(25.0)
    
    return dp_bar_seg * (visk / visk_ref)

def empfehle_drossel_durchmesser(flow_c_lh, druckabfall_bar, temp_c):
    if druckabfall_bar <= 0 or flow_c_lh <= 0: return 1.2
    dp_pa = druckabfall_bar * 100000.0
    rho = get_dichte_wasser(temp_c)
    q_ms = (flow_c_lh / 1000.0) / 3600.0
    c_d = 0.71
    v_theo = math.sqrt(2 * dp_pa / rho)
    area = q_ms / (c_d * v_theo)
    d_m = math.sqrt(area / math.pi) * 2
    return d_m * 1000.0
