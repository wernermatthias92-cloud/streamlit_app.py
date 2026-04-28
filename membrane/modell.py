import math

def berechne_tcf(temp_c):
    if temp_c <= 0: return 0.01
    return math.exp(2640 * (1/298.15 - 1/(temp_c + 273.15)))

def berechne_tcf_salz(temp_c):
    if temp_c <= 0: return 0.01
    return math.exp(3020 * (1/298.15 - 1/(temp_c + 273.15)))

def berechne_osmotischen_druck(tds_ppm, temp_c):
    i = 2.0
    r_gas = 0.08314
    t_kelvin = temp_c + 273.15
    c_mol_l = (tds_ppm / 1000.0) / 58.44
    return i * c_mol_l * r_gas * t_kelvin

def berechne_a_wert(q_test_lh, m_flaeche, p_test_bar, tds_test_ppm):
    pi_test = berechne_osmotischen_druck(tds_test_ppm, 25.0)
    ndp_test = p_test_bar - pi_test
    if ndp_test <= 0: ndp_test = 0.1
    return (q_test_lh / m_flaeche) / ndp_test

def berechne_cp_faktor(q_p_lh, q_f_in_lh, q_c_lh, temp_c, m_flaeche_total_m2, m_flaeche_segment_m2):
    from hydraulik.widerstand import get_viskositaet_wasser
    if m_flaeche_segment_m2 <= 0 or q_p_lh <= 0: return 1.0
    
    q_avg_lh = (q_f_in_lh + q_c_lh) / 2.0
    if q_avg_lh <= 0.001: return 1.0  # Schutz vor Division durch Null bei totalem Stillstand
    
    j_m_s = (q_p_lh / m_flaeche_segment_m2) / 3600.0 / 1000.0
    w_m = m_flaeche_total_m2 / 0.95
    h_spacer_m = 0.0008
    a_c = w_m * h_spacer_m
    v_c = (q_avg_lh / 1000.0 / 3600.0) / a_c
    
    nu_t = get_viskositaet_wasser(temp_c)
    nu_25 = 0.89e-6
    t_kelvin = temp_c + 273.15
    d_ab = 1.61e-9 * (t_kelvin / 298.15) * (nu_25 / nu_t)
    d_h = 0.001
    
    re = (v_c * d_h) / nu_t
    sc = nu_t / d_ab
    sh = 0.065 * (re**0.875) * (sc**0.25)
    k = (sh * d_ab) / d_h
    
    if k <= 1e-12: return 1.0  # Schutz für extrem kleine k-Werte
    
    # NEU: Der mathematische Airbag vor dem OverflowError!
    exponent = j_m_s / k
    if exponent > 5.0:  # e^5 ist ca. 148, mehr brauchen wir ohnehin nicht.
        exponent = 5.0
        
    cp = math.exp(exponent)
    return min(cp, 5.0)
