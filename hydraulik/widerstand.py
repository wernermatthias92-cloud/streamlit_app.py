import math

def get_viskositaet_wasser(temp_c):
    """
    Berechnet die kinematische Viskosität von Wasser in m²/s 
    basierend auf der Temperatur (Näherungsformel nach Poiseuille/Kamburoff).
    """
    # Formel für kinematische Viskosität in 10^-6 m²/s
    # Gilt gut für den Bereich 5-50°C
    visko = 1.778 / (1 + 0.0337 * temp_c + 0.000221 * temp_c**2)
    return visko * 1e-6

def berechne_reibungszahl(re, d_mm, k_mm=0.007):
    """
    Berechnet die Rohrreibungszahl lambda nach Darcy-Weisbach.
    Berücksichtigt laminare und turbulente Strömung (Haaland-Gleichung).
    k_mm: Absolute Rauheit (Standard 0.007mm für glatte Kunststoffrohre)
    """
    if re <= 0:
        return 0
    
    if re < 2300:
        # Laminarer Bereich
        return 64 / re
    elif re > 4000:
        # Turbulenter Bereich (Haaland-Gleichung)
        # Sehr genaue explizite Formel statt der impliziten Colebrook-White
        d_m = d_mm / 1000.0
        k_m = k_mm / 1000.0
        
        term = (k_m / (3.7 * d_m))**1.11 + (6.9 / re)
        inv_sqrt_lambda = -1.8 * math.log10(term)
        return (1.0 / inv_sqrt_lambda)**2
    else:
        # Übergangsbereich (Lineare Interpolation für numerische Stabilität)
        lambda_lam = 64 / 2300
        # Haaland für 4000
        d_m = d_mm / 1000.0
        k_m = k_mm / 1000.0
        term_4k = (k_m / (3.7 * d_m))**1.11 + (6.9 / 4000)
        lambda_turb = (1.0 / (-1.8 * math.log10(term_4k)))**2
        
        # Gewichtung im Übergang
        anteil_turb = (re - 2300) / (4000 - 2300)
        return lambda_lam * (1 - anteil_turb) + lambda_turb * anteil_turb

def berechne_hydraulischen_widerstand(flow_lh, d_mm, l_mm, temp_c, k_mm=0.007, bögen=0):
    """
    Wissenschaftliche Berechnung des Widerstandsbeiwerts R.
    R wird so berechnet, dass Delta_P [bar] = (R * q_ms^2) / 100000
    """
    if d_mm <= 0 or l_mm <= 0:
        return 0
    
    # 1. Umrechnung in Basiseinheiten
    q_m3s = (flow_lh / 1000.0) / 3600.0
    d_m = d_mm / 1000.0
    l_m = l_mm / 1000.0
    area = math.pi * (d_m / 2)**2
    v = q_m3s / area if area > 0 else 0
    
    if v == 0:
        return 0
        
    # 2. Reynolds-Zahl bestimmen
    nu = get_viskositaet_wasser(temp_c)
    re = (v * d_m) / nu
    
    # 3. Reibungszahl bestimmen
    lam = berechne_reibungszahl(re, d_mm, k_mm)
    
    # 4. Druckverlustbeiwert (Zeta) für Bögen (90 Grad Standard)
    # Ein Standardbogen hat ca. zeta = 0.3 bis 0.5
    zeta_boegen = bögen * 0.4
    
    # 5. Gesamtwiderstand R bestimmen
    # Physik: Delta_P = (lam * L/D + zeta) * rho/2 * v^2
    # Da v = Q/A -> v^2 = Q^2 / A^2
    # R = (lam * L/D + zeta) * rho / (2 * A^2)
    rho = 999.0 # Dichte Wasser (kg/m3)
    
    r_wert = (lam * (l_m / d_m) + zeta_boegen) * (rho / (2 * area**2))
    
    return r_wert

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):
    """
    Berechnet den benötigten Drossel-Durchmesser (Blenden-Gleichung).
    """
    if flow_lh <= 0 or delta_p_bar <= 0:
        return 0
    
    q_ms = (flow_lh / 1000.0) / 3600.0
    delta_p_pa = delta_p_bar * 100000.0
    rho = 999.0
    c_d = 0.61  # Durchflusskoeffizient für scharfkantige Blenden
    
    # Formel: Q = Cd * A * sqrt(2 * deltaP / rho)
    # -> A = Q / (Cd * sqrt(2 * deltaP / rho))
    v_theo = math.sqrt(2 * delta_p_pa / rho)
    area_needed = q_ms / (c_d * v_theo)
    
    diameter_m = math.sqrt(4 * area_needed / math.pi)
    return diameter_m * 1000.0
