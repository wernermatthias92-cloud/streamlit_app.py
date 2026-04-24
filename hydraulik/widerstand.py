import math

def get_viskositaet_wasser(temp_c):
    visko = 1.778 / (1 + 0.0337 * temp_c + 0.000221 * temp_c**2)
    return visko * 1e-6

def get_dichte_wasser(temp_c):
    """Berechnet die Dichte von Wasser in kg/m³ in Abhängigkeit von der Temperatur."""
    return 1000 * (1 - ((temp_c - 4)**2) / 115500)

def berechne_reibungszahl(re, d_mm, k_mm=0.007):
    if re <= 0: return 0
    if re < 2300: return 64 / re
    elif re > 4000:
        d_m, k_m = d_mm / 1000.0, k_mm / 1000.0
        term = (k_m / (3.7 * d_m))**1.11 + (6.9 / re)
        return (1.0 / (-1.8 * math.log10(term)))**2
    else:
        l_lam = 64 / 2300
        d_m, k_m = d_mm / 1000.0, k_mm / 1000.0
        l_turb = (1.0 / (-1.8 * math.log10((k_m / (3.7 * d_m))**1.11 + (6.9 / 4000))))**2
        anteil_turb = (re - 2300) / (4000 - 2300)
        return l_lam * (1 - anteil_turb) + l_turb * anteil_turb

def berechne_hydraulischen_widerstand(flow_lh, d_mm, l_mm, temp_c, k_mm=0.007, bögen=0):
    if d_mm <= 0 or l_mm <= 0: return 0
    q_m3s, d_m, l_m = (flow_lh / 1000.0) / 3600.0, d_mm / 1000.0, l_mm / 1000.0
    area = math.pi * (d_m / 2)**2
    v = q_m3s / area if area > 0 else 0
    if v == 0: return 0
    re = (v * d_m) / get_viskositaet_wasser(temp_c)
    lam = berechne_reibungszahl(re, d_mm, k_mm)
    rho = get_dichte_wasser(temp_c) # DYNAMISCHE DICHTE
    r_wert = (lam * (l_m / d_m) + (bögen * 0.4)) * (rho / (2 * area**2))
    return r_wert

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar, temp_c):
    if flow_lh <= 0 or delta_p_bar <= 0: return 0
    q_ms, delta_p_pa = (flow_lh / 1000.0) / 3600.0, delta_p_bar * 100000.0
    rho = get_dichte_wasser(temp_c) # DYNAMISCHE DICHTE
    v_theo = math.sqrt(2 * delta_p_pa / rho)
    area_needed = q_ms / (0.61 * v_theo)
    return math.sqrt(4 * area_needed / math.pi) * 1000.0

def berechne_spacer_dp_segment(q_in_lh, q_c_lh, temp_c, n_seg):
    q_avg = (q_in_lh + q_c_lh) / 2.0
    if q_avg <= 0: return 0.0
    nu_t = get_viskositaet_wasser(temp_c)
    nu_25 = 0.89e-6 
    dp_basis_total = 0.48 * (q_avg / 1000.0)**1.7
    visco_korrektur = (nu_t / nu_25)**0.25
    return (dp_basis_total * visco_korrektur) / n_seg
