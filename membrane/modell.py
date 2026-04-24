import math

def berechne_tcf(temp_c):
    """Temperature Correction Factor für den Permeatfluss"""
    if temp_c <= 0: return 0.01
    return math.exp(2640 * (1/298.15 - 1/(temp_c + 273.15)))

def berechne_tcf_salz(temp_c):
    """Temperature Correction Factor für den Salzdurchgang"""
    if temp_c <= 0: return 0.01
    return math.exp(3020 * (1/298.15 - 1/(temp_c + 273.15)))

def berechne_osmotischen_druck(tds_ppm, temp_c):
    """
    Berechnet den osmotischen Druck nach der van-'t-Hoff-Gleichung (Thermodynamik).
    Formel: Pi = i * c * R * T
    """
    i = 2.0  # van-'t-Hoff-Faktor für NaCl (Dissoziation in Na+ und Cl-)
    r_gas = 0.08314  # Universelle Gaskonstante in L*bar/(K*mol)
    t_kelvin = temp_c + 273.15
    
    # Molare Konzentration c berechnen (Molare Masse NaCl = 58.44 g/mol)
    # 1 ppm entspricht näherungsweise 1 mg/L
    c_mol_l = (tds_ppm / 1000.0) / 58.44
    
    pi_bar = i * c_mol_l * r_gas * t_kelvin
    return pi_bar

def berechne_a_wert(q_test_lh, m_flaeche, p_test_bar, tds_test_ppm):
    """Berechnet den Permeabilitätskoeffizienten A (l/h*m²*bar)"""
    # Datenblatt-Werte beziehen sich immer auf exakt 25°C
    pi_test = berechne_osmotischen_druck(tds_test_ppm, 25.0)
    ndp_test = p_test_bar - pi_test
    if ndp_test <= 0: ndp_test = 0.1
    a_wert = (q_test_lh / m_flaeche) / ndp_test
    return a_wert

def berechne_cp_faktor(q_p_lh, q_f_in_lh, q_c_lh, temp_c, m_flaeche_m2):
    """
    Berechnet die Konzentrationspolarisation nach der Filmtheorie.
    Ermittelt den Stoffübergangskoeffizienten aus Sherwood- und Schmidt-Zahl.
    """
    from hydraulik.widerstand import get_viskositaet_wasser
    
    if m_flaeche_m2 <= 0 or q_p_lh <= 0: return 1.0
    q_avg_lh = (q_f_in_lh + q_c_lh) / 2.0
    if q_avg_lh <= 0: return 1.0
    
    # 1. Permeatflux J in m/s
    j_m_s = (q_p_lh / m_flaeche_m2) / 3600.0 / 1000.0
    
    # 2. Querströmungsgeschwindigkeit v_c (Cross-Flow) in m/s
    # Annahme: Eine Standard-4040-Membran (7.6 m2) hat ca. 0.003 m2 Feed-Querschnittsfläche
    a_c = 0.003 * (m_flaeche_m2 / 7.6)
    v_c = (q_avg_lh / 1000.0 / 3600.0) / a_c
    
    # 3. Viskosität und Diffusionskoeffizient
    nu_t = get_viskositaet_wasser(temp_c) # m2/s
    nu_25 = 0.89e-6
    t_kelvin = temp_c + 273.15
    # Diffusionskoeffizient D_AB von NaCl in Wasser (Stokes-Einstein-Korrektur)
    d_ab = 1.61e-9 * (t_kelvin / 298.15) * (nu_25 / nu_t)
    
    # 4. Dimensionslose Kennzahlen
    d_h = 0.001 # Hydraulischer Durchmesser Spacer ca. 1 mm
    re = (v_c * d_h) / nu_t
    sc = nu_t / d_ab
    
    # 5. Sherwood-Zahl (Korrelation für RO-Spacer nach Schock/Miquel)
    sh = 0.065 * (re**0.875) * (sc**0.25)
    
    # 6. Stoffübergangskoeffizient k (m/s)
    k = (sh * d_ab) / d_h
    if k <= 0: return 1.0
    
    # 7. CP-Faktor (Concentration Polarization)
    cp = math.exp(j_m_s / k)
    return min(cp, 5.0) # Physikalischer Sicherheitsdeckel
