import math

def get_viskositaet_wasser(temp_c):
    # Formel für kinematische Viskosität in 10^-6 m²/s
    visko = 1.778 / (1 + 0.0337 * temp_c + 0.000221 * temp_c**2)
    return visko * 1e-6

def berechne_reibungszahl(re, d_mm, k_mm=0.007):
    if re <= 0:
        return 0
    if re < 2300:
        return 64 / re
    elif re > 4000:
        d_m = d_mm / 1000.0
        k_m = k_mm / 1000.0
        term = (k_m / (3.7 * d_m))**1.11 + (6.9 / re)
        inv_sqrt_lambda = -1.8 * math.log10(term)
        return (1.0 / inv_sqrt_lambda)**2
    else:
        lambda_lam = 64 / 2300
        d_m = d_mm / 1000.0
        k_m = k_mm / 1000.0
        term_4k = (k_m / (3.7 * d_m))**1.11 + (6.9 / 4000)
        lambda_turb = (1.0 / (-1.8 * math.log10(term_4k)))**2
        anteil_turb = (re - 2300) / (4000 - 2300)
        return lambda_lam * (1 - anteil_turb) + lambda_turb * anteil_turb

def berechne_hydraulischen_widerstand(flow_lh, d_mm, l_mm, temp_c, k_mm=0.007, bögen=0):
    if d_mm <= 0 or l_mm <= 0: return 0
    q_m3s = (flow_lh / 1000.0) / 3600.0
    d_m = d_mm / 1000.0
    l_m = l_mm / 1000.0
    area = math.pi * (d_m / 2)**2
    v = q_m3s / area if area > 0 else 0
    if v == 0: return 0
    nu = get_viskositaet_wasser(temp_c)
    re = (v * d_m) / nu
    lam = berechne_reibungszahl(re, d_mm, k_mm)
    zeta_boegen = bögen * 0.4
    rho = 999.0 
    r_wert = (lam * (l_m / d_m) + zeta_boegen) * (rho / (2 * area**2))
    return r_wert

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):
    if flow_lh <= 0 or delta_p_bar <= 0: return 0
    q_ms = (flow_lh / 1000.0) / 3600.0
    delta_p_pa = delta_p_bar * 100000.0
    rho = 999.0
    c_d = 0.61  
    v_theo = math.sqrt(2 * delta_p_pa / rho)
    area_needed = q_ms / (c_d * v_theo)
    diameter_m = math.sqrt(4 * area_needed / math.pi)
    return diameter_m * 1000.0

def berechne_spacer_dp_segment(q_in_lh, q_c_lh, temp_c, n_seg):
    """
    Berechnet den dynamischen Druckverlust für EIN Membran-Segment (Scheibe).
    """
    q_avg = (q_in_lh + q_c_lh) / 2.0
    if q_avg <= 0: return 0.0
    
    nu_t = get_viskositaet_wasser(temp_c)
    nu_25 = 0.89e-6 
    
    # Basis-Druckverlust bei 25°C für das GESAMTE Modul
    dp_basis_total = 0.2 * (q_avg / 1000.0)**1.5
    
    # Temperaturkorrektur
    visco_korrektur = math.sqrt(nu_t / nu_25)
    
    # Auf das Segment (z.B. 1/10 der Länge) herunterrechnen
    return (dp_basis_total * visco_korrektur) / n_seg
