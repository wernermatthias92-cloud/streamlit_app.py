def berechne_hydraulischen_widerstand(d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad):

    if d_inner_mm <= 0: return 1e12

    d_m = d_inner_mm / 1000

    area = math.pi * (d_m/2)**2

    

    zeta_rohr = 0.03 * (laenge_mm/1000 / d_m)

    zeta_drossel = sum([1.5 * (d_inner_mm/d)**4 for d in drosseln_liste if d > 0])

    zeta_bogen = anzahl_90_grad * 1.2

    

    zeta_total = zeta_rohr + zeta_drossel + zeta_bogen

    r_wert = zeta_total * 500 / (area**2)

    return r_wert



def r_parallel(r1, r2):

    if r1 <= 0: return r2

    if r2 <= 0: return r1

    return (1/math.sqrt(r1) + 1/math.sqrt(r2))**-2



def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):

    if flow_lh <= 0 or delta_p_bar <= 0: return 0.0

    q_ms = (flow_lh / 1000) / 3600

    delta_p_pa = delta_p_bar * 100000

    v_spalt = math.sqrt((2 * delta_p_pa) / (2.5 * 1000))

    area_m2 = q_ms / v_spalt

    d_m = math.sqrt((4 * area_m2) / math.pi)

    return d_m * 1000 
